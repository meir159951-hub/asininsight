"""
Domain availability checker for SellerCopilot brand candidates.

Uses python-whois (free) to check WHOIS records.
A domain that has NO whois record (NXDOMAIN-like) is likely available.
A domain WITH a whois record is registered (look at status to confirm).

Usage:
    pip install python-whois
    python scripts/check_domain_availability.py

Output: a table showing which domain candidates are available.

Note: WHOIS data accuracy varies by TLD. For final verification, ALWAYS
check at a registrar like Namecheap, Porkbun, or Cloudflare Registrar
before committing to buy.
"""

from __future__ import annotations

import sys
import time
from typing import Optional


# Candidate domains to check, ordered by preference.
# If you have other names you want to try, add them here.
DOMAIN_CANDIDATES: list[str] = [
    # Primary brand name
    "sellercopilot.com",
    "sellercopilot.ai",
    "sellercopilot.app",
    "sellercopilot.io",
    "sellercopilot.co",
    "sellercopilot.net",

    # Variations
    "seller-copilot.com",
    "sellercopilot.dev",
    "trysellercopilot.com",
    "getsellercopilot.com",
    "usesellercopilot.com",

    # Backup brand candidates (from competitive_deep_dive_2026_05.md)
    "ppcmemory.com",
    "ppcmemory.ai",
    "amzcopilot.com",
    "amzcopilot.ai",
    "adcopilot.ai",
    "sellermemory.com",
    "acosagent.com",
    "acosagent.ai",

    # Hebrew-friendly alternatives (if you want to honor your roots)
    "amzpilot.com",
    "amzpilot.ai",
]


def check_domain(domain: str) -> dict:
    """
    Check if a domain appears to be available via WHOIS lookup.

    Returns:
        dict with keys: domain, status, registrar, expires, raw
    """
    try:
        import whois
    except ImportError:
        print("ERROR: python-whois not installed.")
        print("Install with: pip install python-whois")
        sys.exit(1)

    try:
        result = whois.whois(domain)

        # If there's no domain_name or it's None, the domain is likely available
        if not result or not result.domain_name:
            return {
                "domain": domain,
                "status": "AVAILABLE",
                "registrar": None,
                "expires": None,
            }

        # If we got data, the domain is registered
        return {
            "domain": domain,
            "status": "REGISTERED",
            "registrar": getattr(result, "registrar", "unknown"),
            "expires": str(getattr(result, "expiration_date", "unknown")),
        }
    except Exception as e:
        msg = str(e).lower()
        # Some WHOIS servers throw on NXDOMAIN — that means available
        if "no match" in msg or "not found" in msg or "no entries" in msg:
            return {
                "domain": domain,
                "status": "AVAILABLE",
                "registrar": None,
                "expires": None,
            }
        return {
            "domain": domain,
            "status": f"ERROR: {e}",
            "registrar": None,
            "expires": None,
        }


def print_table(results: list[dict]) -> None:
    """Print a clean table of results."""
    # Determine widths
    max_domain_width = max(len(r["domain"]) for r in results)
    max_status_width = max(len(r["status"]) for r in results)

    print()
    print("=" * (max_domain_width + max_status_width + 40))
    print(f"{'DOMAIN'.ljust(max_domain_width)}  {'STATUS'.ljust(max_status_width)}  {'REGISTRAR'.ljust(25)}  EXPIRES")
    print("-" * (max_domain_width + max_status_width + 40))

    # Available first
    for r in sorted(results, key=lambda x: (x["status"] != "AVAILABLE", x["domain"])):
        domain = r["domain"].ljust(max_domain_width)
        status = r["status"].ljust(max_status_width)
        registrar = (r["registrar"] or "-")[:25].ljust(25)
        expires = (r["expires"] or "-")[:25]

        # Color hints (ANSI codes; works in most modern terminals)
        if r["status"] == "AVAILABLE":
            print(f"\033[92m{domain}\033[0m  \033[92m{status}\033[0m  {registrar}  {expires}")
        elif r["status"].startswith("ERROR"):
            print(f"\033[93m{domain}\033[0m  \033[93m{status}\033[0m  {registrar}  {expires}")
        else:
            print(f"\033[91m{domain}\033[0m  \033[91m{status}\033[0m  {registrar}  {expires}")

    print("=" * (max_domain_width + max_status_width + 40))


def main():
    print(f"Checking {len(DOMAIN_CANDIDATES)} domains...")
    print("(WHOIS queries are rate-limited; this takes about 1-2 minutes)")
    print()

    results = []
    for i, domain in enumerate(DOMAIN_CANDIDATES, 1):
        print(f"  [{i}/{len(DOMAIN_CANDIDATES)}] {domain}...", end=" ", flush=True)
        result = check_domain(domain)
        results.append(result)
        print(result["status"])

        # Small delay to be polite to WHOIS servers
        if i < len(DOMAIN_CANDIDATES):
            time.sleep(1.5)

    print_table(results)

    # Summary
    available = [r["domain"] for r in results if r["status"] == "AVAILABLE"]
    if available:
        print()
        print(f"✅ {len(available)} domain(s) appear available:")
        for d in available:
            print(f"   - {d}")
        print()
        print("⚠️  IMPORTANT: WHOIS data is not always 100% reliable.")
        print("   Before buying, verify availability at a registrar:")
        print("   - https://www.namecheap.com/")
        print("   - https://porkbun.com/")
        print("   - https://www.cloudflare.com/products/registrar/")
    else:
        print()
        print("⚠️  All candidate domains appear registered.")
        print("   Either someone owns SellerCopilot already, or these are common")
        print("   placeholder pages. Verify manually at a registrar.")
        print("   Consider new naming candidates in docs/competitive_deep_dive_2026_05.md")


if __name__ == "__main__":
    main()
