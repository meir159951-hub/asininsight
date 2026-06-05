#!/usr/bin/env python3
"""
Ariel Outdoor Renovation - Project Estimate PDF generator.
Faithful reproduction of the company template, data-driven so photos and
pricing drop in via the CONFIG block below.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ----------------------------------------------------------------------------
# BRAND
# ----------------------------------------------------------------------------
NAVY   = colors.HexColor("#1B2A5B")
NAVY_D = colors.HexColor("#16224A")
GOLD   = colors.HexColor("#B0894A")
CREAM  = colors.HexColor("#FAF6EE")
CREAM2 = colors.HexColor("#F6F1E6")
GREY   = colors.HexColor("#6B7280")
GREY_L = colors.HexColor("#9AA1AC")
INK    = colors.HexColor("#1F2733")
LINE   = colors.HexColor("#E3E6EB")

PAGE_W, PAGE_H = letter
M = 0.85 * inch                      # content side margin
HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "assets", "ariel_logo.png")

def ph(name):
    """Resolve a photo filename inside the photos/ folder (None passes through)."""
    return os.path.join(HERE, "photos", name) if name else None

# ----------------------------------------------------------------------------
# CONFIG  --  edit this block as real data arrives
# ----------------------------------------------------------------------------
COMPANY = {
    "name": "Ariel Outdoor Renovation",
    "tagline": "Class B General Building Contractor  ·  Specializing in outdoor renovation",
    "license": "License #1129259",
    "phone": "(818) 390-7639",
    "web": "arieloutdoorrenovation.com",
    "address": "16350 Ventura Blvd. D149, Encino, CA 91436",
}

CLIENT = {
    "name": "Maria Tarango",
    "addr1": "2699 Arches Court",
    "addr2": "Jurupa Valley, California 92509",
    "phone": "(909) 224-8808",
    "residence": "Tarango Residence",
}

DOC = {
    "project_title": "Backyard Renovation",
    "project_sub": "Pavers & Artificial Turf",
    "date": "June 5, 2026",
    "estimate_no": "AOR-060526-S001",
    "valid_for": "30 Days",
    "pm_name": "Jacob Hayon",
    "pm_phone": "(323) 513-4865",
}

# Square footage of the scope
MEASURE = [
    ("2,720", "SQ FT", "Pavers"),
    ("1,230", "SQ FT", "Artificial Turf"),
    ("3,950", "SQ FT", "Total Area"),
]

# Materials & selections
MATERIALS = [
    ("Pavers", "Angelus Pavilion / Paseo, color Sandstone Copper. Supplied &amp; installed by Ariel."),
    ("Artificial Turf", "Marathon synthetic grass, premium landscape grade. Supplied &amp; installed by Ariel."),
    ("Base &amp; Edging", "Compacted, draining aggregate base under both surfaces, with concrete / paver borders."),
]

# Photos: set "img" to a file path to drop a real photo in; leave None for a
# placeholder frame.  caption = bold lead + description.
FINISHED = {
    "intro": ("Hi Maria,",
              "Thank you for the opportunity to put together this estimate. Below is the "
              "finished aesthetic we walked through together, followed by the full scope, "
              "pricing, and timeline. Pricing covers labor, materials, equipment, and "
              "on-site management for everything shown."),
    "hero": ph("hero_lounge.jpg"),
    "grid": [
        ("Paver area (2,720 sq ft)", "Angelus pavers (Sandstone Copper) set across the yard with a clean, level finish.", None),
        ("Turf area (1,230 sq ft)", "Marathon synthetic grass over a compacted, draining base. Low maintenance, year-round green.", None),
    ],
}

SCOPE_ROWS = [
    ("01", "Site Clearing & Demo",
     "Remove existing grass, debris, and old surfacing across the work area. Haul off and dispose."),
    ("02", "Grading & Base Prep",
     "Cut, fill, and compact the sub-grade. Lay and compact a draining aggregate base to spec."),
    ("03", "Paver Installation",
     "Set 2,720 sq ft of Angelus pavers (Sandstone Copper) over bedding sand with proper slope for drainage; cut, seat, and compact."),
    ("04", "Artificial Turf",
     "Install 1,230 sq ft of Marathon synthetic grass over the prepared base; seam, stake, and infill for a natural look."),
    ("05", "Edging & Borders",
     "Install concrete or paver borders to lock the field in place and keep clean transitions."),
    ("06", "Palm Install & Gravel",
     "Install the client's palm trees and lay the decorative gravel. The gravel is supplied by Ariel; the palm trees are purchased by the client."),
    ("07", "Final Detailing",
     "Joint sand, power-wash, blow-off, and final walkthrough. Site left clean and punch-list closed."),
]

BEFORE_AFTER = {
    "intro": ("The yard is structurally sound but unfinished. Each area below shows how it looks "
              "today next to how it will look once the work is complete."),
    "pairs": [
        (("Main patio, today", "Open dirt along the house, AC unit exposed.", ph("before_4.jpg")),
         ("Main patio, finished", "Sandstone Copper pavers run clean to the house and pool.", ph("after_mainpatio.jpg"))),
        (("Pool & lawn, today", "Open dirt beside the new pool.", ph("before_2.jpg")),
         ("Pool & lawn, finished", "Marathon turf and palms running alongside the pool.", ph("after_poollawn.jpg"))),
        (("Pool & lawn, today", "Graded dirt around the pool.", ph("before_3.jpg")),
         ("Pool & lawn, finished", "Turf, palms, and lighting wrapping the pool at dusk.", ph("after_poolside.jpg"))),
        (("Side yard, today", "Bare ground along the fence line.", ph("before_1.jpg")),
         ("Side yard, finished", "A paver walkway with palms, gravel, and accent lighting.", ph("after_sideyard.jpg"))),
        (("Back patio, today", "Wide dirt area along the house.", ph("before_5.jpg")),
         ("Back patio, finished", "A full paver patio with the fire pit and crisp borders.", ph("after_backpatio.jpg"))),
        (("Side lawn, today", "Open dirt between the houses, ready for finish.", ph("before_7.jpg")),
         ("Side lawn, finished", "Paver patio with a turf strip and a lavender border.", ph("after_lawn.jpg"))),
    ],
    "note": ("How the base goes down",
             "We grade and compact the sub-grade, then lay and compact a draining aggregate base "
             "before any pavers or turf go in. A solid base is what keeps the finished surface flat "
             "and stops it settling over time."),
}

ANGLES = {
    "intro": "More angles. Each shows the area as it is today next to the same angle once finished.",
    "rows": [
        (("Side yard — today", "Bare ground along the fence.", ph("before_1.jpg")),
         ("Side yard — finished", "Pavers / turf with accent lighting.", None)),
        (("Pool side — today", "Open dirt beside the pool.", ph("before_2.jpg")),
         ("Pool side — finished", "Clean deck running to the coping.", None)),
        (("Back patio — today", "Wide dirt area by the fire pit.", ph("before_6.jpg")),
         ("Back patio — finished", "Paved patio, crisp borders.", None)),
    ],
}

PRICING = {
    "total": "$70,300",
    "total_note": "Full backyard: pavers + turf. Labor, materials, equipment and management included.",
    "schedule": [
        ("1", "Contract signing (down payment, CA cap $1,000)", "$1,000", "1.4%"),
        ("2", "Upon material", "$34,150", "48.6%"),
        ("3", "Upon demo", "$20,490", "29.1%"),
        ("4", "Upon base", "$13,660", "19.4%"),
        ("5", "Completion", "$1,000", "1.4%"),
    ],
    "timeline_title": "2 Weeks",
    "timeline_body": ("Roughly two weeks from start to final walkthrough for the full project "
                      "(worst case). Timing depends on weather and material lead times; a weekly "
                      "schedule is shared at contract signing."),
    # Alternative / phased scopes the client can choose instead of the full project
    "options": [
        ("Full backyard: pavers + turf", "Recommended · best price", "$70,300"),
        ("Artificial turf only (1,230 sq ft)", "Marathon synthetic grass", "$14,000"),
        ("Turf, smaller 600 sq ft area", "Partial turf option", "$8,000"),
    ],
    "not_included": [
        "Buying the palm trees (Ariel installs them)",
        "Permits &amp; HOA fees (if any)",
        "Drainage / utility relocation",
        "Outdoor kitchen, BBQ, gas lines",
        "Furniture &amp; accessories",
        "Work outside this scope",
    ],
}

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def ps(name, **kw):
    return ParagraphStyle(name, **kw)

def draw_para(c, text, style, x, y, w, h):
    p = Paragraph(text, style)
    f = Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0,
              bottomPadding=0, showBoundary=0)
    f.addFromList([p], c)

def _tracked(c, x, y, text, font, size, color, spacing):
    c.saveState()
    to = c.beginText(x, y)
    to.setFont(font, size)
    to.setFillColor(color)
    to.setCharSpace(spacing)
    to.textOut(text)
    c.drawText(to)
    c.restoreState()

def eyebrow(c, x, y, text, color=GOLD, size=8.5, spacing=1.6):
    _tracked(c, x, y, text, "Helvetica-Bold", size, color, spacing)

def _spaced(s):
    return s

def gold_rule(c, x, y, w=46, color=GOLD, lw=2):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)

def placeholder(c, x, y, w, h, label="PHOTO"):
    c.saveState()
    c.setFillColor(colors.HexColor("#EEF1F5"))
    c.setStrokeColor(colors.HexColor("#C7CDD6"))
    c.setLineWidth(1)
    c.setDash(4, 3)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
    c.setDash()
    c.setFillColor(GREY_L)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(x + w / 2, y + h / 2 + 4, label)
    c.setFont("Helvetica", 7)
    c.drawCentredString(x + w / 2, y + h / 2 - 7, "drop photo here")
    c.restoreState()

def photo(c, img, x, y, w, h, label="PHOTO"):
    if img and os.path.exists(img):
        try:
            ir = ImageReader(img)
            iw, ih = ir.getSize()
            scale = max(w / iw, h / ih)
            dw, dh = iw * scale, ih * scale
            c.saveState()
            p = c.beginPath()
            p.roundRect(x, y, w, h, 6)
            c.clipPath(p, stroke=0)
            c.drawImage(ir, x + (w - dw) / 2, y + (h - dh) / 2, dw, dh,
                        mask='auto')
            c.restoreState()
            c.setStrokeColor(LINE)
            c.setLineWidth(1)
            c.roundRect(x, y, w, h, 6, stroke=1, fill=0)
            return
        except Exception:
            pass
    placeholder(c, x, y, w, h, label)

def caption(c, x, y, lead, body, w):
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(x, y, lead)
    st = ps("cap", fontName="Helvetica", fontSize=8, leading=10.5, textColor=GREY)
    draw_para(c, body, st, x, y - 34, w, 32)

# ----------------------------------------------------------------------------
# page chrome
# ----------------------------------------------------------------------------
def content_header(c, section_no, section_label):
    # top navy bar + gold rule
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 10, PAGE_W, 10, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - 13, PAGE_W, 3, stroke=0, fill=1)
    # running header
    y = PAGE_H - 44
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M, y, COMPANY["name"].upper())
    c.setFillColor(GREY_L)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - M, y, f"{CLIENT['residence']}  ·  Project Estimate")
    # section eyebrow + title
    eyebrow(c, M, y - 30, f"{section_no} · {section_label}", GOLD, 8)
    return y - 30

def section_title(c, y, title):
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 23)
    c.drawString(M, y - 26, title)
    gold_rule(c, M, y - 38, 46)
    return y - 38

def content_footer(c, page_no, total=7):
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(M, 42, PAGE_W - M, 42)
    c.setFillColor(GREY_L)
    c.setFont("Helvetica", 7.5)
    c.drawString(M, 30, f"{COMPANY['name']}  ·  {COMPANY['license']}  ·  {COMPANY['phone']}")
    c.drawRightString(PAGE_W - M, 30, f"Page {page_no} of {total}")

def info_box(c, x, y, w, h, title, body, accent=GOLD, bg=CREAM, upper=True, title_size=8.5):
    c.setFillColor(bg)
    c.roundRect(x, y, w, h, 4, stroke=0, fill=1)
    c.setFillColor(accent)
    c.rect(x, y, 3.5, h, stroke=0, fill=1)
    tx = x + 16
    c.setFillColor(GOLD if upper else NAVY)
    c.setFont("Helvetica-Bold", title_size)
    c.drawString(tx, y + h - 18, title.upper() if upper else title)
    st = ps("ib", fontName="Helvetica", fontSize=8.5, leading=12, textColor=INK)
    draw_para(c, body, st, tx, y + 9, w - 30, h - 30)

# ----------------------------------------------------------------------------
# PAGE 1 - COVER
# ----------------------------------------------------------------------------
def page_cover(c):
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

    # white rounded card
    cw = PAGE_W - 2 * (0.95 * inch)
    cx = 0.95 * inch
    ch = 4.45 * inch
    cy = PAGE_H - 1.2 * inch - ch
    c.setFillColor(colors.white)
    c.roundRect(cx, cy, cw, ch, 10, stroke=0, fill=1)

    mid = PAGE_W / 2
    # logo
    lw = 1.25 * inch
    c.drawImage(ImageReader(LOGO), mid - lw / 2, cy + ch - 0.35 * inch - lw,
                lw, lw, mask='auto', preserveAspectRatio=True)
    yy = cy + ch - 0.35 * inch - lw - 16
    eyebrow_center(c, mid, yy, "PROJECT ESTIMATE", GOLD, 9)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(mid, yy - 34, DOC["project_title"])
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Oblique", 11)
    c.drawCentredString(mid, yy - 52, DOC["project_sub"])
    gold_rule(c, mid - 28, yy - 66, 56, GOLD, 1.4)

    eyebrow_center(c, mid, yy - 98, "PREPARED FOR", GREY_L, 8.5)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawCentredString(mid, yy - 120, CLIENT["name"])
    c.setFillColor(GREY)
    c.setFont("Helvetica", 10)
    c.drawCentredString(mid, yy - 138, CLIENT["addr1"])
    c.drawCentredString(mid, yy - 152, CLIENT["addr2"])
    c.setFillColor(GREY_L)
    c.setFont("Helvetica", 9.5)
    c.drawCentredString(mid, yy - 170, CLIENT["phone"])

    # gold divider band
    by = cy - 0.5 * inch
    c.setFillColor(GOLD)
    c.rect(0, by, PAGE_W, 2.5, stroke=0, fill=1)

    # lower company block
    lx = 0.95 * inch
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(lx, by - 0.55 * inch, COMPANY["name"].upper())
    c.setFillColor(colors.HexColor("#AEB6CC"))
    c.setFont("Helvetica", 9)
    c.drawString(lx, by - 0.55 * inch - 18, COMPANY["tagline"])

    # date / estimate / valid columns
    colY = by - 1.65 * inch
    cols = [("DATE", DOC["date"]), ("ESTIMATE NO.", DOC["estimate_no"]),
            ("VALID FOR", DOC["valid_for"])]
    colx = lx
    step = 2.3 * inch
    for i, (lab, val) in enumerate(cols):
        x = colx + i * step
        eyebrow(c, x, colY, lab, GOLD, 8, spacing=1.2)
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 10.5)
        c.drawString(x, colY - 18, val)

    # footer rule + line
    fy = 0.95 * inch
    c.setStrokeColor(colors.HexColor("#33406B"))
    c.setLineWidth(1)
    c.line(lx, fy + 14, PAGE_W - lx, fy + 14)
    c.setFillColor(colors.HexColor("#AEB6CC"))
    c.setFont("Helvetica", 7.5)
    c.drawString(lx, fy, f"{COMPANY['license']}  ·  {COMPANY['phone']}  ·  {COMPANY['web']}")
    c.drawRightString(PAGE_W - lx, fy, COMPANY["address"])
    c.showPage()

def eyebrow_center(c, mid, y, text, color, size, spacing=2.0):
    w = c.stringWidth(text, "Helvetica-Bold", size) + spacing * max(len(text) - 1, 0)
    _tracked(c, mid - w / 2, y, text, "Helvetica-Bold", size, color, spacing)

# ----------------------------------------------------------------------------
# PAGE 2 - FINISHED LOOK
# ----------------------------------------------------------------------------
def measure_strip(c, x, y, w, h=0.6 * inch):
    """Three-cell square-footage band."""
    n = len(MEASURE)
    gap = 12
    cellw = (w - gap * (n - 1)) / n
    for i, (val, unit, label) in enumerate(MEASURE):
        cx = x + i * (cellw + gap)
        highlight = (label.lower().startswith("total"))
        c.setFillColor(NAVY if highlight else CREAM)
        c.roundRect(cx, y, cellw, h, 5, stroke=0, fill=1)
        mid = cx + cellw / 2
        c.setFillColor(colors.white if highlight else NAVY)
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(mid, y + 24, val)
        # unit (gold) + label on one line below the number
        c.setFont("Helvetica-Bold", 7)
        ulab = "  ·  " + label
        uw = c.stringWidth(unit, "Helvetica-Bold", 7)
        lw = c.stringWidth(ulab, "Helvetica", 8)
        startx = mid - (uw + lw) / 2
        c.setFillColor(GOLD)
        c.drawString(startx, y + 9, unit)
        c.setFillColor(colors.HexColor("#C9CFE0") if highlight else GREY)
        c.setFont("Helvetica", 8)
        c.drawString(startx + uw, y + 9, ulab)

def page_finished(c):
    y = content_header(c, "01", "DESIGN DIRECTION")
    y = section_title(c, y, "Finished Look")
    cw = PAGE_W - 2 * M
    # intro box
    lead, body = FINISHED["intro"]
    gbh = 78
    info_box(c, M, y - 14 - gbh, cw, gbh, lead, body, GOLD, CREAM,
             upper=False, title_size=11)
    # square-footage strip
    sy = y - 14 - gbh - 14 - 0.6 * inch
    measure_strip(c, M, sy, cw)
    # hero image
    hy = sy - 14 - 1.75 * inch
    photo(c, FINISHED["hero"], M, hy, cw, 1.75 * inch, "FINISHED — HERO")
    # two captions under grid
    gy = hy - 16
    half = (cw - 18) / 2
    ph_h = 1.32 * inch
    py = gy - ph_h - 6
    for i, (lead2, body2, img2) in enumerate(FINISHED["grid"]):
        x = M + i * (half + 18)
        photo(c, img2, x, py, half, ph_h, "PHOTO")
        caption(c, x, py - 12, lead2, body2, half)
    content_footer(c, 2)
    c.showPage()

# ----------------------------------------------------------------------------
# PAGE 3 - WHAT'S INCLUDED
# ----------------------------------------------------------------------------
def page_scope(c):
    y = content_header(c, "02", "SCOPE OF WORK")
    y = section_title(c, y, "What's Included")
    cw = PAGE_W - 2 * M
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    c.drawString(M, y - 24, "Everything below is bundled into the price on page 6. "
                            "Labor, equipment, debris haul-off, and on-site management are included.")
    # table
    ty = y - 40
    rowh = 0.5 * inch
    c.setFillColor(NAVY)
    c.rect(M, ty - 16, cw, 16, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(M + 10, ty - 11, "#")
    c.drawString(M + 36, ty - 11, "PHASE")
    c.drawString(M + 2.1 * inch, ty - 11, "WORK INCLUDED")
    ry = ty - 16
    for i, (num, phase, desc) in enumerate(SCOPE_ROWS):
        ry -= rowh
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F7F8FA"))
            c.rect(M, ry, cw, rowh, stroke=0, fill=1)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(M + 8, ry + rowh - 20, num)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(M + 36, ry + rowh - 20, phase)
        st = ps("d", fontName="Helvetica", fontSize=8, leading=10, textColor=INK)
        draw_para(c, desc, st, M + 2.1 * inch, ry + 6, cw - 2.1 * inch - 12, rowh - 10)
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.rect(M, ry, cw, ty - 16 - ry, stroke=1, fill=0)

    # materials & selections
    ny = ry - 14
    mat_body = "<br/>".join(f"<b>{n}:</b> {d}" for n, d in MATERIALS)
    mbh = 70
    info_box(c, M, ny - mbh, cw, mbh, "Materials & Selections", mat_body, GOLD, CREAM2)
    # two boxes
    by = ny - mbh - 14
    half = (cw - 18) / 2
    bh = 1.35 * inch
    info_box(c, M, by - bh, half, bh, "How we do the job",
             "&bull; Compacted, draining aggregate base under everything.<br/>"
             "&bull; Proper slope so water runs off, never pools.<br/>"
             "&bull; Edges locked with borders so nothing shifts.<br/>"
             "&bull; Site cleaned and hauled off when we leave.", NAVY, CREAM)
    info_box(c, M + half + 18, by - bh, half, bh, "Licensed, insured, specialized",
             "&bull; CSLB License #1129259, Class B General Building.<br/>"
             "&bull; Outdoor renovation only: paving, fencing, hardscape.<br/>"
             "&bull; General liability and workers' comp on file.", NAVY, CREAM)
    content_footer(c, 3)
    c.showPage()

# ----------------------------------------------------------------------------
# PAGE 4 - BEFORE & AFTER
# ----------------------------------------------------------------------------
def page_before_after(c):
    y = content_header(c, "03", "SITE TODAY VS. FINISHED")
    y = section_title(c, y, "Before & After")
    cw = PAGE_W - 2 * M
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    draw_para(c, BEFORE_AFTER["intro"],
              ps("p", fontName="Helvetica", fontSize=9, leading=12, textColor=GREY),
              M, y - 34, cw, 26)
    half = (cw - 24) / 2
    ph_h = 1.45 * inch
    yy = y - 50
    for pair in BEFORE_AFTER["pairs"]:
        yy -= ph_h + 4
        for i, (lead, body, img) in enumerate(pair):
            x = M + i * (half + 24)
            tag = "BEFORE" if i == 0 else "AFTER"
            c.setFillColor(GREY_L)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(x, yy + ph_h + 6, _spaced(tag))
            photo(c, img, x, yy, half, ph_h, tag)
            st = ps("c", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=GREY)
            draw_para(c, body, st, x, yy - 22, half, 20)
        yy -= 30
    # note box
    info_box(c, M, yy - 64, cw, 64, BEFORE_AFTER["note"][0],
             BEFORE_AFTER["note"][1], NAVY, CREAM)
    content_footer(c, 4)
    c.showPage()

# ----------------------------------------------------------------------------
# PAGE 5 - MORE ANGLES
# ----------------------------------------------------------------------------
def page_angles(c):
    y = content_header(c, "04", "MORE ANGLES")
    y = section_title(c, y, "Side Yard, Right Side & Corners")
    cw = PAGE_W - 2 * M
    c.setFillColor(GREY)
    c.setFont("Helvetica", 9)
    c.drawString(M, y - 24, ANGLES["intro"])
    half = (cw - 24) / 2
    ph_h = 1.18 * inch
    yy = y - 36
    for row in ANGLES["rows"]:
        yy -= ph_h + 2
        for i, (lead, body, img) in enumerate(row):
            x = M + i * (half + 24)
            tag = "BEFORE" if i == 0 else "AFTER"
            c.setFillColor(GREY_L)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(x, yy + ph_h + 4, _spaced(tag))
            photo(c, img, x, yy, half, ph_h, tag)
            st = ps("c", fontName="Helvetica", fontSize=7.5, leading=9.5, textColor=GREY)
            draw_para(c, body, st, x, yy - 20, half, 18)
        yy -= 28
    content_footer(c, 5)
    c.showPage()

# ----------------------------------------------------------------------------
# PAGE 6 - PRICING & TERMS
# ----------------------------------------------------------------------------
def page_pricing(c):
    y = content_header(c, "05", "INVESTMENT")
    y = section_title(c, y, "Pricing & Terms")
    cw = PAGE_W - 2 * M
    # total banner
    bh = 0.95 * inch
    by = y - 18 - bh
    c.setFillColor(NAVY)
    c.roundRect(M, by, cw, bh, 6, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(PAGE_W / 2, by + bh - 18, _spaced("TOTAL PROJECT INVESTMENT"))
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(PAGE_W / 2, by + 26, PRICING["total"])
    c.setFillColor(colors.HexColor("#AEB6CC"))
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(PAGE_W / 2, by + 12, PRICING["total_note"])

    # schedule
    sy = by - 26
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(M, sy, "Payment Schedule")
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(M, sy - 14, "Structured per California CSLB rules. Down payment limited to $1,000 by law. "
                             "Progress payments are tied to milestones on site.")
    ty = sy - 26
    c.setFillColor(NAVY)
    c.rect(M, ty - 15, cw, 15, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(M + 10, ty - 10.5, "#")
    c.drawString(M + 34, ty - 10.5, "MILESTONE")
    c.drawRightString(M + cw - 70, ty - 10.5, "AMOUNT")
    c.drawRightString(M + cw - 12, ty - 10.5, "%")
    ry = ty - 15
    rowh = 0.32 * inch
    for i, (num, ms, amt, pct) in enumerate(PRICING["schedule"]):
        ry -= rowh
        if i % 2 == 0:
            c.setFillColor(colors.HexColor("#F7F8FA"))
            c.rect(M, ry, cw, rowh, stroke=0, fill=1)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(M + 10, ry + 8, num)
        c.setFillColor(INK)
        c.setFont("Helvetica", 8.5)
        c.drawString(M + 34, ry + 8, ms)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(NAVY)
        c.drawRightString(M + cw - 70, ry + 8, amt)
        c.setFillColor(GREY)
        c.setFont("Helvetica", 8.5)
        c.drawRightString(M + cw - 12, ry + 8, pct)
    # total row
    ry -= rowh
    c.setFillColor(CREAM2)
    c.rect(M, ry, cw, rowh, stroke=0, fill=1)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M + 34, ry + 8, "TOTAL")
    c.drawRightString(M + cw - 70, ry + 8, PRICING["total"])
    c.drawRightString(M + cw - 12, ry + 8, "100%")
    c.setStrokeColor(LINE)
    c.rect(M, ry, cw, ty - 15 - ry, stroke=1, fill=0)

    # optional scopes band
    obh = 0.92 * inch
    oby = ry - 14 - obh
    c.setFillColor(CREAM)
    c.roundRect(M, oby, cw, obh, 5, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(M + 14, oby + obh - 16, "OPTIONAL SCOPES")
    nopt = len(PRICING["options"])
    ocw = (cw - 28) / nopt
    for i, (name, sub, price) in enumerate(PRICING["options"]):
        ox = M + 14 + i * ocw
        if i > 0:
            c.setStrokeColor(colors.HexColor("#E6DEC9"))
            c.setLineWidth(1)
            c.line(ox - 2, oby + 10, ox - 2, oby + obh - 24)
        rec = "recommended" in sub.lower()
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 19)
        c.drawString(ox, oby + 26, price)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.3)
        c.drawString(ox, oby + 14, name)
        c.setFillColor(GOLD if rec else GREY)
        c.setFont("Helvetica-Bold" if rec else "Helvetica", 7.3)
        c.drawString(ox, oby + 4, sub)

    # timeline + not included
    half = (cw - 18) / 2
    boxy = oby - 12
    bxh = 1.5 * inch
    info_box(c, M, boxy - bxh, half, bxh, "Timeline",
             f"<b><font size=13 color='#1B2A5B'>{PRICING['timeline_title']}</font></b><br/><br/>"
             + PRICING["timeline_body"], GOLD, CREAM)
    ni = "<br/>".join("&bull; " + x for x in PRICING["not_included"])
    info_box(c, M + half + 18, boxy - bxh, half, bxh, "Not Included", ni, NAVY, CREAM2)
    content_footer(c, 6)
    c.showPage()

# ----------------------------------------------------------------------------
# PAGE 7 - THANK YOU
# ----------------------------------------------------------------------------
def page_thanks(c):
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 10, PAGE_W, 10, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, PAGE_H - 13, PAGE_W, 3, stroke=0, fill=1)
    y = PAGE_H - 44
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(M, y, COMPANY["name"].upper())
    c.setFillColor(GREY_L)
    c.setFont("Helvetica", 9)
    c.drawRightString(PAGE_W - M, y, f"{CLIENT['residence']}  ·  Project Estimate")

    mid = PAGE_W / 2
    lw = 1.15 * inch
    c.drawImage(ImageReader(LOGO), mid - lw / 2, PAGE_H - 2.4 * inch, lw, lw,
                mask='auto', preserveAspectRatio=True)
    yy = PAGE_H - 2.4 * inch - 6
    eyebrow_center(c, mid, yy, "THANK YOU", GOLD, 9)
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 25)
    c.drawCentredString(mid, yy - 32, "We Look Forward to Working With You")
    gold_rule(c, mid - 28, yy - 48, 56, GOLD, 1.6)

    cw = PAGE_W - 2 * M
    half = (cw - 22) / 2
    bh = 1.7 * inch
    boxy = yy - 70 - bh
    info_box(c, M, boxy, half, bh, "Next Steps",
             f"Call <b>{DOC['pm_name'].split()[0]}</b> at <b>{DOC['pm_phone']}</b> with any "
             "questions or to move forward. We will schedule an in-person meeting to sign the "
             "formal contract, which includes the California Mechanics Lien Warning, the 3-day "
             "Right to Cancel notice, and full CSLB disclosures.", GOLD, CREAM)
    info_box(c, M + half + 22, boxy, half, bh, "About Ariel",
             "We hold a California CSLB <b>Class B General Building</b> license, but by choice we "
             "work only on outdoor projects: paving, fencing, outdoor kitchens, and hardscape. "
             "Specialization is what keeps our work tight and our timelines predictable.", NAVY, CREAM)

    st = ps("disc", fontName="Helvetica-Oblique", fontSize=9, leading=12,
            textColor=GREY_L, alignment=TA_CENTER)
    draw_para(c, "This is an estimate, not a contract. Pricing valid "
              f"{DOC['valid_for'].lower()} from the cover date. A formal home-improvement "
              "contract supersedes this document upon signing.",
              st, M, boxy - 50, cw, 36)

    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.line(M, 42, PAGE_W - M, 42)
    c.setFillColor(GREY_L)
    c.setFont("Helvetica", 7.5)
    c.drawString(M, 30, f"{COMPANY['name']}  ·  {COMPANY['license']}  ·  {COMPANY['phone']}")
    c.drawRightString(PAGE_W - M, 30, "Page 7 of 7")
    c.showPage()

# ----------------------------------------------------------------------------
def build(out_path):
    c = canvas.Canvas(out_path, pagesize=letter)
    c.setTitle("Ariel Outdoor Renovation - Tarango Estimate")
    c.setAuthor(COMPANY["name"])
    page_cover(c)
    page_finished(c)
    page_scope(c)
    page_before_after(c)
    page_angles(c)
    page_pricing(c)
    page_thanks(c)
    c.save()
    print("wrote", out_path)

if __name__ == "__main__":
    build(os.path.join(HERE, "Tarango_Estimate.pdf"))
