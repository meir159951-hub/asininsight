"""
CLI: seed the local DB with mock PPC data so the dashboard has something to show.

Usage:
    python seed_mock_ppc.py --customer cust_demo
    python seed_mock_ppc.py --customer cust_demo --connection-id 42

What it does:
1. Creates an `amazon_connections` row for the given customer if one does
   not already exist (or reuses --connection-id).
2. Inserts the mock snapshot rows (profiles, campaigns, ad_groups, keywords,
   search_terms) into `ppc_snapshots` for that connection.
3. Runs `ppc_suggestions.generate_suggestions` so `ppc_suggestions` is
   populated and the dashboard shows pending recommendations and a money-
   found total immediately.

This is intentionally separate from `mock_ppc_data.py`. That module only
provides fixtures; this CLI is the operator-facing entry point.

Hard rules respected:
- No Amazon API calls.
- No payments work.
- No commits / pushes / deploys.
- No production credentials are read or written. The encrypted refresh-token
  field is set to a placeholder string. The connection row will fail any real
  decrypt attempt; that is by design, this is a demo seed only.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import mock_ppc_data
import ppc_suggestions

log = logging.getLogger("seed_mock_ppc")


def _ensure_connection(db_ctx_factory, customer_id: str, connection_id: int | None) -> int:
    """
    Return the id of an existing or newly-inserted amazon_connections row.

    If `connection_id` is provided, we reuse that row when it already exists
    and matches the customer; otherwise we INSERT a new row with that id.

    If `connection_id` is None, we look up any active row for this customer
    and reuse it; otherwise we INSERT a new row and let the DB assign the id.
    """
    now = time.time()
    placeholder_token = "DEMO_PLACEHOLDER_NOT_A_REAL_TOKEN"

    with db_ctx_factory() as (cur, ph):
        if connection_id is not None:
            cur.execute(
                f"SELECT customer_id FROM amazon_connections WHERE id = {ph}",
                (connection_id,),
            )
            existing = cur.fetchone()
            if existing:
                if existing[0] != customer_id:
                    raise SystemExit(
                        f"connection_id={connection_id} is owned by a different "
                        f"customer ({existing[0]}). Refusing to overwrite. "
                        f"Pick a different --connection-id or omit it."
                    )
                return int(connection_id)

            cur.execute(
                f"""
                INSERT INTO amazon_connections
                  (id, customer_id, seller_id, marketplace_id,
                   refresh_token_encrypted, connected_at, last_synced_at, active)
                VALUES ({ph}, {ph}, {ph}, 'ATVPDKIKX0DER', {ph}, {ph}, NULL, 1)
                """,
                (
                    connection_id,
                    customer_id,
                    f"A1MOCK{customer_id[:8]}",
                    placeholder_token,
                    now,
                ),
            )
            return int(connection_id)

        cur.execute(
            f"""
            SELECT id FROM amazon_connections
            WHERE customer_id = {ph} AND active = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (customer_id,),
        )
        row = cur.fetchone()
        if row:
            return int(row[0])

        cur.execute(
            f"""
            INSERT INTO amazon_connections
              (customer_id, seller_id, marketplace_id,
               refresh_token_encrypted, connected_at, last_synced_at, active)
            VALUES ({ph}, {ph}, 'ATVPDKIKX0DER', {ph}, {ph}, NULL, 1)
            """,
            (
                customer_id,
                f"A1MOCK{customer_id[:8]}",
                placeholder_token,
                now,
            ),
        )
        # cursor.lastrowid is sqlite-specific; postgres path is unused in
        # this CLI because the local dev DB is sqlite by default.
        return int(cur.lastrowid or 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed mock PPC data for local dev / dashboard demos."
    )
    parser.add_argument(
        "--customer",
        default="cust_demo",
        help="customer_id used to scope the connection row (default cust_demo)",
    )
    parser.add_argument(
        "--connection-id",
        type=int,
        default=None,
        help="explicit amazon_connections.id; default is auto-pick or auto-insert",
    )
    parser.add_argument(
        "--no-suggestions",
        action="store_true",
        help="skip running generate_suggestions after seeding",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="enable INFO-level logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Lazy import so importing this CLI module in tests does not boot Flask.
    from server import _db as db_ctx_factory

    cid = _ensure_connection(db_ctx_factory, args.customer, args.connection_id)
    print(f"connection_id: {cid} (customer_id={args.customer})")

    counts = mock_ppc_data.seed_mock_snapshot(cid, db_ctx_factory)
    print("snapshot rows inserted:")
    for k, v in counts.items():
        print(f"  {k:<14} {v}")

    if args.no_suggestions:
        print("Skipped generate_suggestions (--no-suggestions).")
        return 0

    suggestions = ppc_suggestions.generate_suggestions(cid, db_ctx_factory=db_ctx_factory)
    money = ppc_suggestions.money_found_total(suggestions)
    print(f"suggestions generated: {len(suggestions)}")
    print(f"money found total:     ${money:.2f}")
    by_type: dict[str, int] = {}
    for s in suggestions:
        t = s["suggestion_type"]
        by_type[t] = by_type.get(t, 0) + 1
    for t, n in sorted(by_type.items()):
        print(f"  {t:<22} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
