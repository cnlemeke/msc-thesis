"""Download NBA.com player biodata for the five seasons and save it as CSV.

The page at https://www.nba.com/stats/players/bio is a JavaScript app, so there
is no table in the page source to scrape. It loads its data from a JSON
endpoint, and this script calls that endpoint directly. That is both more
reliable than scraping the rendered page and far gentler on the site: one
request per season instead of a browser session.

Output goes to data/raw/NBA_<year>_bio.csv with the column names
src/build_dataset.py expects, so the pipeline picks the files up with no
further editing.

Run from the repo root:

    python src/fetch_biodata.py --out-dir data/raw

If the request is refused, see the troubleshooting notes at the bottom of
data/README.md. Nothing here needs an account or an API key.
"""

from __future__ import annotations

import argparse
import csv
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENDPOINT = "https://stats.nba.com/stats/leaguedashplayerbiostats"

SEASONS = {
    2019: "2019-20",
    2020: "2020-21",
    2021: "2021-22",
    2022: "2022-23",
    2023: "2023-24",
}

# stats.nba.com rejects a request that leaves any of its filters out, even the
# ones that should be optional, so every parameter is sent explicitly.
BASE_PARAMS = {
    "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
    "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "",
    "GameSegment": "", "Height": "", "LastNGames": "0", "LeagueID": "00",
    "Location": "", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
    "PORound": "0", "PaceAdjust": "N", "PerMode": "Totals", "Period": "0",
    "PlayerExperience": "", "PlayerPosition": "", "PlusMinus": "N", "Rank": "N",
    "SeasonSegment": "", "SeasonType": "Regular Season", "ShotClockRange": "",
    "StarterBench": "", "TeamID": "0", "VsConference": "", "VsDivision": "",
    "Weight": "",
}

# The endpoint refuses anything that does not look like the site's own client.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Connection": "keep-alive",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
}

# What the endpoint calls each field, against what build_dataset.py expects.
COLUMN_MAP = {
    "PLAYER_NAME": "PLAYER",
    "TEAM_ABBREVIATION": "TEAM",
    "AGE": "AGE",
    "PLAYER_HEIGHT": "HEIGHT",
    "PLAYER_WEIGHT": "WEIGHT",
    "COLLEGE": "COLLEGE",
    "COUNTRY": "COUNTRY",
    "DRAFT_YEAR": "DRAFT YEAR",
    "DRAFT_ROUND": "DRAFT ROUND",
    "DRAFT_NUMBER": "DRAFT NUMBER",
    "GP": "GP",
}

REQUIRED = ["PLAYER", "HEIGHT", "WEIGHT", "GP", "DRAFT YEAR"]


def make_opener() -> urllib.request.OpenerDirector:
    """Build an opener that carries cookies, then warm it up on nba.com.

    stats.nba.com will often stall forever on a client that arrives with no
    session cookie, instead of refusing cleanly. Loading the public page first
    picks up the cookies it expects and makes the data request far more likely
    to answer.
    """
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    try:
        warmup = urllib.request.Request("https://www.nba.com/stats/players/bio",
                                        headers=HEADERS)
        opener.open(warmup, timeout=30).read(1)
        print(f"  session warmed up, {len(jar)} cookies")
    except Exception as exc:  # noqa: BLE001 - the data request may still work
        print(f"  could not load nba.com first ({type(exc).__name__}); continuing anyway")
    return opener


def fetch_season(season: str, opener: urllib.request.OpenerDirector | None = None,
                 timeout: int = 90, attempts: int = 3) -> dict:
    """Call the endpoint for one season and return the decoded JSON.

    stats.nba.com throttles and sometimes stalls, and a request that times out
    can succeed on a retry, so this backs off and tries again.
    """
    opener = opener or urllib.request.build_opener()
    params = dict(BASE_PARAMS, Season=season)
    url = f"{ENDPOINT}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - reported and retried below
            last = exc
            if attempt < attempts:
                wait = 5 * attempt
                print(f"    attempt {attempt} timed out after {timeout}s, "
                      f"retrying in {wait}s")
                time.sleep(wait)
    raise RuntimeError(f"{type(last).__name__} after {attempts} attempts")


def to_rows(payload: dict) -> tuple[list[str], list[list]]:
    """Pull the result set out of the response and rename its columns.

    Returns the header row and the data rows, keeping only the fields the
    pipeline uses.
    """
    result_sets = payload.get("resultSets") or payload.get("resultSet")
    if not result_sets:
        raise ValueError("response has no resultSets; the endpoint may have changed")
    block = result_sets[0] if isinstance(result_sets, list) else result_sets

    source_headers = block["headers"]
    missing = [c for c in COLUMN_MAP if c not in source_headers]
    if missing:
        raise ValueError(f"response is missing expected fields: {missing}")

    keep = [(source_headers.index(src), dest) for src, dest in COLUMN_MAP.items()]
    header = [dest for _, dest in keep]
    rows = [[row[i] for i, _ in keep] for row in block["rowSet"]]
    return header, rows


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        for row in rows:
            writer.writerow(["" if value is None else value for value in row])


def check(header: list[str], rows: list[list], season: str) -> None:
    """Fail loudly on an empty or malformed season rather than writing junk."""
    for column in REQUIRED:
        if column not in header:
            raise ValueError(f"{season}: missing required column {column}")
    if len(rows) < 300:
        raise ValueError(f"{season}: only {len(rows)} players returned, expected 400 or more")
    height = header.index("HEIGHT")
    sample = [r[height] for r in rows[:20] if r[height]]
    if not any("-" in str(v) for v in sample):
        raise ValueError(f"{season}: HEIGHT does not look like feet-inches, got {sample[:3]}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--pause", type=float, default=3.0,
                        help="seconds to wait between seasons, to stay polite")
    parser.add_argument("--timeout", type=int, default=90,
                        help="seconds to wait for each request before giving up")
    args = parser.parse_args(argv)

    # A relative --out-dir is resolved against the current folder, so running
    # this from somewhere unwritable (root, or a system folder) fails before
    # anything is downloaded. Say so plainly rather than raising OSError.
    try:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        target = args.out_dir if args.out_dir.is_absolute() else Path.cwd() / args.out_dir
        print(f"Cannot create the output folder: {target}")
        print(f"  {exc.strerror}")
        print(f"\nYou are running from: {Path.cwd()}")
        print("A relative --out-dir is created inside that folder, and this one "
              "cannot be written to.")
        print("\nEither move somewhere writable first:")
        print("    cd ~/Downloads")
        print(f"    python {Path(sys.argv[0]).name} --out-dir nba_bio")
        print("\nor give a full path:")
        print(f"    python {Path(sys.argv[0]).name} --out-dir ~/Downloads/nba_bio")
        return 1

    opener = make_opener()
    written = []
    for year, season in SEASONS.items():
        path = args.out_dir / f"NBA_{year}_bio.csv"
        print(f"{season} -> {path.name}")
        try:
            header, rows = to_rows(fetch_season(season, opener, timeout=args.timeout))
            check(header, rows, season)
        except Exception as exc:  # noqa: BLE001 - reported, then move on
            print(f"    FAILED: {exc}")
            continue
        write_csv(path, header, rows)
        written.append(path)
        print(f"    {len(rows)} players saved")
        if year != max(SEASONS):
            time.sleep(args.pause)

    print(f"\n{len(written)} of {len(SEASONS)} seasons saved to {args.out_dir.resolve()}")
    if len(written) < len(SEASONS):
        print("\nstats.nba.com did not answer. It stalls rather than refusing, so a")
        print("timeout usually means your network or VPN cannot reach it at all.")
        print("Try --timeout 180, or a different connection.")
        print("\nIf it still will not answer, export by hand instead. It takes about")
        print("five minutes and always works: open")
        print("    https://www.nba.com/stats/players/bio?Season=2019-20")
        print("and use the download icon above the table, once per season.")
        print("See data/README.md for the file names.")
        return 1
    print("\nNext: python src/build_dataset.py --raw-dir data/raw --out-dir data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
