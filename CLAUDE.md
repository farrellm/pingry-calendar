# pingry-calendar

Static site + `.ics` generator built from a PDF wall calendar. Build, deploy, and the
data model are in README.md — this file is the things that bit us.

## Invariants

- Month-grid day cells are **two element types**: `<button class="day">` for the 88 days
  with events, `<i class="day">` for the other 277. Any selector sizing or styling day
  cells must name both — a media query that named only `> i` shipped a visible layout bug.
- `site/style.css` keeps every cell background at single-class specificity (`.day`,
  `.day--fill`). Never put `background` on a `.month__grid > i` style selector; it
  silently out-specifies the category colors.
- `.ics` UIDs key on the bare `event["summary"]`, never the rendered `SUMMARY` (which
  appends the category). Changing them turns a re-import into duplicates, not updates.
- `dist/` is gitignored; publishing is a separate `gh-pages` worktree push, so committing
  to `main` does not update the live site.

## Browser testing

The Claude-in-Chrome extension is not connected here; drive browsers from the CLI.

- `google-chrome-stable --headless --disable-gpu --no-sandbox --hide-scrollbars --virtual-time-budget=6000 --window-size=W,H --screenshot=out.png URL`
- Light mode needs `--blink-settings=preferredColorScheme=1`; without it headless renders dark.
- `--dump-dom` clamps the viewport to a **500px minimum**, so narrow-width probes report the
  wrong `innerWidth`. Screenshots do honour the width — use those to check mobile layout.
- Headless does not fire `scroll` for `scrollBy()`; dispatch `new Event('scroll')` on
  `document` to exercise scroll handlers.
- `scrollIntoView` + `--screenshot` captures blank; use a tall `--window-size` instead.
- Probe pattern: inject a `<script>` writing results into `<pre id="probe-out">`, then
  `--dump-dom | sed -n '/probe-out/,/<\/pre>/p'`.
- **Reproduce Safari/iOS bugs with `tools/webkit_shot.py`** (real WebKit via WebKitGTK).
  Chrome-only testing missed a mobile layout bug this caught.
