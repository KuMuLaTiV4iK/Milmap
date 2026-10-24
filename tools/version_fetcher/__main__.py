"""CLI entry point (contracts/fetcher-cli.md):

    python -m version_fetcher fetch --vendor V --source-url URL \
        --models m1,m2 --extractor extractor.json \
        --key-file key.bin --key-id KID --out bundle.json

Exit codes: 0 = bundle written (even with some per-model failures inside
it); 2 = fatal (bad args, missing key, cannot write output) — no partial
bundle left.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from version_fetcher.bundle_writer import write_bundle
from version_fetcher.fetch import fetch_vendor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m version_fetcher")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch")
    fetch_parser.add_argument("--vendor", required=True)
    fetch_parser.add_argument("--source-url", required=True)
    fetch_parser.add_argument("--models", required=True, help="comma-separated model list")
    fetch_parser.add_argument("--extractor", required=True, help="path to extractor JSON config")
    fetch_parser.add_argument("--key-file", required=True)
    fetch_parser.add_argument("--key-id", required=True)
    fetch_parser.add_argument("--out", required=True)

    args = parser.parse_args(argv)

    if args.command != "fetch":
        parser.print_usage(sys.stderr)
        return 2

    try:
        extractor = json.loads(Path(args.extractor).read_text())
    except OSError as exc:
        print(f"error: cannot read extractor config: {exc}", file=sys.stderr)
        return 2

    try:
        key = Path(args.key_file).read_bytes().strip()
    except OSError as exc:
        print(f"error: cannot read key file: {exc}", file=sys.stderr)
        return 2
    if not key:
        print("error: key file is empty", file=sys.stderr)
        return 2

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("error: --models must list at least one model", file=sys.stderr)
        return 2

    payload = fetch_vendor(args.vendor, args.source_url, models, extractor)

    out_path = Path(args.out)
    try:
        write_bundle(payload, key, args.key_id, out_path)
    except OSError as exc:
        print(f"error: cannot write bundle: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
