"""Generate 2-page Project Estimate PDF for Kelly Marchello."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as canvas_mod
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).parent
OUTPUT_PDF = HERE / "Marchello_Estimate_AOR-051226-S001.pdf"
REFERENCE_IMAGE = HERE / "marchello_reference.jpg"

# Brand palette
NAVY = colors.HexColor("#1F2A44")
INK = colors.HexColor("#111827")
SLATE = colors.HexColor("#4B5563")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D1D5DB")
ACCENT = colors.HexColor("#B08C5F")
CREAM = colors.HexColor("#FAF7F2")
SOFT = colors.HexColor("#F3F4F6")
WHITE = colors.white

PAGE_W, PAGE_H = LETTER
MARGIN_X = 0.6 * inch
MARGIN_TOP = 0.55 * inch
MARGIN_BOTTOM = 0.55 * inch
CONTENT_W = PAGE_W - 2 * MARGIN_X

base = getSampleStyleSheet()


def P(text, **kw):
    """Quick paragraph helper."""
    style = ParagraphStyle("p", fontName="Helvetica", fontSize=9, leading=12, textColor=INK, **kw)
    return Paragraph(text, style)


# -----------------------------------------------------------------------------
# Numbered canvas (2-pass for "Page X of N")
# -----------------------------------------------------------------------------
class NumberedCanvas(canvas_mod.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            canvas_mod.Canvas.showPage(self)
        canvas_mod.Canvas.save(self)

    def _draw_footer(self, total):
        self.saveState()
        self.setStrokeColor(LINE)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, 0.42 * inch, PAGE_W - MARGIN_X, 0.42 * inch)
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7.5)
        self.drawString(
            MARGIN_X,
            0.28 * inch,
            "Ariel Outdoor Renovation · License #1129259 · (818) 390-7639 · "
            "16350 Ventura Blvd. D149, Encino, CA 91436",
        )
        self.drawRightString(
            PAGE_W - MARGIN_X,
            0.28 * inch,
            f"Page {self._pageNumber} of {total}",
        )
        self.restoreState()


# -----------------------------------------------------------------------------
# Page 1: Header + Customer + Scope + Image + Materials
# -----------------------------------------------------------------------------
def build_page_1(story):
    # Top banner: company brand (left) + estimate meta (right)
    company_block = Paragraph(
        "<b><font size=15 color='#1F2A44'>ARIEL OUTDOOR RENOVATION</font></b><br/>"
        "<font size=8 color='#B08C5F'><b>CLASS B GENERAL BUILDING CONTRACTOR · CSLB #1129259</b></font><br/>"
        "<font size=8 color='#4B5563'>"
        "16350 Ventura Blvd. D149, Encino, CA 91436 · (818) 390-7639 · arieloutdoorrenovation.com"
        "</font>",
        ParagraphStyle("comp", fontSize=9, leading=12),
    )
    meta_block = Paragraph(
        "<para alignment='right'>"
        "<font size=8 color='#B08C5F'><b>PROJECT ESTIMATE</b></font><br/>"
        "<b><font size=11 color='#1F2A44'>AOR-051226-S001</font></b><br/>"
        "<font size=8 color='#4B5563'>Issued: May 12, 2026 · Valid 30 days</font>"
        "</para>",
        ParagraphStyle("meta", fontSize=9, leading=12, alignment=TA_RIGHT),
    )
    header = Table(
        [[company_block, meta_block]],
        colWidths=[4.6 * inch, 2.7 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 1.5, NAVY),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 0.12 * inch))

    # Prepared For / Project Address
    prep_block = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>PREPARED FOR</b></font><br/>"
        "<b><font size=12 color='#1F2A44'>Kelly Marchello</font></b><br/>"
        "<font size=9 color='#111827'>738 Forestdale Avenue<br/>"
        "Glendora, California 91740<br/>"
        "(626) 321-2397</font>",
        ParagraphStyle("prep", fontSize=9, leading=13),
    )
    proj_block = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>PROJECT</b></font><br/>"
        "<b><font size=12 color='#1F2A44'>Backyard Redwood Feature</font></b><br/>"
        "<font size=9 color='#111827'>"
        "(2) Custom Planter Boxes<br/>"
        "(1) Redwood Deck Wall · 16ft × 6ft<br/>"
        "Premium materials &amp; color-matched hardware</font>",
        ParagraphStyle("proj", fontSize=9, leading=13),
    )
    sales_block = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>SALES REPRESENTATIVE</b></font><br/>"
        "<b><font size=12 color='#1F2A44'>Meir Hayon</font></b><br/>"
        "<font size=9 color='#111827'>Ariel Outdoor Renovation<br/>"
        "(818) 390-7639<br/>"
        "Appt: 05-12-2026 · 1:00 PM</font>",
        ParagraphStyle("sales", fontSize=9, leading=13),
    )
    info_table = Table(
        [[prep_block, proj_block, sales_block]],
        colWidths=[2.45 * inch, 2.45 * inch, 2.4 * inch],
    )
    info_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEAFTER", (0, 0), (0, 0), 0.5, LINE),
                ("LINEAFTER", (1, 0), (1, 0), 0.5, LINE),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ]
        )
    )
    story.append(info_table)
    story.append(Spacer(1, 0.14 * inch))

    # Scope of Work + Reference image side by side
    scope_header = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>SCOPE OF WORK</b></font><br/>"
        "<b><font size=13 color='#1F2A44'>What's Included</font></b>",
        ParagraphStyle("sh", fontSize=9, leading=14, spaceAfter=6),
    )
    story.append(scope_header)

    scope_rows = [
        [
            Paragraph("<b>01</b>", ParagraphStyle("c", fontSize=9, alignment=TA_CENTER, textColor=NAVY)),
            Paragraph(
                "<b><font color='#1F2A44'>Custom Planter Boxes (×2)</font></b><br/>"
                "<font size=8.5 color='#111827'>"
                "Build and install two custom planter boxes from premium redwood. Square edges, tight "
                "joinery, sealed seams, color-matched screws (wood-tone finish) so fasteners disappear "
                "into the grain. Set level and plumb on the existing concrete.</font>",
                ParagraphStyle("s1", fontSize=9, leading=12),
            ),
        ],
        [
            Paragraph("<b>02</b>", ParagraphStyle("c", fontSize=9, alignment=TA_CENTER, textColor=NAVY)),
            Paragraph(
                "<b><font color='#1F2A44'>Redwood Deck Wall · 16ft × 6ft</font></b><br/>"
                "<font size=8.5 color='#111827'>"
                "Build and install a 16-foot by 6-foot redwood feature wall with horizontal slat layout "
                "matching the reference photo. Premium-grade redwood, hidden framing, color-matched "
                "fasteners. Tightened, plumbed, and inspected before sign-off.</font>",
                ParagraphStyle("s2", fontSize=9, leading=12),
            ),
        ],
        [
            Paragraph("<b>03</b>", ParagraphStyle("c", fontSize=9, alignment=TA_CENTER, textColor=NAVY)),
            Paragraph(
                "<b><font color='#1F2A44'>Installation, Sealing &amp; Cleanup</font></b><br/>"
                "<font size=8.5 color='#111827'>"
                "All anchoring, leveling, and structural fastening on site. Cut ends and end-grain "
                "sealed before installation. Daily debris haul-off, final walkthrough with you, "
                "and 1-year workmanship warranty.</font>",
                ParagraphStyle("s3", fontSize=9, leading=12),
            ),
        ],
    ]
    scope_table = Table(scope_rows, colWidths=[0.4 * inch, 6.9 * inch])
    scope_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SOFT]),
            ]
        )
    )
    story.append(scope_table)
    story.append(Spacer(1, 0.12 * inch))

    # Reference image + materials note side-by-side
    img_para = ""
    if REFERENCE_IMAGE.exists():
        img = Image(str(REFERENCE_IMAGE), width=2.6 * inch, height=3.45 * inch, kind="proportional")
        img_cell = img
    else:
        img_cell = Paragraph("[reference]", ParagraphStyle("x", fontSize=9))

    materials = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>MATERIALS &amp; QUALITY</b></font><br/><br/>"
        "<b><font size=10 color='#1F2A44'>Premium Redwood + Color-Matched Hardware</font></b><br/><br/>"
        "<font size=8.5 color='#111827'>"
        "We use premium-grade redwood selected for color, grain, and weather resistance. "
        "All exposed fasteners are <b>color-matched to the wood tone</b> so the finished surface "
        "reads clean and seamless — no silver screw heads breaking the line of the grain.<br/><br/>"
        "Cut edges and end grain are <b>sealed before installation</b> to slow weathering and "
        "lock in color.<br/><br/>"
        "<b>What we supply:</b> the two planter boxes and the redwood deck wall, fully built "
        "and installed.<br/><br/>"
        "<b>Not included:</b> decorative metal screens, plants, soil, irrigation, concrete, "
        "electrical, lighting, stain/paint, HOA fees, and permits."
        "</font>",
        ParagraphStyle("m", fontSize=9, leading=12),
    )

    bottom = Table([[img_cell, materials]], colWidths=[2.8 * inch, 4.5 * inch])
    bottom.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (1, 0), (1, 0), CREAM),
                ("BOX", (1, 0), (1, 0), 0.5, ACCENT),
                ("BOX", (0, 0), (0, 0), 0.5, LINE),
            ]
        )
    )
    story.append(bottom)
    story.append(PageBreak())


# -----------------------------------------------------------------------------
# Page 2: Pricing options + Payment schedule + Timeline + Next steps
# -----------------------------------------------------------------------------
def build_page_2(story):
    # Mini-header re-stating client + estimate # for context if printed standalone
    sub_header = Paragraph(
        "<para alignment='left'>"
        "<font size=8 color='#B08C5F'><b>03 · INVESTMENT &amp; TERMS</b></font><br/>"
        "<b><font size=15 color='#1F2A44'>Pricing &amp; Payment</font></b><br/>"
        "<font size=8.5 color='#4B5563'>"
        "Two material grades for the same build. Both all-inclusive: labor, materials, "
        "color-matched hardware, equipment, insurance, taxes, and on-site management."
        "</font></para>",
        ParagraphStyle("sh", fontSize=9, leading=13),
    )
    story.append(sub_header)
    story.append(Spacer(1, 0.1 * inch))

    # Two option cards
    def card(label, name, price, bullets, recommended):
        rec_tag = '<br/><font size=7.5 color="#B08C5F"><b>★ RECOMMENDED</b></font>' if recommended else ''
        header = Paragraph(
            f"<para alignment='center'>"
            f"<font size=8 color='#B08C5F'><b>{label}</b></font><br/>"
            f"<b><font size=13 color='#1F2A44'>{name}</font></b>"
            f"{rec_tag}"
            f"</para>",
            ParagraphStyle("h", alignment=TA_CENTER, fontSize=9, leading=12),
        )
        price_p = Paragraph(
            f"<para alignment='center'>"
            f"<b><font size=26 color='#1F2A44'>{price}</font></b><br/>"
            f"<font size=7.5 color='#6B7280'>all-inclusive</font>"
            f"</para>",
            ParagraphStyle("pr", alignment=TA_CENTER, fontSize=9, leading=11),
        )
        bullets_html = "<br/>".join(f"· {b}" for b in bullets)
        bullets_p = Paragraph(
            f"<font size=8 color='#111827'>{bullets_html}</font>",
            ParagraphStyle("b", fontSize=8, leading=11),
        )
        return Table(
            [[header], [price_p], [bullets_p]],
            colWidths=[3.5 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CREAM if recommended else WHITE),
                    ("BOX", (0, 0), (-1, -1), 1.2 if recommended else 0.5, ACCENT if recommended else LINE),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
                    ("LINEBELOW", (0, 1), (-1, 1), 0.5, LINE),
                ]
            ),
        )

    opt_a = card(
        "OPTION A",
        "Premium Grade",
        "$7,200",
        [
            "Clear All-Heart Redwood — top grade",
            "Hand-selected boards, uniform grain",
            "Virtually knot-free, premium color depth",
            "Stainless color-matched fasteners",
            "Full end-grain &amp; cut-line sealing",
            "Longest service life, best finish",
        ],
        recommended=True,
    )
    opt_b = card(
        "OPTION B",
        "Standard Grade",
        "$6,300",
        [
            "Construction Common Redwood — quality grade",
            "Sound, durable, weather-resistant",
            "Minor sound knots permitted, natural look",
            "Color-matched fasteners throughout",
            "End-grain sealed at cuts",
            "Strong value, holds up well outdoors",
        ],
        recommended=False,
    )
    opts = Table([[opt_a, opt_b]], colWidths=[3.65 * inch, 3.65 * inch])
    opts.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(opts)
    story.append(Spacer(1, 0.14 * inch))

    # Payment schedule (compact)
    pay_title = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>PAYMENT SCHEDULE</b></font> "
        "<font size=8 color='#4B5563'>· Per California CSLB rules. Down payment capped at "
        "the lesser of 10% or $1,000.</font>",
        ParagraphStyle("pt", fontSize=9, leading=12),
    )
    story.append(pay_title)
    story.append(Spacer(1, 0.05 * inch))

    th = lambda s: Paragraph(f"<font size=8 color='white'><b>{s}</b></font>", ParagraphStyle("th", fontSize=8))
    tc = lambda s: Paragraph(f"<font size=8.5 color='#111827'>{s}</font>", ParagraphStyle("tc", fontSize=8.5, leading=11))
    tcb = lambda s: Paragraph(f"<font size=8.5 color='#1F2A44'><b>{s}</b></font>", ParagraphStyle("tcb", fontSize=8.5, leading=11))

    pay_rows = [
        [th("#"), th("MILESTONE"), th("%"), th("OPTION A · $7,200"), th("OPTION B · $6,300")],
        [tcb("1"), tc("Contract signing (down payment, CA-capped at 10%)"), tc("10%"), tcb("$720"), tcb("$630")],
        [tcb("2"), tc("Materials delivered, crew mobilized on site"), tc("45%"), tcb("$3,240"), tcb("$2,835")],
        [tcb("3"), tc("Final walkthrough, punch-list closed"), tc("45%"), tcb("$3,240"), tcb("$2,835")],
        [Paragraph("", ParagraphStyle("x", fontSize=8)), tcb("TOTAL"), tcb("100%"), tcb("$7,200"), tcb("$6,300")],
    ]
    pay = Table(
        pay_rows,
        colWidths=[0.3 * inch, 3.25 * inch, 0.55 * inch, 1.6 * inch, 1.6 * inch],
    )
    pay.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, NAVY),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, -1), (-1, -1), SOFT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SOFT]),
            ]
        )
    )
    story.append(pay)
    story.append(Spacer(1, 0.14 * inch))

    # Timeline + Not Included + Next Steps in 3 columns
    timeline = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>TIMELINE</b></font><br/><br/>"
        "<b><font size=12 color='#1F2A44'>3 – 5 working days</font></b><br/>"
        "<font size=8 color='#4B5563'>From mobilization to walkthrough. Same timeline for "
        "both options; confirmed at contract signing.</font>",
        ParagraphStyle("tl", fontSize=9, leading=12),
    )
    not_inc = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>NOT INCLUDED</b></font><br/><br/>"
        "<font size=8 color='#111827'>"
        "· Decorative metal screens<br/>"
        "· Plants, soil, irrigation<br/>"
        "· Concrete or hardscape work<br/>"
        "· Electrical or lighting<br/>"
        "· Stain or paint finish<br/>"
        "· HOA fees or permits<br/>"
        "· Out-of-scope changes (billed separately)"
        "</font>",
        ParagraphStyle("ni", fontSize=9, leading=11.5),
    )
    next_steps = Paragraph(
        "<font size=7.5 color='#B08C5F'><b>NEXT STEPS</b></font><br/><br/>"
        "<font size=8.5 color='#111827'>"
        "Call <b>Meir Hayon</b> at <b>(818) 390-7639</b> "
        "to select an option and move forward.<br/><br/>"
        "We will schedule the formal contract signing, which includes the California "
        "Mechanics Lien Warning, 3-day Right to Cancel, and full CSLB disclosures."
        "</font>",
        ParagraphStyle("ns", fontSize=9, leading=12),
    )
    three = Table(
        [[timeline, not_inc, next_steps]],
        colWidths=[2.3 * inch, 2.2 * inch, 2.8 * inch],
    )
    three.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (0, 0), 0.5, LINE),
                ("BOX", (1, 0), (1, 0), 0.5, LINE),
                ("BOX", (2, 0), (2, 0), 0.5, ACCENT),
                ("BACKGROUND", (2, 0), (2, 0), CREAM),
            ]
        )
    )
    story.append(three)
    story.append(Spacer(1, 0.12 * inch))

    # Signature line
    sig = Paragraph(
        "<font size=8 color='#4B5563'><i>This is an estimate, not a contract. Pricing valid "
        "30 days from the issue date. A formal home-improvement contract supersedes this "
        "document upon signing.</i></font>",
        ParagraphStyle("sg", fontSize=9, leading=11, alignment=TA_CENTER),
    )
    story.append(sig)
    story.append(Spacer(1, 0.1 * inch))

    sig_table = Table(
        [
            [
                Paragraph(
                    "<font size=7.5 color='#6B7280'><b>CLIENT ACCEPTANCE — OPTION SELECTED:</b> "
                    "&nbsp;&nbsp; &#9744; Option A ($7,200) &nbsp;&nbsp;&nbsp;&nbsp; &#9744; Option B ($6,300)</font>",
                    ParagraphStyle("sl", fontSize=9, leading=12),
                ),
            ],
            [
                Paragraph(
                    "<font size=8 color='#111827'>Signature: ________________________________ &nbsp;&nbsp;&nbsp; "
                    "Date: _______________</font>",
                    ParagraphStyle("sl2", fontSize=9, leading=14),
                ),
            ],
        ],
        colWidths=[CONTENT_W],
    )
    sig_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BOX", (0, 0), (-1, -1), 0.5, NAVY),
                ("LINEBELOW", (0, 0), (-1, 0), 0.3, LINE),
            ]
        )
    )
    story.append(sig_table)


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------
def build():
    doc = BaseDocTemplate(
        str(OUTPUT_PDF),
        pagesize=LETTER,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title="Project Estimate - Marchello Residence",
        author="Ariel Outdoor Renovation",
        subject="AOR-051226-S001",
    )
    frame = Frame(
        MARGIN_X,
        MARGIN_BOTTOM,
        PAGE_W - 2 * MARGIN_X,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        id="main",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates(PageTemplate(id="main", frames=[frame]))
    story = []
    build_page_1(story)
    build_page_2(story)
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Wrote: {OUTPUT_PDF}")


if __name__ == "__main__":
    build()
