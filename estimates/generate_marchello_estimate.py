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
            "<font name='Times-Bold' size=26 color='#1A2238'>Backyard Redwood Feature</font>",
            ParagraphStyle("pth", fontSize=26, leading=30, spaceAfter=2),
        )
    )
    story.append(
        Paragraph(
            "<font size=10 color='#475569'>"
            "738 Forestdale Avenue, Glendora, CA 91740"
            "</font>",
            ParagraphStyle("pts", fontSize=10, leading=13),
        )
    )
    story.append(Spacer(1, 0.14 * inch))

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
        "Kelly — thanks for having us out. Below is the estimate for the two "
        "planter boxes and the 16ft × 6ft redwood wall we walked through. "
        "Both prices cover everything: labor, materials, hardware, taxes, and "
        "insurance. Any questions, my direct number is above."
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
                "<b><font size=10 color='#1A2238'>Redwood Planter Boxes (×2)</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "Two planter boxes built on site from redwood. Square edges, mitered "
                "corners, sealed seams, and color-matched screws. Set level on the "
                "existing concrete patio."
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
                "<b><font size=10 color='#1A2238'>Redwood Wall — 16ft × 6ft</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "Horizontal-slat redwood wall, matching the reference photo. Hidden "
                "framing, color-matched screws, cut lines sealed before install. "
                "Plumbed and tightened before sign-off."
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
                "<b><font size=10 color='#1A2238'>Install, Cleanup &amp; 1-Year Warranty</font></b><br/>"
                "<font size=8.5 color='#0F172A'>"
                "All anchoring and fastening done on site. Daily cleanup, final "
                "walkthrough with you, and a 1-year warranty on our workmanship."
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
        "<font size=7.5 color='#A07E4F'><b>MATERIALS</b></font><br/><br/>"
        "<font size=9 color='#0F172A'>"
        "Boards are picked on site for color, grain, and weather resistance. "
        "Screws are color-matched to the wood tone so the finished surface "
        "stays clean — no silver heads showing. Cut ends and end grain are "
        "sealed before install to slow weathering."
        "</font><br/><br/>"
        "<font size=7.5 color='#A07E4F'><b>SCOPE</b></font><br/>"
        "<font size=9 color='#0F172A'>"
        "We build and install the two planter boxes and the 16ft × 6ft redwood "
        "wall. The reference photo shows the finished look we're matching."
        "</font>",
        ParagraphStyle("mat", fontSize=9, leading=12),
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
        "<font size=7.5 color='#A07E4F'><b>PRICING</b></font><br/>"
        "<font name='Times-Bold' size=24 color='#1A2238'>Two Options</font><br/>"
        "<font size=9.5 color='#475569'>"
        "Same scope and same crew either way — just two redwood grades to "
        "choose from. Both prices below cover labor, materials, hardware, "
        "taxes, and insurance."
        "</font>",
        ParagraphStyle("sl", fontSize=10, leading=16),
    )
    story.append(section_label)
    story.append(Spacer(1, 0.14 * inch))

    # --- Two pricing cards ---
    def card(label, name, price, bullets, recommended):
        rec_tag = (
            '<br/><font size=7.5 color="#A07E4F"><b>OUR RECOMMENDATION</b></font>'
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
        "Clear Heart Redwood",
        "$7,200",
        [
            "Top grade — Clear All-Heart Redwood",
            "Hand-picked boards, uniform grain",
            "Virtually knot-free",
            "Stainless color-matched screws",
            "End grain and cut lines fully sealed",
            "Holds color and finish the longest",
        ],
        recommended=True,
    )
    opt_b = card(
        "OPTION B",
        "Construction Common Redwood",
        "$6,300",
        [
            "Construction Common grade redwood",
            "Sound, weather-resistant boards",
            "Some small knots (natural look)",
            "Color-matched screws throughout",
            "End grain sealed at cuts",
            "Solid value, holds up well outdoors",
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
        "<font size=7.5 color='#A07E4F'><b>WHO WE ARE</b></font><br/><br/>"
        "<font size=9 color='#0F172A'>"
        "·&nbsp;&nbsp;CSLB Class B licensed &amp; bonded<br/>"
        "·&nbsp;&nbsp;General liability + workers' comp<br/>"
        "·&nbsp;&nbsp;We only do outdoor work<br/>"
        "·&nbsp;&nbsp;1-year warranty on workmanship<br/>"
        "·&nbsp;&nbsp;One point of contact start to finish"
        "</font>",
        ParagraphStyle("w", fontSize=9, leading=13),
    )
    timeline = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>TIMELINE</b></font><br/><br/>"
        "<b><font size=13 color='#1A2238'>3 – 5 working days</font></b><br/>"
        "<font size=8.5 color='#475569'>"
        "From start to walkthrough. Confirmed at contract signing."
        "</font><br/><br/>"
        "<font size=7.5 color='#A07E4F'><b>NOT INCLUDED</b></font><br/>"
        "<font size=8.5 color='#0F172A'>"
        "Metal screens · plants · soil · irrigation · concrete · electrical · "
        "stain · paint · HOA fees · permits"
        "</font>",
        ParagraphStyle("t", fontSize=9, leading=12),
    )
    next_steps = Paragraph(
        "<font size=7.5 color='#A07E4F'><b>NEXT STEP</b></font><br/><br/>"
        "<font size=9 color='#0F172A'>"
        "Kelly — call or text me at <b>(323) 513-4865</b> to pick an option "
        "and we'll set up the contract signing. The contract itself covers "
        "the Mechanics Lien Warning, 3-day Right to Cancel, and the rest of "
        "the CSLB disclosures."
        "</font><br/><br/>"
        "<font size=9 color='#0F172A'><b>Jacob Hayon</b><br/>"
        "<i>Project Manager · Ariel Outdoor Renovation</i></font>",
        ParagraphStyle("ns", fontSize=9, leading=13),
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
    story.append(Spacer(1, 0.18 * inch))

    disclaimer = Paragraph(
        "<font size=8.5 color='#64748B'><i>"
        "This is an estimate, not a contract. Pricing is valid 30 days from "
        "the issue date. A formal home-improvement contract will be provided "
        "for signing once an option is selected."
        "</i></font>",
        ParagraphStyle("st", fontSize=9, leading=11.5, alignment=TA_CENTER),
    )
    story.append(disclaimer)


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
