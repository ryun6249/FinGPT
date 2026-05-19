from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.quantamental.sec_evidence import DEFAULT_FORMS
from pipelines.quantamental.sec_hydration import hydrate_global_sec_aliases


def _parse_tickers(raw: str) -> list[str]:
    return [item.strip().upper() for item in re.split(r"[\s,]+", str(raw or "")) if item.strip()]


def _parse_forms(raw: str) -> list[str]:
    forms = [item.strip().upper() for item in re.split(r"[\s,]+", str(raw or "")) if item.strip()]
    return forms or list(DEFAULT_FORMS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hydrate local SEC data for mapped Quantamental GLOBAL ADR/dual-listed aliases.")
    parser.add_argument("--tickers", default="", help="Comma/space-separated GLOBAL symbols, e.g. ASML.AS 7203.T 0700.HK.")
    parser.add_argument("--all-known", action="store_true", help="Hydrate every curated GLOBAL symbol with a SEC alias.")
    parser.add_argument("--forms", default=",".join(DEFAULT_FORMS), help="SEC forms to request, comma or space separated.")
    parser.add_argument("--lookback-days", type=int, default=365 * 5)
    parser.add_argument("--max-assets", type=int, default=25)
    parser.add_argument("--filing-limit-per-ticker", type=int, default=20)
    parser.add_argument("--max-facts-per-ticker", type=int, default=300)
    parser.add_argument("--no-financials", action="store_true", help="Skip SEC companyfacts hydration.")
    parser.add_argument("--dry-run", action="store_true", help="Only show the mapped SEC tickers; do not write data.")
    parser.add_argument("--output", default="", help="Optional JSON report path.")
    args = parser.parse_args(argv)

    result = hydrate_global_sec_aliases(
        _parse_tickers(args.tickers),
        all_known=args.all_known,
        forms=_parse_forms(args.forms),
        lookback_days=args.lookback_days,
        max_assets=args.max_assets,
        filing_limit_per_ticker=args.filing_limit_per_ticker,
        max_facts_per_ticker=args.max_facts_per_ticker,
        hydrate_financials=not args.no_financials,
        dry_run=args.dry_run,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text)
    return 1 if str(result.get("status") or "").lower() == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
