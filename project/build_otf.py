"""
Wrap a bare CFF (Type1C) font program - as embedded inside a PDF's
/FontFile3 - into a minimal, valid OTF (OpenType/CFF) font file that
fontTools / reportlab / any normal font-rendering stack can load.

PDF's /FontFile3 stream only contains the CFF table itself; it has no
cmap, hmtx, head, hhea, maxp, post, name or OS/2 tables (those are only
needed outside the PDF, where the PDF viewer supplies glyph selection
via the PDF's own /Encoding + /Differences instead of a cmap). To reuse
the font outside the PDF (e.g. registering it with reportlab so our own
overlay text uses the exact template typeface) we have to synthesize
those wrapper tables ourselves.
"""
import io
from fontTools.cffLib import CFFFontSet
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.recordingPen import RecordingPen
from fontTools.agl import AGL2UV


def build_otf_from_cff(cff_path: str, otf_path: str) -> None:
    with open(cff_path, "rb") as f:
        cff_data = f.read()

    cffset = CFFFontSet()
    cffset.decompile(io.BytesIO(cff_data), otFont=None)
    font_name = cffset.fontNames[0]
    top_dict = cffset[font_name]
    charstrings = top_dict.CharStrings
    glyph_order = top_dict.getGlyphOrder()

    units_per_em = int(round(1 / top_dict.rawDict.get("FontMatrix", [0.001])[0]))
    bbox = top_dict.rawDict.get("FontBBox", [0, -200, 1000, 900])

    # --- widths (advance width per glyph, from the charstrings themselves) ---
    widths = {}
    for name in glyph_order:
        cs = charstrings[name]
        pen = RecordingPen()
        try:
            cs.draw(pen)
        except Exception:
            pass
        widths[name] = cs.width if cs.width is not None else top_dict.Private.defaultWidthX

    # --- build the sfnt wrapper ---
    otf = TTFont(sfntVersion="OTTO")
    otf.setGlyphOrder(glyph_order)

    cff_table = newTable("CFF ")
    cff_table.cff = cffset
    otf["CFF "] = cff_table

    # cmap: map every glyph whose name is in the Adobe Glyph List to its
    # Unicode code point, so text drawn by codepoint (what reportlab does)
    # resolves to the correct glyph.
    cmap_table = newTable("cmap")
    cmap_table.tableVersion = 0
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    mapping = {}
    for gname in glyph_order:
        uni = AGL2UV.get(gname)
        if uni is not None:
            mapping[uni] = gname
    sub4 = CmapSubtable.getSubtableClass(4)(4)
    sub4.platformID, sub4.platEncID, sub4.format, sub4.language = 3, 1, 4, 0
    sub4.cmap = mapping
    sub4.data = None
    cmap_table.tables = [sub4]
    otf["cmap"] = cmap_table

    hmtx_table = newTable("hmtx")
    hmtx_table.metrics = {name: (widths.get(name, 0) or 0, 0) for name in glyph_order}
    otf["hmtx"] = hmtx_table

    head_table = newTable("head")
    head_table.tableVersion = 1.0
    head_table.fontRevision = 1.0
    head_table.checkSumAdjustment = 0
    head_table.magicNumber = 0x5F0F3CF5
    head_table.flags = 3
    head_table.unitsPerEm = units_per_em
    head_table.created = head_table.modified = 0
    head_table.xMin, head_table.yMin, head_table.xMax, head_table.yMax = [int(v) for v in bbox]
    head_table.macStyle = 0
    head_table.lowestRecPPEM = 6
    head_table.fontDirectionHint = 2
    head_table.indexToLocFormat = 0
    head_table.glyphDataFormat = 0
    otf["head"] = head_table

    hhea_table = newTable("hhea")
    hhea_table.tableVersion = 1.0
    hhea_table.ascent = int(bbox[3])
    hhea_table.descent = int(bbox[1])
    hhea_table.lineGap = 0
    hhea_table.advanceWidthMax = max(widths.values()) if widths else units_per_em
    hhea_table.minLeftSideBearing = 0
    hhea_table.minRightSideBearing = 0
    hhea_table.xMaxExtent = int(bbox[2])
    hhea_table.caretSlopeRise = 1
    hhea_table.caretSlopeRun = 0
    hhea_table.caretOffset = 0
    hhea_table.reserved0 = hhea_table.reserved1 = hhea_table.reserved2 = hhea_table.reserved3 = 0
    hhea_table.metricDataFormat = 0
    hhea_table.numberOfHMetrics = len(glyph_order)
    otf["hhea"] = hhea_table

    maxp_table = newTable("maxp")
    maxp_table.tableVersion = 0x00005000
    maxp_table.numGlyphs = len(glyph_order)
    otf["maxp"] = maxp_table

    from fontTools.ttLib.tables.O_S_2f_2 import table_O_S_2f_2
    os2 = table_O_S_2f_2()
    os2.version = 4
    os2.xAvgCharWidth = int(sum(widths.values()) / max(len(widths), 1))
    os2.usWeightClass = 700 if "Bold" in font_name or "Extrabold" in font_name else (500 if "Medium" in font_name else 400)
    os2.usWidthClass = 5
    os2.fsType = 0
    os2.ySubscriptXSize = os2.ySubscriptYSize = os2.ySubscriptXOffset = os2.ySubscriptYOffset = 0
    os2.ySuperscriptXSize = os2.ySuperscriptYSize = os2.ySuperscriptXOffset = os2.ySuperscriptYOffset = 0
    os2.yStrikeoutSize = os2.yStrikeoutPosition = 0
    os2.sFamilyClass = 0
    from fontTools.ttLib.tables.O_S_2f_2 import Panose
    os2.panose = Panose()
    for i in range(1, 5):
        setattr(os2, f"ulUnicodeRange{i}", 0)
    os2.ulUnicodeRange1 = 1  # basic latin
    os2.achVendID = b"NGRO"
    os2.fsSelection = 0x40
    os2.usFirstCharIndex = 0x20
    os2.usLastCharIndex = 0x7E
    os2.sTypoAscender = int(bbox[3])
    os2.sTypoDescender = int(bbox[1])
    os2.sTypoLineGap = 0
    os2.usWinAscent = int(bbox[3])
    os2.usWinDescent = abs(int(bbox[1]))
    os2.ulCodePageRange1 = os2.ulCodePageRange2 = 0
    os2.sxHeight = 500
    os2.sCapHeight = int(bbox[3])
    os2.usDefaultChar = 0
    os2.usBreakChar = 32
    os2.usMaxContext = 0
    otf["OS/2"] = os2

    from fontTools.ttLib.tables._n_a_m_e import table__n_a_m_e
    name_table = table__n_a_m_e()
    name_table.names = []
    name_table.setName(font_name, 1, 3, 1, 0x409)
    name_table.setName("Regular", 2, 3, 1, 0x409)
    name_table.setName(font_name, 4, 3, 1, 0x409)
    name_table.setName(font_name, 6, 3, 1, 0x409)
    otf["name"] = name_table

    from fontTools.ttLib.tables._p_o_s_t import table__p_o_s_t
    post_table = table__p_o_s_t()
    post_table.formatType = 3.0
    post_table.italicAngle = 0
    post_table.underlinePosition = -100
    post_table.underlineThickness = 50
    post_table.isFixedPitch = 0
    post_table.minMemType42 = post_table.maxMemType42 = 0
    post_table.minMemType1 = post_table.maxMemType1 = 0
    otf["post"] = post_table

    otf.save(otf_path)


if __name__ == "__main__":
    import os
    weights = ["Regular", "Bold", "Medium", "Extrabold"]
    for w in weights:
        build_otf_from_cff(
            f"/home/claude/fonts/NeurialGrotesk-{w}.cff",
            f"/home/claude/fonts/NeurialGrotesk-{w}.otf",
        )
        print("built", w)