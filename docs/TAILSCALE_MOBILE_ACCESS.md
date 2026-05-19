# Tailscale Mobile Web Access

이 문서는 휴대폰에서 Tailscale을 통해 로컬 FinGPT Web UI를 여는 운영 절차입니다.

## 목표

- PC의 FastAPI Web UI를 Tailscale IPv4 주소에만 바인딩합니다.
- 휴대폰은 같은 Tailnet에 로그인한 상태에서 `http://100.x.y.z:8000/ui/` 형태의 주소로 접속합니다.
- Windows 방화벽은 선택적으로 Tailnet 대역인 `100.64.0.0/10`에서 들어오는 TCP 포트만 허용합니다.

## 사전 조건

1. PC와 휴대폰 모두 Tailscale이 설치되어 있고 같은 Tailnet에 로그인되어 있어야 합니다.
2. PC에서 Tailscale이 연결 상태여야 합니다.
3. FinGPT의 기존 Python 환경(`venv311`)과 의존성은 기존 `scripts/run_web.ps1` 실행 조건과 동일합니다.

Tailscale 상태 확인:

```powershell
tailscale status
tailscale ip -4
```

`tailscale` CLI가 PATH에 없어도 기본 설치 경로의 `tailscale.exe`를 스크립트가 한 번 더 찾습니다.

## 실행

첫 실행에서 휴대폰 접속이 막히지 않게 Windows 방화벽 규칙까지 만들려면 관리자 PowerShell에서 실행합니다.

```powershell
cd F:\LLM\FinGPT
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1 -OpenFirewall
```

관리자 권한 없이 서버만 띄우려면:

```powershell
cd F:\LLM\FinGPT
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1
```

스크립트는 다음을 출력합니다.

```text
Phone URL: http://100.x.y.z:8000/ui/
Docs URL:  http://100.x.y.z:8000/docs
Health:    http://100.x.y.z:8000/api/v1/health
```

휴대폰의 Tailscale 앱이 연결된 상태에서 `Phone URL`을 브라우저에 입력하면 됩니다.

## 포트와 호스트 옵션

기본 포트는 `8000`입니다. 이미 사용 중이면 기본적으로 `8001`부터 `8100`까지 사용 가능한 포트를 자동으로 찾습니다.

명시 포트:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1 -Port 8140
```

환경 변수:

```powershell
$env:FINGPT_TAILSCALE_PORT = "8140"
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1
```

Tailscale IP 자동 감지가 실패했지만 IP를 알고 있으면 직접 지정할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1 -Host 100.x.y.z
```

## 사전 점검만 실행

서버를 띄우기 전에 Tailscale IP, 포트, 방화벽 옵션만 확인하려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_web_tailscale.ps1 -PreflightOnly
```

현재 PC에 Tailscale이 없거나 로그인되어 있지 않으면 이 단계에서 실패합니다.

## 검증

PC에서:

```powershell
Invoke-RestMethod http://100.x.y.z:8000/api/v1/health
```

휴대폰에서:

1. Tailscale 앱 연결 상태를 확인합니다.
2. 브라우저에서 `http://100.x.y.z:8000/ui/`를 엽니다.
3. 로딩이 실패하면 `http://100.x.y.z:8000/docs`도 확인합니다.

## 방화벽 규칙

`-OpenFirewall`은 다음 형태의 인바운드 규칙을 만듭니다.

- 로컬 주소: 감지된 Tailscale IPv4
- 로컬 포트: 실행 포트
- 원격 주소: `100.64.0.0/10`
- 프로토콜: TCP

규칙 삭제 예:

```powershell
Get-NetFirewallRule -DisplayName "FinGPT Web UI (Tailscale)*" | Remove-NetFirewallRule
```

## 문제 해결

- `No Tailscale IPv4 address was detected`: PC의 Tailscale 로그인을 확인하고 `tailscale ip -4`가 `100.x.y.z`를 출력하는지 확인합니다.
- 휴대폰에서 접속 불가: 휴대폰 Tailscale 연결 상태, 같은 Tailnet 여부, Windows 방화벽 규칙을 확인합니다.
- 포트 충돌: `-Port <다른 포트>`를 지정하거나 기본 자동 포트 선택을 사용합니다.
- MagicDNS를 쓰는 경우: 스크립트가 DNS 이름을 감지하면 `MagicDNS` URL도 함께 출력합니다.
