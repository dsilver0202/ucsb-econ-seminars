#!/usr/bin/env python3
"""
Scrape the UC Santa Barbara Economics events pages and publish iCalendar feeds.

Produces one .ics per seminar series plus a combined all.ics in docs/, along
with an index.html landing page with subscribe links. Previously seen events
are cached in events.json so that past talks stay on subscribers' calendars
after they drop off the department's "upcoming" listing.

Usage:
    python scrape.py                 # scrape, write docs/ and events.json
    python scrape.py --offline       # rebuild feeds from events.json only
    python scrape.py --out docs      # change output directory
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field

import requests
from bs4 import BeautifulSoup

BASE = "https://econ.ucsb.edu"

# Listing pages to scrape. Key is the fallback series code used when an event
# title does not announce its own series (e.g. "CARE Seminar: ...").
LISTINGS = {
    "/events/seminars": None,
    "/events/graduate": "GRADUATE",
    "/events/snyder": "SNYDER",
    "/events/babcock": "BABCOCK",
    "/events/conferences": "CONFERENCES",
}

# Human-readable names and default lengths (minutes) per series code.
SERIES_INFO = {
    "CARE": ("CARE Seminar", "Center for Applied Research in Economics", 90),
    "MACRO": ("MACRO Seminar", "Macroeconomics seminar", 90),
    "TEC": ("TEC Seminar", "Theory and Experimental Economics seminar", 90),
    "GRADUATE": ("Graduate Events", "Graduate student events and workshops", 90),
    "SNYDER": ("Snyder Lecture", "Snyder Lecture series", 90),
    "BABCOCK": ("Babcock Lecture", "Babcock Lecture series", 90),
    "CONFERENCES": ("Conferences", "Department conferences", 480),
    "OTHER": ("Other Events", "Department events", 90),
}
DEFAULT_MINUTES = 90

PRODID = "-//UCSB Economics Seminars (unofficial)//scrape.py//EN"
USER_AGENT = (
    "ucsb-econ-seminar-calendar/1.0 "
    "(+https://github.com/USER/ucsb-econ-seminars; unofficial community feed)"
)

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------


@dataclass
class Event:
    url: str
    title: str
    start_utc: str  # ISO 8601, e.g. 2026-10-07T22:30:00Z
    series: str
    location: str = ""
    speaker: str = ""
    talk_title: str = ""
    hosted_by: list[str] = field(default_factory=list)
    bio: str = ""
    abstract: str = ""
    minutes: int = DEFAULT_MINUTES
    seq: int = 0
    content_hash: str = ""

    @property
    def uid(self) -> str:
        digest = hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:20]
        return f"{digest}@econ.ucsb.edu"

    @property
    def start(self) -> dt.datetime:
        return dt.datetime.strptime(self.start_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc
        )

    @property
    def end(self) -> dt.datetime:
        return self.start + dt.timedelta(minutes=self.minutes or DEFAULT_MINUTES)

    def fingerprint(self) -> str:
        payload = "|".join(
            [
                self.title,
                self.start_utc,
                self.location,
                self.speaker,
                self.talk_title,
                ";".join(self.hosted_by),
                self.abstract,
                str(self.minutes),
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

    def summary(self) -> str:
        label = SERIES_INFO.get(self.series, SERIES_INFO["OTHER"])[0]
        who = self.speaker or self.title
        text = f"{label}: {who}"
        if self.talk_title:
            text = f"{text} - {self.talk_title.strip(chr(34))}"
        return text

    def description(self) -> str:
        lines = []
        if self.speaker:
            lines.append(f"Speaker: {self.speaker}")
        if self.talk_title:
            lines.append(f"Title: {self.talk_title}")
        if self.hosted_by:
            lines.append("Hosted by: " + ", ".join(self.hosted_by))
        if self.abstract:
            lines.append("")
            lines.append(self.abstract)
        elif self.bio:
            lines.append("")
            lines.append(self.bio)
        lines.append("")
        lines.append(self.url)
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------


def get(path: str) -> BeautifulSoup:
    url = path if path.startswith("http") else BASE + path
    resp = SESSION.get(url, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def listing_links(path: str) -> list[str]:
    soup = get(path)
    hrefs = []
    for row in soup.select(".views-row"):
        a = row.select_one("h3 a[href]")
        if a:
            hrefs.append(a["href"])
    return hrefs


def section_text(node, heading: str) -> str:
    """Text of the paragraphs following an <h2> with the given heading."""
    for h2 in node.find_all("h2"):
        if h2.get_text(strip=True).lower() != heading.lower():
            continue
        parts = []
        for sib in h2.next_siblings:
            if getattr(sib, "name", None) == "h2":
                break
            text = clean(sib.get_text(" ", strip=True)) if hasattr(sib, "get_text") else ""
            if text:
                parts.append(text)
        return clean(" ".join(parts))
    return ""


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


SERIES_RE = re.compile(r"^([A-Za-z][A-Za-z0-9&/\- ]{0,30}?)\s+(?:Seminar|Lecture|Workshop|Conference)\b", re.I)


def series_code(title: str, fallback: str | None) -> str:
    match = SERIES_RE.match(title or "")
    if match:
        code = re.sub(r"[^A-Z0-9]+", "", match.group(1).upper())
        if code:
            return code
    return fallback or "OTHER"


def parse_event(html: str, url: str, fallback_series: str | None) -> Event | None:
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one(".node--type-event") or soup
    h1 = node.find("h1")
    time_tag = node.find("time")
    if not h1 or not time_tag or not time_tag.get("datetime"):
        return None

    title = clean(h1.get_text(" ", strip=True))
    raw = time_tag["datetime"]
    start = dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(dt.timezone.utc)

    loc_el = node.select_one(".field--name-field-location .field--item")
    hosts = [
        clean(x.get_text(" ", strip=True))
        for x in node.select(".field--name-field-people-ref .field--item")
    ]
    body = node.select_one(".field--name-field-paragraphs") or node

    code = series_code(title, fallback_series)
    return Event(
        url=url,
        title=title,
        start_utc=start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        series=code,
        location=clean(loc_el.get_text(" ", strip=True)) if loc_el else "",
        speaker=section_text(body, "Speaker"),
        talk_title=section_text(body, "Title"),
        hosted_by=[h for h in hosts if h],
        bio=section_text(body, "Biography")[:1500],
        abstract=section_text(body, "Abstract")[:3000],
        minutes=SERIES_INFO.get(code, (None, None, DEFAULT_MINUTES))[2],
    )


def scrape() -> list[Event]:
    seen: dict[str, Event] = {}
    for path, fallback in LISTINGS.items():
        try:
            hrefs = listing_links(path)
        except Exception as exc:  # a missing tab should not sink the run
            print(f"  ! {path}: {exc}", file=sys.stderr)
            continue
        print(f"  {path}: {len(hrefs)} events")
        for href in hrefs:
            url = href if href.startswith("http") else BASE + href
            if url in seen:
                continue
            try:
                resp = SESSION.get(url, timeout=30)
                resp.raise_for_status()
                event = parse_event(resp.text, url, fallback)
            except Exception as exc:
                print(f"  ! {url}: {exc}", file=sys.stderr)
                continue
            if event:
                seen[url] = event
            time.sleep(0.3)  # be polite to the department's server
    return list(seen.values())


# --------------------------------------------------------------------------
# Cache (so past events survive falling off the "upcoming" list)
# --------------------------------------------------------------------------


def merge_with_cache(scraped: list[Event], cache_path: str) -> list[Event]:
    cached: dict[str, Event] = {}
    if os.path.exists(cache_path):
        with open(cache_path) as fh:
            for row in json.load(fh):
                row.pop("uid", None)
                cached[row["url"]] = Event(**row)

    now = dt.datetime.now(dt.timezone.utc)
    merged: dict[str, Event] = {}

    for event in scraped:
        old = cached.get(event.url)
        event.content_hash = event.fingerprint()
        if old:
            event.seq = old.seq + (1 if old.content_hash != event.content_hash else 0)
        merged[event.url] = event

    # Keep events that already happened even though the site no longer lists
    # them. A future event that disappears is treated as cancelled and dropped.
    for url, old in cached.items():
        if url in merged:
            continue
        if old.start < now:
            merged[url] = old

    return sorted(merged.values(), key=lambda e: e.start)


# --------------------------------------------------------------------------
# iCalendar output
# --------------------------------------------------------------------------


def esc(text: str) -> str:
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\n")
        .replace("\n", "\\n")
    )


def fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 73:
        return line
    chunks, current = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        limit = 73 if not chunks else 72
        if len(current) + len(enc) > limit:
            chunks.append(current)
            current = b""
        current += enc
    chunks.append(current)
    return "\r\n ".join(c.decode("utf-8") for c in chunks)


def stamp(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(events: list[Event], name: str, description: str) -> str:
    now = stamp(dt.datetime.now(dt.timezone.utc))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(name)}",
        f"X-WR-CALDESC:{esc(description)}",
        "X-WR-TIMEZONE:America/Los_Angeles",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for ev in sorted(events, key=lambda e: e.start):
        lines += [
            "BEGIN:VEVENT",
            f"UID:{ev.uid}",
            f"DTSTAMP:{now}",
            f"DTSTART:{stamp(ev.start)}",
            f"DTEND:{stamp(ev.end)}",
            f"SUMMARY:{esc(ev.summary())}",
            f"LOCATION:{esc(ev.location)}",
            f"DESCRIPTION:{esc(ev.description())}",
            f"URL:{ev.url}",
            f"CATEGORIES:{esc(ev.series)}",
            f"SEQUENCE:{ev.seq}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


def slug(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", code.lower()).strip("-") or "other"


# --------------------------------------------------------------------------
# Landing page
# --------------------------------------------------------------------------


def build_index(groups: dict[str, list[Event]], events: list[Event], base_url: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = [e for e in events if e.start >= now][:8]

    def local(ev: Event) -> str:
        # Render in Pacific time without requiring a tz database at build time.
        offset = -7 if 3 <= ev.start.month <= 10 else -8
        shown = ev.start + dt.timedelta(hours=offset)
        hour = shown.hour % 12 or 12
        ampm = "am" if shown.hour < 12 else "pm"
        return f"{shown:%a %b %-d, %Y} at {hour}:{shown:%M}{ampm}"

    rows = []
    for code in sorted(groups, key=lambda c: (-len(groups[c]), c)):
        label, blurb, _ = SERIES_INFO.get(code, (code, "Department events", 0))
        file = f"{slug(code)}.ics"
        rows.append(
            f"""      <tr>
        <th scope="row">{label}<span class="blurb">{blurb}</span></th>
        <td class="num">{len(groups[code])}</td>
        <td class="links">
          <a class="btn" href="webcal://{base_url}/{file}">Subscribe</a>
          <a class="plain" href="{file}">.ics</a>
        </td>
      </tr>"""
        )

    items = "\n".join(
        f"""      <li><span class="when">{local(e)}</span>
        <a href="{e.url}">{e.summary()}</a>
        <span class="where">{e.location}</span></li>"""
        for e in upcoming
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UCSB Economics Seminar Calendars</title>
<style>
  :root {{
    --bg: #fbfaf8; --fg: #1b1a18; --muted: #6b6762; --line: #e3ded6;
    --card: #ffffff; --accent: #0b6b6b;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #17181a; --fg: #ececea; --muted: #a2a09c; --line: #2c2e31;
      --card: #1f2124; --accent: #5fc9c0;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #17181a; --fg: #ececea; --muted: #a2a09c; --line: #2c2e31;
    --card: #1f2124; --accent: #5fc9c0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--fg);
    font: 16px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, sans-serif;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 48px 16px 72px; }}
  h1 {{ font-size: 1.6rem; margin: 0 0 6px; letter-spacing: -0.01em; }}
  .sub {{ color: var(--muted); margin: 0 0 32px; }}
  h2 {{ font-size: 1.05rem; margin: 38px 0 12px; }}
  table {{ width: 100%; border-collapse: collapse; background: var(--card);
    border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }}
  th, td {{ text-align: left; padding: 14px 16px; border-bottom: 1px solid var(--line);
    vertical-align: middle; font-weight: 400; }}
  tr:last-child th, tr:last-child td {{ border-bottom: 0; }}
  th[scope="row"] {{ font-weight: 600; }}
  .blurb {{ display: block; font-weight: 400; font-size: .85rem; color: var(--muted); }}
  .num {{ color: var(--muted); white-space: nowrap; width: 1%; }}
  .links {{ text-align: right; white-space: nowrap; width: 1%; }}
  .btn {{ display: inline-block; padding: 6px 12px; border-radius: 999px;
    background: var(--accent); color: #fff; text-decoration: none; font-size: .9rem; }}
  .plain {{ margin-left: 10px; color: var(--muted); font-size: .85rem; }}
  ul.next {{ list-style: none; padding: 0; margin: 0; }}
  ul.next li {{ padding: 10px 0; border-bottom: 1px solid var(--line); }}
  ul.next li:last-child {{ border-bottom: 0; }}
  .when {{ display: block; font-size: .85rem; color: var(--muted); }}
  .where {{ font-size: .85rem; color: var(--muted); }}
  a {{ color: var(--accent); }}
  ol {{ padding-left: 20px; }}
  li {{ margin: 6px 0; }}
  footer {{ margin-top: 44px; font-size: .85rem; color: var(--muted);
    border-top: 1px solid var(--line); padding-top: 16px; }}
  code {{ background: var(--card); border: 1px solid var(--line); border-radius: 4px;
    padding: 1px 5px; font-size: .85em; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>UCSB Economics seminar calendars</h1>
  <p class="sub">Subscribe once and every talk shows up on your calendar, updated
  automatically from the department's events page.</p>

  <table>
    <tbody>
{chr(10).join(rows)}
      <tr>
        <th scope="row">Everything<span class="blurb">All series in one calendar</span></th>
        <td class="num">{len(events)}</td>
        <td class="links">
          <a class="btn" href="webcal://{base_url}/all.ics">Subscribe</a>
          <a class="plain" href="all.ics">.ics</a>
        </td>
      </tr>
    </tbody>
  </table>

  <h2>How to subscribe</h2>
  <ol>
    <li><strong>Apple Calendar / Outlook:</strong> click Subscribe. Your calendar app takes it from there.</li>
    <li><strong>Google Calendar:</strong> copy the <code>.ics</code> link, then Other calendars &rarr;
      Subscribe from URL. Google refreshes external feeds on its own schedule, often once a day.</li>
    <li>Do not download and import the file. Importing makes a one-time copy that never updates.</li>
  </ol>

  <h2>Next up</h2>
  <ul class="next">
{items}
  </ul>

  <footer>
    Unofficial. Built by scraping
    <a href="https://econ.ucsb.edu/events/seminars">econ.ucsb.edu/events/seminars</a>,
    refreshed daily. Times and rooms follow the department page, so check it if
    something looks off. Last updated {now:%B %-d, %Y} at {now:%H:%M} UTC.
  </footer>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs")
    parser.add_argument("--cache", default="events.json")
    parser.add_argument("--offline", action="store_true",
                        help="rebuild feeds from the cache without fetching")
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "example.github.io/ucsb-econ-seminars"),
                        help="host and path where the feeds are published, no scheme")
    args = parser.parse_args()

    if args.offline:
        with open(args.cache) as fh:
            events = sorted(
                (Event(**{k: v for k, v in row.items() if k != "uid"}) for row in json.load(fh)),
                key=lambda e: e.start,
            )
        print(f"Rebuilding from cache: {len(events)} events")
    else:
        print("Scraping econ.ucsb.edu ...")
        events = merge_with_cache(scrape(), args.cache)
        with open(args.cache, "w") as fh:
            json.dump([asdict(e) for e in events], fh, indent=1, ensure_ascii=False)
        print(f"Total events after merge: {len(events)}")

    if not events:
        print("No events parsed. Leaving existing feeds untouched.", file=sys.stderr)
        return 1

    os.makedirs(args.out, exist_ok=True)

    groups: dict[str, list[Event]] = {}
    for ev in events:
        groups.setdefault(ev.series, []).append(ev)

    for code, group in groups.items():
        label, blurb, _ = SERIES_INFO.get(code, (code, "Department events", 0))
        path = os.path.join(args.out, f"{slug(code)}.ics")
        with open(path, "w", newline="") as fh:
            fh.write(build_ics(group, f"UCSB Econ {label}", blurb))
        print(f"  wrote {path} ({len(group)} events)")

    with open(os.path.join(args.out, "all.ics"), "w", newline="") as fh:
        fh.write(build_ics(events, "UCSB Econ Seminars", "All UCSB Economics seminars and lectures"))
    print(f"  wrote {os.path.join(args.out, 'all.ics')} ({len(events)} events)")

    with open(os.path.join(args.out, "index.html"), "w") as fh:
        fh.write(build_index(groups, events, args.base_url.strip("/")))
    print(f"  wrote {os.path.join(args.out, 'index.html')}")

    with open(os.path.join(args.out, ".nojekyll"), "w") as fh:
        fh.write("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
