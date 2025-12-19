"""
Generador de PDF para la sesión 3.4 usando reportlab.

- Toma el texto final (Judge) y las rutas de imágenes por ticker.
- Inserta portada, informe y gráficas por ticker.
- Limpia caracteres fuera de latin-1 convirtiéndolos a ASCII aproximado.
"""

from __future__ import annotations

import os
import unicodedata
from datetime import datetime
from typing import Dict, List
import re

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
)


def _ascii_safe(text: str) -> str:
    # Normaliza y elimina caracteres fuera de ASCII
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _paragraphs_from_text(
    text: str,
    body_style: ParagraphStyle,
    heading1: ParagraphStyle,
    heading2: ParagraphStyle,
    heading3: ParagraphStyle,
    body_bullet: ParagraphStyle,
) -> List[Paragraph]:
    paras: List[Paragraph] = []
    for block in text.split("\n"):
        block = block.strip()
        if not block:
            continue
        block = _ascii_safe(block)
        # Línea separadora Markdown
        if block.strip("-") == "":
            paras.append(Spacer(1, 0.05 * inch))
            continue
        # Bold inline **texto**
        block = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", block)
        # Heading Markdown
        if block.startswith("###"):
            paras.append(Paragraph(f"<b>{block.lstrip('#').strip()}</b>", heading3))
            continue
        if block.startswith("##"):
            paras.append(Paragraph(f"<b>{block.lstrip('#').strip()}</b>", heading2))
            continue
        if block.startswith("#"):
            paras.append(Paragraph(f"<b>{block.lstrip('#').strip()}</b>", heading1))
            continue
        # Bullets
        if block.startswith(("-", "*")):
            paras.append(Paragraph(_ascii_safe(block[1:].strip()), body_bullet))
            continue
        if block[:2].isdigit() and block[1:2] == ".":
            paras.append(Paragraph(_ascii_safe(block[2:].strip()), body_bullet))
            continue
        paras.append(Paragraph(block, body_style))
    return paras


def _safe_image(path: str, max_width: float = 6.5 * inch) -> Image | None:
    if not os.path.exists(path):
        return None
    try:
        img = Image(path)
        # Escalar manteniendo proporción
        w, h = img.wrap(0, 0)
        if w > max_width:
            scale = max_width / w
            img.drawWidth = w * scale
            img.drawHeight = h * scale
        return img
    except Exception:
        return None


def create_pdf_report(
    tickers: List[str],
    final_text: str,
    images_by_ticker: Dict[str, List[str]],
    output_dir: str,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"report_{'_'.join(tickers)}_{ts}.pdf"
    path = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        path,
        pagesize=LETTER,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    body_style = styles["BodyText"]
    body_style.fontName = "Helvetica"
    body_style.fontSize = 10
    body_style.leading = 13
    body_bullet = ParagraphStyle(
        "BodyBullet",
        parent=body_style,
        leftIndent=12,
        bulletIndent=0,
        bulletFontName="Helvetica",
        bulletFontSize=10,
        bulletAnchor="start",
        spaceBefore=2,
        spaceAfter=2,
    )
    title_style = styles["Title"]
    title_style.fontName = "Helvetica-Bold"
    heading1 = styles["Heading1"]
    heading1.fontName = "Helvetica-Bold"
    heading1.fontSize = 14
    heading1.leading = 16
    heading2 = styles["Heading2"]
    heading2.fontName = "Helvetica-Bold"
    heading2.fontSize = 12
    heading2.leading = 14
    heading3 = styles["Heading3"]
    heading3.fontName = "Helvetica-Bold"
    heading3.fontSize = 11
    heading3.leading = 13

    story: List = []

    # Portada
    story.append(Paragraph("Informe de Análisis de Acciones", title_style))
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(f"Tickers: {', '.join(tickers)}", heading2))
    story.append(Paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Este informe es educativo y no constituye recomendación de inversión.", body_style))
    story.append(PageBreak())

    # Informe del Judge
    story.append(Paragraph("Informe", heading1))
    story.append(Spacer(1, 0.15 * inch))
    for para in _paragraphs_from_text(final_text, body_style, heading1, heading2, heading3, body_bullet):
        story.append(para)
        story.append(Spacer(1, 0.05 * inch))

    # Imágenes por ticker
    for ticker in tickers:
        imgs = images_by_ticker.get(ticker) or []
        if not imgs:
            continue
        story.append(PageBreak())
        story.append(Paragraph(f"Gráficas {ticker}", heading2))
        story.append(Spacer(1, 0.1 * inch))
        for img_path in imgs:
            img_obj = _safe_image(img_path)
            if img_obj is None:
                continue
            story.append(img_obj)
            story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    return path
