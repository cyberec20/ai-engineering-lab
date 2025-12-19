# -*- coding: utf-8 -*-
"""
RAG Markdown Converter (DOCX/PDF → MD) - GUI v10

Cambios vs v6:
- PDF: usa PyMuPDF (fitz) como motor principal (mejor orden/columnas/heading por font-size).
- PDF: usa pdfplumber SOLO para tablas (best-effort) y las inserta en el flujo.
- Mantiene: GUI simple + modo CLI.
- Opcional: Compresión lossless de PDF con pikepdf.

Instalación (mínimo):
    pip install python-docx pymupdf pdfplumber pandas tabulate

Opcional (botón "Comprimir PDF"):
    pip install pikepdf
"""

import os
import re
import sys
import math
import statistics
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Word (.docx)
import docx
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph
from docx.table import Table

# PDF engines
import pdfplumber
import pandas as pd

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

# UI
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


# ---------------- Word helpers ----------------
def iter_block_items(doc):
    """Genera cada párrafo o tabla de un documento Word en el orden original."""
    body = doc.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def convert_docx_to_markdown(docx_path: str, md_path: str) -> List[str]:
    doc = docx.Document(docx_path)
    md_lines: List[str] = []
    header_counts = [0] * 6  # hasta 6 niveles

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text == "":
                if md_lines and md_lines[-1] != "":
                    md_lines.append("")
                continue

            style = block.style.name if block.style else ""

            if style.startswith("Heading"):
                try:
                    level = int(style.split()[-1])
                except Exception:
                    level = 1
                level = max(1, min(level, len(header_counts)))

                header_counts[level - 1] += 1
                for i in range(level, len(header_counts)):
                    header_counts[i] = 0

                number_parts = []
                for i in range(level):
                    if header_counts[i] == 0:
                        break
                    number_parts.append(str(header_counts[i]))
                num_str = ".".join(number_parts)
                if level == 1 and not num_str.endswith("."):
                    num_str += "."

                md_lines.append(("#" * level) + " " + num_str + " " + text)

            elif style.startswith("List") or style in ("List Paragraph", "Lista con viñetas"):
                md_lines.append(f"- {text}")

            else:
                md_lines.append(text)

        elif isinstance(block, Table):
            rows = []
            for row in block.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                rows.append(cells)
            if not rows:
                continue

            num_cols = max(len(r) for r in rows)
            for r in rows:
                if len(r) < num_cols:
                    r.extend([""] * (num_cols - len(r)))

            header_cells = [hc if hc != "" else " " for hc in rows[0]]
            md_lines.append("| " + " | ".join(header_cells) + " |")
            md_lines.append("|" + "|".join([" --- " for _ in range(num_cols)]) + "|")

            for data_row in rows[1:]:
                data_cells = [dc if dc != "" else " " for dc in data_row]
                md_lines.append("| " + " | ".join(data_cells) + " |")

            md_lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    return md_lines


# ---------------- PDF (PyMuPDF primary + pdfplumber tables) ----------------
@dataclass
class PdfItem:
    kind: str               # 'line' | 'table'
    text: str
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    size: Optional[float] = None
    col: int = 0            # 0=left, 1=right (si 2 columnas)


def _safe_median(values: List[float]) -> Optional[float]:
    vals = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s{2,}", " ", s).strip()


def _merge_wrapped_lines(lines: List[str]) -> List[str]:
    """Une líneas partidas por wrap + corrige guionización (heurística para RAG)."""
    merged: List[str] = []
    i = 0

    def ends_sentence(x: str) -> bool:
        return bool(re.search(r"[.!?:;]\s*$", x))

    bullet_like = re.compile(r'^[\-\u2022\u00B7\u25E6\u25AA\u25CF\u2219]\s+')
    numbered_like = re.compile(r'^\(?\d+\)?[.)]\s+')
    header_numbered = re.compile(r'^(\d+(?:\.\d+)*)(?:\.)?\s+(.+)')

    while i < len(lines):
        s = (lines[i] or "").rstrip()
        if s == "":
            merged.append("")
            i += 1
            continue

        out = s
        j = i
        while j + 1 < len(lines):
            nxt = (lines[j + 1] or "").lstrip()
            if nxt == "":
                break

            if bullet_like.match(nxt) or numbered_like.match(nxt) or header_numbered.match(nxt):
                break

            if out.endswith("-") and re.match(r"^[a-záéíóúñ]", nxt):
                out = out[:-1] + nxt
                j += 1
                continue

            if (not ends_sentence(out)) and re.match(r"^[a-záéíóúñ(]", nxt):
                out = out + " " + nxt
                j += 1
                continue

            if len(out) <= 60 and len(nxt) <= 60 and (not ends_sentence(out)):
                out = out + " " + nxt
                j += 1
                continue

            break

        merged.append(_normalize_spaces(out))
        i = j + 1

    return merged


def _heading_level_from_font(line_size: Optional[float], body_size: Optional[float]) -> Optional[int]:
    if line_size is None or body_size is None or body_size <= 0:
        return None
    ratio = line_size / body_size
    if ratio >= 1.55:
        return 1
    if ratio >= 1.30:
        return 2
    if ratio >= 1.18:
        return 3
    return None


def _is_underline(line: str) -> bool:
    s = (line or "").strip()
    return bool(re.fullmatch(r"[_\-=]{5,}", s))


def _detect_two_columns(x0s: List[float], page_width: float) -> Tuple[bool, float, float]:
    xs = [x for x in x0s if isinstance(x, (int, float))]
    if len(xs) < 40:
        return (False, 0.0, 0.0)

    xs_sorted = sorted(xs)
    sample = xs_sorted[:: max(1, len(xs_sorted)//200)]
    if len(sample) < 20:
        sample = xs_sorted

    c1 = sample[len(sample)//5]
    c2 = sample[(len(sample)*4)//5]
    if abs(c2 - c1) < page_width * 0.20:
        return (False, 0.0, 0.0)

    for _ in range(12):
        g1, g2 = [], []
        for x in sample:
            if abs(x - c1) <= abs(x - c2):
                g1.append(x)
            else:
                g2.append(x)
        if not g1 or not g2:
            return (False, 0.0, 0.0)
        nc1 = sum(g1) / len(g1)
        nc2 = sum(g2) / len(g2)
        if abs(nc1 - c1) < 0.5 and abs(nc2 - c2) < 0.5:
            break
        c1, c2 = nc1, nc2

    left, right = (c1, c2) if c1 < c2 else (c2, c1)
    sep = right - left
    if sep < page_width * 0.28:
        return (False, 0.0, 0.0)

    n_left = sum(1 for x in xs if abs(x - left) <= abs(x - right))
    n_right = len(xs) - n_left
    if min(n_left, n_right) / max(n_left, n_right) < 0.22:
        return (False, 0.0, 0.0)

    return (True, left, right)


def _extract_tables_pdfplumber(page_plumber) -> List[PdfItem]:
    items: List[PdfItem] = []
    try:
        tables = page_plumber.find_tables()
    except Exception:
        tables = []

    for table in tables or []:
        try:
            data = table.extract()
        except Exception:
            continue
        if not data:
            continue

        max_cols = max((len(r) for r in data if r), default=0)
        if len(data) < 2 or max_cols < 2:
            continue

        df = pd.DataFrame(data)
        if df.shape[0] > 1:
            df.columns = df.iloc[0]
            df_body = df.iloc[1:]
        else:
            df_body = df

        try:
            md_table = df_body.to_markdown(index=False)
        except Exception:
            md_table = "\n".join(["\t".join(str(x) for x in row) for row in df_body.values.tolist()])

        bbox = table.bbox  # (x0, top, x1, bottom)
        x0, top, x1, bottom = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        items.append(PdfItem(kind="table", text=md_table, bbox=(x0, top, x1, bottom), size=None, col=0))

    return items


def _bbox_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    area_a = max(1e-6, (ax1 - ax0) * (ay1 - ay0))
    return inter / area_a


def _extract_lines_pymupdf(page) -> List[PdfItem]:
    textdict = page.get_text("dict")
    items: List[PdfItem] = []
    for b in textdict.get("blocks", []) or []:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []) or []:
            spans = line.get("spans", []) or []
            texts = []
            sizes = []
            for sp in spans:
                t = sp.get("text", "")
                if t:
                    texts.append(t)
                sz = sp.get("size")
                if isinstance(sz, (int, float)):
                    sizes.append(float(sz))
            text = _normalize_spaces("".join(texts))
            if not text:
                continue
            bbox = line.get("bbox") or b.get("bbox")
            if not bbox:
                continue
            x0, y0, x1, y1 = map(float, bbox)
            size_med = _safe_median(sizes)
            items.append(PdfItem(kind="line", text=text, bbox=(x0, y0, x1, y1), size=size_med, col=0))
    return items


def convert_pdf_to_markdown(pdf_path: str, md_path: str) -> Tuple[List[str], dict]:
    if fitz is None:
        md_lines = _convert_pdf_to_markdown_pdfplumber_fallback(pdf_path, md_path)
        return md_lines, {"engine": "pdfplumber_fallback", "two_columns": False}

    doc = fitz.open(pdf_path)
    plumber = pdfplumber.open(pdf_path)

    md_lines: List[str] = []
    header_pattern = re.compile(r'^(\d+(?:\.\d+)*)(?:\.)?\s+(.+)')
    prev_header_num = None

    chapter_re = re.compile(r'^(chapter|cap[ií]tulo)\s+\d+\s*:?\s*(.+)$', re.IGNORECASE)
    toc_re = re.compile(r'^(table of contents|contenido|índice)\s*$', re.IGNORECASE)

    meta = {"engine": "pymupdf+pdfplumber_tables", "two_columns_pages": 0, "pages": doc.page_count}

    for i in range(doc.page_count):
        page = doc[i]
        ppage = plumber.pages[i] if i < len(plumber.pages) else None

        page_w = float(page.rect.width)
        page_h = float(page.rect.height)

        header_cut = page_h * 0.08
        footer_cut = page_h * 0.92

        table_items: List[PdfItem] = []
        if ppage is not None:
            table_items = _extract_tables_pdfplumber(ppage)

        line_items = _extract_lines_pymupdf(page)

        line_items = [it for it in line_items if not (it.bbox[3] <= header_cut or it.bbox[1] >= footer_cut)]
        table_items = [it for it in table_items if not (it.bbox[3] <= header_cut or it.bbox[1] >= footer_cut)]

        if not line_items and not table_items:
            continue

        if table_items:
            filtered_lines = []
            for it in line_items:
                if any(_bbox_overlap(it.bbox, tb.bbox) > 0.55 for tb in table_items):
                    continue
                filtered_lines.append(it)
            line_items = filtered_lines

        body_size = _safe_median([it.size for it in line_items if it.size])

        x0s = [it.bbox[0] for it in line_items]
        two_col, c_left, c_right = _detect_two_columns(x0s, page_w)
        if two_col:
            meta["two_columns_pages"] += 1

        def assign_col(it: PdfItem) -> int:
            if not two_col:
                return 0
            x = it.bbox[0]
            return 0 if abs(x - c_left) <= abs(x - c_right) else 1

        for it in line_items:
            it.col = assign_col(it)
        for tb in table_items:
            tb.col = assign_col(tb)

        items_all: List[PdfItem] = line_items + table_items
        if two_col:
            items_all.sort(key=lambda it: (it.col, it.bbox[1], it.bbox[0]))
        else:
            items_all.sort(key=lambda it: (it.bbox[1], it.bbox[0]))

        page_lines_raw: List[str] = []
        for it in items_all:
            if it.kind == "table":
                page_lines_raw.append("")
                for row in it.text.strip("\n").splitlines():
                    page_lines_raw.append(row.rstrip())
                page_lines_raw.append("")
            else:
                t = (it.text or "").strip()
                if t:
                    page_lines_raw.append(t)

        page_lines = _merge_wrapped_lines(page_lines_raw)

        bullet_re = re.compile(r'^[\-\u2022\u00B7\u25E6\u25AA\u25CF\u2219]\s+')
        numbered_list_re = re.compile(r'^\(?\d+\)?[.)]\s+')

        size_lookup = {}
        for it in line_items:
            if it.text:
                size_lookup.setdefault(it.text.strip(), it.size)

        pending_prev = None

        for line in page_lines:
            stripped = (line or "").strip()
            if stripped == "":
                if md_lines and md_lines[-1] != "":
                    md_lines.append("")
                pending_prev = None
                continue

            if _is_underline(stripped) and pending_prev:
                prev = pending_prev
                if not prev.startswith("#"):
                    md_lines.append("## " + prev)
                pending_prev = None
                continue

            m = header_pattern.match(stripped)
            if m:
                header_num = m.group(1)
                header_text = m.group(2)
                if header_text.strip().lower().endswith("(continued)"):
                    pending_prev = None
                    continue
                if header_num == prev_header_num:
                    pending_prev = None
                    continue
                prev_header_num = header_num

                level = min(max(header_num.count(".") + 1, 1), 6)
                num_str = header_num
                if level == 1 and not num_str.endswith("."):
                    num_str += "."
                md_lines.append(("#" * level) + " " + num_str + " " + header_text.replace("(continued)", "").strip())
                pending_prev = None
                continue

            mc = chapter_re.match(stripped)
            if mc:
                title = mc.group(2).strip() or stripped
                md_lines.append("## " + title)
                pending_prev = None
                continue

            if toc_re.match(stripped):
                md_lines.append("# " + stripped)
                pending_prev = None
                continue

            if bullet_re.match(stripped):
                cleaned = bullet_re.sub("", stripped)
                md_lines.append(f"- {cleaned}")
                pending_prev = None
                continue

            if numbered_list_re.match(stripped):
                cleaned = numbered_list_re.sub("", stripped)
                md_lines.append(f"1. {cleaned}")
                pending_prev = None
                continue

            size = size_lookup.get(stripped)
            lvl = _heading_level_from_font(size, body_size)
            looks_like_title = (len(stripped) <= 80 and stripped.isupper())
            if lvl is not None or looks_like_title:
                lvl = lvl if lvl is not None else 2
                md_lines.append(("#" * lvl) + " " + stripped)
                pending_prev = None
                continue

            md_lines.append(stripped)
            pending_prev = stripped

        if md_lines and md_lines[-1] != "":
            md_lines.append("")

    plumber.close()
    doc.close()

    while md_lines and md_lines[-1] == "":
        md_lines.pop()

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    meta["two_columns"] = meta["two_columns_pages"] > 0
    return md_lines, meta


def _convert_pdf_to_markdown_pdfplumber_fallback(pdf_path: str, md_path: str) -> List[str]:
    pdf = pdfplumber.open(pdf_path)
    md_lines: List[str] = []
    header_pattern = re.compile(r'^(\d+(?:\.\d+)*)(?:\.)?\s+(.+)')
    prev_header_num = None

    for page in pdf.pages:
        chars = list(page.chars)

        tables = page.find_tables()
        chars_without_tables = chars
        virtual_chars = []

        for table in tables:
            bbox = table.bbox
            data = table.extract()
            if not data:
                continue

            df = pd.DataFrame(data)
            if df.shape[0] > 1:
                df.columns = df.iloc[0]
                df_body = df.iloc[1:]
            else:
                df_body = df

            md_table = df_body.to_markdown(index=False)

            table_chars_bbox = []
            for c in chars_without_tables:
                x0, x1 = c.get("x0", 0), c.get("x1", 0)
                top, bottom = c.get("top", 0), c.get("bottom", 0)
                if x0 >= bbox[0] and x1 <= bbox[2] and top >= bbox[1] and bottom <= bbox[3]:
                    table_chars_bbox.append(c)

            if table_chars_bbox:
                template_char = table_chars_bbox[0].copy()
                template_char["text"] = "\n" + md_table + "\n"
                virtual_chars.append(template_char)

            new_chars = []
            for c in chars_without_tables:
                x0, x1 = c.get("x0", 0), c.get("x1", 0)
                top, bottom = c.get("top", 0), c.get("bottom", 0)
                if x0 >= bbox[0] and x1 <= bbox[2] and top >= bbox[1] and bottom <= bbox[3]:
                    continue
                new_chars.append(c)
            chars_without_tables = new_chars

        chars = chars_without_tables + virtual_chars

        page_height = page.height
        header_cut = page_height * 0.08
        footer_cut = page_height * 0.92

        filtered_chars = []
        for c in chars:
            top, bottom = c.get("top", 0), c.get("bottom", 0)
            if bottom <= header_cut:
                continue
            if top >= footer_cut:
                continue
            filtered_chars.append(c)

        if not filtered_chars:
            continue

        page_text = pdfplumber.utils.extract_text(filtered_chars, layout=True)
        if not page_text:
            continue

        for raw_line in page_text.splitlines():
            stripped = raw_line.strip()
            if stripped == "":
                if md_lines and md_lines[-1] != "":
                    md_lines.append("")
                continue

            m = header_pattern.match(stripped)
            if m:
                header_num = m.group(1)
                header_text = m.group(2)
                if header_text.strip().lower().endswith("(continued)"):
                    continue
                if header_num == prev_header_num:
                    continue
                prev_header_num = header_num

                level = min(max(header_num.count(".") + 1, 1), 6)
                num_str = header_num
                if level == 1 and not num_str.endswith("."):
                    num_str += "."
                md_lines.append(("#" * level) + " " + num_str + " " + header_text.replace("(continued)", "").strip())
                continue

            if re.match(r'^[\-\u2022]\s+', stripped):
                cleaned = re.sub(r'^[\-\u2022]\s+', "", stripped)
                md_lines.append(f"- {cleaned}")
                continue

            if re.match(r'^\d+\.\s+', stripped):
                cleaned = re.sub(r'^\d+\.\s+', "", stripped)
                md_lines.append(f"1. {cleaned}")
                continue

            md_lines.append(stripped)

    pdf.close()
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    return md_lines


# ---------------- PDF compression (lossless) ----------------
def compress_pdf_lossless(input_pdf: str, output_pdf: str) -> Tuple[int, int]:
    """Compresión lossless. Requiere: pip install pikepdf"""
    import pikepdf
    in_size = os.path.getsize(input_pdf)
    with pikepdf.open(input_pdf) as pdf:
        pdf.save(
            output_pdf,
            optimize_streams=True,
            compress_streams=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
    out_size = os.path.getsize(output_pdf)
    return in_size, out_size


# ---------------- Dispatcher ----------------
def convert_any_to_md(input_path: str, output_path: str):
    low = input_path.lower()
    if low.endswith(".docx"):
        lines = convert_docx_to_markdown(input_path, output_path)
        return {"engine": "docx"}, lines
    if low.endswith(".pdf"):
        lines, meta = convert_pdf_to_markdown(input_path, output_path)
        return meta, lines
    raise ValueError("Formato no soportado. Use .docx o .pdf.")


# ---------------- UI ----------------
def run_gui():
    root = tk.Tk()
    root.title("RAG Markdown Converter (DOCX/PDF → MD) - v10")
    root.geometry("900x580")

    input_var = tk.StringVar()
    output_var = tk.StringVar()

    def log(msg: str):
        console.configure(state="normal")
        console.insert("end", msg + "\n")
        console.see("end")
        console.configure(state="disabled")

    def pick_input():
        path = filedialog.askopenfilename(
            title="Selecciona documento de entrada",
            filetypes=[("Documentos", "*.docx *.pdf"), ("Word", "*.docx"), ("PDF", "*.pdf")],
        )
        if not path:
            return
        input_var.set(path)
        base = os.path.splitext(os.path.basename(path))[0]
        suggested = os.path.join(os.path.dirname(path), f"{base}.md")
        output_var.set(suggested)
        log(f"Entrada: {path}")
        log(f"Sugerido: {suggested}")

    def pick_output():
        initial = output_var.get().strip() or ""
        init_dir = os.path.dirname(initial) if initial else os.getcwd()
        init_file = os.path.basename(initial) if initial else "salida.md"

        path = filedialog.asksaveasfilename(
            title="Guardar Markdown como...",
            defaultextension=".md",
            initialdir=init_dir,
            initialfile=init_file,
            filetypes=[("Markdown", "*.md")],
        )
        if not path:
            return
        if not path.lower().endswith(".md"):
            path += ".md"
        output_var.set(path)
        log(f"Salida: {path}")

    def generate():
        in_path = input_var.get().strip()
        out_path = output_var.get().strip()

        if not in_path:
            messagebox.showerror("Falta entrada", "Selecciona un archivo .docx o .pdf.")
            return
        if not os.path.isfile(in_path):
            messagebox.showerror("Entrada inválida", "El archivo de entrada no existe.")
            return

        if not out_path:
            base = os.path.splitext(os.path.basename(in_path))[0]
            out_path = os.path.join(os.path.dirname(in_path), f"{base}.md")
            output_var.set(out_path)

        try:
            log("Convirtiendo...")
            meta, _ = convert_any_to_md(in_path, out_path)
            if meta:
                log(f"Engine: {meta.get('engine')}")
                if meta.get("engine") == "pymupdf+pdfplumber_tables":
                    log(f"PDF: 2 columnas detectadas en {meta.get('two_columns_pages', 0)}/{meta.get('pages', 0)} páginas.")
                if meta.get("engine") == "pdfplumber_fallback":
                    log("Aviso: PyMuPDF no está instalado; usando fallback pdfplumber.")
            log("✅ Listo.")
            messagebox.showinfo("Éxito", f"Markdown generado:\n{out_path}")
        except Exception as e:
            log(f"❌ Error: {e}")
            messagebox.showerror("Error", str(e))

    def compress_pdf_ui():
        in_path = input_var.get().strip()
        if not in_path:
            messagebox.showerror("Falta entrada", "Selecciona un PDF para comprimir.")
            return
        if not os.path.isfile(in_path):
            messagebox.showerror("Entrada inválida", "El archivo de entrada no existe.")
            return
        if not in_path.lower().endswith(".pdf"):
            messagebox.showerror("Formato", "La compresión aplica solo a PDF.")
            return

        base = os.path.splitext(os.path.basename(in_path))[0]
        suggested = os.path.join(os.path.dirname(in_path), f"{base}_compressed.pdf")

        out_path = filedialog.asksaveasfilename(
            title="Guardar PDF comprimido como...",
            defaultextension=".pdf",
            initialdir=os.path.dirname(suggested),
            initialfile=os.path.basename(suggested),
            filetypes=[("PDF", "*.pdf")],
        )
        if not out_path:
            return

        try:
            log("Comprimiendo PDF (lossless)...")
            in_b, out_b = compress_pdf_lossless(in_path, out_path)
            log(f"✅ Listo. {in_b/1024/1024:.2f} MB → {out_b/1024/1024:.2f} MB")
            messagebox.showinfo("Éxito", f"PDF comprimido:\n{out_path}")
        except ImportError:
            log("❌ Falta dependencia: pikepdf")
            messagebox.showerror("Falta dependencia", "Instala: pip install pikepdf")
        except Exception as e:
            log(f"❌ Error compresión: {e}")
            messagebox.showerror("Error", str(e))

    frm = tk.Frame(root, padx=12, pady=12)
    frm.pack(fill="both", expand=True)

    tk.Label(frm, text="Archivo de entrada (DOCX o PDF):").grid(row=0, column=0, sticky="w")
    tk.Entry(frm, textvariable=input_var, width=90).grid(row=1, column=0, sticky="we", pady=(2, 8))
    tk.Button(frm, text="Buscar…", command=pick_input, width=14).grid(row=1, column=1, padx=(8, 0))

    tk.Label(frm, text="Salida Markdown (.md):").grid(row=2, column=0, sticky="w")
    tk.Entry(frm, textvariable=output_var, width=90).grid(row=3, column=0, sticky="we", pady=(2, 8))
    tk.Button(frm, text="Guardar como…", command=pick_output, width=14).grid(row=3, column=1, padx=(8, 0))

    btns = tk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=2, sticky="w", pady=(2, 10))
    tk.Button(btns, text="Generar", command=generate, height=2, width=18).pack(side="left")
    tk.Button(btns, text="Comprimir PDF", command=compress_pdf_ui, height=2, width=18).pack(side="left", padx=(10, 0))
    tk.Button(btns, text="Salir", command=root.destroy, height=2, width=10).pack(side="left", padx=(10, 0))

    console = ScrolledText(frm, height=18)
    console.grid(row=5, column=0, columnspan=2, sticky="nsew")
    console.configure(state="disabled")

    frm.grid_columnconfigure(0, weight=1)
    frm.grid_rowconfigure(5, weight=1)

    if fitz is None:
        log("⚠ PyMuPDF no está instalado. Instala: pip install pymupdf  (recomendado)")
    else:
        log("PyMuPDF OK. Modo PDF: PyMuPDF + tablas (pdfplumber).")
    log("UI lista. Selecciona un archivo y genera el .md.")
    root.mainloop()


# ---------------- Entry point ----------------
if __name__ == "__main__":
    if len(sys.argv) >= 3:
        input_path = sys.argv[1]
        output_path = sys.argv[2]
        convert_any_to_md(input_path, output_path)
        print(f"OK: {output_path}")
        sys.exit(0)

    run_gui()
