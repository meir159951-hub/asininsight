"""
CSV ingest path for ASINInsight PPC Agent.

Why this module exists
----------------------
The full live path requires Amazon SP-API Production approval (4 to 8
weeks) plus a connected Seller Central account. Until both are in place,
sellers can still get value from the suggestion engine by uploading their
own Sponsored Products Search Term Report CSV (downloadable from Amazon
Seller Central > Reports > Advertising Reports).

This module reads that CSV in memory, normalises each row into the same
shape the live fetcher writes into `ppc_snapshots`, and lets the existing
`ppc_suggestions.analyze()` produce suggestions.

Approval-first by construction
------------------------------
- No DB writes. Nothing is persisted.
- No Amazon API calls. Nothing reaches Amazon.
- No connection_id is created.
- Suggestions are rendered for the seller to read; there is no Approve
  button on this path because there is no live link to push a change.

Design notes
------------
Amazon's report column names drift over time and across report variants
("Search Term Report" vs "Search-Term Performance Report" vs the v3 Ads
API JSON export). The parser uses substring header matching with a small
synonyms map so a column called "Customer Search Term", "Search term", or
"Customer search term (Q)" all map to the same field.

The parser deliberately accepts partial data. A CSV with no `Spend`
column is treated as cost=0 (nothing waste-related fires), but the rest
of the engine still runs. We log what we recognised so the seller knows
which rules can fire.

The keywords list is derived from the search-term rows: every distinct
(keyword text + ad group + match type) tuple becomes a keyword entry. We
synthesise stable keyword IDs so the engine's keyword-vs-keyword matching
works (rule 5 needs that to skip terms that are already keywords).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any, Iterable

log = logging.getLogger("ppc_csv_ingest")


# ──────────────────────────────────────────────────────────────────────────
#  Header synonyms (lowercase, hyphen/underscore stripped)
# ──────────────────────────────────────────────────────────────────────────
#
# Each canonical field maps to a list of substring fragments. A CSV header
# matches a canonical field if any fragment is contained in the
# normalised header text. First match wins, so list more specific
# fragments before more general ones.

_HEADER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "campaign":      ("campaign name", "campaign"),
    "ad_group":      ("ad group name", "adgroup name", "ad group", "adgroup"),
    "keyword":       ("targeting", "keyword text", "keyword"),
    "match_type":    ("match type", "matchtype"),
    "search_term":   ("customer search term", "search term", "searchterm"),
    "impressions":   ("impressions",),
    "clicks":        ("clicks",),
    "cost":          ("spend", "cost"),
    "sales":         ("7 day total sales", "14 day total sales", "30 day total sales",
                      "total sales", "sales"),
    "orders":        ("7 day total orders", "14 day total orders", "30 day total orders",
                      "total orders", "orders"),
}


def _normalise_header(text: str) -> str:
    """
    Lowercase + strip non-alphanumeric punctuation so headers from
    different report versions reduce to the same string. Keeps spaces so
    "campaign name" and "campaign" stay distinguishable.
    """
    s = (text or "").lower().strip()
    # Replace common separators with space so "ad-group" and "ad group"
    # collapse identically.
    s = re.sub(r"[\-_/]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    # Strip currency / unit markers reviewers love to add.
    s = s.replace("(usd)", "").replace("(#)", "").replace("(%)", "")
    return s.strip()


def _build_header_index(headers: list[str]) -> dict[str, int]:
    """
    Map canonical field name -> column index. Headers that don't map to
    any canonical field are silently ignored (the engine never needs
    them).
    """
    norm = [_normalise_header(h) for h in headers]
    out: dict[str, int] = {}
    for canonical, fragments in _HEADER_SYNONYMS.items():
        for idx, h in enumerate(norm):
            if any(frag in h for frag in fragments):
                # Don't overwrite an earlier (more specific) hit.
                out.setdefault(canonical, idx)
                break
    return out


# ──────────────────────────────────────────────────────────────────────────
#  Numeric parsers
# ──────────────────────────────────────────────────────────────────────────

_MONEY_STRIP = re.compile(r"[^\d\.\-]")


def _parse_money(raw: str | None) -> float:
    """
    Parse an Amazon money cell. Tolerates "$12.34", "12.34", "1,234.56",
    "($5.00)" (parens for negative). Empty / unparseable returns 0.0.
    """
    if raw is None:
        return 0.0
    s = str(raw).strip()
    if not s:
        return 0.0
    negative = s.startswith("(") and s.endswith(")")
    s = _MONEY_STRIP.sub("", s)
    if not s or s == "-" or s == ".":
        return 0.0
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return -v if negative else v


def _parse_int(raw: str | None) -> int:
    """Parse an integer cell. "1,234" -> 1234. Empty / bad -> 0."""
    if raw is None:
        return 0
    s = str(raw).strip().replace(",", "")
    if not s:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


# ──────────────────────────────────────────────────────────────────────────
#  Public API
# ──────────────────────────────────────────────────────────────────────────

class CSVIngestError(Exception):
    """Raised when the CSV is unrecognisable as an Amazon PPC report."""


REQUIRED_FIELDS = ("search_term", "keyword", "impressions")


def parse_search_term_csv(text_or_stream) -> list[dict[str, Any]]:
    """
    Parse a Sponsored Products Search Term Report CSV.

    Args:
        text_or_stream: a str of CSV text, or an object with .read() that
            returns str/bytes (Flask file uploads return BytesIO; the
            caller is expected to decode and pass either a str or a
            text-mode stream).

    Returns:
        list of search-term row dicts shaped to match what the live
        fetcher writes for `data_type='search_terms'`. Each row has:
        campaignId, adGroupId, keywordId, keywordText, matchType,
        searchTerm, impressions, clicks, cost, sales30d, purchases30d.

    Raises:
        CSVIngestError: if the file does not look like a recognisable PPC
            report (no required headers found).

    The parser is intentionally permissive: rows with bad money or count
    cells are recovered to zero rather than dropped, because the seller
    is reading the resulting suggestions to make a judgement, not feeding
    them into a billing system.
    """
    if hasattr(text_or_stream, "read"):
        raw = text_or_stream.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig", errors="replace")
        text = str(raw)
    else:
        text = str(text_or_stream)

    if not text.strip():
        raise CSVIngestError("Uploaded CSV is empty.")

    # Strip BOM if the upstream decode missed it.
    if text.startswith("﻿"):
        text = text[1:]

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        raise CSVIngestError("Uploaded CSV has no rows.")

    index = _build_header_index(headers)
    missing = [f for f in REQUIRED_FIELDS if f not in index]
    if missing:
        raise CSVIngestError(
            "CSV does not look like an Amazon PPC search-term report. "
            f"Missing recognised columns: {', '.join(missing)}. "
            "Expected headers like 'Customer Search Term', 'Targeting' "
            "or 'Keyword', and 'Impressions'. Re-export from Seller Central > "
            "Reports > Advertising Reports > Search Term."
        )

    out: list[dict[str, Any]] = []
    skipped = 0
    for row_no, row in enumerate(reader, start=2):
        if not row or all((cell or "").strip() == "" for cell in row):
            continue
        try:
            cell = lambda field: row[index[field]] if field in index and index[field] < len(row) else ""

            keyword_text = (cell("keyword") or "").strip()
            search_term  = (cell("search_term") or "").strip()
            if not search_term:
                skipped += 1
                continue

            campaign  = (cell("campaign") or "").strip()
            ad_group  = (cell("ad_group") or "").strip()
            match_type = ((cell("match_type") or "").strip().lower() or "broad")

            impressions = _parse_int(cell("impressions"))
            clicks      = _parse_int(cell("clicks"))
            cost        = _parse_money(cell("cost"))
            sales       = _parse_money(cell("sales"))
            orders      = _parse_int(cell("orders"))

            out.append({
                "campaignId":  campaign or "csv-campaign",
                "adGroupId":   ad_group or "csv-adgroup",
                "keywordId":   _stable_keyword_id(keyword_text, ad_group, match_type)
                               if keyword_text else None,
                "keywordText": keyword_text,
                "matchType":   match_type,
                "searchTerm":  search_term,
                "impressions": impressions,
                "clicks":      clicks,
                "cost":        cost,
                "purchases1d": 0,  "purchases7d":  0, "purchases14d": 0,
                "purchases30d": orders,
                "sales1d":     0.0, "sales7d":      0.0, "sales14d":     0.0,
                "sales30d":    sales,
            })
        except Exception as e:
            log.warning("CSV row %d skipped: %s", row_no, e)
            skipped += 1

    if skipped:
        log.info("parse_search_term_csv accepted=%d skipped=%d", len(out), skipped)

    if not out:
        raise CSVIngestError(
            "CSV had recognisable headers but every row was empty or "
            "missing the search term. Re-export the report and make sure "
            "the Customer Search Term column has values."
        )
    return out


def _stable_keyword_id(keyword_text: str, ad_group: str, match_type: str) -> str:
    """
    Synthesise a deterministic keyword ID from the (text, ad_group, match)
    tuple. The engine groups search-term rows by keyword via this id, and
    rule 5 (promote_search_term) compares search terms to the keyword
    list by lowercased text. Stable IDs let two CSV rows with the same
    targeting roll up to one keyword.
    """
    base = f"csv|{ad_group}|{match_type}|{keyword_text}".lower()
    return "csvkw-" + str(abs(hash(base)) % (10 ** 12))


def derive_keywords_from_search_terms(
    search_terms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build a keywords list (data_type='keywords' shape) from the parsed
    search-term rows. One keyword per (text, ad_group, match_type) tuple.

    Bid is set to the implied CPC (cost / clicks) so rule 3 (bid_too_high)
    has a number to compare against the ad-group default. If clicks are
    zero, bid falls back to a small floor so the rule does not fire on
    accidental zeroes.
    """
    by_kw: dict[str, dict[str, Any]] = {}
    for row in search_terms:
        kid = row.get("keywordId")
        if not kid:
            continue
        agg = by_kw.setdefault(kid, {
            "keywordId":   kid,
            "adGroupId":   row.get("adGroupId"),
            "campaignId":  row.get("campaignId"),
            "keywordText": row.get("keywordText"),
            "matchType":   row.get("matchType"),
            "state":       "ENABLED",
            "_cost":       0.0,
            "_clicks":     0,
        })
        agg["_cost"]   += float(row.get("cost", 0) or 0)
        agg["_clicks"] += int(row.get("clicks", 0) or 0)

    out: list[dict[str, Any]] = []
    for agg in by_kw.values():
        cost   = agg.pop("_cost")
        clicks = agg.pop("_clicks")
        agg["bid"] = round(cost / clicks, 2) if clicks else 0.50
        out.append(agg)
    return out


def derive_ad_groups_from_search_terms(
    search_terms: list[dict[str, Any]],
    keywords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Build a minimal ad_groups list. defaultBid is set to the median bid
    of keywords in that ad group, which is what rule 3 compares against.
    Without a median bid, rule 3 cannot fire (and that is the correct
    behaviour for a CSV that lacks ad-group context).
    """
    bids_by_ag: dict[str, list[float]] = {}
    for kw in keywords:
        agid = kw.get("adGroupId")
        bid  = float(kw.get("bid", 0) or 0)
        if agid and bid > 0:
            bids_by_ag.setdefault(agid, []).append(bid)

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in search_terms:
        agid = row.get("adGroupId")
        if not agid or agid in seen:
            continue
        seen.add(agid)
        bids = bids_by_ag.get(agid, [])
        default_bid = (
            round(sorted(bids)[len(bids) // 2], 2)
            if bids
            else 0.50  # neutral floor; rule 3 is then unlikely to fire
        )
        out.append({
            "adGroupId":   agid,
            "campaignId":  row.get("campaignId"),
            "name":        agid,
            "defaultBid":  default_bid,
            "state":       "ENABLED",
        })
    return out


def derive_campaigns_from_search_terms(
    search_terms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Distinct campaign ids -> minimal campaigns list."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in search_terms:
        cid = row.get("campaignId")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "campaignId":  cid,
            "name":        cid,
            "state":       "ENABLED",
            "campaignType": "sponsoredProducts",
        })
    return out


def build_snapshot_from_csv(text_or_stream) -> dict[str, list[dict[str, Any]]]:
    """
    End-to-end: parse a search-term CSV and return the same dict shape
    `mock_ppc_data.build_snapshot_payload()` produces. Feed the result
    directly to `ppc_suggestions.analyze`.

    Raises:
        CSVIngestError: see `parse_search_term_csv`.
    """
    search_terms = parse_search_term_csv(text_or_stream)
    keywords     = derive_keywords_from_search_terms(search_terms)
    ad_groups    = derive_ad_groups_from_search_terms(search_terms, keywords)
    campaigns    = derive_campaigns_from_search_terms(search_terms)
    return {
        "profiles":     [],
        "campaigns":    campaigns,
        "ad_groups":    ad_groups,
        "keywords":     keywords,
        "search_terms": search_terms,
    }


def summarise_ingest(snapshot: dict[str, Iterable[Any]]) -> dict[str, int]:
    """Counts per data_type, used by the dashboard to confirm parse health."""
    return {k: len(list(v)) for k, v in snapshot.items()}
