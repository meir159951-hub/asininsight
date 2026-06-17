#!/usr/bin/env python3
"""Ariel Outdoor Renovation - Front Yard Renovation estimate (Brian Stampley, Temecula)."""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "assets", "ariel_logo.png")
GDIR = os.path.join(HERE, "assets", "gallery")
CACHE = os.path.join(GDIR, "cells")
OUT = os.path.join(HERE, "Brian_Stampley_FrontYard_Estimate.pdf")

W, H = letter
NAVY  = (0.117, 0.176, 0.329)
GOLD  = (0.722, 0.541, 0.196)
CREAM = (0.961, 0.937, 0.886)
INK   = (0.165, 0.176, 0.196)
MUTED = (0.541, 0.565, 0.604)
ROW   = (0.957, 0.969, 0.980)
WHITE = (1, 1, 1)
LINE  = (0.86, 0.88, 0.91)
MARGIN = 54

CLIENT = "Brian Stampley"
HEADER_R = "Brian Stampley  ·  Project Estimate"
FOOTER = ("Ariel Outdoor Renovation  ·  License #1129259  ·  (818) 390-7639  ·  "
          "Jacob Hayon, Project Manager")
REP = "Jacob Hayon, Project Manager"
REP_PHONE = "(323) 513-4865"
TOTAL_PAGES = 2  # cover + scope (pricing & gallery added once numbers/photos arrive)


def sf(c, rgb): c.setFillColorRGB(*rgb)
def ss(c, rgb): c.setStrokeColorRGB(*rgb)

def _tw(c, s, f, sz, tr): return c.stringWidth(s, f, sz) + tr * max(len(s) - 1, 0)

def text(c, x, y, s, font="Helvetica", size=10, color=INK, align="left", tracking=0):
    sf(c, color); c.setFont(font, size)
    if not tracking:
        if align == "center": c.drawCentredString(x, y, s)
        elif align == "right": c.drawRightString(x, y, s)
        else: c.drawString(x, y, s)
        return
    w = _tw(c, s, font, size, tracking)
    if align == "center": x -= w / 2
    elif align == "right": x -= w
    cur = x
    for ch in s:
        c.drawString(cur, y, ch); cur += c.stringWidth(ch, font, size) + tracking

def wrap(c, s, font, size, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= max_w: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def chrome(c, eyebrow, title):
    sf(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    sf(c, NAVY); c.rect(0, H - 10, W, 10, fill=1, stroke=0)
    sf(c, GOLD); c.rect(0, H - 13, W, 3, fill=1, stroke=0)
    text(c, MARGIN, H - 38, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold", 10, NAVY)
    text(c, W - MARGIN, H - 38, HEADER_R, "Helvetica", 10, MUTED, "right")
    text(c, MARGIN, H - 66, eyebrow, "Helvetica-Bold", 9, GOLD, tracking=2)
    text(c, MARGIN, H - 90, title, "Helvetica-Bold", 23, NAVY)
    ss(c, GOLD); c.setLineWidth(2.2); c.line(MARGIN, H - 100, MARGIN + 56, H - 100)
    return W - 2 * MARGIN

def footer(c, page_no):
    ss(c, LINE); c.setLineWidth(0.8); c.line(MARGIN, 44, W - MARGIN, 44)
    text(c, MARGIN, 32, FOOTER, "Helvetica", 8, MUTED)
    text(c, W - MARGIN, 32, f"Page {page_no} of {TOTAL_PAGES}", "Helvetica", 8, MUTED, "right")


def cover(c):
    sf(c, NAVY); c.rect(0, 0, W, H, fill=1, stroke=0)
    cx = W / 2
    card_x, card_w, card_top, card_bot = 71, W - 142, 612, 250
    sf(c, WHITE); c.roundRect(card_x, card_bot, card_w, card_top - card_bot, 14, fill=1, stroke=0)
    try:
        c.drawImage(ImageReader(LOGO), cx - 66, card_top - 18 - 132, 132, 132,
                    mask='auto', preserveAspectRatio=True)
    except Exception:
        pass
    y = card_top - 178
    text(c, cx, y, "PROJECT ESTIMATE", "Helvetica-Bold", 9.5, GOLD, "center", tracking=3.2)
    y -= 30
    text(c, cx, y, "Front Yard Renovation", "Helvetica-Bold", 26, NAVY, "center")
    y -= 22
    text(c, cx, y, "Concrete Pads, Turf, Steps, Block Wall & Lighting",
         "Helvetica-Oblique", 11.5, GOLD, "center")
    y -= 18
    ss(c, GOLD); c.setLineWidth(1.4); c.line(cx - 34, y, cx + 34, y)
    y -= 24
    text(c, cx, y, "PREPARED FOR", "Helvetica-Bold", 9, MUTED, "center", tracking=2.6)
    y -= 22
    text(c, cx, y, "Brian Stampley", "Helvetica-Bold", 16, INK, "center")
    y -= 18
    text(c, cx, y, "40206 Holden Circle", "Helvetica", 11, INK, "center")
    y -= 15
    text(c, cx, y, "Temecula, California 92591", "Helvetica", 11, INK, "center")
    y -= 17
    text(c, cx, y, "(805) 300-3413", "Helvetica", 10.5, MUTED, "center")

    ss(c, GOLD); c.setLineWidth(2); c.line(MARGIN, 168, W - MARGIN, 168)
    by = 150
    text(c, MARGIN, by, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold", 12, WHITE)
    by -= 15
    text(c, MARGIN, by, "Class B General Building Contractor  ·  Specializing in outdoor renovation",
         "Helvetica", 9, (0.78, 0.81, 0.87))
    by -= 22
    text(c, MARGIN, by,
         "940 SF CONCRETE PADS    ·    870 SF ARTIFICIAL TURF    ·    75 LF BLOCK WALL    ·    LED LIGHTING",
         "Helvetica-Bold", 8.5, GOLD, tracking=0.5)
    cols = [(MARGIN, "DATE", "June 17, 2026"), (250, "ESTIMATE NO.", "AOR-061726-S001"),
            (446, "VALID FOR", "30 Days")]
    ly = by - 26
    for x, label, val in cols:
        text(c, x, ly, label, "Helvetica-Bold", 8, GOLD, tracking=1.5)
        text(c, x, ly - 15, val, "Helvetica", 11, WHITE)
    text(c, MARGIN, 40, "License #1129259   ·   (818) 390-7639   ·   arieloutdoorrenovation.com",
         "Helvetica", 8.5, (0.72, 0.75, 0.82))
    text(c, W - MARGIN, 40, "16350 Ventura Blvd. D149, Encino, CA 91436",
         "Helvetica", 8.5, (0.72, 0.75, 0.82), "right")


SECTIONS = [
    ("Driveway: Concrete Pads with Turf Joints", "840 sf",
     "Concrete pads in a grid pattern, about 4 ft by 4 ft each, with 3 inch artificial turf "
     "strips between every pad. Includes demo of the existing surface, base prep and compaction, "
     "forming and pouring the pads, and setting the turf strips."),
    ("Side Area Near House", "100 sf",
     "Grade and level the area, then install concrete pads with turf strips in the same grid "
     "style as the driveway."),
    ("Main Staircase", "3 steps",
     "About 5 ft wide with a 7 ft run, finished with recessed warm white LED strip lighting "
     "under each step."),
    ("Second Staircase Area", "~16 ft",
     "Two to three steps, about 7 ft long, with under step LED step lighting."),
    ("Block Wall", "75 lf x 4 ft",
     "White smooth stucco finish for a modern look, with provisions for lights and planting "
     "pockets. Includes footing, block, grout, finish, and cap."),
    ("Artificial Turf Area", "870 sf",
     "Grade and level, plate compact the base, weed barrier, then install artificial turf with "
     "infill and edging."),
    ("Tree Removal", "3 palms",
     "Remove 3 palm trees (1 large and 2 medium), pull the stumps, and haul away all debris."),
    ("Landscape Lighting (Low Voltage)", "throughout",
     "Under step LED strips on both staircases, path lights, and wall lights, with transformer, "
     "wiring, and full hookup."),
    ("Planting Prep", "included",
     "Prepare planting pockets and areas along the block wall and walkways."),
    ("Demo & Disposal", "included",
     "Demo of all existing surfaces and haul away of all debris."),
]


def scope_page(c):
    bw = chrome(c, "01  ·  SCOPE OF WORK", "What We're Building")
    intro = ("Your full front yard renovation, built start to finish by our own crews. "
             "Here is everything included in the project.")
    iy = H - 116
    for ln in wrap(c, intro, "Helvetica", 9.5, bw):
        text(c, MARGIN, iy, ln, "Helvetica", 9.5, INK); iy -= 13

    txt_x = MARGIN + 30
    qty_x = W - MARGIN
    desc_w = W - MARGIN - txt_x
    y = iy - 14
    for i, (title, qty, desc) in enumerate(SECTIONS, 1):
        dlines = wrap(c, desc, "Helvetica", 8.6, desc_w)
        cy = y - 8
        sf(c, GOLD); c.circle(MARGIN + 9, cy, 9, fill=1, stroke=0)
        text(c, MARGIN + 9, cy - 3.3, str(i), "Helvetica-Bold", 9, WHITE, "center")
        text(c, txt_x, cy - 3.3, title, "Helvetica-Bold", 9.8, NAVY)
        text(c, qty_x, cy - 3.3, qty, "Helvetica-Bold", 8.5, GOLD, "right", tracking=0.5)
        dy = cy - 16
        for ln in dlines:
            text(c, txt_x, dy, ln, "Helvetica", 8.6, (0.32, 0.34, 0.38)); dy -= 10.5
        y = dy - 8
    footer(c, 2)


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("Brian Stampley - Front Yard Renovation - Ariel Outdoor Renovation")
    cover(c); c.showPage()
    scope_page(c); c.showPage()
    c.save()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
