"""
AutoDoc — hujjatni OTM (GOST) standartiga keltiruvchi asosiy modul.

Standart: A4; hoshiyalar: chap 30, o'ng 15, yuqori 20, past 20 mm;
Times New Roman 14; 1.5 interval; abzats 1.25 sm; matn tekislangan (justify);
sahifa raqami pastda o'rtada; mundarija avtomatik (Word maydoni).
"""
import io
import re
from dataclasses import dataclass, field
from typing import Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Mm, Pt, RGBColor

FONT = "Times New Roman"
BODY_SIZE = 14
TABLE_SIZE = 12
LINE_SPACING = 1.5
INDENT = Cm(1.25)


@dataclass
class TitleInfo:
    ministry: str = "O‘ZBEKISTON RESPUBLIKASI OLIY TA’LIM, FAN VA INNOVATSIYALAR VAZIRLIGI"
    university: str = ""
    faculty: str = ""
    work_type: str = "KURS ISHI"
    topic: str = ""
    student: str = ""
    supervisor: str = ""
    city: str = "Toshkent"
    year: str = ""


@dataclass
class Options:
    title: Optional[TitleInfo] = None
    toc: bool = True
    page_numbers: bool = True


# --------------------------------------------------------------------------- #
# Past darajadagi yordamchi funksiyalar
# --------------------------------------------------------------------------- #
_THEME_ATTRS = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")


def _force_rfonts(rpr):
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(a), FONT)
    for a in _THEME_ATTRS:
        rfonts.attrib.pop(qn(a), None)


def _style_font(style, size, bold=False):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = False
    style.font.color.rgb = RGBColor(0, 0, 0)
    _force_rfonts(style.element.get_or_add_rPr())


def _run_font(run, size=None, bold=None):
    run.font.name = FONT
    _force_rfonts(run._r.get_or_add_rPr())
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    run.font.color.rgb = RGBColor(0, 0, 0)
    run.font.highlight_color = None


def _pf(p, align=None, first=None, left=0, before=0, after=0, spacing=LINE_SPACING, keep_next=None):
    f = p.paragraph_format
    if align is not None:
        p.alignment = align
    f.first_line_indent = first
    f.left_indent = left
    f.right_indent = 0
    f.space_before = Pt(before)
    f.space_after = Pt(after)
    f.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    f.line_spacing = spacing
    f.widow_control = True
    if keep_next is not None:
        f.keep_with_next = keep_next


def _add_field(paragraph, instr, placeholder=""):
    def mk(kind):
        r = OxmlElement("w:r")
        c = OxmlElement("w:fldChar")
        c.set(qn("w:fldCharType"), kind)
        r.append(c)
        return r

    r_instr = OxmlElement("w:r")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    r_instr.append(it)
    r_txt = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = placeholder
    r_txt.append(t)
    for el in (mk("begin"), r_instr, mk("separate"), r_txt, mk("end")):
        paragraph._p.append(el)
    for r in paragraph.runs:
        _run_font(r, BODY_SIZE)


# --------------------------------------------------------------------------- #
# Sarlavha va adabiyotni aniqlash
# --------------------------------------------------------------------------- #
UNNUMBERED = {
    "KIRISH", "XULOSA", "XULOSA VA TAKLIFLAR", "XULOSALAR", "ANNOTATSIYA",
    "ILOVALAR", "ILOVA", "QISQARTMALAR", "MUNDARIJA",
    "FOYDALANILGAN ADABIYOTLAR", "FOYDALANILGAN ADABIYOTLAR RO‘YXATI",
    "ADABIYOTLAR RO‘YXATI", "ADABIYOTLAR", "REFERATLAR",
    "ВВЕДЕНИЕ", "ЗАКЛЮЧЕНИЕ", "СОДЕРЖАНИЕ", "СПИСОК ЛИТЕРАТУРЫ",
    "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ", "ПРИЛОЖЕНИЯ", "ПРИЛОЖЕНИЕ", "АННОТАЦИЯ",
    "INTRODUCTION", "CONCLUSION", "REFERENCES", "CONTENTS", "ABSTRACT",
}
BIBLIO = ("ADABIYOT", "СПИСОК", "REFERENCES")
TOC_WORDS = {"MUNDARIJA", "СОДЕРЖАНИЕ", "CONTENTS"}

_RE_CHAPTER = re.compile(r"^(?:[IVX]+|\d+)\s*[-\s]*(?:BOB|БОБ|ГЛАВА|CHAPTER)\b|^(?:BOB|БОБ|ГЛАВА|CHAPTER)\s*[IVX\d]+", re.I)
_RE_L3 = re.compile(r"^\d+\.\d+\.\d+\.?\s+\S")
_RE_L2 = re.compile(r"^\d+\.\d+\.?\s+\S")
_RE_L1 = re.compile(r"^\d+\.?\s+[A-ZА-ЯЎҚҒҲ‘’'ʻ]")
_RE_TOC_LINE = re.compile(r"(\.{3,}|…{1,}|\s{3,})\s*\d+\s*$")
_RE_CAPTION = re.compile(r"^(\d+[\s-]*(rasm|jadval|схема|рис|таблица)|(rasm|jadval|рис\.?|таблица)\s*\d+)", re.I)


def _norm(text: str) -> str:
    t = re.sub(r"\s+", " ", text.replace("\u00a0", " ")).strip()
    return t


def _key(text: str) -> str:
    return re.sub(r"[ʻ’'`ʼ]", "‘", text.upper()).rstrip(".:").strip()


def classify(text: str) -> Optional[int]:
    """Matn sarlavhami? 1/2/3 darajani qaytaradi, aks holda None."""
    t = _norm(text)
    if not t or len(t) > 130:
        return None
    k = _key(t)
    if k in UNNUMBERED or k.replace("'", "‘") in UNNUMBERED:
        return 1
    if _RE_CHAPTER.match(t):
        return 1
    if t.endswith((",", ";")):
        return None
    if _RE_L3.match(t) and len(t) < 110 and not t.endswith("."):
        return 3
    if _RE_L2.match(t) and len(t) < 110 and not t.endswith("."):
        return 2
    if _RE_L1.match(t) and len(t) < 100 and not t.endswith(".") and len(t.split()) <= 12:
        return 1
    return None


# --------------------------------------------------------------------------- #
# Asosiy formatlash
# --------------------------------------------------------------------------- #
def _setup_styles(doc):
    st = doc.styles
    _style_font(st["Normal"], BODY_SIZE)
    for name, size in (("Heading 1", 14), ("Heading 2", 14), ("Heading 3", 14)):
        s = st[name]
        _style_font(s, size, bold=True)
        s.paragraph_format.keep_with_next = True


def _setup_sections(doc, opts: Options):
    for s in doc.sections:
        s.page_width, s.page_height = Mm(210), Mm(297)
        s.left_margin, s.right_margin = Mm(30), Mm(15)
        s.top_margin, s.bottom_margin = Mm(20), Mm(20)
        s.header_distance = s.footer_distance = Mm(12.5)
        s.different_first_page_header_footer = opts.title is not None
        if opts.page_numbers:
            f = s.footer
            f.is_linked_to_previous = False
            for p in list(f.paragraphs)[1:]:
                p._p.getparent().remove(p._p)
            p = f.paragraphs[0]
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _add_field(p, "PAGE", "1")


def _format_heading(p, doc, level, first_chapter_state):
    text = _norm(p.text).rstrip(".:")
    if level == 1:
        text = text.upper()
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    p.style = doc.styles[f"Heading {level}"]
    run = p.add_run(text)
    _run_font(run, BODY_SIZE, bold=True)
    if level == 1:
        _pf(p, WD_ALIGN_PARAGRAPH.CENTER, None, before=0, after=12, keep_next=True)
        p.paragraph_format.page_break_before = True
    else:
        _pf(p, WD_ALIGN_PARAGRAPH.LEFT, INDENT, before=12 if level == 2 else 6, after=6, keep_next=True)
        p.paragraph_format.page_break_before = False


def _format_body(p):
    has_num = p._p.pPr is not None and p._p.pPr.numPr is not None
    has_img = bool(p._p.xpath(".//w:drawing")) or bool(p._p.xpath(".//w:pict"))
    text = _norm(p.text)
    for r in p.runs:
        _run_font(r, BODY_SIZE)
    if has_img:
        _pf(p, WD_ALIGN_PARAGRAPH.CENTER, None, spacing=1.0, before=6, after=6, keep_next=True)
    elif _RE_CAPTION.match(text):
        is_fig = re.search(r"rasm|рис|схема", text[:12], re.I) is not None
        _pf(p, WD_ALIGN_PARAGRAPH.CENTER if is_fig else WD_ALIGN_PARAGRAPH.LEFT, None, spacing=1.0, before=6, after=6)
        if not is_fig:
            p.paragraph_format.keep_with_next = True
    elif has_num:
        _pf(p, WD_ALIGN_PARAGRAPH.JUSTIFY, None, left=Cm(1.25) if False else None)
        p.paragraph_format.left_indent = None
        p.paragraph_format.first_line_indent = None
    else:
        _pf(p, WD_ALIGN_PARAGRAPH.JUSTIFY, INDENT)
        # matn ichidagi ortiqcha bo'shliqlarni tozalash
        if len(p.runs) == 1:
            p.runs[0].text = _norm(p.runs[0].text)


def _format_tables(doc):
    for t in doc.tables:
        try:
            t.style = doc.styles["Table Grid"]
        except KeyError:
            pass
        t.alignment = 1  # center
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _pf(p, WD_ALIGN_PARAGRAPH.LEFT, None, spacing=1.0)
                    for r in p.runs:
                        _run_font(r, TABLE_SIZE)


def _title_page(doc, ti: TitleInfo):
    made = []

    def para(text, size=BODY_SIZE, bold=False, align=WD_ALIGN_PARAGRAPH.CENTER, before=0, after=0, left=0, upper=False):
        if not text:
            return None
        p = doc.add_paragraph()
        r = p.add_run(text.upper() if upper else text)
        _run_font(r, size, bold)
        _pf(p, align, None, left=left, before=before, after=after, spacing=1.15)
        made.append(p)
        return p

    para(ti.ministry, bold=True, after=12)
    para(ti.university, bold=True, upper=True, after=6)
    para(ti.faculty, after=6)
    para(ti.work_type, size=18, bold=True, before=110, after=18, upper=True)
    if ti.topic:
        para(f"Mavzu: «{ti.topic.strip('«»\" ')}»", size=16, bold=True, after=0)
    last_before = 0
    first_right = True
    for label, val in (("Bajardi:", ti.student), ("Tekshirdi:", ti.supervisor)):
        if val:
            para(f"{label} {val}", align=WD_ALIGN_PARAGRAPH.LEFT, left=Cm(8.5),
                 before=90 if first_right else 10)
            first_right = False
    foot = para(f"{ti.city}  {ti.year}".strip(), before=110 if first_right else 90)
    if foot is None:
        foot = para(" ")
    foot.runs[-1].add_break(WD_BREAK.PAGE)
    return [p._p for p in made]


def _toc_block(doc):
    head = doc.add_paragraph()
    r = head.add_run("MUNDARIJA")
    _run_font(r, BODY_SIZE, True)
    _pf(head, WD_ALIGN_PARAGRAPH.CENTER, None, after=12, keep_next=True)
    body = doc.add_paragraph()
    _pf(body, WD_ALIGN_PARAGRAPH.LEFT, None, spacing=1.5)
    _add_field(body, r'TOC \o "1-3" \h \z \u',
               "Mundarija: Word’da ushbu joyni bosib, F9 tugmasini bosing (yoki «Maydonni yangilash»).")
    return [head._p, body._p]


def _mark_update_fields(doc):
    settings = doc.settings.element
    if settings.find(qn("w:updateFields")) is None:
        el = OxmlElement("w:updateFields")
        el.set(qn("w:val"), "true")
        settings.append(el)


def load(data: bytes, filename: str):
    name = filename.lower()
    if name.endswith(".docx"):
        return Document(io.BytesIO(data))
    if name.endswith(".txt"):
        text = None
        for enc in ("utf-8-sig", "cp1251", "utf-16"):
            try:
                text = data.decode(enc)
                break
            except Exception:
                continue
        text = text if text is not None else data.decode("utf-8", "ignore")
        doc = Document()
        for line in re.split(r"\r?\n", text):
            if line.strip():
                doc.add_paragraph(line.strip())
        return doc
    raise ValueError("Faqat .docx yoki .txt fayllar qo‘llab-quvvatlanadi.")


def format_document(data: bytes, filename: str, opts: Optional[Options] = None):
    """(docx_bytes, report_dict) qaytaradi."""
    opts = opts or Options()
    doc = load(data, filename)
    report = {"headings": 0, "references": 0, "paragraphs": 0, "tables": len(doc.tables), "removed_empty": 0}

    _setup_styles(doc)
    _setup_sections(doc, opts)

    in_biblio = False
    ref_no = 0
    first_heading = None

    for p in list(doc.paragraphs):
        text = _norm(p.text)
        has_media = bool(p._p.xpath(".//w:drawing")) or bool(p._p.xpath(".//w:pict"))

        if not text and not has_media:
            p._p.getparent().remove(p._p)
            report["removed_empty"] += 1
            continue

        # eski mundarija qatorlari va "MUNDARIJA" sarlavhasini olib tashlaymiz (o‘zimiz yaratamiz)
        if opts.toc and not has_media:
            if _key(text) in TOC_WORDS or _RE_TOC_LINE.search(text):
                p._p.getparent().remove(p._p)
                continue

        level = classify(text) if not has_media else None
        if level:
            _format_heading(p, doc, level, None)
            report["headings"] += 1
            if first_heading is None:
                first_heading = p
            if level == 1:
                in_biblio = any(w in _key(text) for w in BIBLIO)
                ref_no = 0
            continue

        if in_biblio and not has_media:
            ref_no += 1
            body = re.sub(r"^\s*(\[?\d+[\.\)\]])\s*", "", text)
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            run = p.add_run(f"{ref_no}. {body}")
            _run_font(run, BODY_SIZE)
            _pf(p, WD_ALIGN_PARAGRAPH.JUSTIFY, INDENT)
            report["references"] += 1
            continue

        _format_body(p)
        report["paragraphs"] += 1

    _format_tables(doc)

    # mundarija
    if opts.toc and first_heading is not None:
        for el in _toc_block(doc):
            first_heading._p.addprevious(el)
        _mark_update_fields(doc)

    # titul varaq (eng boshiga)
    if opts.title is not None:
        body = doc.element.body
        anchor = body[0]
        for el in _title_page(doc, opts.title):
            anchor.addprevious(el)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue(), report


# --------------------------------------------------------------------------- #
# Adabiyotlar ro‘yxatini shakllantirish (GOST 7.1 ga yaqin)
# --------------------------------------------------------------------------- #
def make_reference(kind: str, author="", title="", city="", publisher="", year="",
                   pages="", journal="", number="", url="", accessed="") -> str:
    a = author.strip().rstrip(".")
    t = title.strip().rstrip(".")
    head = f"{a}. " if a else ""
    if kind == "kitob":
        parts = f"{head}{t}. – {city.strip()}: {publisher.strip()}, {year.strip()}."
        if pages:
            parts += f" – {pages.strip()} b."
        return re.sub(r"\s+:", ":", parts).replace(" : ,", "").replace(": ,", ",")
    if kind == "maqola":
        s = f"{head}{t} // {journal.strip()}. – {year.strip()}."
        if number:
            s += f" – №{number.strip()}."
        if pages:
            s += f" – B. {pages.strip()}."
        return s
    if kind == "sayt":
        s = f"{head}{t} [Elektron resurs]. – URL: {url.strip()}"
        if accessed:
            s += f" (murojaat sanasi: {accessed.strip()})"
        return s + "."
    if kind == "qonun":
        return f"{t}. – {city.strip() or 'Toshkent'}, {year.strip()}.".replace(" ,", ",")
    raise ValueError("Noma’lum manba turi")
