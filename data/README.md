# Data

The dataset used for this work is public. Basketball Reference and NBA.com own the underlying data and their terms of use apply to it.

## What the pipeline needs

Put all of these in `data/raw`, then run:

```
python src/build_dataset.py --raw-dir data/raw --out-dir data
```

The script prints which sets are complete and which are missing, so you can run it at any point to check your progress.

### Naming, and one trap

**Every file is named by the season's starting year.** The 2019-20 season is `2019`.

Basketball Reference does the opposite for the NBA: it names a season by its **ending** year, so the 2019-20 season lives at `NBA_2020_advanced.html`. Download from their URL, save under ours. The WNBA plays inside one calendar year, so there is no mismatch there.

### 1. NBA per-game stats, 5 files

Already in the repo.

| Save as | Season |
|---|---|
| `NBA_2019_stats.csv` | 2019-20 |
| `NBA_2020_stats.csv` | 2020-21 |
| `NBA_2021_stats.csv` | 2021-22 |
| `NBA_2022_stats.csv` | 2022-23 |
| `NBA_2023_stats.csv` | 2023-24 |

### 2. NBA advanced stats, 5 files

Already in the repo. This is where PER and Win Share come from.

| Save as | Season | Download from |
|---|---|---|
| `NBA_2019_advanced.csv` | 2019-20 | https://www.basketball-reference.com/leagues/NBA_2020_advanced.html |
| `NBA_2020_advanced.csv` | 2020-21 | https://www.basketball-reference.com/leagues/NBA_2021_advanced.html |
| `NBA_2021_advanced.csv` | 2021-22 | https://www.basketball-reference.com/leagues/NBA_2022_advanced.html |
| `NBA_2022_advanced.csv` | 2022-23 | https://www.basketball-reference.com/leagues/NBA_2023_advanced.html |
| `NBA_2023_advanced.csv` | 2023-24 | https://www.basketball-reference.com/leagues/NBA_2024_advanced.html |

On each page, use **Share and Export**, then **Get table as CSV**, and save the result.

Expected columns: `Rk, Player, Age, Team, Pos, G, MP, PER, TS%, 3PAr, FTr, ORB%, DRB%, TRB%, AST%, STL%, BLK%, TOV%, USG%, OWS, DWS, WS, WS/48, OBPM, DBPM, BPM, VORP`.

### 3. WNBA per-game stats, 5 files

Already in the repo.

| Save as | Season |
|---|---|
| `wnba2019.csv` | 2020 |
| `wnba2020.csv` | 2021 |
| `wnba2021.csv` | 2022 |
| `wnba2022.csv` | 2023 |
| `wnba2023.csv` | 2024 |

The names line up with the NBA seasons they are compared against, not with the WNBA calendar year.

### 4. WNBA advanced stats, 5 files

Already in the repo.

| Save as | WNBA season | Download from |
|---|---|---|
| `WNBA_2019_advanced.csv` | 2020 | https://www.basketball-reference.com/wnba/years/2020_advanced.html |
| `WNBA_2020_advanced.csv` | 2021 | https://www.basketball-reference.com/wnba/years/2021_advanced.html |
| `WNBA_2021_advanced.csv` | 2022 | https://www.basketball-reference.com/wnba/years/2022_advanced.html |
| `WNBA_2022_advanced.csv` | 2023 | https://www.basketball-reference.com/wnba/years/2023_advanced.html |
| `WNBA_2023_advanced.csv` | 2024 | https://www.basketball-reference.com/wnba/years/2024_advanced.html |

**Mind the year.** The file name is the NBA season's starting year, the WNBA season is the year after it. The study compares the 2019-20 NBA season with the 2020 WNBA season, so `WNBA_2019_advanced.csv` holds 2020 data. Downloading the 2019 WNBA season instead shifts every file by one and silently drops 2024.

The WNBA advanced table is narrower than the NBA one: no `DRB%`, `WS/48`, `OBPM`, `DBPM`, `BPM`, `VORP`, and no `Age`. The column-removal step in the modelling notebook drops the first six anyway, and `Age` comes from the biodata.

### 5. NBA player biodata, 5 files

Already in the repo, fetched from the NBA.com endpoint on 31 October 2026.

These are required for notebook 02: its column-removal cell names `Draft_status` and `Years Since Draft`, and both come from the biodata, so without them the cell raises a `KeyError`. The instructions below are kept for re-fetching.

NBA.com serves these from a JSON endpoint that is often unreachable from outside a browser, so there are several routes below. Any one of them is fine.

There are two ways to get them. The script is quicker and names the files correctly for you.

#### Option A: run the script

```
python src/fetch_biodata.py --out-dir data/raw
```

It downloads all five seasons and writes them with the column names the pipeline expects. No account and no API key. It pauses between seasons to stay polite, and retries if a request is refused.

The page at https://www.nba.com/stats/players/bio is a JavaScript app with no table in its page source, so there is nothing useful to scrape from the HTML. It loads its data from a JSON endpoint instead, and the script calls that endpoint directly: one request per season rather than a browser session.

#### Option B: export by hand

Go to https://www.nba.com/stats/players/bio, pick the season in the dropdown, and use the download icon above the table. Save each file as below.

| Save as | Season on nba.com |
|---|---|
| `NBA_2019_bio.csv` | 2019-20 |
| `NBA_2020_bio.csv` | 2020-21 |
| `NBA_2021_bio.csv` | 2021-22 |
| `NBA_2022_bio.csv` | 2022-23 |
| `NBA_2023_bio.csv` | 2023-24 |

Needed columns: `PLAYER, HEIGHT, WEIGHT, GP, DRAFT YEAR`. Height is read in feet-inches form, such as `6-7`. A hand export may name the player column `PLAYER NAME` instead; the pipeline accepts either.

#### Option C: run it from the browser console

Use this if the script times out and you cannot find the export button. Your browser already holds
the session cookies stats.nba.com wants, so it works where a terminal request stalls.

1. Open https://www.nba.com/stats/players/bio and let the page finish loading.
2. Open the developer console. Chrome on macOS is Option + Command + J; Safari is
   Option + Command + C, after enabling the Develop menu in Settings, Advanced.
3. Paste in the whole of `src/fetch_biodata_browser.js` and press Enter.
4. Five CSV files download, already named correctly. Allow multiple downloads if asked.
5. Move them into `data/raw`.

#### Option D: save the JSON from browser tabs

The route that cannot be blocked. Opening a URL in a tab is an ordinary page load, not a
cross-origin request, so no CORS rule and no missing cookie can stop it.

1. Print the five URLs:

   ```
   python src/convert_biodata_json.py --print-urls
   ```

2. Open each one in a browser tab. Each shows a block of JSON.
3. Save each page as a file. In Chrome, File then Save Page As. The file names do not
   matter, because the season is read from inside each file.
4. Convert them:

   ```
   python src/convert_biodata_json.py --json-dir ~/Downloads --out-dir data/raw
   ```

### 6. WNBA player biodata, 5 files

Already in the repo, fetched on 31 October 2026 from the same endpoint NBA.com uses, served for the WNBA at `stats.wnba.com` under `LeagueID=10`. The page is https://stats.wnba.com/players/bio/.

| Save as | WNBA season |
|---|---|
| `WNBA_2019_bio.csv` | 2020 |
| `WNBA_2020_bio.csv` | 2021 |
| `WNBA_2021_bio.csv` | 2022 |
| `WNBA_2022_bio.csv` | 2023 |
| `WNBA_2023_bio.csv` | 2024 |

This answers a question the dissertation leaves open. Its WNBA modelling table carried `WEIGHT`, `GP` and `Height_cm`, which Basketball Reference does not publish for the WNBA, and the text never says where they came from. The WNBA side of the NBA.com stats API is the source that fits.

Without these files the pipeline still builds a WNBA table, but it loses those three columns, and the modelling notebook's cross-league section then fails, because it selects the NBA feature list out of the WNBA frame.

#### Re-fetching them

The endpoint refuses ordinary command-line requests, and a browser `fetch` with `credentials: 'include'` is rejected by CORS. A plain same-origin `fetch` from https://stats.wnba.com/players/bio/ works. The URL is the NBA one with `LeagueID=10`, no `PaceAdjust`, `PlusMinus` or `Rank` parameters, and a single-year `Season` such as `2024`.

## What the pipeline produces

| File | Used by | Content |
|---|---|---|
| `NBA_Modelling_New.csv` | notebooks 02 and 03 | 36 columns, one row per player per team per season |
| `WNBA_Modelling_New.csv` | notebooks 02 and 03 | the same columns both leagues share |

## How it is built

Following section 3.1.3 of the dissertation:

1. Read one file per season and tag each with `Season`.
2. Drop the combined row a traded player also gets (`2TM`, `3TM`, `TOT`), keeping the per-team rows. Figure 3.3 of the dissertation shows Precious Achiuwa twice for 2023-24, which confirms this.
3. Inner join the advanced stats to the per-game stats on player, team and season.
4. Left join the biodata on player and season.
5. One-hot encode position, with centre as the reference category.
6. Drop rows with missing values rather than imputing them.

`docs/data_pipeline_notes.md` records what the dissertation states outright and what had to be inferred.
