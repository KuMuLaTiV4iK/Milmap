"""In-runtime ingestion package: configuration + verified bundle import ONLY.

This package MUST NOT import an HTTP client or otherwise reach outside the
local filesystem/database (constitution Principle I, plan.md Constitution
Check). All internet-touching work lives in the separate, out-of-runtime
`tools/version_fetcher/` CLI, which this package never imports either.
"""
from __future__ import annotations
