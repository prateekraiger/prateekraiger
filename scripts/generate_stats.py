#!/usr/bin/env python3
"""Draw the profile README's stat graphics from the GitHub GraphQL API.

No third-party services and no dependencies — standard library only.

Outputs, all sharing one visual language:
  stats.svg   hero total + weekly sparkline
  streak.svg  current and longest streak
  langs.svg   top languages, by bytes and by repo count
  year.svg    the year as a character map, in the portrait's own ramp
  hd-*.svg    section headings in JetBrains Mono

Env:
  GITHUB_TOKEN  required for live data (falls back to initial sample if absent)
  GH_LOGIN      user to summarise (default: prateekraiger)
  OUT_DIR       where to write (default: svg directory)
"""
import base64
import functools
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 privacy: PUBLIC) {
      nodes {
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

LIGHT = dict(data="#6e7681", emph="#424a53", dim="#8c959f",
             rule="#d8dee4", surface="#ffffff")
DARK = dict(data="#c9d1d9", emph="#f0f6fc", dim="#8b949e",
            rule="#30363d", surface="#0d1117")

MONO = ("JBMono,ui-monospace,SFMono-Regular,Menlo,Consolas,"
        "&apos;Liberation Mono&apos;,monospace")
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


@functools.lru_cache(maxsize=None)
def face(filename, weight):
    with open(os.path.join(FONT_DIR, filename), "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return (f"@font-face{{font-family:JBMono;font-style:normal;"
            f"font-weight:{weight};font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}")


def font_text():
    return face("jbmono-400.woff2", 400) + face("jbmono-600.woff2", 600)


def font_head():
    return face("jbmono-head.woff2", 600)

WIDTH = 620
LEFT = 34
REVEAL = 1.30
RAMP = [" ", ":", "+", "#", "@"]
MON = ["jan", "feb", "mar", "apr", "may", "jun",
       "jul", "aug", "sep", "oct", "nov", "dec"]


def window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return (f"{start.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z")


def fetch(login, token):
    since, until = window()
    body = json.dumps({"query": QUERY,
                       "variables": {"login": login,
                                     "from": since, "to": until}}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": f"{login}-profile-stats"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"no such user: {login}")
    return user


def pretty(iso):
    d = date.fromisoformat(iso)
    return f"{MON[d.month - 1]} {d.day}"


def streaks(days):
    best = dict(length=0, start=None, end=None)
    run, run_start = 0, None
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            run_start = run_start or d["date"]
            if run > best["length"]:
                best = dict(length=run, start=run_start, end=d["date"])
        else:
            run, run_start = 0, None

    cur = dict(length=0, start=None, end=None)
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    for d in reversed(tail):
        if d["contributionCount"] == 0:
            break
        cur["length"] += 1
        cur["start"] = d["date"]
        cur["end"] = cur["end"] or d["date"]
    return cur, best


def languages(repos):
    by_size, by_repo = {}, {}
    for node in repos:
        edges = (node.get("languages") or {}).get("edges") or []
        for e in edges:
            name = e["node"]["name"]
            by_size[name] = by_size.get(name, 0) + e["size"]
        if edges:
            top = edges[0]["node"]["name"]
            by_repo[top] = by_repo.get(top, 0) + 1

    def rank(d):
        return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))[:5]

    return rank(by_size), rank(by_repo)


def summarise(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    days = [d for w in weeks for d in w]
    weekly = [sum(d["contributionCount"] for d in w) for w in weeks]
    cur, best = streaks(days)
    by_size, by_repo = languages(user["repositories"]["nodes"])
    return dict(
        total=cal["totalContributions"],
        active=sum(1 for d in days if d["contributionCount"] > 0),
        best_week=max(weekly) if weekly else 0,
        weekly=weekly, weeks=weeks,
        current=cur, longest=best,
        by_size=by_size, by_repo=by_repo)


def fallback_summary():
    today = datetime.now(timezone.utc).date()
    weeks = []
    for w in range(52):
        week_days = []
        for d in range(7):
            dt = (today - timedelta(days=(51 - w) * 7 + (6 - d))).isoformat()
            cnt = (w * 3 + d * 5) % 11 if (w + d) % 2 == 0 else 0
            week_days.append({"contributionCount": cnt, "date": dt, "weekday": d})
        weeks.append(week_days)
    days = [d for w in weeks for d in w]
    weekly = [sum(d["contributionCount"] for d in w) for w in weeks]
    cur, best = streaks(days)
    return dict(
        total=sum(weekly),
        active=sum(1 for d in days if d["contributionCount"] > 0),
        best_week=max(weekly),
        weekly=weekly, weeks=weeks,
        current=cur, longest=best,
        by_size=[("TypeScript", 450000), ("JavaScript", 280000), ("HTML", 120000), ("CSS", 95000), ("Python", 65000)],
        by_repo=[("TypeScript", 8), ("JavaScript", 6), ("Python", 4), ("C++", 3), ("Java", 2)]
    )


def style(extra="", font=None):
    def block(t):
        return (f".d-f{{fill:{t['data']}}}.d-s{{stroke:{t['data']}}}"
                f".e-f{{fill:{t['emph']}}}.m-f{{fill:{t['dim']}}}"
                f".u-s{{stroke:{t['rule']}}}.r{{stroke:{t['surface']}}}")
    return (f"<style>{font or font_text()}"
            f"{block(LIGHT)}.w{{fill:{LIGHT['data']};opacity:.13}}{extra}"
            f"@media(prefers-color-scheme:dark){{{block(DARK)}"
            f".w{{fill:{DARK['data']};opacity:.16}}}}</style>")


def head(w, h, font=None):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" fill="none" font-family="{MONO}">'
            + style(font=font))


def fade(delay, dur=0.45):
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>')


def wipe(cid, x, y, w, h, delay, dur=REVEAL):
    clip = (f'<clipPath id="{cid}"><rect x="{x}" y="{y}" height="{h}" width="0">'
            f'<animate attributeName="width" from="0" to="{w}" '
            f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/></rect></clipPath>')
    cursor = (f'<rect y="{y}" width="2" height="{h}" class="d-f" opacity="0">'
              f'<animate attributeName="x" from="{x}" to="{x + w}" '
              f'begin="{delay:.2f}s" dur="{dur}s" fill="freeze"/>'
              f'<set attributeName="opacity" to="0.55" begin="{delay:.2f}s"/>'
              f'<set attributeName="opacity" to="0" '
              f'begin="{delay + dur:.2f}s"/></rect>')
    return clip, cursor


def label(x, y, text, size=11, cls="m-f", anchor="start", extra=""):
    a = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}"{a}'
            f'{extra}>{text}</text>')


def hbar(x, y, w, h, cls="d-f", r=3.0):
    if w <= 0.6:
        return ""
    r = min(r, h / 2.0, w)
    return (f'<path d="M{x:.1f} {y:.1f}H{x + w - r:.1f}'
            f'Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + r:.1f}'
            f'V{y + h - r:.1f}Q{x + w:.1f} {y + h:.1f} {x + w - r:.1f} {y + h:.1f}'
            f'H{x:.1f}Z" class="{cls}"/>')


def draw_stats(s):
    rows = max(len(s["by_size"]), len(s["by_repo"]), 1)
    H = 430
    weekly = s["weekly"] or [0]
    peak = max(weekly) or 1
    weeks = s["weeks"]

    p = [head(WIDTH, H)]

    # Gradient defs for activity chart
    p.append('<defs>'
             '<linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0%" stop-color="#39d353" stop-opacity="0.35"/>'
             '<stop offset="100%" stop-color="#39d353" stop-opacity="0.0"/>'
             '</linearGradient>'
             '<linearGradient id="areaGradDark" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0%" stop-color="#80F799" stop-opacity="0.30"/>'
             '<stop offset="100%" stop-color="#80F799" stop-opacity="0.0"/>'
             '</linearGradient>'
             '</defs>')

    # Section 1: Hero Contributions Header
    p.append(f'<g opacity="0">{fade(0.10)}'
             + label(0, 36, s["total"], 46, "e-f", extra=' font-weight="600"')
             + label(0, 56, "contributions in the last year", 11) + '</g>')

    for i, (val, lab) in enumerate([(s["active"], "active days"),
                                    (s["best_week"], "best week peak")]):
        p.append(f'<g opacity="0">{fade(0.25 + i * 0.10)}'
                 + label(WIDTH, 26 + i * 32, val, 17, "e-f", "end",
                         ' font-weight="600"')
                 + label(WIDTH, 38 + i * 32, lab, 10, "m-f", "end") + '</g>')

    # Activity Curve Graph
    base_y, top_y = 195, 80
    span_y = base_y - top_y
    chart_x_left, chart_w = 32, WIDTH - 40
    step_x = chart_w / max(len(weekly) - 1, 1)

    pts = [(chart_x_left + i * step_x, base_y - (v / peak) * span_y) for i, v in enumerate(weekly)]

    # Y-axis Scale Gridlines & Labels
    grid_steps = 3
    for gi in range(grid_steps + 1):
        gy = base_y - gi * (span_y / grid_steps)
        gval = int(round(gi * (peak / grid_steps)))
        p.append(f'<line x1="{chart_x_left}" y1="{gy:.1f}" x2="{WIDTH}" y2="{gy:.1f}" '
                 f'class="u-s" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>')
        p.append(label(chart_x_left - 6, gy + 3, str(gval), 9, "m-f", "end"))

    # X-axis Month Labels
    last_m, last_x = None, -999.0
    for i, w in enumerate(weeks):
        if w:
            m = int(w[0]["date"][5:7])
            x = chart_x_left + i * step_x
            if m != last_m and x - last_x >= 32 and x < WIDTH - 20:
                p.append(label(x, base_y + 14, MON[m - 1], 9, "m-f", "center"))
                last_x = x
            last_m = m

    clip, cursor = wipe("rs", chart_x_left, top_y - 6, chart_w + 10, span_y + 12, 0.40)
    p.append(clip)
    p.append('<g clip-path="url(#rs)">')
    # Gradient Area fill
    p.append(f'<path d="M{pts[0][0]:.1f} {base_y:.1f}'
             + "".join(f'L{x:.1f} {y:.1f}' for x, y in pts)
             + f'L{pts[-1][0]:.1f} {base_y:.1f}Z" fill="url(#areaGrad)" class="w"/>')
    # Crisp Stroke Line
    p.append(f'<path d="M{pts[0][0]:.1f} {pts[0][1]:.1f}'
             + "".join(f'L{x:.1f} {y:.1f}' for x, y in pts[1:])
             + f'" class="d-s" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    p.append("</g>")
    p.append(cursor)

    # Highlight Peak Point
    peak_idx = weekly.index(peak) if peak in weekly else 0
    px, py = pts[peak_idx]
    p.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" class="e-f r" '
             f'stroke-width="2" opacity="0">{fade(0.40 + REVEAL, 0.35)}</circle>')

    # Horizontal Divider 1
    p.append(f'<line x1="0" y1="225" x2="{WIDTH}" y2="225" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.50)}</line>')

    # Section 2: Streaks
    cells = []
    for k, lab in (("current", "current streak"), ("longest", "longest streak")):
        r = s[k]
        span_str = (f"{pretty(r['start'])} &#8211; {pretty(r['end'])}"
                    if r["length"] and r["start"] and r["end"] else "&#8212;")
        cells.append((r["length"], lab, span_str))

    p.append(f'<line x1="310" y1="235" x2="310" y2="305" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.55)}</line>')
    for i, (val, lab, span_str) in enumerate(cells):
        x = 0 if i == 0 else 330
        p.append(f'<g opacity="0">{fade(0.60 + i * 0.10)}'
                 + label(x, 264, f"{val} days", 26, "e-f", extra=' font-weight="600"')
                 + label(x, 280, lab, 10, "m-f")
                 + label(x, 294, span_str, 9, "m-f") + '</g>')

    # Horizontal Divider 2
    p.append(f'<line x1="0" y1="315" x2="{WIDTH}" y2="315" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.70)}</line>')

    # Section 3: Languages Breakdown
    colw = (WIDTH - 30) / 2
    name_w, bar_max = 82, colw - 82 - 40

    groups = [(0, "BY BYTES", s["by_size"], True),
              (325, "BY REPOS", s["by_repo"], False)]

    for gi, (gx, title, data, as_pct) in enumerate(groups):
        p.append(f'<g opacity="0">{fade(0.75 + gi * 0.10)}'
                 + label(gx, 332, title, 9, "m-f",
                         extra=' letter-spacing="1.3"') + '</g>')
        if not data:
            continue
        top_val = max(v for _, v in data) or 1
        total_val = sum(v for _, v in data) or 1
        cid = f"rl{gi}"
        clip, cursor = wipe(cid, gx + name_w, 338, bar_max, rows * 18,
                             0.85 + gi * 0.10, 0.90)
        p.append(clip)
        for ri, (name, val) in enumerate(data):
            y = 340 + ri * 17
            shown = (f"{val / total_val * 100:.0f}%" if as_pct else f"{val}")
            p.append(f'<g opacity="0">{fade(0.80 + gi * 0.08 + ri * 0.04)}'
                     + label(gx, y + 7, name.lower()[:11], 10, "e-f")
                     + label(gx + colw, y + 7, shown, 10, "m-f", "end")
                     + '</g>')
            p.append(f'<g clip-path="url(#{cid})">'
                     + hbar(gx + name_w, y, bar_max * val / top_val, 6)
                     + '</g>')
        p.append(cursor)

    p.append("</svg>")
    return "".join(p)


def draw_streak(s):
    H = 96
    cells = []
    for k, lab in (("current", "current streak"), ("longest", "longest streak")):
        r = s[k]
        span = (f"{pretty(r['start'])} &#8211; {pretty(r['end'])}"
                if r["length"] and r["start"] and r["end"] else "&#8212;")
        cells.append((r["length"], lab, span))

    p = [head(WIDTH, H)]
    mid = WIDTH / 2
    p.append(f'<line x1="{mid:.0f}" y1="16" x2="{mid:.0f}" y2="80" '
             f'class="u-s" stroke-width="1" opacity="0">{fade(0.20)}</line>')
    for i, (val, lab, span) in enumerate(cells):
        x = LEFT if i == 0 else mid + LEFT
        p.append(f'<g opacity="0">{fade(0.12 + i * 0.14)}'
                 + label(x, 44, f"{val}", 34, "e-f", extra=' font-weight="600"')
                 + label(x, 64, lab, 11)
                 + label(x, 80, span, 10) + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_langs(s):
    rows = max(len(s["by_size"]), len(s["by_repo"]), 1)
    H = 26 + rows * 22 + 6
    colw = (WIDTH - LEFT - 30) / 2
    name_w, bar_max = 82, colw - 82 - 44

    p = [head(WIDTH, H)]
    groups = [(LEFT, "by bytes", s["by_size"], True),
              (LEFT + colw + 30, "by repos", s["by_repo"], False)]
    for gi, (gx, title, data, as_pct) in enumerate(groups):
        p.append(f'<g opacity="0">{fade(0.10 + gi * 0.10)}'
                 + label(gx, 12, title.upper(), 9, "m-f",
                         extra=' letter-spacing="1.3"') + '</g>')
        if not data:
            continue
        top = max(v for _, v in data) or 1
        total = sum(v for _, v in data) or 1
        cid = f"rl{gi}"
        clip, cursor = wipe(cid, gx + name_w, 20, bar_max, rows * 22,
                             0.34 + gi * 0.12, 0.95)
        p.append(clip)
        for ri, (name, val) in enumerate(data):
            y = 26 + ri * 22
            shown = (f"{val / total * 100:.0f}%" if as_pct else f"{val}")
            p.append(f'<g opacity="0">{fade(0.24 + gi * 0.10 + ri * 0.05)}'
                     + label(gx, y + 8, name.lower()[:11], 11, "e-f")
                     + label(gx + colw - 6, y + 8, shown, 11, "m-f", "end")
                     + '</g>')
            p.append(f'<g clip-path="url(#{cid})">'
                     + hbar(gx + name_w, y, bar_max * val / top, 7)
                     + '</g>')
        p.append(cursor)
    p.append("</svg>")
    return "".join(p)


def draw_heading(word):
    FS = 16
    H = 26
    text_end = len(word) * FS * 0.6 + 18
    p = [head(WIDTH, H, font=font_head())]
    p.append(label(0, 18, word, FS, "e-f", extra=' font-weight="600"'))
    p.append(f'<line x1="{text_end:.0f}" y1="12.5" x2="{WIDTH}" y2="12.5" '
             f'class="u-s" stroke-width="1"/>')
    p.append("</svg>")
    return "".join(p)


def draw_year(s):
    cell_sz, gap = 9, 2.5
    step = cell_sz + gap
    pad_l, pad_t = LEFT + 5, 38
    weeks = s["weeks"]
    H = int(pad_t + 7 * step + 22)

    # Color Levels for GitHub Contribution Matrix
    # 0: empty, 1: 1-2, 2: 3-5, 3: 6-9, 4: 10+
    def color_class(v):
        if v == 0:
            return "c0"
        elif v <= 2:
            return "c1"
        elif v <= 5:
            return "c2"
        elif v <= 9:
            return "c3"
        return "c4"

    # Style override for contribution grid cells in light and dark mode
    extra_style = (
        ".c0{fill:#ebedf0}.c1{fill:#9be9a8}.c2{fill:#40c463}.c3{fill:#30a14e}.c4{fill:#216e39}"
        "@media(prefers-color-scheme:dark){"
        ".c0{fill:#161b22}.c1{fill:#0e4429}.c2{fill:#006d32}.c3{fill:#26a641}.c4{fill:#39d353}}"
    )

    p = [head(WIDTH, H, font=font_text())]
    p.append(f"<style>{extra_style}</style>")

    p.append(f'<g opacity="0">{fade(0.10)}'
             + label(pad_l, 16, "COMMIT ACTIVITY HEATMAP", 9, "m-f",
                     extra=' letter-spacing="1.3"')
             + label(pad_l, 28, f"{s['total']} contributions in {len(weeks)} weeks", 10, "e-f")
             + '</g>')

    # Legend at top right
    lx = WIDTH - 10
    p.append(f'<g opacity="0">{fade(0.20)}'
             + label(lx - 85, 20, "Less", 8, "m-f", "end")
             + "".join(f'<rect x="{lx - 55 + i * 11}" y="12" width="8" height="8" rx="1.5" class="c{i}"/>' for i in range(5))
             + label(lx, 20, "More", 8, "m-f", "end")
             + '</g>')

    # Day labels on left
    for r, lab in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        p.append(label(pad_l - 6, pad_t + r * step + cell_sz - 1, lab, 8, "m-f", "end"))

    # Month labels on top
    last_m, last_x = None, -999.0
    for i, w in enumerate(weeks):
        if w:
            m = int(w[0]["date"][5:7])
            x = pad_l + i * step
            if m != last_m and i < len(weeks) - 1 and x - last_x >= 28:
                p.append(label(x, pad_t - 6, MON[m - 1], 8, "m-f"))
                last_x = x
            last_m = m

    # Render Grid Tiles (Weeks x Days)
    for wi, w in enumerate(weeks):
        x = pad_l + wi * step
        delay = 0.25 + (wi / len(weeks)) * 0.6
        p.append(f'<g opacity="0">{fade(delay, 0.3)}')
        for day in w:
            r = day["weekday"]
            v = day["contributionCount"]
            y = pad_t + r * step
            cls = color_class(v)
            p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_sz}" height="{cell_sz}" rx="2" class="{cls}"/>')
        p.append('</g>')

    p.append("</svg>")
    return "".join(p)



def write(path, svg):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == svg:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN", "prateekraiger")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_out = os.path.join(repo_root, "svg")
    out_dir = os.environ.get("OUT_DIR", default_out)

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    heading_words = ("about", "stack", "projects", "stats", "connect", "extras", "about this page")
    hd_changed = []
    for word in heading_words:
        path = os.path.join(out_dir, f"hd-{word.replace(' ', '-')}.svg")
        if write(path, draw_heading(word)):
            hd_changed.append(f"hd-{word.replace(' ', '-')}.svg")

    if token:
        print(f"Fetching GraphQL stats for {login}...")
        s = summarise(fetch(login, token))
    else:
        print("GITHUB_TOKEN not set locally. Drawing fallback stats SVGs...")
        s = fallback_summary()

    files = {"stats.svg": draw_stats(s), "streak.svg": draw_streak(s),
             "langs.svg": draw_langs(s), "year.svg": draw_year(s)}

    changed = [n for n, svg in files.items()
               if write(os.path.join(out_dir, n), svg)]
    changed.extend(hd_changed)

    print(f"{s['total']} contributions, {s['active']} active days, "
          f"best week {s['best_week']}, current streak "
          f"{s['current']['length']}, longest {s['longest']['length']}")
    print("languages by bytes: "
          + ", ".join(f"{n} {v}" for n, v in s["by_size"]))
    print("updated: " + (", ".join(sorted(changed)) if changed else "nothing"))


if __name__ == "__main__":
    main()
