"""Diabetes Risk Scoring System — Streamlit GUI, single self-contained file.

Run locally:  streamlit run app01-streamlit.py
Deploy:       push repo to GitHub, point Streamlit Community Cloud at this file.
"""

import sqlite3
from pathlib import Path
from statistics import median

import streamlit as st

DB_PATH = Path(__file__).with_name("patients.db")

METRICS = ("Glucose", "BMI", "Age", "BloodPressure")
EDITABLE = ("Glucose", "BMI", "BloodPressure")  # Age is demographic, not re-measured

# Scoring thresholds per metric: (medium_lo, high_lo).
#   value < medium_lo            -> Low    (0)
#   medium_lo <= value < high_lo -> Medium (1)
#   value >= high_lo             -> High   (2)
# ponytail: clinically-flavored defaults; tune here if guidelines change.
THRESHOLDS = {
    "Glucose": (100, 126),       # fasting mg/dL: pre-diabetes / diabetes
    "BMI": (25, 30),             # overweight / obese
    "Age": (40, 60),             # midlife / senior
    "BloodPressure": (80, 90),   # diastolic mmHg: elevated / hypertensive
}

# Physiologically plausible (min, max) per metric.
VALID_RANGES = {
    "Glucose": (20, 600),
    "BMI": (10, 80),
    "Age": (0, 120),
    "BloodPressure": (30, 200),
}


# ---------------------------------------------------------------------------
# Model — Data Access Layer
# ---------------------------------------------------------------------------
class DataAccessLayer:
    """SQLite-backed patient records; seeds demo data and cleans it on first run."""

    _SEED = {
        1: {"Glucose": 148, "BMI": 33.6, "Age": 50, "BloodPressure": 72},
        2: {"Glucose": 85, "BMI": 0, "Age": 31, "BloodPressure": 66},
        3: {"Glucose": 183, "BMI": 23.3, "Age": 32, "BloodPressure": 64},
        4: {"Glucose": 89, "BMI": 28.1, "Age": 21, "BloodPressure": 66},
    }

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        with self._conn() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS patients ("
                "id INTEGER PRIMARY KEY, Glucose REAL, BMI REAL, Age REAL, BloodPressure REAL)"
            )
            if con.execute("SELECT COUNT(*) FROM patients").fetchone()[0] == 0:
                for pid, p in self._SEED.items():
                    con.execute(
                        "INSERT INTO patients VALUES (?, ?, ?, ?, ?)",
                        (pid, p["Glucose"], p["BMI"], p["Age"], p["BloodPressure"]),
                    )
                self._fix_zero_bmi(con)

    # ponytail: connection per call — trivial cost at this scale, no thread issues
    def _conn(self):
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _fix_zero_bmi(con):
        """Replace any BMI of 0 with the median BMI of the other patients."""
        valid = [r[0] for r in con.execute("SELECT BMI FROM patients WHERE BMI != 0")]
        if valid:
            con.execute("UPDATE patients SET BMI = ? WHERE BMI = 0", (median(valid),))

    def ids(self):
        with self._conn() as con:
            return [r[0] for r in con.execute("SELECT id FROM patients ORDER BY id")]

    def get(self, pid):
        with self._conn() as con:
            row = con.execute(
                "SELECT Glucose, BMI, Age, BloodPressure FROM patients WHERE id = ?", (pid,)
            ).fetchone()
        return dict(zip(METRICS, row)) if row else None

    def save(self, pid, profile):
        with self._conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO patients VALUES (?, ?, ?, ?, ?)",
                (pid, profile["Glucose"], profile["BMI"], profile["Age"], profile["BloodPressure"]),
            )


# ---------------------------------------------------------------------------
# Service — Business Logic Layer
# ---------------------------------------------------------------------------
class RiskService:
    """Pure scoring rules. No I/O, no state."""

    @staticmethod
    def score_metric(name, value):
        medium_lo, high_lo = THRESHOLDS[name]
        if value >= high_lo:
            return 2
        if value >= medium_lo:
            return 1
        return 0

    @staticmethod
    def total_score(profile):
        return sum(RiskService.score_metric(m, profile[m]) for m in METRICS)

    @staticmethod
    def categorize(total):
        if total >= 6:
            return "High Risk"
        if total >= 3:
            return "Moderate Risk"
        return "Low Risk"

    @staticmethod
    def assess(profile):
        total = RiskService.total_score(profile)
        return total, RiskService.categorize(total)


def receipt(pid, profile, total, category):
    """Console-style receipt as a string, shown in st.code."""
    bar = "*" * 44
    line = "-" * 44
    rows = [
        bar,
        "          OFFICIAL MEDICAL RECEIPT",
        line,
        f"      DIAGNOSTIC RISK REPORT — Patient {pid}",
        bar,
    ]
    for m in METRICS:
        rows.append(f"  {m:<14}: {profile[m]:<8} (score {RiskService.score_metric(m, profile[m])})")
    rows += [
        line,
        f"  Total Score   : {total}",
        f"  Risk Category : {category}",
        line,
        "    *** CONFIDENTIAL — MEDICAL RECORD ***",
        "     For authorized personnel use only",
        bar,
    ]
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# View/Controller — Streamlit GUI
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Diabetes Risk Scoring System", page_icon="🎮")

# ponytail: 8-bit skin is pure CSS injection; app logic/widgets untouched
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&display=swap');

html, body, [class*="css"], .stApp, .stApp * {
    font-family: 'Press Start 2P', monospace !important;
}

.stApp {
    background-color: #0f0f23;
    color: #33ff33;
}
.stApp p, .stApp label, .stApp span, .stApp div, .stApp td, .stApp th {
    color: #33ff33;
    font-size: 11px;
    line-height: 1.8;
}
h1 { color: #ffcc00 !important; font-size: 20px !important;
     text-shadow: 3px 3px 0 #cc3333; line-height: 1.6 !important; }
h2, h3 { color: #66ccff !important; font-size: 14px !important; }
[data-testid="stCaptionContainer"] * { color: #888 !important; font-size: 9px !important; }

/* chunky pixel borders everywhere, no rounded corners */
.stApp *, .stApp *::before, .stApp *::after { border-radius: 0 !important; }

.stButton button {
    background: #cc3333 !important;
    color: #fff !important;
    border: 4px solid #fff !important;
    box-shadow: 4px 4px 0 #000 !important;
    font-size: 12px !important;
    padding: 12px 20px !important;
}
.stButton button:hover { background: #ff5555 !important; }
.stButton button:active { box-shadow: 1px 1px 0 #000 !important;
                          transform: translate(3px, 3px); }

div[data-baseweb="select"] > div, .stNumberInput input,
[data-testid="stNumberInputContainer"] {
    background: #000 !important;
    color: #33ff33 !important;
    border: 3px solid #33ff33 !important;
}
.stNumberInput button { background: #222 !important; color: #33ff33 !important; }

[data-testid="stMetric"] {
    background: #000;
    border: 3px solid #66ccff;
    box-shadow: 3px 3px 0 #66ccff44;
    padding: 8px;
}
[data-testid="stMetricValue"] > div { color: #ffcc00 !important; font-size: 16px !important; }
[data-testid="stMetricLabel"] p { font-size: 8px !important; }
[data-testid="stMetricDelta"] * { color: #66ccff !important; font-size: 8px !important; }

[data-testid="stTable"] table { border: 3px solid #33ff33 !important; background: #000; }
[data-testid="stTable"] th, [data-testid="stTable"] td { border: 1px solid #33ff3355 !important; }

.stAlert { border: 4px solid currentColor !important; box-shadow: 4px 4px 0 #000 !important; }

.stCode, .stCode pre, .stCode code, [data-testid="stCode"] * {
    background: #000 !important;
    color: #33ff33 !important;
    font-size: 10px !important;
}
[data-testid="stCode"] { border: 3px solid #33ff33; box-shadow: 0 0 12px #33ff3366; }

[data-testid="stWidgetLabel"] p { color: #66ccff !important; }
</style>
""", unsafe_allow_html=True)

model = DataAccessLayer()

st.title("🎮 DIABETES RISK QUEST")
st.caption(f"Data persists in {DB_PATH.name} (SQLite); saved changes survive restarts.")

pid = st.selectbox("Patient ID", model.ids())
profile = dict(model.get(pid))

st.subheader(f"Clinical Profile — Patient {pid}")
modify = st.toggle("Modify metrics before scoring")

if modify:
    for m in METRICS:
        if m in EDITABLE:
            lo, hi = VALID_RANGES[m]
            profile[m] = st.number_input(
                m,
                min_value=float(lo),
                max_value=float(hi),
                value=float(profile[m]),
                step=0.1 if m == "BMI" else 1.0,
                key=f"{pid}-{m}",
            )
        else:
            st.number_input(m, value=float(profile[m]), disabled=True,
                            help="Age is demographic, not re-measured", key=f"{pid}-{m}")
else:
    st.table([{"Metric": m, "Value": profile[m]} for m in METRICS])

if st.button("Assess Patient Risk", type="primary"):
    if modify:
        model.save(pid, profile)

    total, category = RiskService.assess(profile)
    banner = {"Low Risk": st.success, "Moderate Risk": st.warning, "High Risk": st.error}
    banner[category](f"**{category}** — Total Score: {total}")

    cols = st.columns(len(METRICS))
    for col, m in zip(cols, METRICS):
        col.metric(m, profile[m], f"score {RiskService.score_metric(m, profile[m])}",
                   delta_color="off")

    st.code(receipt(pid, profile, total, category), language=None)
