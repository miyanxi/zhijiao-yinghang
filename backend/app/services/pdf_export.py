from io import BytesIO
import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


FONT_CANDIDATES = [
    Path(os.getenv("PDF_CJK_FONT", "C:/Windows/Fonts/simhei.ttf")),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
]
FONT_PATH = next((path for path in FONT_CANDIDATES if path.is_file()), None)
FONT_NAME = "Chinese"
try:
    if FONT_PATH is None:
        raise OSError("没有找到可嵌入的中文字体")
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
except Exception:
    FONT_NAME = "STSong-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))

TITLE = ParagraphStyle("title", fontName=FONT_NAME, fontSize=18, leading=26, alignment=TA_CENTER, spaceAfter=15)
SUBTITLE = ParagraphStyle("subtitle", fontName=FONT_NAME, fontSize=12, leading=18, textColor=colors.HexColor("#216b72"), spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle("body", fontName=FONT_NAME, fontSize=10, leading=16, spaceAfter=5, wordWrap="CJK")
META = ParagraphStyle("meta", parent=BODY, fontSize=9, textColor=colors.HexColor("#60777a"))


def paragraph(value: str, style: ParagraphStyle = BODY) -> Paragraph:
    return Paragraph(escape(value).replace("\n", "<br/>"), style)


def render_pdf(title: str, blocks: list[tuple[str, str]]) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=45, bottomMargin=45)
    story = [paragraph(title, TITLE)]
    for kind, value in blocks:
        story.append(paragraph(value, {"heading": SUBTITLE, "meta": META}.get(kind, BODY)))
        if kind == "heading":
            story.append(Spacer(1, 4))
    document.build(story)
    return output.getvalue()
