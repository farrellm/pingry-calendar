#!/usr/bin/env python3
"""Decode a Pingry Key Dates PDF into a day -> category map.

The PDF is a picture of a wall calendar: twelve month grids, each day cell filled
with one of the six legend colors. This reads the fills back out.

    pdftocairo -svg  -> every fill as a <path fill="rgb(...)" d="M x y L ...">
    pdftotext -bbox  -> every word with its bounding box

A colored rect is matched to the date digit sitting inside it, and the rect's grid
column is checked against that date's real weekday. If the two ever disagree, the
geometry assumptions below have drifted and the output is not trustworthy.

Usage:
    python3 tools/extract_pdf.py path/to/calendar.pdf

Requires poppler-utils (pdftotext, pdftocairo).
"""

import datetime
import html
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

# Legend swatch colors, plus the lighter tints the source uses interchangeably
# inside the grids. Keys are pdftocairo's percentage notation.
CATEGORY_BY_FILL = {
    "87.843323%, 39.99939%, 39.99939%": "closed-no-activities",   # E06666
    "90.196228%, 56.863403%, 21.960449%": "closed-athletics",     # E69138
    "96.470642%, 69.804382%, 41.960144%": "closed-athletics",     # F6B26B tint
    "100%, 85.098267%, 39.99939%": "no-homework-evening",         # FFD966
    "100%, 89.804077%, 60.00061%": "no-homework-evening",         # FFE599 tint
    "57.647705%, 76.863098%, 49.01886%": "basking-ridge",         # 93C47D
    "41.567993%, 65.882874%, 30.979919%": "basking-ridge",        # 6AA84F
    "43.528748%, 65.882874%, 86.274719%": "short-hills",          # 6FA8DC
    "23.921204%, 52.157593%, 77.6474%": "short-hills",            # 3D85C6
    "55.686951%, 48.626709%, 76.470947%": "employees",            # 8E7CC3
    "40.391541%, 30.587769%, 65.490723%": "employees",            # 675099 (digits)
    "2.745056%, 21.568298%, 38.822937%": "all-school",            # 073763
    "10.980225%, 27.058411%, 52.941895%": "all-school",           # 1C4587
}

# Month grid geometry, in PDF points. Two columns of six month blocks; the header
# baseline of each block and which side of the page it sits on.
MONTH_BLOCKS = [
    ("AUG", 2026, 84, "L"), ("FEB", 2027, 84, "R"),
    ("SEP", 2026, 198, "L"), ("MAR", 2027, 198, "R"),
    ("OCT", 2026, 313, "L"), ("APR", 2027, 313, "R"),
    ("NOV", 2026, 427, "L"), ("MAY", 2027, 427, "R"),
    ("DEC", 2026, 541, "L"), ("JUN", 2027, 541, "R"),
    ("JAN", 2027, 655, "L"), ("JUL", 2027, 655, "R"),
]
MONTH_NUMBER = dict(JAN=1, FEB=2, MAR=3, APR=4, MAY=5, JUN=6,
                    JUL=7, AUG=8, SEP=9, OCT=10, NOV=11, DEC=12)

BLOCK_HEIGHT = 112
SIDE_SPLIT = 310  # x below this is the left column of month blocks
COLUMN_X = {  # left edge of each weekday column, Sunday first
    "L": [187, 203, 219, 234, 250, 266, 282],
    "R": [313, 329, 345, 360, 376, 392, 408],
}
CELL_W = (8, 30)  # a date cell is this wide; wider fills are legend swatches
CELL_H = (6, 20)


def _run(*args):
    subprocess.run(args, check=True, capture_output=True)


def _fills(svg_text):
    """Yield (category, x0, y0, x1, y1) for every date-cell-sized colored rect."""
    pattern = r'<path[^>]*fill="rgb\(([^)]*)\)"[^>]*d="([^"]*)"'
    for fill, path_data in re.findall(pattern, svg_text):
        category = CATEGORY_BY_FILL.get(fill)
        if category is None:
            continue
        nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", path_data)]
        xs, ys = nums[0::2], nums[1::2]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        if not (CELL_W[0] < x1 - x0 < CELL_W[1] and CELL_H[0] < y1 - y0 < CELL_H[1]):
            continue
        yield category, x0, y0, x1, y1


def _words(bbox_text):
    pattern = (r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
               r'xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>')
    for x0, y0, x1, y1, text in re.findall(pattern, bbox_text):
        yield float(x0), float(y0), float(x1), float(y1), html.unescape(text)


def extract(pdf_path):
    """Return (day_map, problems). day_map is {date: set(category)}."""
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = Path(tmp) / "cal.svg"
        bbox_path = Path(tmp) / "cal.bbox.html"
        _run("pdftocairo", "-svg", str(pdf_path), str(svg_path))
        _run("pdftotext", "-bbox", str(pdf_path), str(bbox_path))
        svg_text = svg_path.read_text()
        words = list(_words(bbox_path.read_text()))

    digits = [w for w in words if w[4].isdigit()]
    day_map = defaultdict(set)
    problems = []

    for category, x0, y0, x1, y1 in _fills(svg_text):
        side = "L" if x0 < SIDE_SPLIT else "R"
        block = next((b for b in MONTH_BLOCKS
                      if b[3] == side and b[2] < y0 < b[2] + BLOCK_HEIGHT), None)
        if block is None:
            problems.append(f"fill at ({x0:.0f}, {y0:.0f}) sits outside every month block")
            continue

        inside = [d[4] for d in digits
                  if d[0] >= x0 - 2 and d[2] <= x1 + 2 and d[1] >= y0 - 3 and d[3] <= y1 + 3]
        if len(inside) != 1:
            problems.append(f"fill at ({x0:.0f}, {y0:.0f}) covers {len(inside)} date digits")
            continue

        name, year, _, _ = block
        date = datetime.date(year, MONTH_NUMBER[name], int(inside[0]))
        columns = COLUMN_X[side]
        column = min(range(7), key=lambda i: abs(columns[i] - x0))
        if (date.weekday() + 1) % 7 != column:
            problems.append(f"{date} is a {date:%A} but sits in grid column {column}")
            continue

        day_map[date].add(category)

    return dict(sorted(day_map.items())), problems


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)

    day_map, problems = extract(sys.argv[1])

    counts = defaultdict(int)
    for categories in day_map.values():
        for category in categories:
            counts[category] += 1

    for date, categories in day_map.items():
        print(f"{date}  {date:%a}  {', '.join(sorted(categories))}")
    print(f"\n{len(day_map)} colored days")
    for category, count in sorted(counts.items()):
        print(f"  {count:3d}  {category}")

    if problems:
        print(f"\n{len(problems)} problems — do not trust this output:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
