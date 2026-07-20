#!/usr/bin/env python3
"""
Build an always-up-to-date Wallabies (Men's 15s) Test calendar.

Future-proof design — nothing is pinned to a single year:

  1. LIVE  - Auto-discovers every fixturedownload.com competition that Australia
             plays in for the CURRENT and NEXT calendar year (Nations
             Championship, The Rugby Championship, Bledisloe, Rugby World Cup,
             Autumn internationals, ...). Times AND final scores update
             themselves after each match.
  2. STABLE - baseline.json fills in Tests that no public structured feed carries
             (e.g. Rugby Championship away kickoff times). Add future seasons
             here as they're announced; old ones roll off automatically.

Event title format (matches common rugby calendar feeds):
    🏉 Australia V Ireland | Mens | Nations Championship 2026        (upcoming)
    🏉 Australia 31-33 Ireland | Mens | Nations Championship 2026    (full time)

Output: docs/wallabies-2026.ics  (filename kept stable so subscriptions keep
working)  +  docs/index.html.  Standard library only.
"""

import json
import re
import urllib.request
import urllib.error
import datetime as dt
from pathlib import Path

BASE = "https://fixturedownload.com"
INDEX = f"{BASE}/sport/rugby-union"
TEAM = "australia"

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
OUT_ICS = DOCS / "wallabies-2026.ics"      # stable filename — don't rename
CAL_NAME = "Wallabies Test Calendar"
MATCH_DURATION_MIN = 135
WINDOW_PAST_DAYS = 180
WINDOW_FUTURE_DAYS = 540

SLUG_TEMPLATES = [
    "nations-championship-{y}", "the-rugby-championship-{y}", "rugby-championship-{y}",
    "bledisloe-cup-{y}", "rugby-world-cup-{y}", "autumn-nations-series-{y}",
    "autumn-internationals-{y}", "world-rugby-nations-cup-{y}", "mid-year-internationals-{y}",
]


def log(msg):
    print(f"[build] {msg}")


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "wallabies-calendar/3.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def target_years(today):
    return [today.year, today.year + 1]


def comp_name_from_slug(slug):
    """'nations-championship-2026' -> 'Nations Championship 2026'."""
    words = [p if p.isdigit() else p.capitalize() for p in slug.split("-")]
    return " ".join(words)


def discover_slugs(years):
    slugs = set()
    ys = [str(y) for y in years]
    for y in years:
        for t in SLUG_TEMPLATES:
            slugs.add(t.format(y=y))
    try:
        html = http_get(INDEX)
        for m in re.findall(r"/(?:results|download/ics|view/json)/([a-z0-9\-]+)", html):
            if any(m.endswith(y) for y in ys):
                slugs.add(m)
        log(f"index scan ok; {len(slugs)} candidate competitions")
    except Exception as e:  # noqa: BLE001
        log(f"index scan skipped ({e}); using templates only")
    return sorted(slugs)


def fetch_competition(slug):
    url = f"{BASE}/feed/json/{slug}/{TEAM}"
    try:
        data = json.loads(http_get(url))
        data = [m for m in data if "Australia" in (m.get("HomeTeam", ""), m.get("AwayTeam", ""))]
        for m in data:
            m["_comp"] = comp_name_from_slug(slug)
        if data:
            log(f"  + {slug}: {len(data)} Australia matches")
        return data
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log(f"  ! {slug}: HTTP {e.code}")
        return []
    except Exception:  # noqa: BLE001
        return []


def fetch_live(years):
    matches = []
    for slug in discover_slugs(years):
        matches.extend(fetch_competition(slug))
    if not matches:
        log("WARNING: no live matches found; building from baseline only")
    return matches


def parse_utc(s):
    s = s.strip()
    if len(s) <= 10:
        return dt.datetime.strptime(s, "%Y-%m-%d").date(), True
    return dt.datetime.strptime(s.replace("Z", "").strip(), "%Y-%m-%d %H:%M:%S"), False


def as_datetime(d):
    return d if isinstance(d, dt.datetime) else dt.datetime.combine(d, dt.time.min)


def make_title(home, away, comp, hs=None, as_=None, tbc=False):
    if hs is not None and as_ is not None:
        core = f"{home} {hs}-{as_} {away}"
    else:
        core = f"{home} V {away}"
    suffix = " (time TBC)" if tbc else ""
    return f"{core} | Mens | {comp}{suffix}"


def event_from_live(m):
    home, away = m.get("HomeTeam", ""), m.get("AwayTeam", "")
    opp = away if home == "Australia" else home
    when, all_day = parse_utc(m["DateUtc"])
    hs, as_ = m.get("HomeTeamScore"), m.get("AwayTeamScore")
    comp = m.get("_comp", "")
    rnd = m.get("RoundNumber")
    desc = f"Round {rnd}." if rnd is not None else ""
    if hs is not None and as_ is not None:
        desc = (desc + " Full time.").strip()
    return {
        "uid": f"aus-{as_datetime(when).strftime('%Y%m%d')}-{opp.lower().replace(' ','')}@wallabies-cal",
        "summary": make_title(home, away, comp, hs, as_, tbc=all_day and hs is None),
        "location": m.get("Location", ""), "description": desc,
        "dt": when, "all_day": all_day, "opp": opp.lower(), "src": "live",
    }


def event_from_baseline(m):
    when, all_day = parse_utc(m["dateUtc"])
    all_day = all_day or bool(m.get("allDay"))
    opp = m["opponent"]
    year = as_datetime(when).year
    comp = f"{m.get('competition','').strip()} {year}".strip()
    if m.get("summary"):
        summary = m["summary"]
    else:
        home = "Australia" if m.get("homeAway") == "home" else opp
        away = opp if m.get("homeAway") == "home" else "Australia"
        summary = make_title(home, away, comp, tbc=all_day)
    return {
        "uid": f"aus-{as_datetime(when).strftime('%Y%m%d')}-{opp.lower().replace(' ','')}@wallabies-cal",
        "summary": summary, "location": m.get("venue", ""),
        "description": m.get("note", ""),
        "dt": when, "all_day": all_day, "opp": opp.lower(), "src": "baseline",
    }


def dedupe_prefer_live(events):
    by_key = {}
    for e in sorted(events, key=lambda x: 0 if x["src"] == "live" else 1):
        by_key.setdefault((as_datetime(e["dt"]).date(), e["opp"]), e)
    return list(by_key.values())


def in_window(e, today):
    d = as_datetime(e["dt"]).date()
    return (today - dt.timedelta(days=WINDOW_PAST_DAYS)) <= d <= (today + dt.timedelta(days=WINDOW_FUTURE_DAYS))


def fold(line):
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 74:
            out.append(cur); cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def render_event(ev, stamp):
    lines = ["BEGIN:VEVENT", f"UID:{ev['uid']}", f"DTSTAMP:{stamp}"]
    if ev["all_day"]:
        d = ev["dt"]; end = d + dt.timedelta(days=1)
        lines += [f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}", "STATUS:TENTATIVE"]
    else:
        start = ev["dt"]; end = start + dt.timedelta(minutes=MATCH_DURATION_MIN)
        lines += [f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}Z",
                  f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}Z", "STATUS:CONFIRMED"]
    lines.append(f"SUMMARY:{esc('🏉 ' + ev['summary'])}")
    if ev["location"]:
        lines.append(f"LOCATION:{esc(ev['location'])}")
    if ev["description"]:
        lines.append(f"DESCRIPTION:{esc(ev['description'])}")
    lines.append("END:VEVENT")
    return "\r\n".join(fold(l) for l in lines)


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    years = target_years(today)
    log(f"today {today}; target seasons {years}")

    live = [event_from_live(m) for m in fetch_live(years)]
    baseline_data = json.loads((ROOT / "baseline.json").read_text())
    base = [event_from_baseline(m) for m in baseline_data.get("matches", [])]

    merged = dedupe_prefer_live(live + base)
    events = sorted([e for e in merged if in_window(e, today)], key=lambda e: as_datetime(e["dt"]))
    log(f"events in window: {len(events)} (from {len(live)} live + {len(base)} baseline)")

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    head = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Wallabies Calendar//EN",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{CAL_NAME}",
            "X-WR-CALDESC:Australia Wallabies men's Test schedule (auto-updated, auto-rolling).",
            "REFRESH-INTERVAL;VALUE=DURATION:P1D", "X-PUBLISHED-TTL:PT12H"]
    body = "\r\n".join([*[fold(l) for l in head],
                        *[render_event(e, stamp) for e in events], "END:VCALENDAR"]) + "\r\n"
    DOCS.mkdir(exist_ok=True)
    OUT_ICS.write_text(body, encoding="utf-8")
    log(f"wrote {OUT_ICS}")

    rows = "".join(
        f"<tr><td>{esc(e['summary'])}</td>"
        f"<td>{'all-day' if e['all_day'] else e['dt'].strftime('%d %b %Y %H:%M')+'Z'}</td></tr>"
        for e in events)
    (DOCS / "index.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Wallabies Test Calendar</title>"
        "<style>body{font-family:system-ui;max-width:680px;margin:40px auto;padding:0 16px}"
        "table{border-collapse:collapse;width:100%}td{border-bottom:1px solid #ddd;padding:6px 4px}"
        "code{background:#f4f4f4;padding:2px 6px;border-radius:4px}</style>"
        "<h1>🏉 Wallabies Test Calendar</h1>"
        "<p>Subscribe using <code>wallabies-2026.ics</code> in this folder "
        "(swap <code>https</code> for <code>webcal</code> on Apple/Outlook).</p>"
        f"<p>Last built {stamp} · {len(events)} Tests in view · auto-rolls each season.</p>"
        f"<table>{rows}</table>", encoding="utf-8")
    log("wrote docs/index.html")


if __name__ == "__main__":
    main()
