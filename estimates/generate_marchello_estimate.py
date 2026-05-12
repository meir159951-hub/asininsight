"""Generate Project Estimate PDF for Kelly Marchello (Ariel Outdoor Renovation)."""

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
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas_mod.Canvas):
    """Two-pass canvas that knows total page count when drawing footer."""

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
            if self._pageNumber > 1:
                self._draw_page_number(total)
            canvas_mod.Canvas.showPage(self)
        canvas_mod.Canvas.save(self)

    def _draw_page_number(self, total):
        self.saveState()
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 8)
        self.drawRightString(
            PAGE_W - MARGIN_X,
            0.42 * inch,
            f"Page {self._pageNumber} of {total}",
        )
        self.restoreState()

HERE = Path(__file__).parent
OUTPUT_PDF = HERE / "Marchello_Estimate_AOR-051226-S001.pdf"
REFERENCE_IMAGE = HERE / "marchello_reference.jpg"

# Brand palette (matches reference estimate tone)
NAVY = colors.HexColor("#1F2A44")
INK = colors.HexColor("#111827")
SLATE = colors.HexColor("#4B5563")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D1D5DB")
ACCENT = colors.HexColor("#B08C5F")  # warm wood tone
CREAM = colors.HexColor("#FAF7F2")
SOFT = colors.HexColor("#F3F4F6")
WHITE = colors.white

PAGE_W, PAGE_H = LETTER
MARGIN_X = 0.75 * inch
MARGIN_TOP = 0.75 * inch
MARGIN_BOTTOM = 0.85 * inch

# -----------------------------------------------------------------------------
# Styles
# -----------------------------------------------------------------------------
base = getSampleStyleSheet()

styles = {
    "cover_kicker": ParagraphStyle(
        "cover_kicker",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=6,
    ),
    "cover_title": ParagraphStyle(
        "cover_title",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=32,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=4,
    ),
    "cover_subtitle": ParagraphStyle(
        "cover_subtitle",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=SLATE,
        alignment=TA_CENTER,
    ),
    "section_kicker": ParagraphStyle(
        "section_kicker",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=ACCENT,
        spaceAfter=4,
    ),
    "section_title": ParagraphStyle(
        "section_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=NAVY,
        spaceAfter=6,
    ),
    "sub_title": ParagraphStyle(
        "sub_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=NAVY,
        spaceAfter=4,
    ),
    "body": ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=INK,
        spaceAfter=6,
    ),
    "body_muted": ParagraphStyle(
        "body_muted",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=SLATE,
    ),
    "small": ParagraphStyle(
        "small",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=MUTED,
    ),
    "small_center": ParagraphStyle(
        "small_center",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=MUTED,
        alignment=TA_CENTER,
    ),
    "prepared_for": ParagraphStyle(
        "prepared_for",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=8,
    ),
    "client_name": ParagraphStyle(
        "client_name",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=NAVY,
        alignment=TA_CENTER,
    ),
    "client_line": ParagraphStyle(
        "client_line",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=SLATE,
        alignment=TA_CENTER,
    ),
    "price_big": ParagraphStyle(
        "price_big",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=42,
        leading=46,
        textColor=NAVY,
        alignment=TA_CENTER,
    ),
    "price_kicker": ParagraphStyle(
        "price_kicker",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=4,
    ),
    "thank_title": ParagraphStyle(
        "thank_title",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=30,
        textColor=NAVY,
        alignment=TA_CENTER,
    ),
    "thank_kicker": ParagraphStyle(
        "thank_kicker",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=6,
    ),
    "table_header": ParagraphStyle(
        "table_header",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=WHITE,
    ),
    "table_cell": ParagraphStyle(
        "table_cell",
        parent=base["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=INK,
    ),
    "table_cell_bold": ParagraphStyle(
        "table_cell_bold",
        parent=base["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=NAVY,
    ),
}


# -----------------------------------------------------------------------------
# Page header / footer
# -----------------------------------------------------------------------------
def draw_header_footer(canvas, doc):
    canvas.saveState()

    page_num = canvas.getPageNumber()

    if page_num > 1:
        # Top header bar
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(
            MARGIN_X, PAGE_H - 0.45 * inch, "ARIEL OUTDOOR RENOVATION"
        )
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(
            PAGE_W - MARGIN_X,
            PAGE_H - 0.45 * inch,
            "Marchello Residence · Project Estimate",
        )
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(
            MARGIN_X,
            PAGE_H - 0.55 * inch,
            PAGE_W - MARGIN_X,
            PAGE_H - 0.55 * inch,
        )

    # Footer (page number is drawn by NumberedCanvas in second pass)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(
        MARGIN_X, 0.6 * inch, PAGE_W - MARGIN_X, 0.6 * inch
    )
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        MARGIN_X,
        0.42 * inch,
        "Ariel Outdoor Renovation · License #1129259 · (818) 390-7639",
    )
    canvas.restoreState()


def draw_cover_header_footer(canvas, doc):
    """Special handling for cover page - just footer with company line."""
    canvas.saveState()
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8.5)
    left = (
        "License #1129259 · (818) 390-7639 · arieloutdoorrenovation.com"
    )
    right = "16350 Ventura Blvd. D149, Encino, CA 91436"
    canvas.drawString(MARGIN_X, 0.55 * inch, left)
    canvas.drawRightString(PAGE_W - MARGIN_X, 0.55 * inch, right)
    canvas.restoreState()


def on_page(canvas, doc):
    if canvas.getPageNumber() == 1:
        draw_cover_header_footer(canvas, doc)
    else:
        draw_header_footer(canvas, doc)


# -----------------------------------------------------------------------------
# Content builders
# -----------------------------------------------------------------------------
def build_cover(story):
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("PROJECT ESTIMATE", styles["cover_kicker"]))
    story.append(
        Paragraph("Backyard Redwood Feature", styles["cover_title"])
    )
    story.append(
        Paragraph(
            "Privacy Planter Boxes &amp; Redwood Deck Wall",
            styles["cover_subtitle"],
        )
    )
    story.append(Spacer(1, 0.5 * inch))

    story.append(Paragraph("PREPARED FOR", styles["prepared_for"]))
    story.append(Paragraph("Kelly Marchello", styles["client_name"]))
    story.append(Spacer(1, 0.05 * inch))
    story.append(
        Paragraph("738 Forestdale Avenue", styles["client_line"])
    )
    story.append(
        Paragraph("Glendora, California 91740", styles["client_line"])
    )
    story.append(Paragraph("(626) 321-2397", styles["client_line"]))

    story.append(Spacer(1, 0.45 * inch))

    # Company block
    company = Paragraph(
        "<b><font size=12 color='#1F2A44'>ARIEL OUTDOOR RENOVATION</font></b>",
        ParagraphStyle(
            "comp_name", alignment=TA_CENTER, fontSize=12, leading=16
        ),
    )
    tagline = Paragraph(
        "<font color='#4B5563'>Class B General Building Contractor · "
        "Specializing in outdoor renovation</font>",
        ParagraphStyle(
            "comp_tag", alignment=TA_CENTER, fontSize=10, leading=13
        ),
    )
    story.append(company)
    story.append(tagline)

    story.append(Spacer(1, 0.45 * inch))

    # Meta table: DATE | ESTIMATE NO. | VALID FOR
    meta_header = [
        Paragraph("DATE", styles["section_kicker"]),
        Paragraph("ESTIMATE NO.", styles["section_kicker"]),
        Paragraph("VALID FOR", styles["section_kicker"]),
    ]
    meta_values = [
        Paragraph(
            "<b><font color='#111827'>May 12, 2026</font></b>",
            ParagraphStyle("m1", fontSize=11, leading=14),
        ),
        Paragraph(
            "<b><font color='#111827'>AOR-051226-S001</font></b>",
            ParagraphStyle("m2", fontSize=11, leading=14),
        ),
        Paragraph(
            "<b><font color='#111827'>30 Days</font></b>",
            ParagraphStyle("m3", fontSize=11, leading=14),
        ),
    ]
    meta_table = Table(
        [meta_header, meta_values],
        colWidths=[2.2 * inch, 2.4 * inch, 2.0 * inch],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, 0), (-1, 0), 0.75, LINE),
                ("LINEBELOW", (0, 1), (-1, 1), 0.75, LINE),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(meta_table)

    story.append(PageBreak())


def build_design_direction(story):
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("01 · DESIGN DIRECTION", styles["section_kicker"]))
    story.append(Paragraph("Finished Look", styles["section_title"]))

    intro = (
        "Kelly,<br/><br/>"
        "Thank you for the opportunity to put this estimate together. "
        "Below is the finished look we walked through, followed by the full "
        "scope, pricing, and timeline. The price covers labor, materials, "
        "equipment, insurance, taxes, and on-site management for everything "
        "shown."
    )
    story.append(Paragraph(intro, styles["body"]))
    story.append(Spacer(1, 0.1 * inch))

    # Reference image
    if REFERENCE_IMAGE.exists():
        img = Image(
            str(REFERENCE_IMAGE),
            width=6.2 * inch,
            height=4.65 * inch,
            kind="proportional",
        )
        story.append(img)
        story.append(Spacer(1, 0.08 * inch))
        story.append(
            Paragraph(
                "<i>Reference — finished aesthetic. Ariel Outdoor Renovation "
                "supplies and installs the two planter boxes and the redwood deck "
                "wall (16ft × 6ft). Decorative metal screens and plants shown "
                "for context are not part of this scope.</i>",
                styles["small_center"],
            )
        )

    story.append(PageBreak())


def build_scope(story):
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("02 · SCOPE OF WORK", styles["section_kicker"]))
    story.append(Paragraph("What's Included", styles["section_title"]))

    story.append(
        Paragraph(
            "Two work packages, bundled in the price on the next page. Labor, "
            "premium redwood lumber, color-matched hardware, equipment, debris "
            "haul-off, and on-site management are all included.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    header = [
        Paragraph("#", styles["table_header"]),
        Paragraph("PHASE", styles["table_header"]),
        Paragraph("WORK INCLUDED", styles["table_header"]),
    ]
    rows = [
        header,
        [
            Paragraph("01", styles["table_cell_bold"]),
            Paragraph(
                "Custom Planter<br/>Boxes (×2)",
                styles["table_cell_bold"],
            ),
            Paragraph(
                "Build and install two custom planter boxes from premium "
                "redwood. Square edges, tight joinery, sealed seams, "
                "color-matched screws (wood-tone finish) so fasteners disappear "
                "into the grain. Set level and plumb on the existing concrete.",
                styles["table_cell"],
            ),
        ],
        [
            Paragraph("02", styles["table_cell_bold"]),
            Paragraph(
                "Redwood Deck Wall<br/>16ft × 6ft",
                styles["table_cell_bold"],
            ),
            Paragraph(
                "Build and install a 16-foot by 6-foot redwood feature wall "
                "with horizontal slat layout matching the reference photo. "
                "Premium-grade redwood, hidden framing, color-matched fasteners. "
                "Tightened, plumbed, and inspected before sign-off.",
                styles["table_cell"],
            ),
        ],
    ]

    scope_table = Table(rows, colWidths=[0.45 * inch, 1.55 * inch, 4.7 * inch])
    scope_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, SOFT]),
            ]
        )
    )
    story.append(scope_table)
    story.append(Spacer(1, 0.2 * inch))

    # Materials callout
    materials = Paragraph(
        "<b><font color='#1F2A44'>MATERIAL STANDARDS</font></b><br/><br/>"
        "<font color='#111827'>"
        "We use premium-grade redwood selected for color, grain, and weather "
        "resistance. All exposed fasteners are color-matched to the wood tone "
        "so the finished surface reads clean and seamless. Cut edges and end "
        "grain are sealed before installation to slow weathering and lock in "
        "color."
        "</font>",
        ParagraphStyle(
            "mat",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=INK,
        ),
    )
    materials_box = Table(
        [[materials]], colWidths=[6.7 * inch]
    )
    materials_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CREAM),
                ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(materials_box)
    story.append(Spacer(1, 0.18 * inch))

    # Two-column: How we run it / Licensed
    left_block = Paragraph(
        "<b><font color='#1F2A44'>HOW WE RUN THE JOB</font></b><br/><br/>"
        "· Premium redwood, kiln-dried, hand-selected on site.<br/>"
        "· Hidden framing where possible; color-matched screws<br/>"
        "&nbsp;&nbsp;&nbsp;everywhere they show.<br/>"
        "· Sealed cut ends and seams to slow weathering.<br/>"
        "· Daily debris haul-off; site swept at end of each day.<br/>"
        "· Final walkthrough with you before sign-off.",
        ParagraphStyle("hb", fontSize=9, leading=13, textColor=INK),
    )
    right_block = Paragraph(
        "<b><font color='#1F2A44'>LICENSED, INSURED, SPECIALIZED</font></b>"
        "<br/><br/>"
        "· CSLB License #1129259, Class B General Building<br/>"
        "&nbsp;&nbsp;&nbsp;Contractor, active and in good standing.<br/>"
        "· Specializing in outdoor renovation: paving, fencing,<br/>"
        "&nbsp;&nbsp;&nbsp;outdoor kitchens, hardscape, and wood features.<br/>"
        "· General liability and workers compensation on file.<br/>"
        "· 1-year workmanship warranty on installed work.",
        ParagraphStyle("rb", fontSize=9, leading=13, textColor=INK),
    )
    two_col = Table(
        [[left_block, right_block]],
        colWidths=[3.3 * inch, 3.4 * inch],
    )
    two_col.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEABOVE", (0, 0), (-1, 0), 0.5, LINE),
            ]
        )
    )
    story.append(two_col)

    story.append(PageBreak())


def _option_card(label, name, price, bullets, recommended=False):
    """Build a single pricing option card."""
    badge_html = ""
    if recommended:
        badge_html = (
            "<font color='#B08C5F'><b>★ RECOMMENDED</b></font><br/>"
        )

    header_para = Paragraph(
        f"<b><font color='#B08C5F'>{label}</font></b><br/>"
        f"<b><font size=14 color='#1F2A44'>{name}</font></b><br/>"
        f"{badge_html}",
        ParagraphStyle("oh", fontSize=9, leading=12, alignment=TA_CENTER),
    )

    price_para = Paragraph(
        f"<b><font size=30 color='#1F2A44'>{price}</font></b><br/>"
        "<font size=8 color='#6B7280'>all-inclusive</font>",
        ParagraphStyle("op", alignment=TA_CENTER, fontSize=9, leading=14),
    )

    bullets_html = "<br/>".join(f"· {b}" for b in bullets)
    bullets_para = Paragraph(
        f"<font size=8.5 color='#111827'>{bullets_html}</font>",
        ParagraphStyle("ob", fontSize=8.5, leading=12),
    )

    rows = [[header_para], [price_para], [bullets_para]]
    border_color = ACCENT if recommended else LINE
    border_width = 1.2 if recommended else 0.5

    card = Table(rows, colWidths=[3.2 * inch])
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CREAM if recommended else WHITE),
                ("BOX", (0, 0), (-1, -1), border_width, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, LINE),
                ("LINEBELOW", (0, 1), (-1, 1), 0.5, LINE),
            ]
        )
    )
    return card


def build_investment(story):
    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph("03 · INVESTMENT", styles["section_kicker"]))
    story.append(Paragraph("Pricing & Terms", styles["section_title"]))

    story.append(
        Paragraph(
            "Two material grades are offered for the same build. Both options "
            "are all-inclusive: labor, materials, color-matched hardware, "
            "equipment, insurance, taxes, and on-site management.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 0.08 * inch))

    option_a = _option_card(
        label="OPTION A",
        name="Premium Grade",
        price="$7,200",
        bullets=[
            "Clear All-Heart Redwood — top grade",
            "Hand-selected boards, tight uniform grain",
            "Virtually knot-free, premium color depth",
            "Stainless color-matched fasteners",
            "Full end-grain &amp; cut-line sealing",
            "Longest service life, best finish",
        ],
        recommended=True,
    )
    option_b = _option_card(
        label="OPTION B",
        name="Standard Grade",
        price="$6,300",
        bullets=[
            "Construction Common Redwood — quality grade",
            "Sound, durable, weather-resistant boards",
            "Minor sound knots permitted, natural look",
            "Color-matched fasteners throughout",
            "End-grain sealed at cuts",
            "Strong value, holds up well outdoors",
        ],
        recommended=False,
    )

    options_table = Table(
        [[option_a, option_b]],
        colWidths=[3.35 * inch, 3.35 * inch],
    )
    options_table.setStyle(
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
    story.append(options_table)
    story.append(Spacer(1, 0.14 * inch))

    story.append(Paragraph("Payment Schedule", styles["sub_title"]))
    story.append(
        Paragraph(
            "Per California CSLB rules. Down payment capped at the lesser of "
            "10% or $1,000. Progress payments tied to milestones on site.",
            styles["body_muted"],
        )
    )
    story.append(Spacer(1, 0.06 * inch))

    pay_header = [
        Paragraph("#", styles["table_header"]),
        Paragraph("MILESTONE", styles["table_header"]),
        Paragraph("%", styles["table_header"]),
        Paragraph("OPTION A<br/>$7,200", styles["table_header"]),
        Paragraph("OPTION B<br/>$6,300", styles["table_header"]),
    ]
    pay_rows = [
        pay_header,
        [
            Paragraph("1", styles["table_cell_bold"]),
            Paragraph(
                "Contract signing (down payment, CA-capped at 10%)",
                styles["table_cell"],
            ),
            Paragraph("10%", styles["table_cell"]),
            Paragraph("$720", styles["table_cell_bold"]),
            Paragraph("$630", styles["table_cell_bold"]),
        ],
        [
            Paragraph("2", styles["table_cell_bold"]),
            Paragraph(
                "Materials delivered, crew mobilized on site",
                styles["table_cell"],
            ),
            Paragraph("45%", styles["table_cell"]),
            Paragraph("$3,240", styles["table_cell_bold"]),
            Paragraph("$2,835", styles["table_cell_bold"]),
        ],
        [
            Paragraph("3", styles["table_cell_bold"]),
            Paragraph(
                "Final walkthrough, punch-list closed",
                styles["table_cell"],
            ),
            Paragraph("45%", styles["table_cell"]),
            Paragraph("$3,240", styles["table_cell_bold"]),
            Paragraph("$2,835", styles["table_cell_bold"]),
        ],
        [
            Paragraph("", styles["table_cell_bold"]),
            Paragraph("<b>TOTAL</b>", styles["table_cell_bold"]),
            Paragraph("<b>100%</b>", styles["table_cell_bold"]),
            Paragraph("<b>$7,200</b>", styles["table_cell_bold"]),
            Paragraph("<b>$6,300</b>", styles["table_cell_bold"]),
        ],
    ]
    pay_table = Table(
        pay_rows,
        colWidths=[
            0.35 * inch,
            3.05 * inch,
            0.55 * inch,
            1.4 * inch,
            1.4 * inch,
        ],
    )
    pay_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, NAVY),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, -1), (-1, -1), SOFT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SOFT]),
            ]
        )
    )
    story.append(pay_table)
    story.append(Spacer(1, 0.12 * inch))

    # Two-column: Timeline / Not Included
    timeline_block = Paragraph(
        "<b><font color='#1F2A44'>TIMELINE</font></b><br/><br/>"
        "<b><font size=13 color='#111827'>3 – 5 working days</font></b><br/><br/>"
        "<font color='#4B5563'>"
        "From mobilization to walkthrough. Same timeline for both options; "
        "schedule confirmed at contract signing."
        "</font>",
        ParagraphStyle("tl", fontSize=9, leading=12.5, textColor=INK),
    )
    not_inc_block = Paragraph(
        "<b><font color='#1F2A44'>NOT INCLUDED</font></b><br/><br/>"
        "· Decorative metal screens (panels behind boxes)<br/>"
        "· Plants, soil, irrigation, or sprinkler work<br/>"
        "· Concrete pad, paving, or hardscape work<br/>"
        "· Electrical, lighting, or low-voltage<br/>"
        "· Stain or paint finish (natural redwood)<br/>"
        "· HOA fees or permits, if required<br/>"
        "· Changes outside this scope (billed separately)",
        ParagraphStyle("ni", fontSize=8.5, leading=12, textColor=INK),
    )
    two_col2 = Table(
        [[timeline_block, not_inc_block]],
        colWidths=[3.0 * inch, 3.7 * inch],
    )
    two_col2.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (0, 0), SOFT),
                ("BACKGROUND", (1, 0), (1, 0), SOFT),
                ("BOX", (0, 0), (0, 0), 0.5, LINE),
                ("BOX", (1, 0), (1, 0), 0.5, LINE),
            ]
        )
    )
    story.append(two_col2)

    story.append(PageBreak())


def build_thank_you(story):
    story.append(Spacer(1, 0.6 * inch))
    story.append(Paragraph("THANK YOU", styles["thank_kicker"]))
    story.append(
        Paragraph(
            "We Look Forward to Working With You",
            styles["thank_title"],
        )
    )
    story.append(Spacer(1, 0.4 * inch))

    next_steps = Paragraph(
        "<b><font color='#1F2A44'>NEXT STEPS</font></b><br/><br/>"
        "<font color='#111827'>"
        "Call Jacob at (323) 513-4865 with any questions or to move forward. "
        "We will schedule an in-person meeting to sign the formal contract, "
        "which includes the California Mechanics Lien Warning, the 3-day Right "
        "to Cancel notice, and full CSLB disclosures."
        "</font>",
        ParagraphStyle("ns", fontSize=10, leading=14, textColor=INK),
    )
    about_block = Paragraph(
        "<b><font color='#1F2A44'>ABOUT ARIEL</font></b><br/><br/>"
        "<font color='#111827'>"
        "We hold a California CSLB Class B General Building license, but by "
        "choice we work only on outdoor projects: paving, fencing, outdoor "
        "kitchens, hardscape, and wood features. Specialization is what keeps "
        "our work tight and our timelines predictable."
        "</font>",
        ParagraphStyle("ab", fontSize=10, leading=14, textColor=INK),
    )

    two_col = Table(
        [[next_steps, about_block]],
        colWidths=[3.35 * inch, 3.35 * inch],
    )
    two_col.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (0, 0), 0.5, LINE),
                ("BOX", (1, 0), (1, 0), 0.5, LINE),
            ]
        )
    )
    story.append(two_col)
    story.append(Spacer(1, 0.6 * inch))

    # Sales rep line
    rep_block = Paragraph(
        "<b><font color='#B08C5F'>YOUR SALES REPRESENTATIVE</font></b><br/><br/>"
        "<b><font size=12 color='#1F2A44'>Meir Hayon</font></b><br/>"
        "<font color='#4B5563'>Ariel Outdoor Renovation</font>",
        ParagraphStyle(
            "rep",
            fontSize=9,
            leading=13,
            alignment=TA_CENTER,
        ),
    )
    story.append(rep_block)
    story.append(Spacer(1, 0.4 * inch))

    disclaimer = Paragraph(
        "<i>This is an estimate, not a contract. Pricing valid 30 days from "
        "the cover date. A formal home-improvement contract supersedes this "
        "document upon signing.</i>",
        styles["small_center"],
    )
    story.append(disclaimer)


# -----------------------------------------------------------------------------
# Build the doc
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
    )
    doc.addPageTemplates(
        PageTemplate(id="main", frames=[frame], onPage=on_page)
    )

    story = []
    build_cover(story)
    build_design_direction(story)
    build_scope(story)
    build_investment(story)
    build_thank_you(story)
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Wrote: {OUTPUT_PDF}")


if __name__ == "__main__":
    build()
