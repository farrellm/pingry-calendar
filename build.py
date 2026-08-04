#!/usr/bin/env python3
"""Build the Pingry Key Dates site and its .ics calendars into dist/.

    python3 build.py

Everything comes from data/keydates.json. Standard library only.
"""

import datetime
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data" / "keydates.json"
SITE = ROOT / "site"
DIST = ROOT / "dist"

# Which fill wins when a day carries more than one category.
PRECEDENCE = [
    "all-school",
    "closed-no-activities",
    "closed-athletics",
    "no-homework-evening",
    "short-hills",
    "basking-ridge",
    "employees",
]

WEEKDAY_INITIALS = ["S", "M", "T", "W", "Th", "F", "S"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------- dates

def parse_day_specs(specs):
    """Expand ["2026-09-07", "2026-11-23..2026-11-27"] into a set of dates."""
    days = set()
    for spec in specs:
        if ".." in spec:
            first, last = (datetime.date.fromisoformat(s) for s in spec.split(".."))
            if last < first:
                raise ValueError(f"range runs backwards: {spec}")
            while first <= last:
                days.add(first)
                first += datetime.timedelta(days=1)
        else:
            days.add(datetime.date.fromisoformat(spec))
    return days


def date_range(first, last):
    day = first
    while day <= last:
        yield day
        day += datetime.timedelta(days=1)


def format_span(start, end):
    """'Thu 3 Sep 2026' or 'Sat 21 – Sun 29 Nov 2026'."""
    if start == end:
        return f"{start:%a} {start.day} {start:%b} {start.year}"
    if start.year != end.year:
        return (f"{start:%a} {start.day} {start:%b} {start.year} – "
                f"{end:%a} {end.day} {end:%b} {end.year}")
    if start.month != end.month:
        return (f"{start:%a} {start.day} {start:%b} – "
                f"{end:%a} {end.day} {end:%b} {end.year}")
    return f"{start:%a} {start.day} – {end:%a} {end.day} {end:%b} {end.year}"


# ---------------------------------------------------------------- iCalendar

def fold(line):
    """Wrap a content line to 75 octets, continuations indented by one space."""
    octets = line.encode("utf-8")
    if len(octets) <= 75:
        return line
    pieces, start = [], 0
    limit = 75
    while start < len(octets):
        end = min(start + limit, len(octets))
        while end > start and (octets[end - 1] & 0xC0) == 0x80:
            end -= 1  # never split a UTF-8 sequence
        pieces.append(octets[start:end].decode("utf-8"))
        start = end
        limit = 74  # subsequent lines carry a leading space
    return "\r\n ".join(pieces[:1] + [p for p in pieces[1:]])


def escape(text):
    return (text.replace("\\", "\\\\")
                .replace(";", r"\;")
                .replace(",", r"\,")
                .replace("\n", r"\n"))


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_ics(name, description, events, data, stamp):
    """Render one VCALENDAR. Events are all-day; DTEND is exclusive."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//farrellm//pingry-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(name)}",
        f"X-WR-CALDESC:{escape(description)}",
        f"X-WR-TIMEZONE:{data['timezone']}",
        "REFRESH-INTERVAL;VALUE=DURATION:P7D",
        "X-PUBLISHED-TTL:P7D",
    ]
    for event in events:
        start = datetime.date.fromisoformat(event["start"])
        end = datetime.date.fromisoformat(event.get("end", event["start"]))

        # The category rides in the title, which is the one piece of an event a
        # calendar app prints in the month grid. CATEGORIES carries it too, but
        # Google, Apple, and Outlook all ignore that property.
        names = [data["names"][key] for key in event["categories"]]
        summary = event["summary"]
        if names:
            summary += f" ({', '.join(names)})"

        lines += [
            "BEGIN:VEVENT",
            # Keyed on the bare summary, not the decorated one: these UIDs are
            # already published, and changing them would turn a re-import into
            # 44 duplicates instead of 44 updates.
            f"UID:{slug(event['summary'])}-{start:%Y%m%d}@farrellm.github.io",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{end + datetime.timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{escape(summary)}",
            "TRANSP:TRANSPARENT",
            "CLASS:PUBLIC",
        ]
        if event.get("description"):
            lines.append(f"DESCRIPTION:{escape(event['description'])}")
        if names:
            lines.append("CATEGORIES:" + ",".join(escape(n) for n in names))
        lines += [f"URL:{data['source_pdf']}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in lines) + "\r\n"


# ---------------------------------------------------------------- html

def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def render_spine(data, fills, marks, labels):
    """365 day-ticks, Aug 1 to Jul 31 — the whole year as one strip."""
    first, last = (datetime.date.fromisoformat(d) for d in data["span"])
    ticks = []
    for day in date_range(first, last):
        categories = sorted(fills.get(day, set()) | marks.get(day, set()),
                            key=PRECEDENCE.index)
        attrs = [f'data-d="{day.isoformat()}"']
        if categories:
            attrs.append(f'data-cats="{" ".join(categories)}"')
            attrs.append(f'style="--c:var(--{categories[0]})"')
        if labels.get(day):
            names = " · ".join(e["summary"] for e in labels[day])
            attrs.append(f'data-l="{esc(names)}"')
        ticks.append(f'<i class="tick"{"" if not attrs else " " + " ".join(attrs)}></i>')

    months = []
    day = first
    while day <= last:
        following = (day.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        span = (min(following, last + datetime.timedelta(days=1)) - day).days
        months.append(f'<span style="--span:{span}">{day:%b}</span>')
        day = following

    return (f'<div class="spine__ticks">{"".join(ticks)}</div>\n'
            f'      <div class="spine__months">{"".join(months)}</div>')


def render_day_events(data, labels):
    """ISO date -> the events on it, as a JSON island the popup reads."""
    days = {}
    for day, events in sorted(labels.items()):
        days[day.isoformat()] = [
            {
                "name": event["summary"],
                "description": event.get("description", ""),
                "categories": [
                    {"key": key, "name": data["names"][key]}
                    for key in event["categories"]
                ],
            }
            for event in events
        ]
    blob = json.dumps(days, ensure_ascii=False, separators=(",", ":"))
    # Nothing may close the <script> early, whatever ends up in an event name.
    return blob.replace("</", "<\\/")


def render_months(data, fills, marks, labels):
    first, last = (datetime.date.fromisoformat(d) for d in data["span"])
    blocks = []
    month = first.replace(day=1)
    while month <= last:
        following = (month.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        cells = ['<i class="pad"></i>'] * ((month.weekday() + 1) % 7)
        for day in date_range(month, following - datetime.timedelta(days=1)):
            categories = sorted(fills.get(day, set()) | marks.get(day, set()),
                                key=PRECEDENCE.index)
            classes = ["day"]
            if day.weekday() >= 5:
                classes.append("day--weekend")
            attrs = ""
            if fills.get(day):
                fill = sorted(fills[day], key=PRECEDENCE.index)[0]
                classes.append("day--fill")
                attrs += f' style="--c:var(--{fill})"'
                if fill == "all-school":
                    classes.append("day--all-school")
            elif marks.get(day):
                mark = sorted(marks[day], key=PRECEDENCE.index)[0]
                classes.append("day--mark")
                attrs += f' style="--c:var(--{mark})"'
            if categories:
                attrs += f' data-cats="{" ".join(categories)}"'

            # A day with events is a button so it can be clicked and tabbed to;
            # the rest stay inert <i>, keeping 277 blanks out of the tab order.
            if labels.get(day):
                attrs += f' type="button" data-d="{day.isoformat()}"'
                cells.append(
                    f'<button class="{" ".join(classes)}"{attrs}>{day.day}</button>')
            else:
                cells.append(f'<i class="{" ".join(classes)}"{attrs}>{day.day}</i>')

        heads = "".join(f"<i>{d}</i>" for d in WEEKDAY_INITIALS)
        blocks.append(
            f'<div class="month">\n'
            f'          <h3>{MONTH_NAMES[month.month - 1]} <span>{month.year}</span></h3>\n'
            f'          <div class="month__grid"><div class="month__head">{heads}</div>'
            f'{"".join(cells)}</div>\n'
            f'        </div>'
        )
        month = following
    return "\n        ".join(blocks)


def render_feeds(feeds):
    rows = []
    for feed in feeds:
        listing = "".join(
            f'<li><span class="when">{esc(format_span(e["_start"], e["_end"]))}</span>'
            f'<span class="what">{esc(e["summary"])}'
            + (f'<em>{esc(e["description"])}</em>' if e.get("description") else "")
            + "</span></li>"
            for e in feed["events"]
        )
        count = len(feed["events"])
        rows.append(f"""<details class="feed" data-cat="{feed['key']}">
          <summary>
            <span class="feed__chip" style="--c:var(--{feed['key']})"></span>
            <span class="feed__name">{esc(feed['name'])}</span>
            <span class="feed__count">{count} date{'' if count == 1 else 's'}</span>
          </summary>
          <div class="feed__body">
            <p class="feed__blurb">{esc(feed['blurb'])}</p>
            <ol class="feed__list">{listing}</ol>
            <div class="feed__actions">
              <a class="btn" href="{esc(feed['file'])}" download>Download .ics</a>
            </div>
          </div>
        </details>""")
    return "\n        ".join(rows)


# ---------------------------------------------------------------- main

def main():
    data = json.loads(DATA.read_text())
    categories = data["categories"]
    data["names"] = {c["key"]: c["name"] for c in categories}

    fills = {}
    for key, specs in data["days"].items():
        for day in parse_day_specs(specs):
            fills.setdefault(day, set()).add(key)
    marks = {}
    for key, specs in data["marks"].items():
        for day in parse_day_specs(specs):
            marks.setdefault(day, set()).add(key)

    events = []
    labels = {}
    for event in data["events"]:
        event["_start"] = datetime.date.fromisoformat(event["start"])
        event["_end"] = datetime.date.fromisoformat(event.get("end", event["start"]))
        events.append(event)
        for day in date_range(event["_start"], event["_end"]):
            labels.setdefault(day, []).append(event)
    events.sort(key=lambda e: (e["_start"], e["_end"]))

    combined = {
        "key": "all",
        "name": "Every date",
        "blurb": "Every date on the calendar, whichever campus or division you are in.",
    }

    slugs = {"no-homework-evening": "no-homework"}
    feeds = []
    for category in categories + [combined]:
        key = category["key"]
        matching = ([e for e in events] if key == "all"
                    else [e for e in events if key in e["categories"]])
        filename = f"pingry-{data['year']}-{slugs.get(key, key)}.ics"
        feeds.append({
            "key": key,
            "name": category["name"],
            "blurb": category["blurb"],
            "events": matching,
            "file": filename,
        })

    DIST.mkdir(exist_ok=True)
    for stale in DIST.glob("*.ics"):
        stale.unlink()

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for feed in feeds:
        name = f"Pingry {data['year']} · {feed['name']}"
        (DIST / feed["file"]).write_text(
            build_ics(name, feed["blurb"], feed["events"], data, stamp),
            newline="")

    page = (SITE / "index.html").read_text()
    replacements = {
        "{{YEAR}}": data["year"].replace("-", "–"),
        "{{TITLE}}": data["title"],
        "{{SCHOOL}}": data["school"],
        "{{SOURCE_PDF}}": data["source_pdf"],
        "{{SOURCE_UPDATED}}": data["source_updated"],
        "{{FEED_COUNT}}": str(len(feeds)),
        "{{SPINE}}": render_spine(data, fills, marks, labels),
        "{{MONTHS}}": render_months(data, fills, marks, labels),
        "{{DAY_EVENTS}}": render_day_events(data, labels),
        "{{FEEDS}}": render_feeds(feeds),
        "{{BUILT}}": datetime.date.today().strftime("%-d %B %Y"),
    }
    for token, value in replacements.items():
        page = page.replace(token, value)
    if "{{" in page:
        raise SystemExit("unreplaced template token: " + re.search(r"\{\{\w+\}\}", page).group())
    (DIST / "index.html").write_text(page)

    for asset in ("style.css", "app.js"):
        shutil.copy(SITE / asset, DIST / asset)
    shutil.copytree(SITE / "fonts", DIST / "fonts", dirs_exist_ok=True)
    (DIST / ".nojekyll").write_text("")

    print(f"dist/ — {len(feeds)} feeds, {len(events)} events")
    for feed in feeds:
        print(f"  {len(feed['events']):3d}  {feed['file']}")


if __name__ == "__main__":
    main()
