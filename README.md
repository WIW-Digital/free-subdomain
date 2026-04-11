# free-subdomain

> **Get a free subdomain** backed by Cloudflare DNS — similar to [is-a.dev](https://is-a.dev).  
> Simply open a pull request with a JSON file and your subdomain will be provisioned automatically.

[![Validate Domain Files](https://github.com/WIW-Digital/free-subdomain/actions/workflows/validate.yml/badge.svg)](https://github.com/WIW-Digital/free-subdomain/actions/workflows/validate.yml)
[![Sync DNS Records](https://github.com/WIW-Digital/free-subdomain/actions/workflows/sync.yml/badge.svg)](https://github.com/WIW-Digital/free-subdomain/actions/workflows/sync.yml)

---

## Table of Contents

- [How it works](#how-it-works)
- [Register a subdomain](#register-a-subdomain)
- [JSON file format](#json-file-format)
- [Supported record types](#supported-record-types)
- [Rules & restrictions](#rules--restrictions)
- [Updating or removing your subdomain](#updating-or-removing-your-subdomain)
- [Repository structure](#repository-structure)
- [Self-hosting](#self-hosting)

---

## How it works

1. You open a pull request adding a file `domains/<your-subdomain>.json`.
2. A GitHub Actions workflow validates the file against the [JSON schema](schemas/domain.json).
3. Once a maintainer merges the PR, another workflow syncs the records to Cloudflare DNS automatically.

---

## Register a subdomain

### Step 1 — Fork this repository

Click the **Fork** button at the top right of this page.

### Step 2 — Create your JSON file

Inside the `domains/` folder create a new file named `<your-subdomain>.json`.  
For example, to claim `hello.example.com` create `domains/hello.json`.

Use the template below (or copy [`domains/_example.json`](domains/_example.json)):

```json
{
  "description": "My personal website",
  "owner": {
    "username": "your-github-username",
    "email": "optional@example.com"
  },
  "record": {
    "A": ["203.0.113.42"]
  }
}
```

### Step 3 — Open a pull request

Commit your file and open a pull request against `main`.  
The validation workflow will run automatically and report any issues in the PR.

### Step 4 — Wait for a maintainer to review & merge

Once merged your DNS record will be created within a few minutes.

---

## JSON file format

| Field | Required | Description |
|-------|----------|-------------|
| `description` | No | Short description of what this subdomain is for (max 256 chars) |
| `owner.username` | **Yes** | Your GitHub username |
| `owner.email` | No | Contact email |
| `record` | **Yes** | Object containing one or more DNS record types (see below) |

---

## Supported record types

You can include **one or more** of the following record types inside the `record` object.  
**A/AAAA and CNAME cannot be combined** in the same file.

### A record — point to an IPv4 address

```json
"record": {
  "A": ["203.0.113.42"]
}
```

### AAAA record — point to an IPv6 address

```json
"record": {
  "AAAA": ["2001:db8::1"]
}
```

### CNAME record — alias to another hostname

```json
"record": {
  "CNAME": "your-target.example.com"
}
```

> **Note:** CNAME cannot be combined with A or AAAA records.

### TXT record — arbitrary text (SPF, domain verification, etc.)

```json
"record": {
  "A": ["203.0.113.42"],
  "TXT": ["v=spf1 include:example.com ~all"]
}
```

### MX record — mail exchange

```json
"record": {
  "A": ["203.0.113.42"],
  "MX": [
    { "priority": 10, "value": "mail.example.com" }
  ]
}
```

### NS record — delegate to your own nameservers

```json
"record": {
  "NS": ["ns1.example.com", "ns2.example.com"]
}
```

---

## Rules & restrictions

- The subdomain name must contain only **lowercase letters, digits, and hyphens** (`-`).
- It must **not** start or end with a hyphen.
- Maximum label length is **63 characters** (DNS limit).
- A few names are **reserved** (`www`, `mail`, `ns`, `ns1`, `ns2`, …) and cannot be registered.
- Each registrant is allowed **one subdomain** per GitHub account (maintainers may enforce this manually).
- Subdomains may be reclaimed if they appear abandoned or are used in violation of these rules.
- **Do not** point your subdomain to IP addresses or content that violates applicable laws.

---

## Updating or removing your subdomain

### Update

Edit your `domains/<subdomain>.json` file and open a new pull request.

### Remove

Delete your `domains/<subdomain>.json` file and open a pull request.  
Once merged the DNS records will be removed automatically.

---

## Repository structure

```
free-subdomain/
├── .github/
│   └── workflows/
│       ├── validate.yml   # Validates JSON files on every PR
│       └── sync.yml       # Syncs DNS records on merge to main
├── domains/
│   ├── _example.json      # Example file — do not modify
│   └── <subdomain>.json   # Your subdomain file
├── schemas/
│   └── domain.json        # JSON schema for validation
├── scripts/
│   ├── validate.py        # Validation script
│   └── sync.py            # Cloudflare DNS sync script
├── requirements.txt
└── README.md
```

---

## Self-hosting

Want to run your own instance?

### 1. Fork this repository

### 2. Add the following repository secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `CF_API_TOKEN` | Cloudflare API token with **Zone › DNS › Edit** permission |
| `CF_ZONE_ID` | The Cloudflare Zone ID for your domain |
| `BASE_DOMAIN` | Your base domain, e.g. `example.com` |

### 3. Update the example file

Edit `domains/_example.json` to reflect your domain.

### 4. You're done!

Pull requests to `domains/` will be validated automatically and merged records will be synced to your Cloudflare zone.

---

## License

[MIT](LICENSE)