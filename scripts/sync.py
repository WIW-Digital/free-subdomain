#!/usr/bin/env python3
"""
sync.py — Syncs subdomain JSON records from the domains/ directory to Cloudflare DNS.

Required environment variables:
    CF_API_TOKEN  — Cloudflare API token with Zone:DNS:Edit permission
    CF_ZONE_ID    — The Cloudflare Zone ID for your base domain
    BASE_DOMAIN   — The base domain (e.g. "example.com") — subdomains become <name>.<BASE_DOMAIN>

Optional environment variables:
    DOMAINS_DIR   — Path to the domains directory (default: domains/)
    DRY_RUN       — Set to "true" to print planned changes without applying them

Usage:
    python scripts/sync.py
"""

import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests is not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID", "")
BASE_DOMAIN = os.environ.get("BASE_DOMAIN", "")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

REPO_ROOT = Path(__file__).resolve().parent.parent
DOMAINS_DIR = Path(os.environ.get("DOMAINS_DIR", str(REPO_ROOT / "domains")))

CF_API_BASE = "https://api.cloudflare.com/client/v4"

# How long to sleep between Cloudflare API calls to avoid rate-limiting
API_SLEEP = 0.3


# ---------------------------------------------------------------------------
# Cloudflare API helpers
# ---------------------------------------------------------------------------


def cf_headers() -> dict:
    return {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }


def cf_get(path: str) -> dict:
    url = f"{CF_API_BASE}{path}"
    resp = requests.get(url, headers=cf_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def cf_post(path: str, data: dict) -> dict:
    url = f"{CF_API_BASE}{path}"
    resp = requests.post(url, headers=cf_headers(), json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cf_put(path: str, data: dict) -> dict:
    url = f"{CF_API_BASE}{path}"
    resp = requests.put(url, headers=cf_headers(), json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def cf_delete(path: str) -> dict:
    url = f"{CF_API_BASE}{path}"
    resp = requests.delete(url, headers=cf_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Record helpers
# ---------------------------------------------------------------------------

SUPPORTED_TYPES = {"A", "AAAA", "CNAME", "TXT", "MX", "NS"}


def desired_records(name: str, record_block: dict) -> list[dict]:
    """Convert the JSON record block to a flat list of Cloudflare record dicts."""
    records = []

    for rtype in ("A", "AAAA"):
        for ip in record_block.get(rtype, []):
            records.append(
                {
                    "type": rtype,
                    "name": name,
                    "content": ip,
                    "ttl": 1,  # 1 = automatic
                    "proxied": False,
                }
            )

    if "CNAME" in record_block:
        target = record_block["CNAME"]
        if not target.endswith("."):
            target += "."
        records.append(
            {
                "type": "CNAME",
                "name": name,
                "content": target.rstrip("."),
                "ttl": 1,
                "proxied": False,
            }
        )

    for txt in record_block.get("TXT", []):
        records.append(
            {
                "type": "TXT",
                "name": name,
                "content": txt,
                "ttl": 1,
            }
        )

    for mx in record_block.get("MX", []):
        records.append(
            {
                "type": "MX",
                "name": name,
                "content": mx["value"],
                "priority": mx["priority"],
                "ttl": 1,
            }
        )

    for ns in record_block.get("NS", []):
        records.append(
            {
                "type": "NS",
                "name": name,
                "content": ns,
                "ttl": 1,
            }
        )

    return records


def records_equal(existing: dict, desired: dict) -> bool:
    """Return True if the existing Cloudflare record matches the desired state."""
    for key in ("type", "name", "content"):
        if existing.get(key) != desired.get(key):
            return False
    if desired.get("type") == "MX" and existing.get("priority") != desired.get("priority"):
        return False
    if existing.get("proxied") != desired.get("proxied"):
        return False
    return True


def fetch_existing_records(subdomain_fqdn: str) -> list[dict]:
    """Fetch all existing Cloudflare DNS records for a given FQDN."""
    result = []
    page = 1
    while True:
        data = cf_get(
            f"/zones/{CF_ZONE_ID}/dns_records?name={subdomain_fqdn}&per_page=100&page={page}"
        )
        result.extend(data.get("result", []))
        info = data.get("result_info", {})
        if page >= info.get("total_pages", 1):
            break
        page += 1
        time.sleep(API_SLEEP)
    return result


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------


def sync_subdomain(stem: str, record_block: dict) -> None:
    fqdn = f"{stem}.{BASE_DOMAIN}"
    desired = desired_records(fqdn, record_block)

    if DRY_RUN:
        print(f"  [DRY RUN] Desired records for {fqdn}:")
        for r in desired:
            print(f"    {r['type']:6} {r['content']}")
        return

    existing = fetch_existing_records(fqdn)
    existing_by_id = {r["id"]: r for r in existing}

    # Match desired records to existing ones
    unmatched_existing = list(existing_by_id.values())
    unmatched_desired = list(desired)
    to_create = []
    to_update = []  # (existing_id, desired_dict)

    for d in desired:
        matched = next(
            (e for e in unmatched_existing if records_equal(e, d)),
            None,
        )
        if matched:
            unmatched_existing.remove(matched)
        else:
            # Check if there is an existing record of the same type to update
            same_type = next(
                (e for e in unmatched_existing if e["type"] == d["type"]),
                None,
            )
            if same_type:
                unmatched_existing.remove(same_type)
                to_update.append((same_type["id"], d))
            else:
                to_create.append(d)

    to_delete = unmatched_existing

    for record in to_create:
        print(f"  CREATE {record['type']:6} {fqdn} -> {record['content']}")
        cf_post(f"/zones/{CF_ZONE_ID}/dns_records", record)
        time.sleep(API_SLEEP)

    for record_id, record in to_update:
        print(f"  UPDATE {record['type']:6} {fqdn} -> {record['content']}")
        cf_put(f"/zones/{CF_ZONE_ID}/dns_records/{record_id}", record)
        time.sleep(API_SLEEP)

    for record in to_delete:
        # Only delete record types we manage to avoid touching manually-added records
        if record["type"] in SUPPORTED_TYPES:
            print(f"  DELETE {record['type']:6} {fqdn} (id={record['id']})")
            cf_delete(f"/zones/{CF_ZONE_ID}/dns_records/{record['id']}")
            time.sleep(API_SLEEP)


def main() -> int:
    errors = []
    if not CF_API_TOKEN:
        errors.append("CF_API_TOKEN environment variable is not set.")
    if not CF_ZONE_ID:
        errors.append("CF_ZONE_ID environment variable is not set.")
    if not BASE_DOMAIN:
        errors.append("BASE_DOMAIN environment variable is not set.")

    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if DRY_RUN:
        print("Running in DRY RUN mode — no changes will be applied.\n")

    domain_files = sorted(DOMAINS_DIR.glob("*.json"))
    if not domain_files:
        print("No domain files found.")
        return 0

    success = 0
    failed = 0

    for file_path in domain_files:
        stem = file_path.stem
        if stem.startswith("_"):
            continue  # skip example / internal files

        print(f"\nProcessing: {stem}.{BASE_DOMAIN}")
        try:
            with open(file_path, encoding="utf-8") as fh:
                data = json.load(fh)
            sync_subdomain(stem, data.get("record", {}))
            success += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}", file=sys.stderr)
            failed += 1

    print(f"\n{'='*50}")
    print(f"Synced {success} subdomain(s), {failed} error(s).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
