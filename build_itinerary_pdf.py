#!/usr/bin/env python3
"""Render greece_trip_itinerary.md to a styled PDF."""
import markdown
from weasyprint import HTML

with open("greece_trip_itinerary.md", encoding="utf-8") as f:
    md_text = f.read()

body = markdown.markdown(md_text, extensions=["tables", "extra", "sane_lists"])

css = """
@page { size: A4; margin: 2cm 1.8cm; }
body { font-family: 'DejaVu Sans', 'Helvetica', sans-serif; font-size: 10.5pt;
       line-height: 1.5; color: #1a2330; }
h1 { font-size: 22pt; color: #0a5c8a; border-bottom: 3px solid #1a9fd4;
     padding-bottom: 8px; margin-bottom: 4px; }
h2 { font-size: 15pt; color: #0a5c8a; margin-top: 22px;
     border-bottom: 1px solid #d4e4ef; padding-bottom: 4px; page-break-after: avoid; }
h3 { font-size: 12.5pt; color: #c2581b; margin-top: 16px; page-break-after: avoid; }
a { color: #1a7fb0; text-decoration: none; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9.5pt; }
th { background: #0a5c8a; color: #fff; text-align: left; padding: 6px 9px; }
td { border: 1px solid #d4e4ef; padding: 6px 9px; vertical-align: top; }
tr:nth-child(even) td { background: #f3f8fb; }
blockquote { border-left: 4px solid #1a9fd4; background: #f3f8fb; margin: 12px 0;
             padding: 8px 14px; color: #33424f; font-style: italic; }
code { background: #eef3f7; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }
hr { border: none; border-top: 1px solid #d4e4ef; margin: 18px 0; }
strong { color: #0a3d5c; }
ul, ol { margin: 6px 0; padding-left: 22px; }
li { margin: 3px 0; }
"""

html = f"<html><head><meta charset='utf-8'><style>{css}</style></head><body>{body}</body></html>"
HTML(string=html).write_pdf("greece_trip_itinerary.pdf")
print("Wrote greece_trip_itinerary.pdf")
