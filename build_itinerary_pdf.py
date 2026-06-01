#!/usr/bin/env python3
"""Render greece_trip_itinerary.md to a polished, cover-paged PDF."""
import markdown
from weasyprint import HTML

with open("greece_trip_itinerary.md", encoding="utf-8") as f:
    md_text = f.read()

# Drop the H1 from the body (it lives on the cover) — first line.
lines = md_text.splitlines()
body_md = "\n".join(lines[1:]).lstrip("\n")
body = markdown.markdown(body_md, extensions=["tables", "extra", "sane_lists"])

cover = """
<div class="cover">
  <div class="cover-kicker">SUMMER TRIP &middot; 10 DAYS</div>
  <div class="cover-title">GREECE</div>
  <div class="cover-dates">July 1 &ndash; 10, 2026</div>
  <div class="cover-rule"></div>
  <div class="cover-route">Athens &nbsp;&bull;&nbsp; Thessaloniki &nbsp;&bull;&nbsp; Sithonia</div>
  <div class="cover-sub">A northern loop: capital &rarr; food city &rarr; the best beaches<br>
  you can reach without backtracking.</div>
</div>
"""

css = """
@page { size: A4; margin: 1.9cm 1.7cm; }
@page :first { margin: 0; }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 10pt;
       line-height: 1.5; color: #1c2733; }

/* Cover */
.cover { height: 100vh; width: 100%; box-sizing: border-box;
         background: linear-gradient(150deg,#0a5c8a 0%,#1496c8 55%,#27c0d4 100%);
         color: #fff; padding: 5.5cm 2.2cm; page-break-after: always; }
.cover-kicker { font-size: 11pt; letter-spacing: 6px; opacity: .85; }
.cover-title { font-size: 68pt; font-weight: bold; letter-spacing: 4px; margin: 6px 0 0; }
.cover-dates { font-size: 19pt; opacity: .95; margin-top: 2px; }
.cover-rule { width: 70px; height: 4px; background: #fff; opacity: .9; margin: 26px 0; }
.cover-route { font-size: 15pt; font-weight: bold; letter-spacing: 1px; }
.cover-sub { font-size: 11pt; opacity: .9; margin-top: 14px; line-height: 1.6; }

/* Headings */
h2 { font-size: 14.5pt; color: #fff; background: #0a5c8a; padding: 7px 12px;
     margin: 24px 0 10px; border-radius: 4px; page-break-after: avoid; letter-spacing: .3px; }
h3 { font-size: 11.5pt; color: #c2581b; margin: 14px 0 4px; page-break-after: avoid;
     border-bottom: 1px dotted #e0b89a; padding-bottom: 2px; }
a { color: #1a7fb0; text-decoration: none; }

/* Tables */
table { border-collapse: collapse; width: 100%; margin: 9px 0; font-size: 9pt;
        page-break-inside: avoid; }
th { background: #0a5c8a; color: #fff; text-align: left; padding: 6px 9px; }
td { border: 1px solid #d4e4ef; padding: 5px 9px; vertical-align: top; }
tr:nth-child(even) td { background: #f3f8fb; }

/* Callouts */
blockquote { border-left: 4px solid #27c0d4; background: #eef9fb; margin: 11px 0;
             padding: 8px 14px; color: #2a3a47; font-style: italic; border-radius: 0 4px 4px 0; }
code { background: #eef3f7; padding: 1px 4px; border-radius: 3px; font-size: 9pt; }
hr { border: none; border-top: 1px solid #e2e9ef; margin: 16px 0; }
strong { color: #0a3d5c; }
ul, ol { margin: 5px 0; padding-left: 20px; }
li { margin: 2.5px 0; }
p { margin: 6px 0; }
"""

html = (f"<html><head><meta charset='utf-8'><style>{css}</style></head>"
        f"<body>{cover}{body}</body></html>")
HTML(string=html).write_pdf("greece_trip_itinerary.pdf")
print("Wrote greece_trip_itinerary.pdf")
