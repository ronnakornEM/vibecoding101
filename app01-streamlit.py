"""Diabetes Risk Scoring System — Streamlit GUI, single self-contained file.

Run locally:  streamlit run app01-streamlit.py
Deploy:       push repo to GitHub, point Streamlit Community Cloud at this file.
"""

from statistics import median

import streamlit as st

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
    """Holds raw patient records and cleans them on load."""

    def __init__(self):
        self.patients = {
            1: {"Glucose": 148, "BMI": 33.6, "Age": 50, "BloodPressure": 72},
            2: {"Glucose": 85, "BMI": 0, "Age": 31, "BloodPressure": 66},
            3: {"Glucose": 183, "BMI": 23.3, "Age": 32, "BloodPressure": 64},
            4: {"Glucose": 89, "BMI": 28.1, "Age": 21, "BloodPressure": 66},
        }
        self._fix_zero_bmi()

    def _fix_zero_bmi(self):
        """Replace any BMI of 0 with the median BMI of the other patients."""
        valid = [p["BMI"] for p in self.patients.values() if p["BMI"] != 0]
        if not valid:
            return
        fill = median(valid)
        for p in self.patients.values():
            if p["BMI"] == 0:
                p["BMI"] = fill

    def ids(self):
        return list(self.patients.keys())

    def get(self, pid):
        return self.patients.get(pid)

    def save(self, pid, profile):
        self.patients[pid] = profile


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
st.set_page_config(page_title="Diabetes Risk Scoring System", page_icon="🩺")

# ponytail: in-memory model kept in session_state, same volatility as the console app
if "model" not in st.session_state:
    st.session_state.model = DataAccessLayer()
model = st.session_state.model

st.title("🩺 Diabetes Risk Scoring System")
st.caption("Data is in-memory only; refreshing the page resets all changes.")

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
