// Download the NBA.com player biodata for all five seasons, straight from the
// browser. Use this when the Python script cannot reach stats.nba.com: your
// browser already has the session cookies the endpoint expects, so it works
// where a terminal request stalls.
//
// HOW TO RUN
//   1. Open https://www.nba.com/stats/players/bio and let the page load.
//   2. Open the developer console:
//        Chrome on macOS   Option + Command + J
//        Safari on macOS   Option + Command + C
//                          (first enable Develop menu in Settings > Advanced)
//   3. Paste this whole file in, press Enter, and wait. It prints progress.
//   4. Five CSV files download, one per season. If the browser asks whether to
//      allow multiple downloads, say yes.
//   5. Move them into data/raw. The names are already correct.
//
// The files are named by the season's STARTING year, which is what
// src/build_dataset.py expects: NBA_2019_bio.csv is the 2019-20 season.

(async () => {
  const SEASONS = {
    2019: '2019-20', 2020: '2020-21', 2021: '2021-22',
    2022: '2022-23', 2023: '2023-24',
  };

  // The endpoint rejects a request that leaves any filter out, even empty ones.
  const BASE = {
    College: '', Conference: '', Country: '', DateFrom: '', DateTo: '',
    Division: '', DraftPick: '', DraftYear: '', GameScope: '', GameSegment: '',
    Height: '', LastNGames: '0', LeagueID: '00', Location: '', Month: '0',
    OpponentTeamID: '0', Outcome: '', PORound: '0', PaceAdjust: 'N',
    PerMode: 'Totals', Period: '0', PlayerExperience: '', PlayerPosition: '',
    PlusMinus: 'N', Rank: 'N', SeasonSegment: '', SeasonType: 'Regular Season',
    ShotClockRange: '', StarterBench: '', TeamID: '0', VsConference: '',
    VsDivision: '', Weight: '',
  };

  // What the endpoint calls each field, against what build_dataset.py expects.
  const COLUMNS = [
    ['PLAYER_NAME', 'PLAYER'], ['TEAM_ABBREVIATION', 'TEAM'], ['AGE', 'AGE'],
    ['PLAYER_HEIGHT', 'HEIGHT'], ['PLAYER_WEIGHT', 'WEIGHT'],
    ['COLLEGE', 'COLLEGE'], ['COUNTRY', 'COUNTRY'],
    ['DRAFT_YEAR', 'DRAFT YEAR'], ['DRAFT_ROUND', 'DRAFT ROUND'],
    ['DRAFT_NUMBER', 'DRAFT NUMBER'], ['GP', 'GP'],
  ];

  const cell = (value) => {
    if (value === null || value === undefined) return '';
    const text = String(value);
    return /[",\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  };

  const save = (name, text) => {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  };

  const pause = (ms) => new Promise((r) => setTimeout(r, ms));

  let saved = 0;
  for (const [year, season] of Object.entries(SEASONS)) {
    const url = 'https://stats.nba.com/stats/leaguedashplayerbiostats?' +
      new URLSearchParams({ ...BASE, Season: season });

    try {
      // A plain GET with no custom headers and no credentials option. Anything
      // else makes this a "non-simple" request, and the browser then sends a
      // CORS preflight that stats.nba.com does not answer properly. The
      // x-nba-stats-* headers a terminal request needs are the very thing that
      // breaks it here, so they are deliberately absent.
      const response = await fetch(url);
      if (!response.ok) throw new Error('HTTP ' + response.status);

      const block = (await response.json()).resultSets[0];
      const indexes = COLUMNS.map(([src]) => {
        const i = block.headers.indexOf(src);
        if (i === -1) throw new Error('field not in response: ' + src);
        return i;
      });

      if (block.rowSet.length < 300) {
        throw new Error('only ' + block.rowSet.length + ' players, expected 400 or more');
      }

      const lines = [COLUMNS.map(([, dest]) => dest).join(',')];
      for (const row of block.rowSet) {
        lines.push(indexes.map((i) => cell(row[i])).join(','));
      }

      save(`NBA_${year}_bio.csv`, lines.join('\n'));
      saved += 1;
      console.log(`${season}: ${block.rowSet.length} players -> NBA_${year}_bio.csv`);
    } catch (error) {
      console.error(`${season} FAILED: ${error.message}`);
    }

    await pause(1500);  // stay polite between seasons
  }

  console.log(`\nDone. ${saved} of ${Object.keys(SEASONS).length} seasons downloaded.`);
  if (saved < Object.keys(SEASONS).length) {
    console.log('If a season failed, reload the page and run this again.');
  } else {
    console.log('Move the five files into data/raw, then run:');
    console.log('    python src/build_dataset.py --raw-dir data/raw --out-dir data');
  }
})();
