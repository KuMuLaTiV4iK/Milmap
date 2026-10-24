"""Standalone staging fetcher CLI (out-of-runtime).

Run on a SEPARATE, internet-connected staging machine — never inside the
air-gapped deployment, and never imported by `src/asset_dashboard/`
(constitution Principle I; research D5). This is the only component in the
repository permitted to make outbound network requests.
"""
from __future__ import annotations
