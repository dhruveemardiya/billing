"""
template_geometry.py
=====================
Root-cause fix for the meter-details-box alignment/border bug.
"""

import hashlib
import os
import re

from pypdf import PdfReader
from pypdf.generic import ContentStream

_geometry_cache = {}


def _template_hash(template_path: str) -> str:
    h = hashlib.sha1()
    with open(template_path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def _iter_path_polygons(template_path: str, page_index: int):
    reader = PdfReader(template_path)
    page = reader.pages[page_index]
    stream = ContentStream(page["/Contents"].get_object(), reader)

    polygons = []
    current = []
    for operands, operator in stream.operations:
        op = operator.decode() if isinstance(operator, bytes) else operator
        if op == "m":
            if len(current) > 1:
                polygons.append(current)
            x, y = float(operands[0]), float(operands[1])
            current = [(x, y)]
        elif op == "l":
            x, y = float(operands[0]), float(operands[1])
            current.append((x, y))
        elif op in ("c", "v", "y"):
            x, y = float(operands[-2]), float(operands[-1])
            current.append((x, y))
        elif op in ("h", "s", "b", "f", "S", "B", "F", "n") and current:
            if len(current) > 1:
                polygons.append(current)
            current = []
    if len(current) > 1:
        polygons.append(current)
    return polygons


def _find_box_polygon(template_path: str, page_index: int, approx_bbox):
    reader = PdfReader(template_path)
    page = reader.pages[page_index]
    page_height = float(page.mediabox.height)

    x0_lo, x0_hi, top_lo, top_hi = approx_bbox
    best = None
    for poly in _iter_path_polygons(template_path, page_index):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        tops = [page_height - y for y in ys]
        px0, px1 = min(xs), max(xs)
        ptop, pbottom = min(tops), max(tops)
        if x0_lo <= px0 <= x0_hi and top_lo <= ptop <= top_hi and 60 <= (px1 - px0) <= 120:
            if best is None or len(poly) > len(best):
                best = poly

    if best is None:
        return None

    return [(x, page_height - y) for x, y in best]


def _edge_at(polygon, y, side, inset):
    best_x = None
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if y1 == y2:
            continue
        lo, hi = sorted((y1, y2))
        if lo <= y <= hi:
            t = (y - y1) / (y2 - y1)
            x_at_y = x1 + t * (x2 - x1)
            if side == "right":
                if best_x is None or x_at_y > best_x:
                    best_x = x_at_y
            else:
                if best_x is None or x_at_y < best_x:
                    best_x = x_at_y
    if best_x is None:
        return None
    return best_x - inset if side == "right" else best_x + inset


def _get_polygon(template_path, page_index, approx_bbox):
    cache_key = (_template_hash(template_path), page_index, approx_bbox)
    polygon = _geometry_cache.get(cache_key, "__missing__")
    if polygon == "__missing__":
        polygon = _find_box_polygon(template_path, page_index, approx_bbox)
        _geometry_cache[cache_key] = polygon
    return polygon


def get_box_edge(template_path, page_index, approx_bbox, rows, side="right", inset=1.5):
    polygon = _get_polygon(template_path, page_index, approx_bbox)
    if not polygon:
        return None

    edges = []
    for top, bottom in rows:
        for y in (top, bottom, (top + bottom) / 2):
            edge = _edge_at(polygon, y, side=side, inset=inset)
            if edge is not None:
                edges.append(edge)

    if not edges:
        return None

    return min(edges) if side == "right" else max(edges)