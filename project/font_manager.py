import hashlib
import io
import os

from pypdf import PdfReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from fontTools.cffLib import CFFFontSet
from fontTools.ttLib import TTFont as FTFont, newTable
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.agl import AGL2UV

_FONT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "static", "extracted_fonts")
_registered_for = set()


def _template_hash(template_path: str) -> str:
    h = hashlib.sha1()
    with open(template_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def _extract_cff_fonts(template_path: str) -> dict:
    reader = PdfReader(template_path)
    found = {}
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources or "/Font" not in resources:
            continue
        for _key, font_ref in resources["/Font"].items():
            font_obj = font_ref.get_object()
            base_font = str(font_obj.get("/BaseFont", "")).lstrip("/")
            ps_name = base_font.split("+")[-1]
            descriptor = font_obj.get("/FontDescriptor")
            if not descriptor:
                descendants = font_obj.get("/DescendantFonts")
                if descendants:
                    descriptor = descendants[0].get_object().get("/FontDescriptor")
            if not descriptor:
                continue
            descriptor = descriptor.get_object()
            if "/FontFile3" in descriptor:
                stream = descriptor["/FontFile3"].get_object()
                if stream.get("/Subtype") in ("/Type1C", "/CIDFontType0C"):
                    data = stream.get_data()
                    if ps_name not in found or len(data) > len(found[ps_name]):
                        found[ps_name] = data
    return found


def _resolve_base_encoding(encoding_name):
    try:
        if encoding_name == "/WinAnsiEncoding":
            from reportlab.pdfbase._fontdata_enc_winansi import WinAnsiEncoding
            return list(WinAnsiEncoding)
        if encoding_name == "/MacRomanEncoding":
            from reportlab.pdfbase._fontdata_enc_macroman import MacRomanEncoding
            return list(MacRomanEncoding)
        from reportlab.pdfbase._fontdata_enc_standard import StandardEncoding
        return list(StandardEncoding)
    except ImportError:
        rev = {v: k for k, v in AGL2UV.items()}
        table = [None] * 256
        for code in range(0x20, 0x7F):
            name = rev.get(code)
            if name:
                table[code] = name
        return table


def _build_code_to_name_map(font_obj) -> dict:
    base_table = _resolve_base_encoding("/StandardEncoding")
    differences = None

    encoding = font_obj.get("/Encoding")
    if encoding is not None:
        encoding = encoding.get_object() if hasattr(encoding, "get_object") else encoding
        if isinstance(encoding, str):
            base_table = _resolve_base_encoding(encoding)
        elif hasattr(encoding, "get"):
            base_name = encoding.get("/BaseEncoding")
            if base_name:
                base_table = _resolve_base_encoding(str(base_name))
            differences = encoding.get("/Differences")

    code_to_name = {i: n for i, n in enumerate(base_table) if n}

    if differences:
        current_code = None
        for item in differences:
            if isinstance(item, (int, float)):
                current_code = int(item)
            else:
                name = str(item).lstrip("/")
                if current_code is not None:
                    code_to_name[current_code] = name
                    current_code += 1

    return code_to_name


def _extract_pdf_widths(template_path: str) -> dict:
    reader = PdfReader(template_path)
    widths_by_font = {}

    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources or "/Font" not in resources:
            continue
        for _key, font_ref in resources["/Font"].items():
            font_obj = font_ref.get_object()
            base_font = str(font_obj.get("/BaseFont", "")).lstrip("/")
            ps_name = base_font.split("+")[-1]
            if ps_name in widths_by_font:
                continue

            entry = {}

            if font_obj.get("/Subtype") == "/Type0":
                descendants = font_obj.get("/DescendantFonts")
                if descendants:
                    df = descendants[0].get_object()
                    default_w = df.get("/DW", 1000)
                    w_array = df.get("/W")
                    if w_array:
                        i = 0
                        while i < len(w_array):
                            start = int(w_array[i])
                            if isinstance(w_array[i + 1], list):
                                for j, w in enumerate(w_array[i + 1]):
                                    entry[start + j] = float(w)
                                i += 2
                            else:
                                end, w = int(w_array[i + 1]), w_array[i + 2]
                                for cid in range(start, end + 1):
                                    entry[cid] = float(w)
                                i += 3
                    entry["_default"] = float(default_w)
            else:
                first_char = font_obj.get("/FirstChar")
                widths_arr = font_obj.get("/Widths")
                if first_char is not None and widths_arr:
                    code_to_name = _build_code_to_name_map(font_obj)
                    for i, w in enumerate(widths_arr):
                        code = int(first_char) + i
                        glyph_name = code_to_name.get(code)
                        if glyph_name:
                            entry[glyph_name] = float(w)

            if entry:
                widths_by_font[ps_name] = entry

    return widths_by_font


def _cff_to_ttf_bytes(cff_data: bytes, pdf_widths: dict = None) -> bytes:
    cffset = CFFFontSet()
    cffset.decompile(io.BytesIO(cff_data), otFont=None)
    font_name = cffset.fontNames[0]
    top_dict = cffset[font_name]
    charstrings = top_dict.CharStrings
    glyph_order = top_dict.getGlyphOrder()
    units_per_em = int(round(1 / top_dict.rawDict.get("FontMatrix", [0.001])[0]))
    bbox = [int(v) for v in top_dict.rawDict.get("FontBBox", [0, -200, 1000, 900])]

    glyphs, widths = {}, {}
    for gid, name in enumerate(glyph_order):
        cs = charstrings[name]
        rec = RecordingPen()
        try:
            cs.draw(rec)
        except Exception:
            pass
        ttpen = TTGlyphPen(None)
        if rec.value:
            rec.replay(Cu2QuPen(ttpen, max_err=1.0, reverse_direction=True))
        glyphs[name] = ttpen.glyph()

        pdf_w = None
        if pdf_widths:
            pdf_w = pdf_widths.get(name)
            if pdf_w is None:
                pdf_w = pdf_widths.get(gid)
            if pdf_w is None:
                pdf_w = pdf_widths.get("_default")

        if pdf_w is not None:
            widths[name] = int(round(pdf_w / 1000.0 * units_per_em))
        else:
            widths[name] = int(cs.width if cs.width is not None
                                else top_dict.Private.defaultWidthX)

    ttf = FTFont(sfntVersion="\x00\x01\x00\x00")
    ttf.setGlyphOrder(glyph_order)

    glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = glyphs
    ttf["glyf"] = glyf
    ttf["loca"] = newTable("loca")

    hmtx = newTable("hmtx")
    hmtx.metrics = {n: (widths.get(n, 0) or 0, 0) for n in glyph_order}
    ttf["hmtx"] = hmtx

    head = newTable("head")
    head.tableVersion, head.fontRevision = 1.0, 1.0
    head.checkSumAdjustment, head.magicNumber = 0, 0x5F0F3CF5
    head.flags, head.unitsPerEm = 3, units_per_em
    head.created = head.modified = 3406620000
    head.xMin, head.yMin, head.xMax, head.yMax = bbox
    head.macStyle, head.lowestRecPPEM = 0, 6
    head.fontDirectionHint = 2
    head.indexToLocFormat, head.glyphDataFormat = 1, 0
    ttf["head"] = head

    hhea = newTable("hhea")
    hhea.tableVersion = 1.0
    hhea.ascent, hhea.descent, hhea.lineGap = bbox[3], bbox[1], 0
    hhea.advanceWidthMax = max(widths.values()) if widths else units_per_em
    hhea.minLeftSideBearing = hhea.minRightSideBearing = 0
    hhea.xMaxExtent = bbox[2]
    hhea.caretSlopeRise, hhea.caretSlopeRun, hhea.caretOffset = 1, 0, 0
    hhea.reserved0 = hhea.reserved1 = hhea.reserved2 = hhea.reserved3 = 0
    hhea.metricDataFormat = 0
    hhea.numberOfHMetrics = len(glyph_order)
    ttf["hhea"] = hhea

    maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    maxp.numGlyphs = len(glyph_order)
    for field in ["maxPoints", "maxContours", "maxCompositePoints", "maxCompositeContours",
                  "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                  "maxStackElements", "maxSizeOfInstructions", "maxComponentElements",
                  "maxComponentDepth"]:
        setattr(maxp, field, 0)
    maxp.maxZones = 1
    ttf["maxp"] = maxp

    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    cmap = newTable("cmap")
    cmap.tableVersion = 0
    mapping = {AGL2UV[n]: n for n in glyph_order if n in AGL2UV}
    _rupee_glyph = next((g for g in glyph_order if "rupee" in g.lower()
                        or g.lower() in ("uni20b9", "afii57636")), None)
    if _rupee_glyph:
       mapping[0x20B9] = _rupee_glyph
    sub4 = CmapSubtable.getSubtableClass(4)(4)
    sub4.platformID, sub4.platEncID, sub4.format, sub4.language = 3, 1, 4, 0
    sub4.cmap = mapping
    cmap.tables = [sub4]
    ttf["cmap"] = cmap

    from fontTools.ttLib.tables.O_S_2f_2 import table_O_S_2f_2, Panose
    os2 = table_O_S_2f_2()
    os2.version = 4
    os2.xAvgCharWidth = int(sum(widths.values()) / max(len(widths), 1))
    os2.usWeightClass = 700 if ("Bold" in font_name or "Extrabold" in font_name) else (
        500 if "Medium" in font_name else 400)
    os2.usWidthClass = 5
    os2.fsType = 0
    os2.ySubscriptXSize = os2.ySubscriptYSize = os2.ySubscriptXOffset = os2.ySubscriptYOffset = 0
    os2.ySuperscriptXSize = os2.ySuperscriptYSize = os2.ySuperscriptXOffset = os2.ySuperscriptYOffset = 0
    os2.yStrikeoutSize = os2.yStrikeoutPosition = 0
    os2.sFamilyClass = 0
    os2.panose = Panose()
    os2.ulUnicodeRange1 = 1
    os2.ulUnicodeRange2 = os2.ulUnicodeRange3 = os2.ulUnicodeRange4 = 0
    os2.achVendID = b"NGRO"
    os2.fsType = 0
    os2.fsSelection = 0x40
    os2.usFirstCharIndex, os2.usLastCharIndex = 0x20, 0x7E
    os2.sTypoAscender, os2.sTypoDescender, os2.sTypoLineGap = bbox[3], bbox[1], 0
    os2.usWinAscent, os2.usWinDescent = bbox[3], abs(bbox[1])
    os2.ulCodePageRange1 = os2.ulCodePageRange2 = 0
    os2.sxHeight, os2.sCapHeight = 500, bbox[3]
    os2.usDefaultChar, os2.usBreakChar, os2.usMaxContext = 0, 32, 0
    ttf["OS/2"] = os2

    from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
    name_table = table__n_a_m_e()
    name_table.names = []
    for nid in (1, 4, 6):
        name_table.setName(font_name, nid, 3, 1, 0x409)
    name_table.setName("Regular", 2, 3, 1, 0x409)
    ttf["name"] = name_table

    from fontTools.ttLib.tables._p_o_s_t import table__p_o_s_t
    post = table__p_o_s_t()
    post.formatType = 2.0
    post.italicAngle = 0
    post.underlinePosition, post.underlineThickness = -100, 50
    post.isFixedPitch = 0
    post.minMemType42 = post.maxMemType42 = post.minMemType1 = post.maxMemType1 = 0
    post.glyphOrder = glyph_order
    post.extraNames = []
    post.mapping = {}
    ttf["post"] = post

    buf = io.BytesIO()
    ttf.save(buf)
    return buf.getvalue()


def _extract_symbol_ttf_fonts(template_path: str) -> dict:
    """
    Find embedded /FontFile2 TrueType "symbol" fonts (e.g. the SymbolMT font
    the template uses to draw the ₹ rupee icon via a private-use-area glyph
    trick). These are legitimate, complete TTF glyph outlines - they just
    ship, as subsetted by the PDF producer, without a 'name' or 'post'
    table, which reportlab's font loader requires. Returns raw bytes keyed
    by PS font name.
    """
    reader = PdfReader(template_path)
    found = {}
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources or "/Font" not in resources:
            continue
        for _key, font_ref in resources["/Font"].items():
            font_obj = font_ref.get_object()
            base_font = str(font_obj.get("/BaseFont", "")).lstrip("/")
            ps_name = base_font.split("+")[-1]
            descriptor = font_obj.get("/FontDescriptor")
            if not descriptor:
                continue
            descriptor = descriptor.get_object()
            if "/FontFile2" in descriptor:
                data = descriptor["/FontFile2"].get_object().get_data()
                if ps_name not in found or len(data) > len(found[ps_name]):
                    found[ps_name] = data
    return found


def _repair_symbol_ttf_bytes(raw_ttf_bytes: bytes) -> bytes:
    """
    Patch a subsetted symbol TrueType font so reportlab can load it, and add
    a proper Unicode cmap entry for U+20B9 (₹) pointing at whichever glyph
    the font's own (3,0) "Symbol" cmap has mapped to code point '$' (0x24 ->
    0xF024) - that's the glyph the original template already relies on to
    draw the rupee icon.
    """
    buf = io.BytesIO(raw_ttf_bytes)
    ttf = FTFont(file=buf)

    symbol_subtable = next(
        (t for t in ttf["cmap"].tables if (t.platformID, t.platEncID) == (3, 0)), None
    )
    if symbol_subtable is not None:
        rupee_glyph = symbol_subtable.cmap.get(0xF000 + 0x24)
        if rupee_glyph:
            from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
            unicode_subtable = CmapSubtable.getSubtableClass(4)(4)
            unicode_subtable.platformID, unicode_subtable.platEncID = 3, 1
            unicode_subtable.format, unicode_subtable.language = 4, 0
            unicode_subtable.cmap = {0x20B9: rupee_glyph}
            ttf["cmap"].tables.append(unicode_subtable)

    if "name" not in ttf:
        from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
        name_table = table__n_a_m_e()
        name_table.names = []
        for nid in (1, 4, 6):
            name_table.setName("EmbeddedSymbolFont", nid, 3, 1, 0x409)
        name_table.setName("Regular", 2, 3, 1, 0x409)
        ttf["name"] = name_table

    if "post" not in ttf:
        from fontTools.ttLib.tables._p_o_s_t import table__p_o_s_t
        post = table__p_o_s_t()
        post.formatType = 3.0
        post.italicAngle = 0
        post.underlinePosition, post.underlineThickness = -100, 50
        post.isFixedPitch = 0
        post.minMemType42 = post.maxMemType42 = post.minMemType1 = post.maxMemType1 = 0
        ttf["post"] = post

    out = io.BytesIO()
    ttf.save(out)
    return out.getvalue()


def ensure_template_fonts_registered(template_path: str) -> dict:
    key = _template_hash(template_path)
    os.makedirs(_FONT_CACHE_DIR, exist_ok=True)
    cff_fonts = _extract_cff_fonts(template_path)
    pdf_widths = _extract_pdf_widths(template_path)
    registered = {}
    for ps_name, cff_bytes in cff_fonts.items():
        ttf_path = os.path.join(_FONT_CACHE_DIR, f"{key}_{ps_name}.ttf")
        if not os.path.exists(ttf_path):
            try:
                ttf_bytes = _cff_to_ttf_bytes(cff_bytes, pdf_widths.get(ps_name))
            except Exception as e:
                print("skip", ps_name, e)
                continue
            with open(ttf_path, "wb") as f:
                f.write(ttf_bytes)
        try:
            pdfmetrics.registerFont(TTFont(ps_name, ttf_path))
            registered[ps_name] = True
        except Exception as e:
            print("register fail", ps_name, e)
            continue

    symbol_fonts = _extract_symbol_ttf_fonts(template_path)
    for ps_name, raw_bytes in symbol_fonts.items():
        ttf_path = os.path.join(_FONT_CACHE_DIR, f"{key}_{ps_name}_symbol.ttf")
        if not os.path.exists(ttf_path):
            try:
                fixed_bytes = _repair_symbol_ttf_bytes(raw_bytes)
            except Exception as e:
                print("skip symbol font", ps_name, e)
                continue
            with open(ttf_path, "wb") as f:
                f.write(fixed_bytes)
        try:
            pdfmetrics.registerFont(TTFont(ps_name, ttf_path))
            registered[ps_name] = True
        except Exception as e:
            print("register fail", ps_name, e)
            continue

    _registered_for.add(key)
    return registered