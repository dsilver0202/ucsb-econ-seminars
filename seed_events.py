#!/usr/bin/env python3
"""Seed events.json with the 2026-27 schedule captured on 2026-09-21.

This exists so the repository ships with working feeds before the first
scheduled scrape runs. Speaker bios and abstracts are filled in by scrape.py.
"""
import json
from scrape import Event, SERIES_INFO, DEFAULT_MINUTES

BASE = "https://econ.ucsb.edu/events/all/"

# slug, ISO start (UTC), title, speaker, host, talk title
ROWS = [
 ("2026/care-seminar-yihong-liu-university-california-santa-barbara","2026-10-07T22:30:00Z","CARE Seminar: Yihong Liu, University of California, Santa Barbara","Yihong Liu, University of California, Santa Barbara","Daniel Martin",""),
 ("2026/care-seminar-juan-nicolas-herrera-university-california-santa-barbara","2026-10-14T22:30:00Z","CARE Seminar: Juan Nicolas Herrera, University of California, Santa Barbara","Juan Nicolas Herrera, University of California, Santa Barbara","Daniel Martin",""),
 ("2026/care-seminar-mauricio-colladom-university-california-santa-barbara","2026-10-21T22:30:00Z","CARE Seminar: Mauricio Colladom University of California, Santa Barbara","Mauricio Collado, University of California, Santa Barbara","Daniel Martin",""),
 ("2026/macro-seminar-diego-daruich-university-southern-california","2026-10-29T22:30:00Z","MACRO Seminar: Diego Daruich, University of Southern California","Diego Daruich, University of Southern California","",'"The Macroeconomics of Intergenerational Mental Health Dynamics"'),
 ("2026/care-seminar-barbara-biasi-yale-som","2026-11-04T23:30:00Z","CARE Seminar: Barbara Biasi, Yale SOM)","Barbara Biasi, Yale SOM","Mitchell Hoffman",""),
 ("2026/macro-seminar-fahad-saleh-university-florida","2026-11-05T23:30:00Z","MACRO Seminar: Fahad Saleh, University of Florida","Fahad Saleh, University of Florida","Rod Garratt",""),
 ("2026/tec-seminar-ori-heffetz-cornell-university","2026-11-10T20:30:00Z","TEC Seminar: Ori Heffetz, Cornell University","Ori Heffetz, Cornell University","Jason Somerville",""),
 ("2026/macro-seminar-sephorah-mangin-australian-national-university","2026-11-12T23:30:00Z","MACRO Seminar: Sephorah Mangin, Australian National University","Sephorah Mangin, Australian National University","Peter Rupert",""),
 ("2026/tec-seminar-kirby-nielsen-cal-tech","2026-11-17T20:30:00Z","TEC Seminar: Kirby Nielsen, Cal Tech","Kirby Nielsen, Cal Tech","Jason Somerville",""),
 ("2026/care-seminar-felipe-lobel-duke","2026-11-18T23:30:00Z","CARE Seminar: Felipe Lobel, Duke","Felipe Lobel, Duke","Youssef Benzarti",""),
 ("2026/macro-seminar-jeremy-pearce-federal-reserve-bank-new-york","2026-11-19T23:30:00Z","MACRO Seminar: Jeremy Pearce, Federal Reserve Bank of New York","Jeremy Pearce, Federal Reserve Bank of New York","Yueyuan Ma",""),
 ("2026/tec-seminar-paulo-natenzon-washington-university-saint-louis","2026-12-01T20:30:00Z","TEC Seminar: Paulo Natenzon, Washington University in Saint Louis","Paulo Natenzon, Washington University in Saint Louis","Jason Somerville",""),
 ("2026/care-seminar-eleonora-patacchini-cornell-university","2026-12-02T23:30:00Z","CARE Seminar: Eleonora Patacchini, Cornell University","Eleonora Patacchini","Peter Kuhn",""),
 ("2027/care-seminar-yana-gallen-university-chicago","2027-01-13T23:30:00Z","CARE Seminar: Yana Gallen, University of Chicago","Yana Gallen, University of Chicago","Heather Royer",""),
 ("2027/macro-seminar-jeremy-greenwood-university-pennsylvania","2027-01-14T23:30:00Z","MACRO Seminar: Jeremy Greenwood, University of Pennsylvania","Jeremy Greenwood, University of Pennsylvania","Peter Rupert",""),
 ("2027/care-seminar-eric-chyn-university-texas-austin","2027-02-03T23:30:00Z","CARE Seminar: Eric Chyn, University of Texas at Austin","Eric Chyn, University of Texas at Austin","Heather Royer",""),
 ("2027/macro-seminar-adrien-bilal-stanford","2027-02-04T23:30:00Z","MACRO Seminar: Adrien Bilal, Stanford","Adrien Bilal, Stanford","Simon Margolin",""),
 ("2027/care-seminar-nicole-maestas-harvard-medical","2027-02-10T23:30:00Z","CARE Seminar: Nicole Maestas, Harvard Medical","Nicole Maestas, Harvard Medical","David Silver",""),
 ("2027/macro-seminar-jane-olmstead-rumsey-london-school-economics","2027-03-04T23:30:00Z","MACRO Seminar: Jane Olmstead-Rumsey, London School of Economics","Jane Olmstead-Rumsey, London School of Economics","Laura Murphy",""),
 ("2027/care-seminar-ben-handel-uc-berkeley","2027-03-10T23:30:00Z","CARE Seminar: Ben Handel, UC Berkeley","Ben Handel, UC Berkeley","H. E. (Ted) Frech, III",""),
 ("2027/care-seminar-rebekah-dix-stanford","2027-03-31T22:30:00Z","CARE Seminar: Rebekah Dix, Stanford","Rebekah Dix, Stanford","David Silver",""),
 ("2027/care-seminar-audrey-guo-santa-clara-university","2027-04-07T22:30:00Z","CARE Seminar: Audrey Guo, Santa Clara University","Audrey Guo, Santa Clara University","Youssef Benzarti",""),
 ("2027/care-seminar-leonardo-bursztyn-university-chicago","2027-04-14T22:30:00Z","CARE Seminar: Leonardo Bursztyn, University of Chicago","Leonardo Bursztyn, University of Chicago","Heather Royer",""),
 ("2027/care-seminar-cody-tuttle-university-texas-austin","2027-05-05T22:30:00Z","CARE Seminar: Cody Tuttle, University of Texas at Austin","Cody Tuttle, University of Texas at Austin","David Silver",""),
 ("2027/care-seminar-guo-xu-berkeley-haas","2027-05-19T22:30:00Z","CARE Seminar: Guo Xu, Berkeley Haas","Guo Xu, Berkeley Haas","Mitchell Hoffman",""),
 ("2027/care-seminar-chris-walters-university-california-berkeley","2027-05-26T22:30:00Z","CARE Seminar: Chris Walters, University California, Berkeley","Chris Walters, University California, Berkeley","Mitchell Hoffman",""),
]


def main() -> None:
    events = []
    for slug, start, title, speaker, host, talk in ROWS:
        code = title.split(" ", 1)[0].upper()
        ev = Event(
            url=BASE + slug,
            title=title,
            start_utc=start,
            series=code,
            location="North Hall 2111",
            speaker=speaker,
            talk_title=talk,
            hosted_by=[host] if host else [],
            minutes=SERIES_INFO.get(code, (None, None, DEFAULT_MINUTES))[2],
        )
        ev.content_hash = ev.fingerprint()
        events.append(ev)

    from dataclasses import asdict
    with open("events.json", "w") as fh:
        json.dump([asdict(e) for e in events], fh, indent=1, ensure_ascii=False)
    print(f"wrote events.json with {len(events)} events")


if __name__ == "__main__":
    main()
