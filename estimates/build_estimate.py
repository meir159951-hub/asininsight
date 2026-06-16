#!/usr/bin/env python3
"""Ariel Outdoor Renovation - paver estimate (Mike Irvine, Murrieta)."""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageOps

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "assets", "ariel_logo.png")
OUT = os.path.join(HERE, "Mike_Irvine_Paver_Estimate.pdf")
GDIR = os.path.join(HERE, "assets", "gallery")
CACHE = os.path.join(GDIR, "cells")

# Before / After pairs: (title, before_image, after_image)
PAIRS = [
    ("Main Driveway (Street View)",
     os.path.join(GDIR, "before_1.jpg"), os.path.join(GDIR, "after_1.jpg")),
    ("Driveway at the Garage",
     os.path.join(GDIR, "before_2.jpg"), os.path.join(GDIR, "after_2.jpg")),
    ("Side Walkway & Iron Gate",
     os.path.join(GDIR, "before_3.jpg"), os.path.join(GDIR, "after_3.jpg")),
    ("Front Walkway & Rose Bed",
     os.path.join(GDIR, "before_4.jpg"), os.path.join(GDIR, "after_4.jpg")),
    ("Entry Landing",
     os.path.join(GDIR, "before_5.jpg"), os.path.join(GDIR, "after_5.jpg")),
    ("Side Garden Bed & Paver Edging",
     os.path.join(GDIR, "before_6.jpg"), os.path.join(GDIR, "after_6.jpg")),
]
TOTAL_PAGES = 5
REP = "Jacob Hayon, Project Manager"
REP_PHONE = "(323) 513-4865"
FOOTER = ("Ariel Outdoor Renovation  ·  License #1129259  ·  (818) 390-7639  ·  "
          "Jacob Hayon, Project Manager")

W, H = letter  # 612 x 792

# Brand palette (sampled from Ariel sample estimate)
NAVY   = (0.117, 0.176, 0.329)   # #1E2D54
GOLD   = (0.722, 0.541, 0.196)   # #B88A32
CREAM  = (0.961, 0.937, 0.886)   # #F5EFE2
INK    = (0.165, 0.176, 0.196)   # #2A2D32
MUTED  = (0.541, 0.565, 0.604)   # #8A909A
ROW    = (0.957, 0.969, 0.980)   # #F4F7FA
WHITE  = (1, 1, 1)
LINE   = (0.86, 0.88, 0.91)

MARGIN = 54

def set_fill(c, rgb): c.setFillColorRGB(*rgb)
def set_stroke(c, rgb): c.setStrokeColorRGB(*rgb)

def _tracked_width(c, s, font, size, tracking):
    return c.stringWidth(s, font, size) + tracking * max(len(s) - 1, 0)

def _draw_tracked(c, x, y, s, font, size, tracking):
    cur = x
    for ch in s:
        c.drawString(cur, y, ch)
        cur += c.stringWidth(ch, font, size) + tracking

def text(c, x, y, s, font="Helvetica", size=10, color=INK, align="left",
         tracking=0, leading=None):
    set_fill(c, color)
    c.setFont(font, size)
    if not tracking:
        if align == "center":
            c.drawCentredString(x, y, s)
        elif align == "right":
            c.drawRightString(x, y, s)
        else:
            c.drawString(x, y, s)
        return
    w = _tracked_width(c, s, font, size, tracking)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    _draw_tracked(c, x, y, s, font, size, tracking)

def wrap(c, s, font, size, max_w):
    words = s.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- PAGE 1
def cover(c):
    set_fill(c, NAVY)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # White rounded card
    cx = W / 2
    card_x, card_w = 71, W - 142
    card_top, card_bottom = 612, 250
    set_fill(c, WHITE)
    c.roundRect(card_x, card_bottom, card_w, card_top - card_bottom, 14,
                fill=1, stroke=0)

    # Logo
    try:
        img = ImageReader(LOGO)
        lw = 132
        c.drawImage(img, cx - lw / 2, card_top - 18 - lw, lw, lw,
                    mask='auto', preserveAspectRatio=True)
    except Exception:
        pass

    y = card_top - 178
    text(c, cx, y, "PROJECT ESTIMATE", "Helvetica-Bold", 9.5, GOLD,
         "center", tracking=3.2)
    y -= 30
    text(c, cx, y, "Driveway, Walkway & Backyard", "Helvetica-Bold", 25,
         NAVY, "center")
    y -= 28
    text(c, cx, y, "Paver Installation", "Helvetica-Bold", 25, NAVY, "center")
    y -= 22
    text(c, cx, y, "Premium Hardscape  ·  Gray Moss Charcoal / Charcoal Border",
         "Helvetica-Oblique", 12, GOLD, "center")
    y -= 18
    set_stroke(c, GOLD); c.setLineWidth(1.4)
    c.line(cx - 34, y, cx + 34, y)
    y -= 24
    text(c, cx, y, "PREPARED FOR", "Helvetica-Bold", 9, MUTED, "center",
         tracking=2.6)
    y -= 22
    text(c, cx, y, "Mike Irvine", "Helvetica-Bold", 16, INK, "center")
    y -= 18
    text(c, cx, y, "42784 Trail Blaze Pass", "Helvetica", 11, INK, "center")
    y -= 15
    text(c, cx, y, "Murrieta, California 92562", "Helvetica", 11, INK, "center")
    y -= 17
    text(c, cx, y, "(951) 677-6787", "Helvetica", 10.5, MUTED, "center")

    # Bottom band
    set_stroke(c, GOLD); c.setLineWidth(2)
    c.line(MARGIN, 168, W - MARGIN, 168)

    by = 150
    text(c, MARGIN, by, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold", 12,
         WHITE)
    by -= 15
    text(c, MARGIN, by,
         "Class B General Building Contractor  ·  Specializing in outdoor renovation",
         "Helvetica", 9, (0.78, 0.81, 0.87))
    by -= 22
    text(c, MARGIN, by,
         "3,215 SQ FT PAVERS    ·    DRIVEWAY, WALKWAY & BACKYARD    ·    GRAY MOSS CHARCOAL / CHARCOAL BORDER",
         "Helvetica-Bold", 8.5, GOLD, tracking=0.6)

    # three meta columns
    cols = [(MARGIN, "DATE", "June 16, 2026"),
            (250, "ESTIMATE NO.", "AOR-061626-S001"),
            (446, "VALID FOR", "30 Days")]
    ly = by - 26
    for x, label, val in cols:
        text(c, x, ly, label, "Helvetica-Bold", 8, GOLD, tracking=1.5)
        text(c, x, ly - 15, val, "Helvetica", 11, WHITE)

    # footer
    text(c, MARGIN, 40,
         "License #1129259   ·   (818) 390-7639   ·   arieloutdoorrenovation.com",
         "Helvetica", 8.5, (0.72, 0.75, 0.82))
    text(c, W - MARGIN, 40, "16350 Ventura Blvd. D149, Encino, CA 91436",
         "Helvetica", 8.5, (0.72, 0.75, 0.82), "right")

# ---------------------------------------------------------------- PAGE 2 (SCOPE)
def page_chrome(c, eyebrow, title):
    """Shared interior-page header + top bars. Returns bw."""
    set_fill(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    set_fill(c, NAVY); c.rect(0, H - 10, W, 10, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(0, H - 13, W, 3, fill=1, stroke=0)
    text(c, MARGIN, H - 38, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold", 10,
         NAVY)
    text(c, W - MARGIN, H - 38, "Mike Irvine  ·  Project Estimate",
         "Helvetica", 10, MUTED, "right")
    text(c, MARGIN, H - 66, eyebrow, "Helvetica-Bold", 9, GOLD, tracking=2)
    text(c, MARGIN, H - 90, title, "Helvetica-Bold", 23, NAVY)
    set_stroke(c, GOLD); c.setLineWidth(2.2)
    c.line(MARGIN, H - 100, MARGIN + 56, H - 100)
    return W - 2 * MARGIN

def page_footer(c, page_no):
    set_stroke(c, LINE); c.setLineWidth(0.8)
    c.line(MARGIN, 44, W - MARGIN, 44)
    text(c, MARGIN, 32, FOOTER, "Helvetica", 8, MUTED)
    text(c, W - MARGIN, 32, f"Page {page_no} of {TOTAL_PAGES}", "Helvetica", 8,
         MUTED, "right")

def scope_page(c):
    bw = page_chrome(c, "01  ·  SCOPE OF WORK", "How We Build It")
    intro = ("Every job is built start to finish by our own crews. Here is how your "
             "pavers go in, step by step.")
    iy = H - 116
    for ln in wrap(c, intro, "Helvetica", 9.5, bw):
        text(c, MARGIN, iy, ln, "Helvetica", 9.5, INK); iy -= 13

    steps = [
        "Demolition and removal of the existing surface.",
        "Apply the gravel base mix over the soil.",
        "Grade level and compact the base.",
        "Apply the bedding sand and compact.",
        "Install the pavers across all 3,215 sq ft.",
        "Cut the perimeter frame and set the special Charcoal border stones in the contrasting color.",
        "Apply polymeric joint sand.",
        "Compact the polymeric sand into the joints.",
        "Clean all the pavers. The job is complete.",
    ]
    txt_x = MARGIN + 34
    txt_w = W - MARGIN - txt_x
    y = iy - 18
    for i, step in enumerate(steps, 1):
        lines = wrap(c, step, "Helvetica", 10, txt_w)
        cy = y - 9
        set_fill(c, GOLD)
        c.circle(MARGIN + 10, cy, 9.5, fill=1, stroke=0)
        text(c, MARGIN + 10, cy - 3.4, str(i), "Helvetica-Bold", 9.5, WHITE,
             "center")
        ty = cy - 3.4 + (len(lines) - 1) * 6
        for ln in lines:
            text(c, txt_x, ty, ln, "Helvetica", 10, INK); ty -= 12
        y -= max(len(lines) * 12, 18) + 19

    # About Ariel (single clean box)
    body = ("Ariel Outdoor Renovation holds a California Class B General Building license, "
            "but we focus only on outdoor work. That is what makes what we do every day "
            "different. The crews we build with already bring over 20 years of real "
            "experience in paver installation.")
    blines = wrap(c, body, "Helvetica", 9.8, bw - 32)
    box_h = 30 + len(blines) * 13
    box_top = y - 8
    set_fill(c, CREAM)
    c.roundRect(MARGIN, box_top - box_h, bw, box_h, 7, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(MARGIN, box_top - box_h, 4, box_h, fill=1, stroke=0)
    text(c, MARGIN + 18, box_top - 18, "ABOUT ARIEL", "Helvetica-Bold", 9, GOLD,
         tracking=1.5)
    by = box_top - 34
    for ln in blines:
        text(c, MARGIN + 18, by, ln, "Helvetica", 9.8, INK); by -= 13

    page_footer(c, 2)

# ---------------------------------------------------------------- PAGE 3 (INVESTMENT)
def interior(c):
    set_fill(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    # top bars
    set_fill(c, NAVY); c.rect(0, H - 10, W, 10, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(0, H - 13, W, 3, fill=1, stroke=0)

    # header row
    text(c, MARGIN, H - 38, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold",
         10, NAVY)
    text(c, W - MARGIN, H - 38, "Mike Irvine  ·  Project Estimate",
         "Helvetica", 10, MUTED, "right")

    # title
    text(c, MARGIN, H - 66, "02  ·  OVERVIEW & INVESTMENT",
         "Helvetica-Bold", 9, GOLD, tracking=2)
    text(c, MARGIN, H - 90, "Project Overview", "Helvetica-Bold", 23, NAVY)
    set_stroke(c, GOLD); c.setLineWidth(2.2)
    c.line(MARGIN, H - 100, MARGIN + 56, H - 100)

    # intro cream box
    bx, bw = MARGIN, W - 2 * MARGIN
    btop, bh = H - 116, 56
    set_fill(c, CREAM); c.roundRect(bx, btop - bh, bw, bh, 6, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(bx, btop - bh, 3.5, bh, fill=1, stroke=0)
    text(c, bx + 16, btop - 18, "Hi Mike,", "Helvetica-Bold", 11, NAVY)
    intro = ("Thank you for the opportunity to put this together. Below is the full scope, "
             "materials, and pricing for your paver installation. The price covers labor, "
             "materials, equipment, and on-site management for everything shown.")
    iy = btop - 32
    for ln in wrap(c, intro, "Helvetica", 9.3, bw - 30):
        text(c, bx + 16, iy, ln, "Helvetica", 9.3, INK); iy -= 12

    # stat cards
    sy_top = btop - bh - 14
    sh = 52
    gap = 12
    cw = (bw - 2 * gap) / 3
    cards = [(CREAM, NAVY, "3,215", "SQ FT  ·  Pavers"),
             (CREAM, NAVY, "3 Areas", "Driveway · Walkway · Yard"),
             (NAVY, WHITE, "$60,000", "Total Investment")]
    for i, (bg, fg, big, small) in enumerate(cards):
        x = bx + i * (cw + gap)
        set_fill(c, bg); c.roundRect(x, sy_top - sh, cw, sh, 6, fill=1, stroke=0)
        sub = GOLD if bg == NAVY else GOLD
        text(c, x + cw / 2, sy_top - 24, big, "Helvetica-Bold", 18, fg, "center")
        text(c, x + cw / 2, sy_top - 40, small, "Helvetica-Bold", 7.6, sub,
             "center", tracking=0.4)

    # two columns: what's included + materials
    col_top = sy_top - sh - 22
    text(c, MARGIN, col_top, "WHAT'S INCLUDED",
         "Helvetica-Bold", 9, GOLD, tracking=1.4)
    text(c, MARGIN + bw / 2 + 6, col_top, "MATERIALS & SELECTIONS",
         "Helvetica-Bold", 9, GOLD, tracking=1.4)
    set_stroke(c, LINE); c.setLineWidth(0.8)
    c.line(MARGIN, col_top - 6, MARGIN + bw / 2 - 10, col_top - 6)
    c.line(MARGIN + bw / 2 + 6, col_top - 6, W - MARGIN, col_top - 6)

    scope = [
        "All labor, materials, and equipment for the full install.",
        "Demolition and haul-off of the existing surfaces.",
        "3,215 sq ft of pavers across the driveway, walkway, and backyard.",
        "Cement-set Charcoal border around every paved area.",
        "Full base prep, polymeric sand, and final cleaning.",
        "On-site project management from start to walkthrough.",
    ]
    ly = col_top - 22
    lw = bw / 2 - 16
    for item in scope:
        set_fill(c, GOLD); c.circle(MARGIN + 3, ly + 3, 1.6, fill=1, stroke=0)
        lines = wrap(c, item, "Helvetica", 8.7, lw - 12)
        for j, ln in enumerate(lines):
            text(c, MARGIN + 12, ly, ln, "Helvetica", 8.7, INK)
            ly -= 11
        ly -= 4

    mx = MARGIN + bw / 2 + 6
    mats = [
        ("Pavers", "Premium interlocking concrete pavers, Gray Moss Charcoal blend. Supplied & installed by Ariel."),
        ("Border", "Solid Charcoal soldier-course banding framing all paved areas."),
        ("Base & Edging", "Compacted, free-draining aggregate base with concrete / paver edge restraints."),
        ("Coverage", "3,215 sq ft total across the front entrance, walkway, and backyard."),
    ]
    my = col_top - 22
    mw = bw / 2 - 12
    for title_, body in mats:
        text(c, mx, my, title_, "Helvetica-Bold", 9.2, NAVY); my -= 12
        for ln in wrap(c, body, "Helvetica", 8.6, mw):
            text(c, mx, my, ln, "Helvetica", 8.6, (0.34, 0.36, 0.40)); my -= 10
        my -= 6

    # Investment band
    inv_top = min(ly, my) - 10
    inv_h = 40
    set_fill(c, NAVY); c.roundRect(MARGIN, inv_top - inv_h, bw, inv_h, 7,
                                   fill=1, stroke=0)
    text(c, MARGIN + 18, inv_top - 16, "TOTAL PROJECT INVESTMENT",
         "Helvetica-Bold", 8.5, GOLD, tracking=1.5)
    text(c, MARGIN + 18, inv_top - 31,
         "Labor, materials, equipment & on-site management included.",
         "Helvetica", 8.5, (0.80, 0.83, 0.89))
    text(c, W - MARGIN - 16, inv_top - 26, "$60,000", "Helvetica-Bold", 24,
         WHITE, "right")

    # Payment schedule
    ps_top = inv_top - inv_h - 18
    text(c, MARGIN, ps_top, "PAYMENT SCHEDULE  ·  PER CALIFORNIA CSLB RULES",
         "Helvetica-Bold", 9, GOLD, tracking=1.2)
    text(c, MARGIN, ps_top - 12,
         "Down payment limited to $1,000 by law. Progress payments tied to on-site milestones.",
         "Helvetica", 8, MUTED)

    rows = [
        ("1", "Contract signing (down payment, CA cap $1,000)", "$1,000", "1.7%"),
        ("2", "Upon material delivery", "$29,000", "48.3%"),
        ("3", "Upon demo & excavation", "$17,500", "29.2%"),
        ("4", "Upon base completion", "$11,500", "19.1%"),
        ("5", "Completion & final walkthrough", "$1,000", "1.7%"),
    ]
    tbl_top = ps_top - 22
    rh = 16
    cols_x = [MARGIN + 8, MARGIN + 34, W - MARGIN - 110, W - MARGIN - 14]
    # header
    set_fill(c, NAVY)
    c.rect(MARGIN, tbl_top - rh, bw, rh, fill=1, stroke=0)
    text(c, cols_x[0], tbl_top - 11, "#", "Helvetica-Bold", 7.5, WHITE)
    text(c, cols_x[1], tbl_top - 11, "MILESTONE", "Helvetica-Bold", 7.5, WHITE,
         tracking=0.6)
    text(c, cols_x[2], tbl_top - 11, "AMOUNT", "Helvetica-Bold", 7.5, WHITE,
         "right", tracking=0.6)
    text(c, cols_x[3], tbl_top - 11, "%", "Helvetica-Bold", 7.5, WHITE, "right")
    ry = tbl_top - rh
    for i, (n, ms, amt, pct) in enumerate(rows):
        if i % 2 == 1:
            set_fill(c, ROW); c.rect(MARGIN, ry - rh, bw, rh, fill=1, stroke=0)
        text(c, cols_x[0], ry - 11, n, "Helvetica-Bold", 8.5, GOLD)
        text(c, cols_x[1], ry - 11, ms, "Helvetica", 8.5, INK)
        text(c, cols_x[2], ry - 11, amt, "Helvetica-Bold", 8.5, INK, "right")
        text(c, cols_x[3], ry - 11, pct, "Helvetica", 8.5, MUTED, "right")
        ry -= rh
    # total row
    set_fill(c, CREAM); c.rect(MARGIN, ry - rh, bw, rh, fill=1, stroke=0)
    text(c, cols_x[1], ry - 11, "TOTAL", "Helvetica-Bold", 8.5, NAVY)
    text(c, cols_x[2], ry - 11, "$60,000", "Helvetica-Bold", 8.5, NAVY, "right")
    text(c, cols_x[3], ry - 11, "100%", "Helvetica-Bold", 8.5, NAVY, "right")
    ry -= rh

    # not included + signature
    foot_top = ry - 16
    text(c, MARGIN, foot_top, "NOT INCLUDED", "Helvetica-Bold", 8, GOLD,
         tracking=1.2)
    ni = ("Permits & HOA fees  ·  drainage / utility relocation  ·  "
          "outdoor kitchen, BBQ & gas lines  ·  furniture  ·  any work outside this scope.")
    niy = foot_top - 12
    for ln in wrap(c, ni, "Helvetica", 8.3, bw):
        text(c, MARGIN, niy, ln, "Helvetica", 8.3, (0.34, 0.36, 0.40)); niy -= 10

    # signature lines
    sigy = niy - 16
    set_stroke(c, INK); c.setLineWidth(0.8)
    c.line(MARGIN, sigy, MARGIN + 210, sigy)
    c.line(W - MARGIN - 150, sigy, W - MARGIN, sigy)
    text(c, MARGIN, sigy - 11, "Accepted by (client signature)", "Helvetica",
         8, MUTED)
    text(c, W - MARGIN - 150, sigy - 11, "Date", "Helvetica", 8, MUTED)

    # questions / contact callout
    qy = sigy - 28
    qh = 22
    set_fill(c, CREAM); c.roundRect(MARGIN, qy - qh, bw, qh, 6, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(MARGIN, qy - qh, 3.5, qh, fill=1, stroke=0)
    text(c, MARGIN + 14, qy - 14, "Questions?", "Helvetica-Bold", 9, NAVY)
    text(c, MARGIN + 78, qy - 14,
         f"Call {REP} directly at {REP_PHONE} anytime.",
         "Helvetica", 9, INK)

    # closing note
    note = ("This is an estimate, not a contract. Pricing valid 30 days from the cover date. "
            "A formal California home-improvement contract supersedes this document upon signing.")
    ny = qy - qh - 12
    for ln in wrap(c, note, "Helvetica-Oblique", 7.8, bw):
        text(c, MARGIN, ny, ln, "Helvetica-Oblique", 7.8, MUTED); ny -= 10

    # footer
    set_stroke(c, LINE); c.setLineWidth(0.8)
    c.line(MARGIN, 44, W - MARGIN, 44)
    text(c, MARGIN, 32, FOOTER, "Helvetica", 8, MUTED)
    text(c, W - MARGIN, 32, f"Page 3 of {TOTAL_PAGES}", "Helvetica", 8, MUTED,
         "right")

# ---------------------------------------------------------------- GALLERY
def cover_crop(path, cell_w_pt, cell_h_pt):
    """Return a print-res image cropped (cover) to the cell aspect ratio."""
    os.makedirs(CACHE, exist_ok=True)
    px_w, px_h = int(cell_w_pt * 2.6), int(cell_h_pt * 2.6)  # ~190 dpi
    out = os.path.join(CACHE, os.path.basename(path).replace(".jpg",
          f"_{px_w}x{px_h}.jpg"))
    if not os.path.exists(out) and os.path.exists(path):
        im = Image.open(path).convert("RGB")
        im = ImageOps.fit(im, (px_w, px_h), Image.LANCZOS, centering=(0.5, 0.45))
        im.save(out, quality=88)
    return out

def photo_cell(c, path, x, y, w, h):
    out = cover_crop(path, w, h)
    set_fill(c, (0.93, 0.94, 0.95))
    c.roundRect(x, y, w, h, 5, fill=1, stroke=0)
    if out and os.path.exists(out):
        c.saveState()
        p = c.beginPath(); p.roundRect(x, y, w, h, 5)
        c.clipPath(p, stroke=0, fill=0)
        c.drawImage(ImageReader(out), x, y, w, h, mask='auto')
        c.restoreState()
    set_stroke(c, LINE); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 5, fill=0, stroke=1)

def gallery_page(c, pairs, page_no, intro=None):
    set_fill(c, WHITE); c.rect(0, 0, W, H, fill=1, stroke=0)
    set_fill(c, NAVY); c.rect(0, H - 10, W, 10, fill=1, stroke=0)
    set_fill(c, GOLD); c.rect(0, H - 13, W, 3, fill=1, stroke=0)

    text(c, MARGIN, H - 38, "ARIEL OUTDOOR RENOVATION", "Helvetica-Bold", 10,
         NAVY)
    text(c, W - MARGIN, H - 38, "Mike Irvine  ·  Project Estimate",
         "Helvetica", 10, MUTED, "right")

    sec = "03" if page_no == 4 else "04"
    text(c, MARGIN, H - 66, f"{sec}  ·  OUR WORK", "Helvetica-Bold", 9, GOLD,
         tracking=2)
    title = "Before & After" if page_no == 4 else "Before & After  (continued)"
    text(c, MARGIN, H - 90, title, "Helvetica-Bold", 23, NAVY)
    set_stroke(c, GOLD); c.setLineWidth(2.2)
    c.line(MARGIN, H - 100, MARGIN + 56, H - 100)

    bw = W - 2 * MARGIN
    if intro:
        iy = H - 116
        for ln in wrap(c, intro, "Helvetica", 9.3, bw):
            text(c, MARGIN, iy, ln, "Helvetica", 9.3, INK); iy -= 12
        top = iy - 8
    else:
        top = H - 120

    cell_gap = 14
    cw = (bw - cell_gap) / 2
    ch = 172
    row_gap = 20
    y = top
    for title_, before, after in pairs:
        # pair title + labels
        text(c, MARGIN, y, title_, "Helvetica-Bold", 10, NAVY)
        text(c, MARGIN + cw, y, "BEFORE", "Helvetica-Bold", 7.5, MUTED,
             "right", tracking=1)
        text(c, W - MARGIN, y, "AFTER", "Helvetica-Bold", 7.5, GOLD, "right",
             tracking=1)
        cy = y - 8 - ch
        photo_cell(c, before, MARGIN, cy, cw, ch)
        photo_cell(c, after, MARGIN + cw + cell_gap, cy, cw, ch)
        y = cy - row_gap

    set_stroke(c, LINE); c.setLineWidth(0.8)
    c.line(MARGIN, 44, W - MARGIN, 44)
    text(c, MARGIN, 32, FOOTER, "Helvetica", 8, MUTED)
    text(c, W - MARGIN, 32, f"Page {page_no} of {TOTAL_PAGES}", "Helvetica", 8,
         MUTED, "right")

def main():
    c = canvas.Canvas(OUT, pagesize=letter)
    c.setTitle("Mike Irvine - Paver Estimate - Ariel Outdoor Renovation")
    cover(c)
    c.showPage()
    scope_page(c)
    c.showPage()
    interior(c)
    c.showPage()
    intro = ("Six recent projects from our own crews, each shown before and after "
             "from the same angle. This is the craftsmanship and finish you can "
             "expect on your driveway, walkway, and backyard.")
    gallery_page(c, PAIRS[:3], 4, intro=intro)
    c.showPage()
    gallery_page(c, PAIRS[3:], 5)
    c.showPage()
    c.save()
    print("wrote", OUT)

if __name__ == "__main__":
    main()
