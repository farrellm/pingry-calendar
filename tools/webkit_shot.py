#!/usr/bin/env python3
"""Render a page in real WebKit, to catch what headless Chrome cannot.

Safari and iOS share this engine, so layout bugs that only show up on a phone
show up here too. A month-grid sizing bug that Chrome rendered perfectly was
reproduced with this in one run.

    python3 tools/webkit_shot.py URL out.png [width] [height]
    python3 tools/webkit_shot.py URL --eval 'document.title' [width] [height]

`--eval` runs a JS expression and prints the result instead of screenshotting —
use it to measure geometry rather than squinting at pixels. The expression's
value is stringified, so return JSON for anything structured.

Needs webkit2gtk, python-gobject, and Xvfb; there is no display in this
environment, so run it under xvfb-run:

    xvfb-run -a -s "-screen 0 1400x3000x24 +extension GLX" \\
        python3 tools/webkit_shot.py http://localhost:8412/ out.png 430

LIBGL_ALWAYS_SOFTWARE=1 and WEBKIT_DISABLE_COMPOSITING_MODE=1 are set below
because WebKitGTK aborts on a GL context it cannot create under Xvfb.

This script exits 0 on success and 1 on failure, but xvfb-run's own teardown
clobbers that with a failed `kill`. To branch on the result, capture it inside:
`xvfb-run ... bash -c 'python3 tools/webkit_shot.py ...; echo $?'`.
"""

import os
import sys

os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
os.environ.setdefault("WEBKIT_DISABLE_COMPOSITING_MODE", "1")

import gi  # noqa: E402  — must follow the env vars above

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import GLib, Gtk, WebKit2  # noqa: E402

SETTLE_MS = 1500   # let fonts and scripts finish before measuring
TIMEOUT_MS = 25000


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        sys.exit(__doc__)

    url, target = args[0], args[1]
    script = args[2] if target == "--eval" else None
    rest = args[3:] if target == "--eval" else args[2:]
    width = int(rest[0]) if rest else 1200
    height = int(rest[1]) if len(rest) > 1 else 900

    window = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    view.set_size_request(width, height)
    window.add(view)
    window.show_all()

    status = {"code": 1}

    def finish_snapshot(webview, result, _):
        try:
            webview.get_snapshot_finish(result).write_to_png(target)
            print(f"wrote {target} ({width}x{height} css px)")
            status["code"] = 0
        except GLib.Error as error:
            print(f"snapshot failed: {error}", file=sys.stderr)
        Gtk.main_quit()

    def finish_eval(webview, result, _):
        try:
            print(webview.evaluate_javascript_finish(result).to_string())
            status["code"] = 0
        except GLib.Error as error:
            print(f"eval failed: {error}", file=sys.stderr)
        Gtk.main_quit()

    def act():
        if script is None:
            view.get_snapshot(WebKit2.SnapshotRegion.FULL_DOCUMENT,
                              WebKit2.SnapshotOptions.NONE, None,
                              finish_snapshot, None)
        else:
            view.evaluate_javascript(script, -1, None, None, None,
                                     finish_eval, None)
        return False

    def on_load(webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(SETTLE_MS, act)

    def on_failed(webview, event, failing_uri, error):
        print(f"load failed: {failing_uri}: {error.message}", file=sys.stderr)
        Gtk.main_quit()
        return True

    view.connect("load-changed", on_load)
    view.connect("load-failed", on_failed)
    view.load_uri(url)

    def give_up():
        print("timed out waiting for the page", file=sys.stderr)
        Gtk.main_quit()
        return False

    GLib.timeout_add(TIMEOUT_MS, give_up)
    Gtk.main()
    sys.exit(status["code"])


if __name__ == "__main__":
    main()
