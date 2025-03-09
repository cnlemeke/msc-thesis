"""Turn saved stats.nba.com JSON responses into the biodata CSVs.

Use this with the browser-tab route, for when both the Python fetch and the
console snippet are blocked. Opening a URL directly in a tab is an ordinary
page load, not a cross-origin request, so nothing can refuse it on CORS
grounds and no cookies or headers are needed.

HOW TO USE

  1. Open each of these five URLs in a browser tab. Each one shows or
     downloads a block of JSON.

       python src/convert_biodata_json.py --print-urls

  2. Save each page as a .json file, anywhere you like. In Chrome use
     File > Save Page As, or right click and Save As. The file names do not
     matter; the season is read from inside each file.

  3. Point this script at the folder you saved them in:

       python src/convert_biodata_json.py --json-dir ~/Downloads --out-dir data/raw

It writes NBA_<year>_bio.csv for each season it finds, named by the season's
starting year, which is what src/build_dataset.py expects.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_biodata import (  # noqa: E402
    BASE_PARAMS, ENDPOINT, SEASONS, check, to_rows, write_csv,
)

SEASON_TO_YEAR = {season: year for year, season in SEASONS.items()}


def urls() -> list[tuple[str, str]]:
    """The five URLs to open, one per season."""
    return [(season, f"{ENDPOINT}?{urllib.parse.urlencode(dict(BASE_PARAMS, Season=season))}")
            for season in SEASONS.values()]


def season_of(payload: dict, path: Path) -> str | None:
    """Work out which season a saved response is for.

    The response carries its own parameters, so the file name does not matter.
    If those are missing, fall back to a season written in the file name.
    """
    params = payload.get("parameters") or {}
    season = params.get("Season") or params.get("SeasonYear")
    if season in SEASON_TO_YEAR:
        return season
    for candidate in SEASONS.values():
        if candidate in path.name:
            return candidate
    return None


def load(path: Path) -> dict | None:
    """Read a saved response, tolerating a file saved as HTML-wrapped JSON."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Some browsers wrap a JSON view in markup when the page is saved.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print-urls", action="store_true",
                        help="print the five URLs to open, then exit")
    parser.add_argument("--json-dir", type=Path, default=Path("."),
                        help="folder holding the saved .json files")
    parser.add_argument("--out-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)

    if args.print_urls:
        print("Open each of these in a browser tab and save the page as .json:\n")
        for season, url in urls():
            print(f"{season}\n{url}\n")
        return 0

    candidates = sorted(p for p in args.json_dir.glob("*")
                        if p.is_file() and p.suffix.lower() in (".json", ".txt", ""))
    if not candidates:
        print(f"No .json files found in {args.json_dir.resolve()}")
        print("Run with --print-urls to get the five URLs to save first.")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written, seen = [], set()
    for path in candidates:
        payload = load(path)
        if not payload or "resultSets" not in payload:
            continue
        season = season_of(payload, path)
        if season is None:
            print(f"{path.name}: cannot tell which season this is, skipping")
            continue
        if season in seen:
            print(f"{path.name}: {season} already done, skipping")
            continue
        try:
            header, rows = to_rows(payload)
            check(header, rows, season)
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: {exc}")
            continue
        out = args.out_dir / f"NBA_{SEASON_TO_YEAR[season]}_bio.csv"
        write_csv(out, header, rows)
        written.append(out)
        seen.add(season)
        print(f"{path.name}  ->  {out.name}  ({len(rows)} players, {season})")

    missing = [s for s in SEASONS.values() if s not in seen]
    print(f"\n{len(written)} of {len(SEASONS)} seasons converted into {args.out_dir.resolve()}")
    if missing:
        print("Still missing:", ", ".join(missing))
        print("Run with --print-urls to get the URLs for those seasons.")
        return 1
    print("\nNext: python src/build_dataset.py --raw-dir data/raw --out-dir data")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
