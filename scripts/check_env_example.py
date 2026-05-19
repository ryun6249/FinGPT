from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
SETTINGS_FILE = PROJECT_ROOT / "core" / "config" / "settings.py"

EXTRA_OPERATOR_ENV = {
    "AI_PORTFOLIO_DATA_DIR",
    "AI_PORTFOLIO_DB_PATH",
    "FINGPT_BROWSER_UI_HEADLESS",
    "FINGPT_BUILD_ID",
    "FINGPT_GIT_BRANCH",
    "FINGPT_GIT_COMMIT",
    "FINGPT_VALIDATION_CHILD_FORCE_EXIT",
    "FINGPT_VALIDATION_FAST_INFERENCE",
    "FINGPT_VALIDATION_INFERENCE_TIMEOUT_S",
    "FORECAST_AI_MAX_LATENCY_S",
    "FORECAST_ARTIFACT_SIGNING_KEY",
    "FORECAST_JOB_WORKERS",
    "QUANTAMENTAL_DATA_DIR",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
}

SECRET_KEY_RE = re.compile(r"(^|_)(API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)($|_)")

SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)

SAFE_EMPTY_OR_PLACEHOLDER = {
    "",
    "0",
    "false",
    "disabled",
    "none",
    "null",
}


def _parse_env_example(path: Path) -> tuple[dict[str, tuple[int, str]], list[str], list[str]]:
    values: dict[str, tuple[int, str]] = {}
    duplicates: list[str] = []
    malformed: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            malformed.append(f"{line_number}:{stripped}")
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            malformed.append(f"{line_number}:{key}")
            continue
        if key in values:
            duplicates.append(f"{key} first={values[key][0]} duplicate={line_number}")
        values[key] = (line_number, value.strip())
    return values, duplicates, malformed


def _settings_env_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    names.add(item.target.id.upper())
    return names


def _secret_value_issues(values: dict[str, tuple[int, str]]) -> list[str]:
    issues: list[str] = []
    for key, (line_number, value) in values.items():
        normalized = value.strip().strip('"').strip("'")
        lower = normalized.lower()
        if SECRET_KEY_RE.search(key):
            if lower not in SAFE_EMPTY_OR_PLACEHOLDER and "example" not in lower and "contact@" not in lower:
                issues.append(f"{line_number}:{key}=<non-placeholder-secret>")
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(normalized):
                issues.append(f"{line_number}:{key}=<secret-looking-value>")
                break
    return issues


def main() -> int:
    values, duplicates, malformed = _parse_env_example(ENV_EXAMPLE)
    settings_names = _settings_env_names(SETTINGS_FILE)
    expected_names = settings_names | EXTRA_OPERATOR_ENV
    missing = sorted(expected_names - set(values))
    unknown = sorted(set(values) - expected_names)
    secret_issues = _secret_value_issues(values)

    problems: list[str] = []
    if duplicates:
        problems.append("duplicate keys:\n  " + "\n  ".join(duplicates))
    if malformed:
        problems.append("malformed lines:\n  " + "\n  ".join(malformed))
    if missing:
        problems.append("settings missing from .env.example:\n  " + "\n  ".join(missing))
    if unknown:
        problems.append("unknown .env.example keys:\n  " + "\n  ".join(unknown))
    if secret_issues:
        problems.append("secret-looking defaults:\n  " + "\n  ".join(secret_issues))

    if problems:
        print("\n\n".join(problems))
        return 1

    print(f".env.example ok: {len(values)} keys checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
