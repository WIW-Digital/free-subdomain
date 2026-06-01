#!/usr/bin/env python3
"""
validate.py — Validates all JSON files in the domains/ directory.

Checks performed:
  1. Valid JSON syntax
  2. Schema compliance (schemas/domain.json)
  3. File-name rules (only lowercase letters, digits, and hyphens; no leading/trailing hyphens)
  4. No A + CNAME conflict (also enforced by schema, but double-checked here for clearer errors)
  5. At least one DNS record type is present

Usage:
    python scripts/validate.py [--domains-dir domains] [--schema schemas/domain.json] [file ...]

If one or more file paths are supplied on the command line only those files are
checked; otherwise every *.json file inside --domains-dir is checked.
"""

import argparse
import ipaddress
import json
import os
import re
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema is not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
RESERVED_NAMES = {
    "_example",
    "www",
    "mail",
    "smtp",
    "pop",
    "pop3",
    "imap",
    "ftp",
    "sftp",
    "webmail",
    "cpanel",
    "whm",
    "ns",
    "ns1",
    "ns2",
    "ns3",
    "ns4",
    "autoconfig",
    "autodiscover",
    "localhost",
    "broadcasthost",
    "local",
    "blog",
}


def load_schema(schema_path: Path) -> dict:
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_file(file_path: Path, schema: dict) -> list[str]:
    """Return a (possibly empty) list of human-readable error strings."""
    errors: list[str] = []
    stem = file_path.stem  # filename without .json

    # 1. Skip the example file silently
    if stem == "_example":
        return []

    # 2. File-name rules
    if not SUBDOMAIN_RE.match(stem):
        errors.append(
            f"Invalid subdomain name '{stem}': must contain only lowercase letters, "
            "digits, and hyphens, and must not start or end with a hyphen."
        )

    if stem in RESERVED_NAMES:
        errors.append(f"The subdomain '{stem}' is reserved and cannot be registered.")

    if len(stem) > 63:
        errors.append(f"Subdomain '{stem}' exceeds the 63-character DNS label limit.")

    # 3. Parse JSON
    try:
        with open(file_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON: {exc}")
        return errors  # can't validate further

    # 4. Schema validation
    validator = jsonschema.Draft7Validator(schema)
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"Schema error at {path}: {error.message}")

    # 5. Semantic checks on the record block
    record = data.get("record", {})

    if not record:
        errors.append("At least one DNS record (A, AAAA, CNAME, TXT, MX, NS) must be specified.")

    if "CNAME" in record and "A" in record:
        errors.append("A record and CNAME record cannot both be present for the same subdomain.")

    if "CNAME" in record and "AAAA" in record:
        errors.append("AAAA record and CNAME record cannot both be present for the same subdomain.")

    # 6. Basic IP validation (extra safety beyond the schema format check)
    for ip_str in record.get("A", []):
        try:
            addr = ipaddress.IPv4Address(ip_str)
            if addr.is_loopback:
                errors.append(f"A record '{ip_str}' is a loopback address.")
            elif addr.is_unspecified:
                errors.append(f"A record '{ip_str}' is an unspecified address (0.0.0.0).")
        except ValueError:
            errors.append(f"A record '{ip_str}' is not a valid IPv4 address.")

    for ip_str in record.get("AAAA", []):
        try:
            addr = ipaddress.IPv6Address(ip_str)
            if addr.is_loopback:
                errors.append(f"AAAA record '{ip_str}' is a loopback address.")
            elif addr.is_unspecified:
                errors.append(f"AAAA record '{ip_str}' is an unspecified address.")
        except ValueError:
            errors.append(f"AAAA record '{ip_str}' is not a valid IPv6 address.")

    return errors


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate subdomain JSON files.")
    parser.add_argument(
        "--domains-dir",
        default="domains",
        help="Directory containing subdomain JSON files (default: domains)",
    )
    parser.add_argument(
        "--schema",
        default="schemas/domain.json",
        help="Path to the JSON schema file (default: schemas/domain.json)",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific files to validate (defaults to all *.json in --domains-dir)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / args.schema
    domains_dir = repo_root / args.domains_dir

    if not schema_path.exists():
        print(f"ERROR: Schema file not found: {schema_path}", file=sys.stderr)
        return 1

    schema = load_schema(schema_path)

    if args.files:
        files = [Path(f).resolve() for f in args.files]
    else:
        files = sorted(domains_dir.glob("*.json"))

    if not files:
        print("No domain files found to validate.")
        return 0

    total = 0
    failed = 0

    for file_path in files:
        if file_path.stem == "_example":
            continue
        total += 1
        file_errors = validate_file(file_path, schema)
        if file_errors:
            failed += 1
            print(f"\n❌  {file_path.name}")
            for err in file_errors:
                print(f"    • {err}")
        else:
            print(f"✅  {file_path.name}")

    print(f"\n{'='*50}")
    print(f"Validated {total} file(s): {total - failed} passed, {failed} failed.")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
