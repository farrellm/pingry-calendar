# Pingry Key Dates → calendar feeds

The Pingry School publishes its key dates calendar as a one-page PDF: a picture of a wall calendar,
color-coded against a six-item legend. You cannot subscribe to a picture. This turns it into seven
`.ics` feeds and one page that lets you pick the one that describes you.

**→ [farrellm.github.io/pingry-calendar](https://farrellm.github.io/pingry-calendar/)**

Unofficial, and not affiliated with the school. Check the school's own calendar before you plan
around a date.

## The feeds

One per legend category, plus everything in one.

| Feed | Legend color | Dates |
| --- | --- | --- |
| `pingry-2026-27-closed-no-activities.ics` | `#E06666` School closed, no activities | 10 |
| `pingry-2026-27-closed-athletics.ics` | `#E69138` School closed, athletics continue | 8 |
| `pingry-2026-27-no-homework.ics` | `#FFD966` No homework evening | 3 |
| `pingry-2026-27-basking-ridge.ics` | `#93C47D` Basking Ridge specific | 6 |
| `pingry-2026-27-short-hills.ics` | `#6FA8DC` Short Hills specific | 6 |
| `pingry-2026-27-employees.ics` | `#8E7CC3` Employees only | 6 |
| `pingry-2026-27-all.ics` | — | 44 |

Subscribe with the feed's URL — for example
`https://farrellm.github.io/pingry-calendar/pingry-2026-27-all.ics`. Events are all-day in
America/New_York, and multi-day breaks are single spanning events, so Winter Break arrives as one
band rather than sixteen entries.

## Fidelity

Everything is transcribed from the source PDF. Two places where that matters:

- The PDF marks a no-homework evening on **Friday 18 September**, not on 20 September when Yom
  Kippur begins. That is what it prints, so that is what the feeds say.
- The PDF colors five days in navy — first day, three returns from break, last day. That is
  emphasis rather than a legend category, so those days appear in the combined feed only.

## Building

Standard library Python 3, no dependencies.

```sh
python3 build.py                # writes dist/
python3 tools/check.py          # validates the generated .ics files
python3 -m http.server -d dist  # preview
```

- `data/keydates.json` is the source of truth. `days` and `marks` are the PDF's cell fills and
  colored date digits, and drive the page's grids. `events` are the labelled dates from the PDF
  margins, and are what the feeds contain.
- `site/` holds the page template, stylesheet, script, and self-hosted fonts.
- `dist/` is the build output and is not committed; it is published to the `gh-pages` branch.

### Next year

```sh
curl -o cal.pdf <url of the new key dates PDF>
python3 tools/extract_pdf.py cal.pdf
```

`tools/extract_pdf.py` reads the cell fills straight back out of the PDF, and asserts that every
colored cell's grid column matches that date's real weekday — if the layout has drifted it says so
instead of producing quiet nonsense. Update `data/keydates.json` from its output, then:

```sh
python3 build.py && python3 tools/check.py cal.pdf
```

`check.py` re-decodes the PDF and diffs it against `keydates.json`, so a transcription slip fails
the check rather than reaching the feeds. Requires `poppler-utils` (`pdftotext`, `pdftocairo`).

Note that the extractor sees cell *fills* only. A handful of days are marked in the PDF by coloring
the date digit rather than the cell — those are the `marks` block in `keydates.json` and are
maintained by hand.

## Deploying

```sh
python3 build.py
git worktree add /tmp/gh-pages gh-pages
cp -r dist/. /tmp/gh-pages/
git -C /tmp/gh-pages add -A && git -C /tmp/gh-pages commit -m "Publish" && git -C /tmp/gh-pages push
git worktree remove /tmp/gh-pages
```
