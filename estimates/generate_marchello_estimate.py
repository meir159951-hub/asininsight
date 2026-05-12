"""Generate 2-page Project Estimate PDF for Kelly Marchello.

Refined version: project-manager voice (Jacob Hayon), personal opening,
trust signals, signature block, and tightened typography.
"""

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

# Refined palette — restrained, premium feel
NAVY = colors.HexColor("#1A2238")
INK = colors.HexColor("#0F172A")
SLATE = colors.HexColor("#475569")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
LINE_DARK = colors.HexColor("#CBD5E1")
ACCENT = colors.HexColor("#A07E4F")  # warm bronze
ACCENT_SOFT = colors.HexColor("#EFE7DC")
CREAM = colors.HexColor("#FBF8F3")
SOFT = colors.HexColor("#F8FAFC")
WHITE = colors.white

PAGE_W, PAGE_H = LETTER
MARGIN_X = 0.6 * inch
MARGIN_TOP = 0.55 * inch
MARGIN_BOTTOM = 0.55 * inch
CONTENT_W = PAGE_W - 2 * MARGIN_X


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
        # Thin accent line
        self.setStrokeColor(ACCENT)
        self.setLineWidth(0.4)
        self.line(MARGIN_X, 0.46 * inch, MARGIN_X + 0.4 * inch, 0.46 * inch)
        # Company line
        self.setFillColor(MUTED)
        self.setFont("Helvetica", 7.5)
        self.drawString(
            MARGIN_X,
            0.28 * inch,
            "Ariel Outdoor Renovation  ·  CSLB License #1129259  ·  "
            "16350 Ventura Blvd. D149, Encino, CA 91436  ·  (818) 390-7639",
        )
        self.drawRightString(
            PAGE_W - MARGIN_X,
            0.28 * inch,
            f"{self._pageNumber} / {total}",
        )
        self.restoreState()


# -----------------------------------------------------------------------------
# Page 1
# -----------------------------------------------------------------------------
def build_page_1(story):
    # --- Top header band ---
    company = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>"
        "CSLB CLASS B  ·  LICENSE #1129259  ·  FULLY INSURED"
        "</b></font><br/>"
        "<font name='Times-Bold' size=22 color='#1A2238'>Ariel Outdoor Renovation</font>",
        ParagraphStyle("c", fontSize=10, leading=26),
    )
    meta = Paragraph(
        "<para alignment='right'>"
        "<font size=7.5 color='#A07E4F'><b>PROJECT ESTIMATE</b></font><br/>"
        "<font name='Times-Bold' size=15 color='#1A2238'>AOR-051226-S001</font><br/>"
        "<font size=8 color='#475569'>Issued May 12, 2026  ·  Valid for 30 days</font>"
        "</para>",
        ParagraphStyle("m", fontSize=10, leading=16, alignment=TA_RIGHT),
    )
    header = Table([[company, meta]], colWidths=[4.4 * inch, 2.9 * inch])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, NAVY),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 0.14 * inch))

    # --- Project title block ---
    story.append(
        Paragraph(
            "<font size=8 color='#A07E4F'><b>PROJECT</b></font>",
            ParagraphStyle("ptl", fontSize=9, leading=11, spaceAfter=2),
        )
    )
    story.append(
        Paragraph(
            "<font name='Times-Bold' size=24 color='#1A2238'>Backyard Redwood Feature</font>",
            ParagraphStyle("pth", fontSize=24, leading=28, spaceAfter=2),
        )
    )
    story.append(
        Paragraph(
            "<font size=9.5 color='#475569'>"
            "Two custom planter boxes and a 16ft × 6ft redwood wall, "
            "built and installed at 738 Forestdale Avenue, Glendora."
            "</font>",
            ParagraphStyle("pts", fontSize=10, leading=13),
        )
    )
    story.append(Spacer(1, 0.12 * inch))

    # --- Client / PM info row ---
    prep_block = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>PREPARED FOR</b></font><br/><br/>"
        "<b><font size=11 color='#1A2238'>Kelly Marchello</font></b><br/>"
        "<font size=9 color='#0F172A'>"
        "738 Forestdale Avenue<br/>"
        "Glendora, California 91740<br/>"
        "(626) 321-2397"
        "</font>",
        ParagraphStyle("pf", fontSize=9, leading=12.5),
    )
    pm_block = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>PROJECT MANAGER</b></font><br/><br/>"
        "<b><font size=11 color='#1A2238'>Jacob Hayon</font></b><br/>"
        "<font size=9 color='#0F172A'>"
        "Ariel Outdoor Renovation<br/>"
        "Direct: (323) 513-4865<br/>"
        "Office: (818) 390-7639"
        "</font>",
        ParagraphStyle("pm", fontSize=9, leading=12.5),
    )
    info = Table([[prep_block, pm_block]], colWidths=[3.65 * inch, 3.65 * inch])
    info.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("LINEAFTER", (0, 0), (0, 0), 0.5, LINE_DARK),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ]
        )
    )
    story.append(info)
    story.append(Spacer(1, 0.12 * inch))

    # --- Personal note ---
    note = Paragraph(
        "<font color='#0F172A'>"
        "Kelly, thank you for inviting us to your home. Below is the full "
        "estimate for the two planter boxes and the 16ft × 6ft redwood wall "
        "we walked through. Pricing is <b>all-inclusive</b> — the number you "
        "choose is the number you pay. I'll be your single point of contact "
        "from contract signing through final walkthrough."
        "</font>",
        ParagraphStyle("n", fontSize=9.5, leading=13),
    )
    story.append(note)
    story.append(Spacer(1, 0.12 * inch))

    # --- Scope of work table ---
    section_label = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>SCOPE OF WORK</b></font>",
        ParagraphStyle("sl", fontSize=10, leading=12, spaceAfter=4),
    )
    story.append(section_label)

    scope_rows = [
        [
            Paragraph(
                "<b><font color='#A07E4F' size=9>01</font></b>",
                ParagraphStyle("n1", alignment=TA_CENTER, fontSize=9),
            ),
            Paragraph(
                "<b><font size=10 color='#1A2238'>Custom Redwood Planter Boxes (×2)</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "Built to fit your space from premium-grade redwood. Square edges, "
                "mitered corners, sealed seams, and color-matched screws (wood-tone "
                "finish) so fasteners disappear into the grain. Set level and plumb "
                "on the existing concrete patio."
                "</font>",
                ParagraphStyle("r1", fontSize=9, leading=12),
            ),
        ],
        [
            Paragraph(
                "<b><font color='#A07E4F' size=9>02</font></b>",
                ParagraphStyle("n2", alignment=TA_CENTER, fontSize=9),
            ),
            Paragraph(
                "<b><font size=10 color='#1A2238'>Redwood Feature Wall — 16ft × 6ft</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "Horizontal-slat redwood wall, matching the reference photo. "
                "Premium-grade boards, hidden framing, color-matched fasteners "
                "throughout. Tightened, plumbed, sealed at all cut lines, and "
                "inspected before sign-off."
                "</font>",
                ParagraphStyle("r2", fontSize=9, leading=12),
            ),
        ],
        [
            Paragraph(
                "<b><font color='#A07E4F' size=9>03</font></b>",
                ParagraphStyle("n3", alignment=TA_CENTER, fontSize=9),
            ),
            Paragraph(
                "<b><font size=10 color='#1A2238'>Installation, Cleanup &amp; Warranty</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "All anchoring, leveling, and structural fastening on site. End-grain "
                "sealed before installation to lock in color. Daily debris haul-off, "
                "final walkthrough with you, and a <b>1-year workmanship warranty</b> "
                "on everything we install."
                "</font>",
                ParagraphStyle("r3", fontSize=9, leading=12),
            ),
        ],
    ]
    scope = Table(scope_rows, colWidths=[0.55 * inch, 6.75 * inch])
    scope.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE_DARK),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, SOFT]),
            ]
        )
    )
    story.append(scope)
    story.append(Spacer(1, 0.1 * inch))

    # --- Image + reference caption row ---
    if REFERENCE_IMAGE.exists():
        img = Image(
            str(REFERENCE_IMAGE),
            width=2.1 * inch,
            height=2.8 * inch,
            kind="proportional",
        )
        img_cell = img
    else:
        img_cell = Paragraph("[reference]", ParagraphStyle("x", fontSize=9))

    materials = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>MATERIALS &amp; CRAFTSMANSHIP</b></font><br/>"
        "<b><font size=10 color='#1A2238'>Premium Redwood. Hardware You Won't See.</font></b>"
        "<br/><br/>"
        "<font size=8.5 color='#0F172A'>"
        "Every board is hand-selected for color, grain, and weather resistance. "
        "Exposed fasteners are <b>color-matched to the wood tone</b> so the finished "
        "surface reads clean and seamless. Cut edges and end grain are "
        "<b>sealed before installation</b> to slow weathering and lock in color "
        "from day one."
        "</font><br/><br/>"
        "<font size=7.5 color='#A07E4F'><b>WHAT WE SUPPLY</b></font><br/>"
        "<font size=8 color='#0F172A'>"
        "The two planter boxes and the redwood feature wall, fully built and "
        "installed. Reference image shows the finished aesthetic."
        "</font>",
        ParagraphStyle("mat", fontSize=9, leading=11),
    )
    bottom = Table([[img_cell, materials]], colWidths=[2.2 * inch, 5.1 * inch])
    bottom.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (1, 0), (1, 0), CREAM),
                ("BOX", (1, 0), (1, 0), 0.5, ACCENT),
                ("BOX", (0, 0), (0, 0), 0.5, LINE),
            ]
        )
    )
    story.append(bottom)
    story.append(PageBreak())


# -----------------------------------------------------------------------------
# Page 2
# -----------------------------------------------------------------------------
def build_page_2(story):
    section_label = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>INVESTMENT &amp; TERMS</b></font><br/>"
        "<font name='Times-Bold' size=22 color='#1A2238'>Two Material Grades. One Beautiful Result.</font><br/>"
        "<font size=9 color='#475569'>"
        "Same scope, same crew, same workmanship — choose the redwood grade "
        "that fits your goals. Both prices are <b>all-inclusive</b>: labor, "
        "materials, color-matched hardware, equipment, insurance, and taxes."
        "</font>",
        ParagraphStyle("sl", fontSize=10, leading=16),
    )
    story.append(section_label)
    story.append(Spacer(1, 0.14 * inch))

    # --- Two pricing cards ---
    def card(label, name, price, bullets, recommended):
        rec_tag = (
            '<br/><font size=7 color="#A07E4F"><b>★ RECOMMENDED FOR LONGEVITY</b></font>'
            if recommended
            else ""
        )
        header = Paragraph(
            f"<para alignment='center'>"
            f"<font size=7.5 color='#A07E4F'><b>{label}</b></font><br/>"
            f"<b><font size=13 color='#1A2238'>{name}</font></b>"
            f"{rec_tag}"
            f"</para>",
            ParagraphStyle("h", alignment=TA_CENTER, fontSize=9, leading=12),
        )
        price_p = Paragraph(
            f"<para alignment='center'>"
            f"<font name='Times-Bold' size=30 color='#1A2238'>{price}</font><br/>"
            f"<font size=7.5 color='#64748B'>all-inclusive · taxes &amp; insurance covered</font>"
            f"</para>",
            ParagraphStyle("pr", alignment=TA_CENTER, fontSize=9, leading=11),
        )
        bullets_html = "<br/>".join(f"·&nbsp;&nbsp;{b}" for b in bullets)
        bullets_p = Paragraph(
            f"<font size=8.5 color='#0F172A'>{bullets_html}</font>",
            ParagraphStyle("b", fontSize=8.5, leading=12),
        )
        return Table(
            [[header], [price_p], [bullets_p]],
            colWidths=[3.5 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), CREAM if recommended else WHITE),
                    (
                        "BOX",
                        (0, 0),
                        (-1, -1),
                        1.2 if recommended else 0.5,
                        ACCENT if recommended else LINE_DARK,
                    ),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINE),
                    ("LINEBELOW", (0, 1), (-1, 1), 0.4, LINE),
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
            "Longest service life, finest finish",
        ],
        recommended=True,
    )
    opt_b = card(
        "OPTION B",
        "Standard Grade",
        "$6,300",
        [
            "Construction Common Redwood — quality grade",
            "Sound, durable, weather-resistant boards",
            "Minor sound knots permitted (natural look)",
            "Color-matched fasteners throughout",
            "End-grain sealed at all cuts",
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

    # --- Payment schedule ---
    pay_title = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>PAYMENT SCHEDULE</b></font>"
        "&nbsp;&nbsp;<font size=8.5 color='#475569'>"
        "Per California CSLB rules. Down payment capped at the lesser of "
        "10% or $1,000."
        "</font>",
        ParagraphStyle("pt", fontSize=9, leading=12),
    )
    story.append(pay_title)
    story.append(Spacer(1, 0.05 * inch))

    th = lambda s: Paragraph(
        f"<font size=8 color='white'><b>{s}</b></font>",
        ParagraphStyle("th", fontSize=8),
    )
    tc = lambda s: Paragraph(
        f"<font size=8.5 color='#0F172A'>{s}</font>",
        ParagraphStyle("tc", fontSize=8.5, leading=11),
    )
    tcb = lambda s: Paragraph(
        f"<font size=8.5 color='#1A2238'><b>{s}</b></font>",
        ParagraphStyle("tcb", fontSize=8.5, leading=11),
    )

    pay_rows = [
        [th("#"), th("MILESTONE"), th("%"), th("OPTION A · $7,200"), th("OPTION B · $6,300")],
        [tcb("1"), tc("Contract signing (CA-capped down payment)"), tc("10%"), tcb("$720"), tcb("$630")],
        [tcb("2"), tc("Materials delivered, crew mobilized on site"), tc("45%"), tcb("$3,240"), tcb("$2,835")],
        [tcb("3"), tc("Final walkthrough, punch-list closed"), tc("45%"), tcb("$3,240"), tcb("$2,835")],
        [
            Paragraph("", ParagraphStyle("x", fontSize=8)),
            tcb("TOTAL"),
            tcb("100%"),
            tcb("$7,200"),
            tcb("$6,300"),
        ],
    ]
    pay = Table(
        pay_rows,
        colWidths=[0.3 * inch, 3.2 * inch, 0.55 * inch, 1.65 * inch, 1.6 * inch],
    )
    pay.setStyle(
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
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, NAVY),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE_DARK),
                ("BACKGROUND", (0, -1), (-1, -1), SOFT),
                ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, SOFT]),
            ]
        )
    )
    story.append(pay)
    story.append(Spacer(1, 0.14 * inch))

    # --- Why Ariel · Timeline · Next Steps three-column ---
    why = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>WHY ARIEL</b></font><br/><br/>"
        "<font size=8.5 color='#0F172A'>"
        "·&nbsp;&nbsp;CSLB Class B — licensed &amp; in good standing<br/>"
        "·&nbsp;&nbsp;General liability + workers' comp on file<br/>"
        "·&nbsp;&nbsp;Outdoor specialists — wood, hardscape, kitchens<br/>"
        "·&nbsp;&nbsp;1-Year workmanship warranty<br/>"
        "·&nbsp;&nbsp;One point of contact from start to finish"
        "</font>",
        ParagraphStyle("w", fontSize=9, leading=12),
    )
    timeline = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>TIMELINE</b></font><br/><br/>"
        "<b><font size=13 color='#1A2238'>3 – 5 working days</font></b><br/>"
        "<font size=8.5 color='#475569'>"
        "From mobilization to walkthrough. Same timeline for both options; "
        "confirmed at contract signing."
        "</font><br/><br/>"
        "<font size=7.5 color='#A07E4F'><b>NOT INCLUDED</b></font><br/>"
        "<font size=8 color='#0F172A'>"
        "Decorative metal screens · plants · soil · irrigation · concrete · "
        "electrical · stain/paint · HOA fees · permits"
        "</font>",
        ParagraphStyle("t", fontSize=9, leading=12),
    )
    next_steps = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>NEXT STEPS</b></font><br/><br/>"
        "<font size=8.5 color='#0F172A'>"
        "Kelly — call or text me directly at <b>(323) 513-4865</b> to select "
        "an option and we'll schedule the contract signing. The formal "
        "home-improvement contract includes the California Mechanics Lien "
        "Warning, 3-day Right to Cancel, and all CSLB disclosures.<br/><br/>"
        "<b>Jacob Hayon</b><br/>"
        "<i>Project Manager · Ariel Outdoor Renovation</i>"
        "</font>",
        ParagraphStyle("ns", fontSize=9, leading=12),
    )
    three = Table(
        [[why, timeline, next_steps]],
        colWidths=[2.3 * inch, 2.3 * inch, 2.7 * inch],
    )
    three.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("BACKGROUND", (0, 0), (1, 0), SOFT),
                ("BACKGROUND", (2, 0), (2, 0), CREAM),
                ("BOX", (0, 0), (0, 0), 0.5, LINE_DARK),
                ("BOX", (1, 0), (1, 0), 0.5, LINE_DARK),
                ("BOX", (2, 0), (2, 0), 0.6, ACCENT),
            ]
        )
    )
    story.append(three)
    story.append(Spacer(1, 0.16 * inch))

    # --- Signature block ---
    sig_text = Paragraph(
        "<font size=8 color='#475569'><i>"
        "This is an estimate, not a contract. Pricing valid 30 days from the "
        "issue date. A formal home-improvement contract supersedes this "
        "document upon signing."
        "</i></font>",
        ParagraphStyle("st", fontSize=9, leading=11, alignment=TA_CENTER),
    )
    story.append(sig_text)
    story.append(Spacer(1, 0.08 * inch))

    sig_block = Table(
        [
            [
                Paragraph(
                    "<font size=8 color='#64748B'><b>OPTION SELECTED</b></font><br/>"
                    "<font size=10 color='#0F172A'>"
                    "&#9744;&nbsp;&nbsp;Option A · $7,200 &nbsp;&nbsp;&nbsp;&nbsp; "
                    "&#9744;&nbsp;&nbsp;Option B · $6,300"
                    "</font>",
                    ParagraphStyle("o", fontSize=9, leading=14),
                ),
                Paragraph(
                    "<font size=8 color='#64748B'><b>CLIENT SIGNATURE</b></font><br/>"
                    "<font size=10 color='#0F172A'>"
                    "________________________________"
                    "</font>",
                    ParagraphStyle("cs", fontSize=9, leading=14),
                ),
                Paragraph(
                    "<font size=8 color='#64748B'><b>DATE</b></font><br/>"
                    "<font size=10 color='#0F172A'>"
                    "____________________"
                    "</font>",
                    ParagraphStyle("d", fontSize=9, leading=14),
                ),
            ],
        ],
        colWidths=[2.8 * inch, 2.8 * inch, 1.7 * inch],
    )
    sig_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("BOX", (0, 0), (-1, -1), 0.7, NAVY),
                ("LINEAFTER", (0, 0), (0, 0), 0.3, LINE),
                ("LINEAFTER", (1, 0), (1, 0), 0.3, LINE),
            ]
        )
    )
    story.append(sig_block)


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
        title="Project Estimate — Marchello Residence",
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
