"""Parser tests against real markup captured from econ.ucsb.edu."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape import parse_event, series_code, build_ics, Event  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "event.html")


def load():
    with open(FIXTURE) as fh:
        return fh.read()


def test_parses_core_fields():
    ev = parse_event(load(), "https://econ.ucsb.edu/events/all/2026/macro-seminar-diego-daruich-university-southern-california", None)
    assert ev is not None
    assert ev.series == "MACRO"
    assert ev.start_utc == "2026-10-29T22:30:00Z"
    assert ev.location == "North Hall 2111"
    assert ev.speaker.startswith("Diego Daruich")
    assert "Intergenerational Mental Health" in ev.talk_title
    assert ev.hosted_by == ["Rod Garratt"]
    assert ev.bio.startswith("I am an Assistant Professor")


def test_start_is_3_30_pacific():
    ev = parse_event(load(), "https://econ.ucsb.edu/x", None)
    # 22:30 UTC on Oct 29 is 3:30pm Pacific Daylight Time.
    assert ev.start.hour == 22 and ev.start.minute == 30
    assert ev.end - ev.start == dt.timedelta(minutes=90)


def test_series_code_variants():
    assert series_code("CARE Seminar: A B, C", None) == "CARE"
    assert series_code("TEC Seminar: X", None) == "TEC"
    assert series_code("Snyder Lecture: Someone", None) == "SNYDER"
    assert series_code("Annual Alumni Mixer", "GRADUATE") == "GRADUATE"
    assert series_code("Annual Alumni Mixer", None) == "OTHER"


def test_ics_escaping_and_folding():
    ev = Event(
        url="https://econ.ucsb.edu/x",
        title="CARE Seminar: Someone, Somewhere",
        start_utc="2026-10-07T22:30:00Z",
        series="CARE",
        location="North Hall 2111",
        speaker="Someone, Somewhere; with a semicolon",
        talk_title='"A Very Long Talk Title That Should Be Folded Across Several Lines Because It Exceeds Seventy Five Octets"',
    )
    text = build_ics([ev], "Test", "Test feed")
    assert "\\, Somewhere\\; with" in text
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert text.endswith("END:VCALENDAR\r\n")
    for line in text.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"ok   {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if failures else 0)
