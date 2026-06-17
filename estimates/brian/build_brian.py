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
TOTAL_PAGES = 4  # cover + scope + investment + before/after gallery

GD = os.path.join(HERE, "assets", "gallery")
PAIRS = [
    ("Driveway", os.path.join(GD, "before_1.jpg"), os.path.join(GD, "after_1.jpg")),
    ("House Frontage", os.path.join(GD, "before_2.jpg"), os.path.join(GD, "after_2.jpg")),
    ("Side Walkway", os.path.join(GD, "before_3.jpg"), os.path.join(GD, "after_3.jpg")),
    ("Main Entrance", os.path.join(GD, "before_4.jpg"), os.path.join(GD, "after_4.jpg")),
]


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


def investment_page(c):
    bw = chrome(c, "02  ·  INVESTMENT", "Investment & Timeline")
    bx = MARGIN
    btop, bh = H - 116, 44
    sf(c, CREAM); c.roundRect(bx, btop - bh, bw, bh, 6, fill=1, stroke=0)
    sf(c, GOLD); c.rect(bx, btop - bh, 3.5, bh, fill=1, stroke=0)
    text(c, bx + 16, btop - 17, "Hi Brian,", "Helvetica-Bold", 11, NAVY)
    intro = ("Below is the turnkey price for your full front yard renovation. It covers labor, "
             "materials, equipment, and on-site management for everything in the scope.")
    iy = btop - 31
    for ln in wrap(c, intro, "Helvetica", 9.3, bw - 30):
        text(c, bx + 16, iy, ln, "Helvetica", 9.3, INK); iy -= 12

    # stat cards
    sy = btop - bh - 14
    shh, gap = 52, 12
    cw = (bw - 2 * gap) / 3
    cards = [(CREAM, NAVY, "940 sf", "Concrete Pads"),
             (CREAM, NAVY, "870 sf", "Artificial Turf"),
             (NAVY, WHITE, "$73,800", "Total Investment")]
    for i, (bg, fg, big, small) in enumerate(cards):
        x = bx + i * (cw + gap)
        sf(c, bg); c.roundRect(x, sy - shh, cw, shh, 6, fill=1, stroke=0)
        text(c, x + cw / 2, sy - 24, big, "Helvetica-Bold", 18, fg, "center")
        text(c, x + cw / 2, sy - 40, small, "Helvetica-Bold", 7.6, GOLD, "center", tracking=0.4)

    # two columns
    col_top = sy - shh - 20
    text(c, MARGIN, col_top, "WHAT'S INCLUDED", "Helvetica-Bold", 9, GOLD, tracking=1.4)
    text(c, MARGIN + bw / 2 + 6, col_top, "MATERIALS & SELECTIONS", "Helvetica-Bold", 9, GOLD, tracking=1.4)
    ss(c, LINE); c.setLineWidth(0.8)
    c.line(MARGIN, col_top - 6, MARGIN + bw / 2 - 10, col_top - 6)
    c.line(MARGIN + bw / 2 + 6, col_top - 6, W - MARGIN, col_top - 6)

    incl = [
        "All labor, materials, and equipment.",
        "Demo and haul-off of the existing surfaces.",
        "Concrete pads with turf joints (driveway and side area).",
        "870 sf artificial turf area.",
        "Two LED-lit staircases.",
        "75 lf white block wall, footing to cap.",
        "Removal of 3 palm trees and stumps.",
        "Low voltage landscape lighting and planting prep.",
    ]
    ly = col_top - 22
    lw = bw / 2 - 16
    for item in incl:
        sf(c, GOLD); c.circle(MARGIN + 3, ly + 3, 1.6, fill=1, stroke=0)
        for ln in wrap(c, item, "Helvetica", 8.5, lw - 12):
            text(c, MARGIN + 12, ly, ln, "Helvetica", 8.5, INK); ly -= 10.5
        ly -= 3

    mx = MARGIN + bw / 2 + 6
    mw = bw / 2 - 12
    mats = [
        ("Concrete Pads", "Poured concrete pads in a 4 ft grid with 3 inch artificial turf joints."),
        ("Artificial Turf", "Premium landscape grade synthetic turf, supplied and installed."),
        ("Block Wall", "75 lf, 4 ft high, white smooth stucco finish, footing to cap."),
        ("Lighting", "Low voltage warm white LED: under step strips, path lights, and wall lights."),
    ]
    my = col_top - 22
    for title_, body in mats:
        text(c, mx, my, title_, "Helvetica-Bold", 9.2, NAVY); my -= 12
        for ln in wrap(c, body, "Helvetica", 8.5, mw):
            text(c, mx, my, ln, "Helvetica", 8.5, (0.34, 0.36, 0.40)); my -= 10
        my -= 5

    # investment band + timeline
    inv_top = min(ly, my) - 8
    inv_h = 40
    sf(c, NAVY); c.roundRect(MARGIN, inv_top - inv_h, bw, inv_h, 7, fill=1, stroke=0)
    text(c, MARGIN + 18, inv_top - 16, "TOTAL PROJECT INVESTMENT", "Helvetica-Bold", 8.5, GOLD, tracking=1.5)
    text(c, MARGIN + 18, inv_top - 31, "Turnkey: labor, materials, equipment & management included.",
         "Helvetica", 8.5, (0.80, 0.83, 0.89))
    text(c, W - MARGIN - 16, inv_top - 26, "$73,800", "Helvetica-Bold", 24, WHITE, "right")

    tl_top = inv_top - inv_h - 14
    sf(c, CREAM); c.roundRect(MARGIN, tl_top - 20, bw, 20, 5, fill=1, stroke=0)
    sf(c, GOLD); c.rect(MARGIN, tl_top - 20, 3.5, 20, fill=1, stroke=0)
    text(c, MARGIN + 14, tl_top - 13, "TIMELINE", "Helvetica-Bold", 8.5, NAVY, tracking=1)
    text(c, MARGIN + 74, tl_top - 13,
         "About 3 weeks from start to final walkthrough, weather permitting.",
         "Helvetica", 8.8, INK)

    # payment schedule
    ps_top = tl_top - 20 - 16
    text(c, MARGIN, ps_top, "PAYMENT SCHEDULE  ·  PER CALIFORNIA CSLB RULES", "Helvetica-Bold", 9, GOLD, tracking=1.2)
    text(c, MARGIN, ps_top - 12, "Down payment limited to $1,000 by law. Progress payments tied to on-site milestones.",
         "Helvetica", 8, MUTED)
    rows = [
        ("1", "Contract signing (down payment, CA cap $1,000)", "$1,000", "1.4%"),
        ("2", "Upon material delivery", "$35,000", "47.4%"),
        ("3", "Upon demo & excavation", "$20,000", "27.1%"),
        ("4", "Upon base & block wall completion", "$16,800", "22.7%"),
        ("5", "Completion & final walkthrough", "$1,000", "1.4%"),
    ]
    tbl_top = ps_top - 22
    rh = 15
    cols_x = [MARGIN + 8, MARGIN + 34, W - MARGIN - 110, W - MARGIN - 14]
    sf(c, NAVY); c.rect(MARGIN, tbl_top - rh, bw, rh, fill=1, stroke=0)
    text(c, cols_x[0], tbl_top - 10.5, "#", "Helvetica-Bold", 7.5, WHITE)
    text(c, cols_x[1], tbl_top - 10.5, "MILESTONE", "Helvetica-Bold", 7.5, WHITE, tracking=0.6)
    text(c, cols_x[2], tbl_top - 10.5, "AMOUNT", "Helvetica-Bold", 7.5, WHITE, "right", tracking=0.6)
    text(c, cols_x[3], tbl_top - 10.5, "%", "Helvetica-Bold", 7.5, WHITE, "right")
    ry = tbl_top - rh
    for i, (n, ms, amt, pct) in enumerate(rows):
        if i % 2 == 1:
            sf(c, ROW); c.rect(MARGIN, ry - rh, bw, rh, fill=1, stroke=0)
        text(c, cols_x[0], ry - 10.5, n, "Helvetica-Bold", 8.5, GOLD)
        text(c, cols_x[1], ry - 10.5, ms, "Helvetica", 8.5, INK)
        text(c, cols_x[2], ry - 10.5, amt, "Helvetica-Bold", 8.5, INK, "right")
        text(c, cols_x[3], ry - 10.5, pct, "Helvetica", 8.5, MUTED, "right")
        ry -= rh
    sf(c, CREAM); c.rect(MARGIN, ry - rh, bw, rh, fill=1, stroke=0)
    text(c, cols_x[1], ry - 10.5, "TOTAL", "Helvetica-Bold", 8.5, NAVY)
    text(c, cols_x[2], ry - 10.5, "$73,800", "Helvetica-Bold", 8.5, NAVY, "right")
    text(c, cols_x[3], ry - 10.5, "100%", "Helvetica-Bold", 8.5, NAVY, "right")
    ry -= rh

    # not included
    foot_top = ry - 14
    text(c, MARGIN, foot_top, "NOT INCLUDED", "Helvetica-Bold", 8, GOLD, tracking=1.2)
    ni = ("Permits beyond the block wall  ·  HOA fees  ·  drainage / utility relocation  ·  "
          "furniture & accessories  ·  any work outside this scope.")
    niy = foot_top - 11
    for ln in wrap(c, ni, "Helvetica", 8.3, bw):
        text(c, MARGIN, niy, ln, "Helvetica", 8.3, (0.34, 0.36, 0.40)); niy -= 10

    # questions callout
    qy = niy - 8
    qh = 22
    sf(c, CREAM); c.roundRect(MARGIN, qy - qh, bw, qh, 6, fill=1, stroke=0)
    sf(c, GOLD); c.rect(MARGIN, qy - qh, 3.5, qh, fill=1, stroke=0)
    text(c, MARGIN + 14, qy - 14, "Questions?", "Helvetica-Bold", 9, NAVY)
    text(c, MARGIN + 78, qy - 14, f"Call {REP} directly at {REP_PHONE} anytime.",
         "Helvetica", 9, INK)

    # signature
    sigy = qy - qh - 22
    ss(c, INK); c.setLineWidth(0.8)
    c.line(MARGIN, sigy, MARGIN + 210, sigy)
    c.line(W - MARGIN - 150, sigy, W - MARGIN, sigy)
    text(c, MARGIN, sigy - 11, "Accepted by (client signature)", "Helvetica", 8, MUTED)
    text(c, W - MARGIN - 150, sigy - 11, "Date", "Helvetica", 8, MUTED)

    note = ("This is an estimate, not a contract. Pricing valid 30 days from the cover date. "
            "A formal California home-improvement contract supersedes this document upon signing.")
    ny = sigy - 26
    for ln in wrap(c, note, "Helvetica-Oblique", 7.8, bw):
        text(c, MARGIN, ny, ln, "Helvetica-Oblique", 7.8, MUTED); ny -= 10

    footer(c, 3)


def cover_crop(path, cw_pt, ch_pt):
    os.makedirs(CACHE, exist_ok=True)
    pw, ph = int(cw_pt * 2.6), int(ch_pt * 2.6)
    out = os.path.join(CACHE, os.path.basename(path).replace(".jpg", f"_{pw}x{ph}.jpg"))
    if not os.path.exists(out) and os.path.exists(path):
        im = Image.open(path).convert("RGB")
        im = ImageOps.fit(im, (pw, ph), Image.LANCZOS, centering=(0.5, 0.5))
        im.save(out, quality=88)
    return out

def photo_cell(c, path, x, y, w, h):
    out = cover_crop(path, w, h)
    sf(c, (0.93, 0.94, 0.95)); c.roundRect(x, y, w, h, 5, fill=1, stroke=0)
    if out and os.path.exists(out):
        c.saveState()
        p = c.beginPath(); p.roundRect(x, y, w, h, 5)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(ImageReader(out), x, y, w, h, mask='auto')
        c.restoreState()
    ss(c, LINE); c.setLineWidth(0.6); c.roundRect(x, y, w, h, 5, fill=0, stroke=1)

def gallery_page(c):
    bw = chrome(c, "03  ·  THE VISION", "Before & After")
    intro = ("Here is your front yard today next to the proposed design for each area, so you "
             "can picture exactly what we are building. After images are design renderings of "
             "the finished result.")
    iy = H - 116
    for ln in wrap(c, intro, "Helvetica", 9.3, bw):
        text(c, MARGIN, iy, ln, "Helvetica", 9.3, INK); iy -= 12

    top = iy - 8
    cell_gap = 14
    cw = (bw - cell_gap) / 2
    n = len(PAIRS)
    avail = top - 52
    per_row = avail / n
    ch = per_row - 30
    y = top
    for title_, before, after in PAIRS:
        text(c, MARGIN, y, title_, "Helvetica-Bold", 10, NAVY)
        text(c, MARGIN + cw, y, "BEFORE", "Helvetica-Bold", 7.5, MUTED, "right", tracking=1)
        text(c, W - MARGIN, y, "AFTER", "Helvetica-Bold", 7.5, GOLD, "right", tracking=1)
        cy = y - 8 - ch
        photo_cell(c, before, MARGIN, cy, cw, ch)
        photo_cell(c, after, MARGIN + cw + cell_gap, cy, cw, ch)
        y = cy - (per_row - ch - 8)
    footer(c, 4)


def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("Brian Stampley - Front Yard Renovation - Ariel Outdoor Renovation")
    cover(c); c.showPage()
    scope_page(c); c.showPage()
    investment_page(c); c.showPage()
    gallery_page(c); c.showPage()
    c.save()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
