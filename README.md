# Predicting NBA Player Performance Using Machine Learning Methods

MSc Dissertation in Applied Data Science, University of Sunderland, January 2025.

The study predicts two advanced basketball metrics for NBA players, Player Efficiency Rating (PER) and Win Shares (WS). It employed historical box-score and
advanced statistics, player biodata, and match statistics across five NBA seasons
(2019–20 to 2023–24). The trained models are additionally validated on WNBA data to
test cross-league robustness. 

> **Note on the thesis document:** The full dissertation is available in
> the [thesis](./docs/Thesis.pdf) as an anonymised PDF. Personal identifiers (supervisor's names, student ID,
> institutional details) have been removed for public release.

---

## Overview

Traditional basketball evaluation has often relied on counting stats (points, rebounds, assists) to measure player performance. This project instead uses **advanced metrics** and **machine learning** to build interpretable, predictive models of player contribution, following the **CRISP-DM** methodology. Two modelling formulations are explored:

- **Single-task**: predict PER only.
- **Multi-task**: predict PER and WS simultaneously from the same feature set.

Three regressors are compared: **Random Forest**, **Support Vector Regression (SVR)**,
and a **Recurrent Neural Network (RNN)**. A cross-league test applies the best NBA-trained
model to WNBA data.

---

## Key Results

### Single-task (PER)

| Model | RMSE | MAE |
|---|---|---|
| Random Forest | 2.24 | 1.25 |
| SVR | 2.65 | 1.14 |
| **RNN** | **1.48** | **0.98** |

### Multi-task (PER and WS)

| Model | PER RMSE | PER MAE | WS RMSE | WS MAE |
|---|---|---|---|---|
| Random Forest | 2.29 | 1.36 | 0.89 | 0.56 |
| SVR | 2.71 | 1.30 | **0.88** | **0.52** |
| RNN | **1.79** | **1.13** | 1.23 | 0.75 |

**Key Findings**
- The RNN is the strongest model for **PER** in both formulations, consistent with its
  ability to capture sequential and non-linear structure.
- **SVR** performs best for **Win Share**, which appears to be better modelled by
  near-linear relationships and is less sensitive to outliers under MAE.
- **Feature importance** (Random Forest) identifies **True Shooting % (TS%)**,
  **Usage % (USG%)**, **Offensive Win Share (OWS)**, **Total Rebound % (TRB%)** and
  **Points (PTS)** as the dominant predictors of PER; **Minutes Played (MP)** dominates
  WS prediction.

### Cross-league validation (NBA-trained RNN → WNBA)

| Target | MAE | RMSE |
|---|---|---|
| PER | 2.09 | 3.04 |
| WS | 1.28 | 1.72 |

The drop in performance is attributed to league-specific dynamics and a substantially smaller WNBA sample. This motivates the recommendations on transfer learning and more inclusive datasets in
the thesis.

## Data

The datasets were assembled from:

- **Player box-score and advanced statistics:** [Basketball Reference](https://www.basketball-reference.com/)
- **Player biodata:** [NBA Advanced Stats](https://www.nba.com/stats/players/bio), [WNBA Advanced Stats](https//www.wnba.com/players)

Five seasons were collected: **2019–20, 2020–21, 2021–22, 2022–23, 2023–24**. Each
season's files were concatenated and merged on `Player`, `Team`, and `Season`. The
feature set covers traditional box-score stats, advanced metrics (PER, TS%, USG%, WS,
BPM, VORP, etc.), and player biodata (height, weight, age, draft information). 

**Note on the WNBA data:** cross-league validation uses WNBA seasons from the same
period, assembled from the same sources.

---

## Methodology

### Pipeline (CRISP-DM)

1. **Business understanding** — predict PER and WS to support scouting, roster and
   contract decisions.
2. **Data acquisition & understanding** — manual export per season from the sources above.
3. **Data preparation**
   - concatenation and inner/left joins across the three datasets;
   - removal of redundant columns 
   - row-wise handling of missing values (missingness < 10%, so rows were dropped rather
     than imputed to preserve variability in key features such as TS% and 3PAr);
   - `StandardScaler` for numeric features;
   - season-based split: 2019–20 to 2022–23 for training, 2023–24 for testing;
   - tensor reshaping for the RNN.
4. **Modelling** — Random Forest, SVR (RBF kernel, default hyperparameters), and a
   3-layer `SimpleRNN` (64 units per layer, `tanh`, Adam, 20 epochs, batch size 32).
5. **Evaluation** — MAE and RMSE, plus Random Forest feature importances.
6. **Cross-league validation** — the best NBA-trained model was applied to WNBA data.

### Models Rationale

- **SVR**: effective for non-linear relationships via the kernel trick; shown in prior
  work to outperform linear regression on player-efficiency tasks.
- **Random Forest**: handles high-dimensional, heterogeneous data and provides feature
  importances, which are central to the interpretation in this study.
- **RNN**: captures temporal and sequential dependencies across games, aligning the
  study with the growing use of deep learning in sports analytics.

---

## Reproducing the Results

```bash
git clone [YOUR_REPO_URL]
cd [YOUR_REPO_NAME]
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt


## Author

Chigozie Nlemeke. MSc Applied Data Science, University of Sunderland.
