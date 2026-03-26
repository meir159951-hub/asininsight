from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "sample_data" / "demo_store.json"
OUTPUT_DIR = BASE_DIR / "output"


@dataclass
class Issue:
    asin: str
    product_title: str
    category: str
    area: str
    severity: str
    impact: str
    recommendation: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an Amazon seller audit report.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to store JSON data.")
    return parser.parse_args()


def load_store(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def severity_rank(severity: str) -> int:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return order.get(severity, 99)


def evaluate_product(product: dict[str, Any]) -> list[Issue]:
    issues: list[Issue] = []
    asin = product["asin"]
    title = product["title"]
    category = product["category"]

    def add_issue(area: str, severity: str, impact: str, recommendation: str, reason: str) -> None:
        issues.append(
            Issue(
                asin=asin,
                product_title=title,
                category=category,
                area=area,
                severity=severity,
                impact=impact,
                recommendation=recommendation,
                reason=reason,
            )
        )

    if product["title_length"] < 40:
        add_issue(
            "listing",
            "medium",
            "Missing keyword coverage can reduce discoverability.",
            "Expand the title to include the top buying intent keywords and core product attributes.",
            f"Title length is only {product['title_length']} characters.",
        )

    if product["bullet_count"] < 5:
        add_issue(
            "listing",
            "medium",
            "Thin bullets usually lower conversion by failing to answer buyer objections.",
            "Add five buyer-focused bullets covering use case, materials, dimensions, and differentiation.",
            f"Listing has {product['bullet_count']} bullet points.",
        )

    if product["images_count"] < 6:
        add_issue(
            "listing",
            "high",
            "Weak image coverage lowers click-through rate and conversion.",
            "Add more images, including one infographic and one lifestyle image.",
            f"Listing has {product['images_count']} images.",
        )

    if not product["has_a_plus"]:
        add_issue(
            "listing",
            "medium",
            "Missing A+ content reduces brand trust and conversion depth.",
            "Add A+ content with brand story, comparison chart, and feature callouts.",
            "A+ content is not enabled.",
        )

    if product["conversion_rate"] < 0.025:
        severity = "critical" if product["conversion_rate"] < 0.018 else "high"
        add_issue(
            "conversion",
            severity,
            "Low conversion means traffic is not turning into enough orders.",
            "Review pricing, creatives, reviews, and listing clarity for this ASIN.",
            f"Conversion rate is {product['conversion_rate']:.2%}.",
        )

    if product["ctr"] < 0.0035:
        add_issue(
            "traffic",
            "high",
            "A low click-through rate suggests the main image or title is losing the search click.",
            "Test a stronger hero image and clearer value-driven title structure.",
            f"CTR is {product['ctr']:.2%}.",
        )

    if product["rating"] < 4.0:
        add_issue(
            "reviews",
            "high",
            "Low product rating can block conversion and ad efficiency.",
            "Inspect review themes, fix product complaints, and improve post-purchase review flow.",
            f"Average rating is {product['rating']:.1f}.",
        )

    if product["review_count"] < 25:
        add_issue(
            "reviews",
            "medium",
            "Low review count weakens trust against better-established competitors.",
            "Prioritize compliant review generation and post-purchase follow-up.",
            f"Only {product['review_count']} reviews are available.",
        )

    if product["days_of_cover"] < 14:
        severity = "critical" if product["days_of_cover"] < 8 else "high"
        add_issue(
            "inventory",
            severity,
            "Low stock cover creates revenue risk and ranking loss if inventory runs out.",
            "Replenish this ASIN or reduce spend until inventory stabilizes.",
            f"Estimated days of cover: {product['days_of_cover']}.",
        )

    if product["acos"] > 0.45:
        severity = "critical" if product["acos"] > 0.8 else "high"
        add_issue(
            "ads",
            severity,
            "Advertising spend is inefficient relative to attributed sales.",
            "Cut weak search terms, lower bids on poor segments, and re-check listing conversion before scaling ads.",
            f"ACOS is {product['acos']:.0%}.",
        )

    if product["organic_rank_top_keyword"] > 30:
        add_issue(
            "seo",
            "medium",
            "Weak organic rank limits low-cost traffic growth.",
            "Improve keyword targeting in title, bullets, backend terms, and external traffic support.",
            f"Top keyword organic rank is {product['organic_rank_top_keyword']}.",
        )

    return issues


def calculate_store_score(products: list[dict[str, Any]], issues: list[Issue]) -> int:
    score = 100

    for issue in issues:
        if issue.severity == "critical":
            score -= 8
        elif issue.severity == "high":
            score -= 5
        elif issue.severity == "medium":
            score -= 3
        else:
            score -= 1

    if not products:
        return 0

    weak_conversion_products = sum(1 for product in products if product["conversion_rate"] < 0.025)
    if weak_conversion_products >= max(1, len(products) // 2):
        score -= 5

    return max(score, 0)


def summarize_issues(issues: list[Issue]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for issue in issues:
        summary[issue.area] = summary.get(issue.area, 0) + 1
    return dict(sorted(summary.items(), key=lambda item: item[1], reverse=True))


def build_priority_actions(issues: list[Issue]) -> list[Issue]:
    return sorted(
        issues,
        key=lambda issue: (
            severity_rank(issue.severity),
            issue.area,
            issue.asin,
        ),
    )[:5]


def health_label(score: int) -> str:
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Watch"
    if score >= 50:
        return "At Risk"
    return "Critical"


def render_html(store: dict[str, Any], issues: list[Issue], score: int) -> str:
    issue_summary = summarize_issues(issues)
    priority_actions = build_priority_actions(issues)
    products = store.get("products", [])

    summary_items = "".join(
        f"<li><strong>{escape(area.title())}</strong>: {count} issue(s)</li>"
        for area, count in issue_summary.items()
    )

    priority_rows = "".join(
        """
        <tr>
          <td>{severity}</td>
          <td>{asin}</td>
          <td>{area}</td>
          <td>{reason}</td>
          <td>{recommendation}</td>
        </tr>
        """.format(
            severity=escape(issue.severity.upper()),
            asin=escape(issue.asin),
            area=escape(issue.area.title()),
            reason=escape(issue.reason),
            recommendation=escape(issue.recommendation),
        )
        for issue in priority_actions
    )

    product_rows = "".join(
        """
        <tr>
          <td>{asin}</td>
          <td>{title}</td>
          <td>{conversion}</td>
          <td>{ctr}</td>
          <td>{rating}</td>
          <td>{days}</td>
          <td>{acos}</td>
        </tr>
        """.format(
            asin=escape(product["asin"]),
            title=escape(product["title"]),
            conversion=f"{product['conversion_rate']:.2%}",
            ctr=f"{product['ctr']:.2%}",
            rating=f"{product['rating']:.1f}",
            days=product["days_of_cover"],
            acos=f"{product['acos']:.0%}",
        )
        for product in products
    )

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    label = health_label(score)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Amazon Seller Audit</title>
  <style>
    :root {{
      --bg: #f5f0e8;
      --panel: #fffdf9;
      --ink: #1f1f1f;
      --muted: #6e675f;
      --line: #ded5c8;
      --accent: #b44c2d;
      --accent-soft: #f3d1c6;
      --ok: #2d6a4f;
      --warn: #b08900;
      --bad: #9b2226;
    }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #efe6da 0%, var(--bg) 100%);
      color: var(--ink);
      font: 16px/1.5 Georgia, "Times New Roman", serif;
    }}
    .wrap {{
      max-width: 1100px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 28px;
      box-shadow: 0 8px 30px rgba(70, 42, 24, 0.08);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 38px;
      line-height: 1.1;
    }}
    .muted {{
      color: var(--muted);
    }}
    .score {{
      display: inline-block;
      margin-top: 18px;
      padding: 12px 18px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px;
      margin-top: 20px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 22px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: left;
      padding: 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    ul {{
      padding-left: 20px;
      margin: 0;
    }}
    .footer {{
      margin-top: 18px;
      font-size: 13px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <h1>{escape(store['store_name'])} Audit Report</h1>
      <div class="muted">{escape(store['marketplace'])} | Seller type: {escape(store['seller_type'])}</div>
      <div class="score">Store Health Score: {score}/100 ({label})</div>
      <p class="muted">Generated at {generated_at}. This report is based on demo data and simple rules to validate the product direction.</p>
    </section>

    <section class="grid">
      <div class="card">
        <h2>Store Snapshot</h2>
        <ul>
          <li>{len(products)} active products analyzed</li>
          <li>{len(issues)} total issues detected</li>
          <li>{sum(1 for issue in issues if issue.severity == 'critical')} critical issues</li>
          <li>{sum(1 for issue in issues if issue.severity == 'high')} high-priority issues</li>
        </ul>
      </div>
      <div class="card">
        <h2>Issue Mix</h2>
        <ul>{summary_items}</ul>
      </div>
    </section>

    <section class="card" style="margin-top: 16px;">
      <h2>Top Priority Actions</h2>
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>ASIN</th>
            <th>Area</th>
            <th>Why This Matters</th>
            <th>Recommended Action</th>
          </tr>
        </thead>
        <tbody>{priority_rows}</tbody>
      </table>
    </section>

    <section class="card" style="margin-top: 16px;">
      <h2>Product Metrics</h2>
      <table>
        <thead>
          <tr>
            <th>ASIN</th>
            <th>Title</th>
            <th>Conversion</th>
            <th>CTR</th>
            <th>Rating</th>
            <th>Days of Cover</th>
            <th>ACOS</th>
          </tr>
        </thead>
        <tbody>{product_rows}</tbody>
      </table>
      <div class="footer">
        MVP scope note: the next step would be replacing demo JSON with seller-uploaded CSV or live API data.
      </div>
    </section>
  </div>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    store = load_store(args.input)
    products = store.get("products", [])
    issues = sorted(
        [issue for product in products for issue in evaluate_product(product)],
        key=lambda issue: (severity_rank(issue.severity), issue.area, issue.asin),
    )
    score = calculate_store_score(products, issues)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    output_path.write_text(render_html(store, issues, score), encoding="utf-8")

    print(f"Generated report: {output_path}")
    print(f"Store health score: {score}/100")
    print(f"Issues found: {len(issues)}")


if __name__ == "__main__":
    main()
