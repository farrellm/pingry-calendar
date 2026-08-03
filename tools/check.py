#!/usr/bin/env python3
"""Check the built feeds, and check the data against the source PDF.

    python3 tools/check.py                    # feeds only
    python3 tools/check.py path/to/cal.pdf    # feeds + re-decode the PDF and diff

Exits non-zero on the first category of failure. Standard library only.
"""

import datetime
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))

failures = []


def fail(message):
    failures.append(message)
    print(f"  FAIL  {message}")


def unfold(raw):
    """Reverse RFC 5545 line folding, returning logical content lines."""
    lines = []
    for line in raw.split("\r\n"):
        if line.startswith(" ") and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return [line for line in lines if line]


def check_feeds():
    print("feeds")
    paths = sorted((ROOT / "dist").glob("*.ics"))
    if not paths:
        fail("no .ics files in dist/ — run build.py first")
        return

    for path in paths:
        raw = path.read_bytes().decode("utf-8")
        if "\r\n" not in raw:
            fail(f"{path.name}: no CRLF line endings")
        if raw.replace("\r\n", "\n").count("\n") != raw.count("\r\n"):
            fail(f"{path.name}: mixed line endings")
        for line in raw.split("\r\n"):
            if len(line.encode("utf-8")) > 75:
                fail(f"{path.name}: line over 75 octets — {line[:40]}…")

        lines = unfold(raw)
        if lines[0] != "BEGIN:VCALENDAR" or lines[-1] != "END:VCALENDAR":
            fail(f"{path.name}: not wrapped in VCALENDAR")
        if lines.count("BEGIN:VEVENT") != lines.count("END:VEVENT"):
            fail(f"{path.name}: unbalanced VEVENT blocks")

        uids, count = [], 0
        start = end = None
        for line in lines:
            if line.startswith("UID:"):
                uids.append(line[4:])
            elif line.startswith("DTSTART;VALUE=DATE:"):
                start = line.rsplit(":", 1)[1]
            elif line.startswith("DTEND;VALUE=DATE:"):
                end = line.rsplit(":", 1)[1]
            elif line == "END:VEVENT":
                count += 1
                if not (start and end and end > start):
                    fail(f"{path.name}: event {count} has DTEND {end} <= DTSTART {start}")
                start = end = None
        if len(uids) != len(set(uids)):
            dupes = {u for u in uids if uids.count(u) > 1}
            fail(f"{path.name}: duplicate UIDs — {', '.join(sorted(dupes))}")

        print(f"  ok    {path.name}  {count} events, {len(raw)} bytes")


def check_against_pdf(pdf_path):
    print(f"\ndata vs {pdf_path}")
    from extract_pdf import extract

    decoded, problems = extract(pdf_path)
    for problem in problems:
        fail(f"extractor: {problem}")

    data = json.loads((ROOT / "data" / "keydates.json").read_text())
    sys.path.insert(0, str(ROOT))
    from build import parse_day_specs

    declared = defaultdict(set)
    for key, specs in data["days"].items():
        for day in parse_day_specs(specs):
            declared[day].add(key)

    for day in sorted(set(decoded) | set(declared)):
        found, said = decoded.get(day, set()), declared.get(day, set())
        if found != said:
            fail(f"{day}: PDF says {sorted(found) or '—'}, "
                 f"keydates.json says {sorted(said) or '—'}")

    if not failures:
        print(f"  ok    {len(decoded)} colored days match keydates.json")

    # The extractor only sees cell fills, so colored date *digits* are declared
    # by hand in "marks". Confirm none of them collide with a fill.
    for key, specs in data["marks"].items():
        for day in parse_day_specs(specs):
            if key in declared.get(day, set()):
                fail(f"{day}: {key} is both a fill and a mark")


def main():
    check_feeds()
    if len(sys.argv) > 1:
        check_against_pdf(sys.argv[1])

    print()
    if failures:
        print(f"{len(failures)} failure{'' if len(failures) == 1 else 's'}")
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
