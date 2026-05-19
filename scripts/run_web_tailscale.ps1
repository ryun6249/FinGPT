[CmdletBinding()]
param(
    [int]$Port = 0,
    [Alias("Host")]
    [string]$BindAddress = "",
    [switch]$OpenFirewall,
    [switch]$PreflightOnly,
    [switch]$NoAutoPort,
    [switch]$CopyUrl,
    [switch]$AllowNonTailscaleHost,
    [string]$FirewallRuleName = "FinGPT Web UI (Tailscale)"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

function Fail([string]$Message, [int]$Code = 1) {
    [Console]::Error.WriteLine("[run_web_tailscale] ERROR: $Message")
    exit $Code
}

function Info([string]$Message) {
    Write-Host "[run_web_tailscale] $Message" -ForegroundColor Cyan
}

function Warn([string]$Message) {
    Write-Host "[run_web_tailscale] WARNING: $Message" -ForegroundColor Yellow
}

function Test-IPv4Address([string]$Address) {
    $Parsed = $null
    return [System.Net.IPAddress]::TryParse($Address, [ref]$Parsed) -and
        $Parsed.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork
}

function Test-TailscaleIPv4([string]$Address) {
    $Parsed = $null
    if (-not [System.Net.IPAddress]::TryParse($Address, [ref]$Parsed)) {
        return $false
    }
    if ($Parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) {
        return $false
    }

    $Bytes = $Parsed.GetAddressBytes()
    return $Bytes[0] -eq 100 -and $Bytes[1] -ge 64 -and $Bytes[1] -le 127
}

function Resolve-Port([int]$RequestedPort) {
    if ($RequestedPort -gt 0) {
        return $RequestedPort
    }

    foreach ($EnvName in @("FINGPT_TAILSCALE_PORT", "FINGPT_WEB_PORT")) {
        $Value = [Environment]::GetEnvironmentVariable($EnvName)
        if (-not [string]::IsNullOrWhiteSpace($Value)) {
            $Parsed = 0
            if (-not [int]::TryParse($Value, [ref]$Parsed)) {
                Fail "$EnvName must be a numeric TCP port, got '$Value'."
            }
            return $Parsed
        }
    }

    return 8000
}

function Get-TailscaleCommand {
    $Command = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }

    $KnownPaths = @(
        (Join-Path $env:ProgramFiles "Tailscale\tailscale.exe")
    )
    if ($env:ProgramFiles -and (Test-Path "env:ProgramFiles(x86)")) {
        $KnownPaths += (Join-Path ${env:ProgramFiles(x86)} "Tailscale\tailscale.exe")
    }

    foreach ($Path in $KnownPaths) {
        if ($Path -and (Test-Path $Path)) {
            return $Path
        }
    }

    return $null
}

function Add-TailscaleCandidate($Candidates, [string]$Address, [string]$Source, [int]$Priority) {
    if ([string]::IsNullOrWhiteSpace($Address)) {
        return
    }
    $CleanAddress = $Address.Trim()
    if (Test-TailscaleIPv4 $CleanAddress) {
        $Candidates.Add([pscustomobject]@{
            IPAddress = $CleanAddress
            Source = $Source
            Priority = $Priority
        }) | Out-Null
    }
}

function Get-TailscaleIPv4Candidates([string]$TailscaleExe) {
    $Candidates = [System.Collections.Generic.List[object]]::new()

    if ($TailscaleExe) {
        try {
            $CliAddresses = & $TailscaleExe ip -4 2>$null
            foreach ($Line in $CliAddresses) {
                Add-TailscaleCandidate $Candidates $Line "tailscale ip -4" 10
            }
        } catch {
            Warn "Unable to query '$TailscaleExe ip -4': $($_.Exception.Message)"
        }
    }

    try {
        $Adapters = Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -match "Tailscale|WireGuard" -or
                $_.InterfaceDescription -match "Tailscale|WireGuard"
            }
        foreach ($Adapter in $Adapters) {
            $Addresses = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $Adapter.ifIndex -ErrorAction SilentlyContinue |
                Where-Object { $_.AddressState -in @("Preferred", "Tentative") }
            foreach ($Address in $Addresses) {
                Add-TailscaleCandidate $Candidates $Address.IPAddress "adapter $($Adapter.Name)" 20
            }
        }
    } catch {
        Warn "Unable to inspect local network adapters: $($_.Exception.Message)"
    }

    try {
        $FallbackAddresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.AddressState -in @("Preferred", "Tentative") }
        foreach ($Address in $FallbackAddresses) {
            Add-TailscaleCandidate $Candidates $Address.IPAddress "100.64.0.0/10 fallback" 30
        }
    } catch {
        Warn "Unable to inspect local IPv4 addresses: $($_.Exception.Message)"
    }

    $Candidates |
        Sort-Object Priority, IPAddress -Unique |
        Group-Object IPAddress |
        ForEach-Object { $_.Group | Sort-Object Priority | Select-Object -First 1 }
}

function Get-TailscaleDnsName([string]$TailscaleExe) {
    if (-not $TailscaleExe) {
        return $null
    }

    try {
        $StatusText = (& $TailscaleExe status --self --json 2>$null | Out-String).Trim()
        if (-not $StatusText.StartsWith("{")) {
            return $null
        }
        $Status = $StatusText | ConvertFrom-Json
        if ($Status.Self -and $Status.Self.DNSName) {
            return ([string]$Status.Self.DNSName).TrimEnd(".")
        }
    } catch {
        return $null
    }

    return $null
}

function Test-CanBind([string]$Address, [int]$CandidatePort) {
    $Listener = $null
    try {
        $ParsedAddress = [System.Net.IPAddress]::Parse($Address)
        $Listener = [System.Net.Sockets.TcpListener]::new($ParsedAddress, $CandidatePort)
        $Listener.Start()
        return $true
    } catch {
        return $false
    } finally {
        if ($Listener) {
            $Listener.Stop()
        }
    }
}

function Get-PortOwnerSummary([int]$PortNumber) {
    $Connections = Get-NetTCPConnection -State Listen -LocalPort $PortNumber -ErrorAction SilentlyContinue
    if (-not $Connections) {
        return "no listening process reported by Get-NetTCPConnection"
    }

    $OwnerLines = foreach ($ProcessId in ($Connections | Select-Object -ExpandProperty OwningProcess -Unique)) {
        try {
            $ProcessName = (Get-Process -Id $ProcessId -ErrorAction Stop).ProcessName
        } catch {
            $ProcessName = "unknown"
        }
        "$ProcessName (PID $ProcessId)"
    }

    return (($OwnerLines | Sort-Object -Unique) -join ", ")
}

function Resolve-AvailablePort([string]$Address, [int]$RequestedPort, [switch]$DisableAutoPort) {
    if (Test-CanBind $Address $RequestedPort) {
        return $RequestedPort
    }

    if ($DisableAutoPort) {
        $Owners = Get-PortOwnerSummary $RequestedPort
        Fail "Cannot bind $Address`:$RequestedPort. Current owners on port ${RequestedPort}: $Owners"
    }

    $LastPort = [Math]::Min(65535, $RequestedPort + 100)
    for ($CandidatePort = $RequestedPort + 1; $CandidatePort -le $LastPort; $CandidatePort++) {
        if (Test-CanBind $Address $CandidatePort) {
            Warn "Port $RequestedPort is not available on $Address. Using $CandidatePort instead."
            return $CandidatePort
        }
    }

    $Owners = Get-PortOwnerSummary $RequestedPort
    Fail "No free port found from $RequestedPort to $LastPort on $Address. Current owners on port ${RequestedPort}: $Owners"
}

function Test-IsElevated {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Ensure-FirewallRule([string]$Address, [int]$PortNumber, [string]$BaseRuleName) {
    if (-not (Get-Command New-NetFirewallRule -ErrorAction SilentlyContinue)) {
        Warn "NetSecurity cmdlets are unavailable; skipping firewall rule creation."
        return
    }

    if (-not (Test-IsElevated)) {
        Fail "Firewall setup requires an elevated PowerShell session. Re-run as Administrator with -OpenFirewall, or create an inbound TCP rule manually for $Address`:$PortNumber from 100.64.0.0/10."
    }

    $DisplayName = "$BaseRuleName $Address`:$PortNumber"
    $Existing = Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue
    if ($Existing) {
        Info "Firewall rule already exists: $DisplayName"
        return
    }

    New-NetFirewallRule `
        -DisplayName $DisplayName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalAddress $Address `
        -LocalPort $PortNumber `
        -RemoteAddress "100.64.0.0/10" `
        -Profile Any | Out-Null

    Info "Created firewall rule: $DisplayName"
}

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..")).Path
$RunWebScript = Join-Path $ProjectRoot "scripts\run_web.ps1"
if (-not (Test-Path $RunWebScript)) {
    Fail "Expected launcher not found: $RunWebScript"
}

$TailscaleExe = Get-TailscaleCommand
$BindHost = $BindAddress.Trim()
if (-not $BindHost) {
    $Candidates = @(Get-TailscaleIPv4Candidates $TailscaleExe)
    if (-not $Candidates) {
        Fail "No Tailscale IPv4 address was detected. Install/start Tailscale, log in on this PC, connect the phone to the same tailnet, then retry. You can override with -Host <100.x.y.z>."
    }

    $Selected = $Candidates | Sort-Object Priority, IPAddress | Select-Object -First 1
    $BindHost = $Selected.IPAddress
    Info "Detected Tailscale IPv4 $BindHost from $($Selected.Source)."
} else {
    Info "Using explicit bind host $BindHost."
}

if (-not (Test-IPv4Address $BindHost)) {
    Fail "Host '$BindHost' is not a valid IPv4 address. This launcher currently supports Tailscale IPv4 only."
}

if (-not $AllowNonTailscaleHost -and -not (Test-TailscaleIPv4 $BindHost)) {
    Fail "Host '$BindHost' is outside Tailscale's 100.64.0.0/10 IPv4 range. Use a Tailscale IPv4 address or pass -AllowNonTailscaleHost for explicit local testing."
}

$ResolvedPort = Resolve-Port $Port
if ($ResolvedPort -lt 1 -or $ResolvedPort -gt 65535) {
    Fail "Port must be between 1 and 65535, got $ResolvedPort."
}

$ResolvedPort = Resolve-AvailablePort $BindHost $ResolvedPort -DisableAutoPort:$NoAutoPort

if ($OpenFirewall) {
    Ensure-FirewallRule $BindHost $ResolvedPort $FirewallRuleName
} else {
    Warn "Firewall rule was not changed. If the phone cannot connect, re-run from elevated PowerShell with -OpenFirewall."
}

$UiUrl = "http://$BindHost`:$ResolvedPort/ui/"
$DocsUrl = "http://$BindHost`:$ResolvedPort/docs"
$HealthUrl = "http://$BindHost`:$ResolvedPort/api/v1/health"
$DnsName = Get-TailscaleDnsName $TailscaleExe

Write-Host ""
Write-Host "Phone URL: $UiUrl" -ForegroundColor Green
Write-Host "Docs URL:  $DocsUrl"
Write-Host "Health:    $HealthUrl"
if ($DnsName) {
    Write-Host "MagicDNS:  http://$DnsName`:$ResolvedPort/ui/"
}
Write-Host ""
Write-Host "Open that URL from a phone signed in to the same Tailscale tailnet."
Write-Host ""

if ($CopyUrl) {
    try {
        Set-Clipboard -Value $UiUrl
        Info "Copied phone URL to the Windows clipboard."
    } catch {
        Warn "Unable to copy URL to clipboard: $($_.Exception.Message)"
    }
}

if ($PreflightOnly) {
    Info "Preflight complete. Re-run without -PreflightOnly to start the web server."
    exit 0
}

$env:FINGPT_WEB_HOST = $BindHost
$env:FINGPT_WEB_PORT = [string]$ResolvedPort

Info "Starting FinGPT Web UI through scripts\run_web.ps1..."
& $RunWebScript
exit $LASTEXITCODE
