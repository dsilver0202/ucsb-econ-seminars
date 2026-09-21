# UCSB Economics seminar calendars

Unofficial iCalendar feeds for the UC Santa Barbara Economics seminar series.
A scheduled job scrapes [econ.ucsb.edu/events](https://econ.ucsb.edu/events/seminars)
once a day and republishes one `.ics` feed per series plus a combined feed, so
anyone can subscribe once and have the talks appear on their own calendar.

Feeds produced:

| File | Contents |
| --- | --- |
| `docs/care.ics` | CARE seminars |
| `docs/macro.ics` | MACRO seminars |
| `docs/tec.ics` | TEC seminars |
| `docs/all.ics` | Everything |

Other series (Graduate, Snyder, Babcock, Conferences) get their own file as soon
as the department lists an upcoming event on those tabs.

## Setup, about five minutes

1. Create a new **public** GitHub repository and push these files to `main`.
2. **Settings &rarr; Pages**: set Source to "Deploy from a branch", branch `main`,
   folder `/docs`. Save.
3. **Settings &rarr; Actions &rarr; General**: under Workflow permissions, pick
   "Read and write permissions". The job needs this to commit refreshed feeds.
4. **Actions** tab &rarr; "Update seminar calendars" &rarr; **Run workflow**. The first
   run scrapes the site and rewrites `docs/`.

Your feeds are then at:

```
https://<your-github-username>.github.io/<repo-name>/          landing page
https://<your-github-username>.github.io/<repo-name>/all.ics   combined feed
https://<your-github-username>.github.io/<repo-name>/care.ics  CARE only
```

## Subscribing

- **Apple Calendar / Outlook**: use the `webcal://` link on the landing page, or
  File &rarr; New Calendar Subscription and paste the `https://...ics` URL.
- **Google Calendar**: Other calendars &rarr; **From URL** &rarr; paste the `https`
  link. Google controls its own refresh interval and is often a day behind; that
  is a Google limitation, not a property of the feed.
- Do not use **Import**. Importing copies the events once and never updates.

## How it works

`scrape.py` reads each events tab, follows every event link, and parses the
Drupal fields the department's site emits:

- `<time datetime="...">` gives an unambiguous UTC timestamp, so daylight saving
  is handled by the source rather than guessed here. Feeds are emitted in UTC.
- Location, "Hosted By", and the Speaker / Title / Abstract / Biography sections
  become the event location and description.
- The series code comes from the event title (`CARE Seminar: ...`), falling back
  to the tab the event was listed on.

Stability details that matter for subscribers:

- **UIDs** are a hash of the event URL, so an event stays the same event across
  refreshes instead of duplicating.
- **SEQUENCE** increments whenever a talk's time, room, speaker, or title
  changes, which is how calendar clients know to update an event in place.
- **`events.json`** is a committed cache. Past talks stay in the feeds after the
  department drops them from the upcoming list, so subscribers keep their
  history. An event that disappears while still in the future is treated as
  cancelled and removed.
- If a run parses zero events, it exits non-zero and leaves the existing feeds
  alone rather than publishing an empty calendar.

## Local use

```bash
pip install -r requirements.txt
python scrape.py --out docs --base-url "your-username.github.io/repo-name"
python scrape.py --offline          # rebuild feeds from the cache, no network
python tests/test_parse.py          # parser tests against saved markup
```

## Adjusting

- Seminar length defaults to 90 minutes. Change `SERIES_INFO` in `scrape.py`
  (the third value in each tuple) if a series runs longer or shorter.
- Add a tab to `LISTINGS` to cover another events page.
- Series display names also live in `SERIES_INFO`.

## Caveats

This is a community project, not a department service. It reflects whatever the
department's events pages say at scrape time, so if a talk is moved or cancelled
without the website changing, the feed will not know. If the site's markup is
redesigned, the run will start failing loudly; check the Actions tab.
