"""Build the modelling tables for the NBA player performance study.

Turns the raw Basketball Reference and NBA.com exports into the two files the
modelling notebook reads:

    data/NBA_Modelling_New.csv
    data/WNBA_Modelling_New.csv

The dissertation describes these steps in section 3.1.3 but its appendix only
shows the first one (concatenation). The rest is rebuilt here from that
description. Every choice that the text does not pin down is marked ASSUMPTION
in a comment and listed in docs/data_pipeline_notes.md.

Run it from the repo root:

    python src/build_dataset.py --raw-dir data/raw --out-dir data
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd

# A Basketball Reference export labelled with the starting year maps to the
# season that begins in that year: 2019 -> "2019-20".
SEASONS = [2019, 2020, 2021, 2022, 2023]

# Rows where a traded player's whole season is aggregated. Basketball Reference
# writes "2TM"/"3TM"/"4TM" for the NBA and "TOT" for the WNBA. The dissertation
# keeps the per-team rows 
# so the aggregate row is dropped.
AGGREGATE_TEAM_LABELS = {"TOT", "2TM", "3TM", "4TM", "5TM"}

# The 36 columns of the modelling table, in the order figure 3.3 shows them.
MODELLING_COLUMNS = [
    "Player", "Pos", "Age", "G", "MP",
    "PER", "TS%", "3PAr", "FTr",
    "ORB%", "DRB%", "TRB%", "AST%", "STL%", "BLK%", "TOV%", "USG%",
    "OWS", "DWS", "WS", "WS/48", "OBPM", "DBPM", "BPM", "VORP",
    "Season", "PTS",
    "WEIGHT", "GP", "Height_cm", "Draft_status", "Years Since Draft",
    "PF", "PG", "SF", "SG",
]

POSITION_DUMMIES = ["PF", "PG", "SF", "SG"]  # C is the reference category


def season_label(start_year: int) -> str:
    """2019 -> '2019-20'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def read_bref_csv(path: Path) -> pd.DataFrame:
    """Read a Basketball Reference export.

    The exports in this project are semicolon separated and carry a UTF-8 BOM.
    Comma separated files are also accepted so the pipeline still works if a
    file is re-exported with different settings.
    """
    with open(path, "r", encoding="utf-8-sig") as fh:
        first_line = fh.readline()
    sep = ";" if first_line.count(";") > first_line.count(",") else ","
    df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
    # Basketball Reference repeats some header names (G and MP appear twice in
    # the WNBA tables); pandas renames the repeats to "G.1", "MP.1".
    df = df.loc[:, ~df.columns.str.match(r".+\.\d+$")]
    df.columns = [c.strip() for c in df.columns]
    return df


# Players whose two exports use genuinely different names rather than a
# different spelling of the same one. Each was checked by matching team,
# games and minutes across the two files. Keyed by the normalised per-game
# name, valued by the normalised advanced name.
NAME_ALIASES = {
    # Basketball Reference against Basketball Reference
    "jeenathan williams": "nate williams",
    # Basketball Reference against NBA.com, which uses the short form
    "cameron reynolds": "cam reynolds",
    "rj nembhard": "ruben nembhard",
    "tre scott": "trevon scott",
    "matthew hurt": "matt hurt",
    # Basketball Reference against stats.wnba.com. Three are married or
    # reverted surnames that one source adopted and the other did not; the
    # fourth is a nickname WNBA.com prints in brackets.
    "skylar digginssmith": "skylar diggins",      # WNBA.com: Skylar Diggins
    "cheyenne parker": "cheyenne parkertyus",     # WNBA.com: Cheyenne Parker-Tyus
    "brittany boyd": "brittany boydjones",        # WNBA.com: Brittany Boyd-Jones
    "ad durr": "asia ad durr",                    # WNBA.com: Asia (AD) Durr
    # The WNBA per-game exports predate her marriage; the advanced exports and
    # WNBA.com both use the married name.
    "megan gustafson": "megan dileo",
}

# Players Basketball Reference lists but stats.wnba.com has no biodata row for,
# in any season. Their rows lose WEIGHT, GP and Height_cm and are dropped with
# the other incomplete rows. Recorded here so the loss is visible rather than
# silent.
WNBA_BIO_ABSENT = ("nia coffey",)

# Basketball Reference appends summary rows to some exports. They are not
# players and must not reach the modelling table.
NON_PLAYER_ROWS = {"league average", "league averages", "team totals"}


def clean_player_names(s: pd.Series) -> pd.Series:
    """Strip the Hall-of-Fame asterisk and surrounding spaces."""
    return s.astype(str).str.replace("*", "", regex=False).str.strip()


def name_key(s: pd.Series) -> pd.Series:
    """Build the key the two exports are joined on.

    The per-game and advanced exports do not spell names the same way. The
    per-game files strip accents and drop generational suffixes, while the
    advanced files keep both: "Dante Exum" against "Danté Exum", "Jeff Dowtin"
    against "Jeff Dowtin Jr.". Joining on the raw name loses those players, so
    the key folds accents to plain ASCII, removes the suffix, lowercases, and
    collapses punctuation and spacing.
    """
    folded = (
        s.astype(str)
        .map(lambda t: unicodedata.normalize("NFKD", t))
        .str.encode("ascii", "ignore").str.decode("ascii")
        .str.replace("*", "", regex=False)
        .str.lower()
        .str.replace(r"\b(jr|sr|ii|iii|iv)\.?\s*$", "", regex=True)
        .str.replace(r"[^a-z\s]", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    return folded.replace(NAME_ALIASES)


def drop_aggregate_team_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove the combined-season row a traded player also gets."""
    team_col = "Team" if "Team" in df.columns else "Tm"
    keep = ~df[team_col].astype(str).str.upper().isin(AGGREGATE_TEAM_LABELS)
    return df.loc[keep].copy()


def load_season_stack(paths: dict[int, Path], kind: str) -> pd.DataFrame:
    """Read one file per season, tag it with Season, and stack them.

    This is the step appendix B2 shows. The aggregate rows for traded players
    are dropped here so later joins cannot double count them.
    """
    frames = []
    for year in sorted(paths):
        df = read_bref_csv(paths[year])
        df = drop_aggregate_team_rows(df)
        df["Season"] = season_label(year)
        if "Tm" in df.columns and "Team" not in df.columns:
            df = df.rename(columns={"Tm": "Team"})
        df["Player"] = clean_player_names(df["Player"])
        df["name_key"] = name_key(df["Player"])
        summary = df["name_key"].isin(NON_PLAYER_ROWS)
        if summary.any():
            print(f"    dropped {int(summary.sum())} summary row(s) from "
                  f"{season_label(year)}: {df.loc[summary, 'Player'].tolist()}")
            df = df.loc[~summary]
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    # Rk is a row number in the export and carries no information.
    out = out.drop(columns=[c for c in ("Rk", "Awards", "Player-additional") if c in out.columns])

    # Two different players must never fold onto the same key within a season.
    clash = (out.groupby(["name_key", "Team", "Season"])["Player"]
             .nunique().pipe(lambda s: s[s > 1]))
    if len(clash):
        raise ValueError(f"name key collides for {len(clash)} player-team-seasons: "
                         f"{clash.index.tolist()[:5]}")

    print(f"  {kind}: {len(out)} rows across {len(paths)} seasons")
    return out


def height_to_cm(value) -> float:
    """Convert an NBA.com height such as '6-7' to centimetres.

    Returns NaN for anything that does not parse, so the row can be dropped
    with the other missing values rather than silently becoming a number.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    text = str(value).strip()
    match = re.fullmatch(r"(\d+)\s*[-']\s*(\d+(?:\.\d+)?)\"?", text)
    if match:
        feet, inches = float(match.group(1)), float(match.group(2))
        return round((feet * 12 + inches) * 2.54, 3)
    try:  # already numeric: treat a plausible value as centimetres
        number = float(text)
    except ValueError:
        return float("nan")
    return round(number, 3) if number > 100 else float("nan")


def prepare_biodata(bio: pd.DataFrame, season: str) -> pd.DataFrame:
    """Normalise one season of NBA.com biodata to the columns we keep.

    NBA.com exports headers in capitals and sometimes with spaces. Only the
    fields the dissertation lists are carried forward.
    """
    bio = bio.copy()
    bio.columns = [c.strip().upper() for c in bio.columns]
    rename = {
        "PLAYER": "Player", "PLAYER NAME": "Player",
        "HEIGHT": "HEIGHT", "WEIGHT": "WEIGHT", "GP": "GP",
        "DRAFT YEAR": "DRAFT YEAR", "DRAFT_YEAR": "DRAFT YEAR",
        "DRAFT ROUND": "DRAFT ROUND", "DRAFT NUMBER": "DRAFT NUMBER",
    }
    bio = bio.rename(columns={k: v for k, v in rename.items() if k in bio.columns})
    missing = [c for c in ("Player", "HEIGHT", "WEIGHT", "GP", "DRAFT YEAR") if c not in bio.columns]
    if missing:
        raise ValueError(f"biodata for {season} is missing columns: {missing}")

    bio["Player"] = clean_player_names(bio["Player"])
    bio["name_key"] = name_key(bio["Player"])
    bio["Height_cm"] = bio["HEIGHT"].map(height_to_cm)
    bio["WEIGHT"] = pd.to_numeric(bio["WEIGHT"], errors="coerce")
    bio["GP"] = pd.to_numeric(bio["GP"], errors="coerce")

    # ASSUMPTION: NBA.com writes "Undrafted" in the draft year field for an
    # undrafted player. Draft_status is 1 when a draft year is present.
    draft_year = pd.to_numeric(bio["DRAFT YEAR"], errors="coerce")
    bio["Draft_status"] = draft_year.notna().astype(float)
    # ASSUMPTION: years since draft counts from the season's starting year, and
    # is 0 for an undrafted player, who has no draft year to count from.
    bio["Years Since Draft"] = (int(season[:4]) - draft_year).fillna(0.0)
    bio["Season"] = season

    # Two different players must not fold onto the same key, or the dedup below
    # would quietly drop one of them and the wrong biodata would be joined on.
    clash = bio.groupby("name_key")["Player"].nunique().pipe(lambda s: s[s > 1])
    if len(clash):
        lines = []
        for key in clash.index[:3]:
            names = sorted(bio.loc[bio["name_key"] == key, "Player"].unique())
            shown = ", ".join(names[:3])
            more = f" and {len(names) - 3} more" if len(names) > 3 else ""
            lines.append(f"  {key!r}: {shown}{more}")
        raise ValueError(
            f"{season}: {len(clash)} name key(s) match more than one player:\n"
            + "\n".join(lines))

    # Age is carried through only when the export has it. Basketball
    # Reference's NBA advanced table already supplies Age, but its WNBA table
    # does not, so for the WNBA this is the only source of that column.
    keep = ["name_key", "Season", "WEIGHT", "GP", "Height_cm", "Draft_status", "Years Since Draft"]
    if "AGE" in bio.columns:
        bio["Age"] = pd.to_numeric(bio["AGE"], errors="coerce")
        keep.insert(2, "Age")
    return bio.loc[:, keep].drop_duplicates(subset=["name_key", "Season"], keep="first")


def add_position_dummies(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode the primary position, with centre as the reference.

    A player listed as "PF-SF" is counted under the first position shown, which
    is the one Basketball Reference treats as primary.
    """
    primary = df["Pos"].astype(str).str.split("-").str[0].str.strip().str.upper()
    for position in POSITION_DUMMIES:
        df[position] = (primary == position).astype(int)
    return df


def build_nba_table(per_game: pd.DataFrame, advanced: pd.DataFrame,
                    biodata: pd.DataFrame | None,
                    min_minutes: float = 0.0) -> pd.DataFrame:
    """Join the three sources and return the modelling table.

    Section 3.1.3.1 of the dissertation: player statistics are joined to the
    advanced statistics on player, team and season with an inner join, and the
    result is joined to the biodata on player and season with a left join.
    """
    # PTS is the only per-game column the modelling table keeps; every other
    # feature comes from the advanced table, which already covers the same
    # ground as a rate rather than a count.
    left = per_game.loc[:, ["name_key", "Team", "Season", "PTS"]].copy()
    left["PTS"] = pd.to_numeric(left["PTS"], errors="coerce")

    merged = advanced.merge(left, on=["name_key", "Team", "Season"], how="inner")
    dropped = len(advanced) - len(merged)
    print(f"  inner join with per-game stats: {len(merged)} rows"
          f"{f' ({dropped} advanced rows had no match)' if dropped else ''}")
    if dropped:
        unmatched = advanced.merge(left, on=["name_key", "Team", "Season"],
                                   how="left", indicator=True)
        names = unmatched.loc[unmatched["_merge"] == "left_only", "Player"].unique()
        print(f"    unmatched players: {sorted(names)[:10]}")

    if biodata is not None:
        # The advanced table already carries Age for the NBA, so the biodata
        # copy is dropped rather than creating an Age_x / Age_y pair.
        biodata = biodata.drop(columns=["Age"], errors="ignore")
        merged = merged.merge(biodata, on=["name_key", "Season"], how="left")
        print(f"  left join with biodata: {len(merged)} rows, "
              f"{int(merged['Height_cm'].isna().sum())} without a biodata match")

    merged = add_position_dummies(merged)

    present = [c for c in MODELLING_COLUMNS if c in merged.columns]
    absent = [c for c in MODELLING_COLUMNS if c not in merged.columns]
    if absent:
        print(f"  note: columns not present in the inputs: {absent}")
    table = merged.loc[:, present].copy()

    # Section 3.1.3.2: rows with missing values are dropped rather than imputed.
    numeric = [c for c in table.columns if c not in ("Player", "Pos", "Season")]
    table[numeric] = table[numeric].apply(pd.to_numeric, errors="coerce")
    before = len(table)
    table = table.dropna().reset_index(drop=True)
    print(f"  dropped {before - len(table)} rows with missing values -> {len(table)} rows")
    return apply_minutes_floor(table, min_minutes)


def apply_minutes_floor(table: pd.DataFrame, min_minutes: float) -> pd.DataFrame:
    """Optionally drop players below a minutes threshold.

    Off by default. See the --min-minutes help text for why it exists.
    """
    if not min_minutes or "MP" not in table.columns:
        return table
    before = len(table)
    table = table.loc[table["MP"] >= min_minutes].reset_index(drop=True)
    print(f"  minutes floor of {min_minutes:g}: dropped {before - len(table)} rows "
          f"-> {len(table)} rows")
    return table


def build_wnba_table(per_game: pd.DataFrame, advanced: pd.DataFrame,
                     biodata: pd.DataFrame | None = None,
                     min_minutes: float = 0.0) -> pd.DataFrame:
    """Same shape as the NBA table.

    The WNBA biodata comes from stats.wnba.com, which serves the same endpoint
    as NBA.com under LeagueID 10. Without it the table loses WEIGHT, GP and
    Height_cm, and the author's notebook cannot run its cross-league section,
    because it selects the NBA feature list out of the WNBA frame.

    Basketball Reference's WNBA advanced table is narrower than the NBA one: it
    has no DRB%, WS/48, OBPM, DBPM, BPM or VORP. Those columns are simply
    absent here, and the column-removal step in the modelling notebook drops
    every one of them anyway.
    """
    left = per_game.loc[:, ["name_key", "Team", "Season", "PTS"]].copy()
    left["PTS"] = pd.to_numeric(left["PTS"], errors="coerce")
    merged = advanced.merge(left, on=["name_key", "Team", "Season"], how="inner")
    dropped = len(advanced) - len(merged)
    print(f"  inner join with per-game stats: {len(merged)} rows"
          f"{f' ({dropped} advanced rows had no match)' if dropped else ''}")

    if biodata is not None:
        merged = merged.merge(biodata, on=["name_key", "Season"], how="left")
        missing = int(merged["Height_cm"].isna().sum())
        print(f"  left join with biodata: {len(merged)} rows, "
              f"{missing} without a biodata match")
        if missing:
            names = merged.loc[merged["Height_cm"].isna(), "Player"].unique()
            print(f"    unmatched: {sorted(names)[:10]}")

    merged = add_position_dummies(merged)
    present = [c for c in MODELLING_COLUMNS if c in merged.columns]
    table = merged.loc[:, present].copy()
    numeric = [c for c in table.columns if c not in ("Player", "Pos", "Season")]
    # The WNBA export writes a bare "-" where a rate is undefined.
    table[numeric] = table[numeric].replace("-", pd.NA).apply(pd.to_numeric, errors="coerce")
    before = len(table)
    table = table.dropna().reset_index(drop=True)
    print(f"  dropped {before - len(table)} rows with missing values -> {len(table)} rows")
    return apply_minutes_floor(table, min_minutes)


def find_files(raw_dir: Path, patterns: list[str]) -> dict[int, Path]:
    """Locate one file per season using the first pattern that matches."""
    found: dict[int, Path] = {}
    for year in SEASONS:
        for pattern in patterns:
            matches = sorted(raw_dir.glob(pattern.format(year=year)))
            if matches:
                found[year] = matches[0]
                break
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--min-minutes", type=float, default=0.0, metavar="MP",
        help=(
            "Drop players below this many minutes in a season. Default 0, which "
            "keeps everyone and reconstructs the table as described. Rate "
            "statistics are meaningless at the bottom of this range: 27 NBA rows "
            "sit under 5 minutes with PER from -45.2 to 76.2, against -40.6 to "
            "45.5 for everyone else, and those few rows move the reported errors "
            "substantially. See docs/data_pipeline_notes.md."
        ),
    )
    args = parser.parse_args(argv)

    raw, out = args.raw_dir, args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    sets = {
        "NBA per-game": find_files(raw, ["*NBA_{year}_stats.csv", "*NBA_{year}_per_game.csv"]),
        "NBA advanced": find_files(raw, ["*NBA_{year}_advanced.csv"]),
        "NBA biodata": find_files(raw, ["*NBA_{year}_bio.csv", "*nba_{year}_biodata.csv"]),
        "WNBA per-game": find_files(raw, ["*wnba{year}*.csv", "*WNBA_{year}_per_game.csv"]),
        "WNBA advanced": find_files(raw, ["*WNBA_{year}_advanced.csv", "*wnba_{year}_advanced.csv"]),
        "WNBA biodata": find_files(raw, ["*WNBA_{year}_bio.csv", "*wnba_{year}_bio.csv"]),
    }
    print("Files found in", raw.resolve())
    for name, paths in sets.items():
        missing = [season_label(y) for y in SEASONS if y not in paths]
        state = "complete" if not missing else f"MISSING {', '.join(missing)}"
        print(f"  {name:16s} {len(paths)}/5  {state}")

    # Each league is built on its own, so a missing WNBA file does not hold up
    # the NBA table. Whatever can be built is written; the rest is reported.
    complete = {name: len(paths) == len(SEASONS) for name, paths in sets.items()}
    written, skipped = [], []

    if complete["NBA per-game"] and complete["NBA advanced"]:
        print("\nNBA")
        biodata = None
        if complete["NBA biodata"]:
            biodata = pd.concat(
                [prepare_biodata(read_bref_csv(sets["NBA biodata"][y]), season_label(y))
                 for y in SEASONS],
                ignore_index=True,
            )
            print(f"  biodata: {len(biodata)} rows across {len(SEASONS)} seasons")
        else:
            print("  biodata: not found, building without the biodata columns")
        nba = build_nba_table(
            load_season_stack(sets["NBA per-game"], "per-game"),
            load_season_stack(sets["NBA advanced"], "advanced"),
            biodata,
            args.min_minutes,
        )
        path = out / "NBA_Modelling_New.csv"
        nba.to_csv(path, index=False)
        written.append((path, nba.shape))

        counts = nba.groupby("Season")["Player"].nunique().sort_index()
        reported = {"2019-20": 528, "2020-21": 540, "2021-22": 605,
                    "2022-23": 538, "2023-24": 571}
        print("\n  Unique players per season, against figure 3.4:")
        for season, n in counts.items():
            diff = n - reported.get(season, 0)
            print(f"    {season}: {n:4d}   dissertation {reported.get(season, '?'):>4}"
                  f"   {'exact' if diff == 0 else f'{diff:+d}'}")
    else:
        skipped.append("NBA (needs the per-game and advanced exports)")

    if complete["WNBA per-game"] and complete["WNBA advanced"]:
        print("\nWNBA")
        wnba_bio = None
        if complete["WNBA biodata"]:
            wnba_bio = pd.concat(
                [prepare_biodata(read_bref_csv(sets["WNBA biodata"][y]), season_label(y))
                 for y in SEASONS],
                ignore_index=True,
            )
            print(f"  biodata: {len(wnba_bio)} rows across {len(SEASONS)} seasons")
        else:
            print("  biodata: not found, building without the biodata columns")
        wnba = build_wnba_table(
            load_season_stack(sets["WNBA per-game"], "per-game"),
            load_season_stack(sets["WNBA advanced"], "advanced"),
            wnba_bio,
            args.min_minutes,
        )
        path = out / "WNBA_Modelling_New.csv"
        wnba.to_csv(path, index=False)
        written.append((path, wnba.shape))
    else:
        skipped.append("WNBA (needs the per-game and advanced exports)")

    print()
    for path, shape in written:
        print(f"Wrote {path} ({shape[0]} rows, {shape[1]} columns)")
    for item in skipped:
        print(f"Not built: {item}")
    if skipped:
        print("See data/README.md for the download links.")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
