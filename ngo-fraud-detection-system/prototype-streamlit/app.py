from __future__ import annotations

import html
import re
from itertools import combinations
from pathlib import Path
from typing import Iterable

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz

try:
    import plotly.express as px
except ImportError:  # pragma: no cover - Streamlit fallback for lean installs
    px = None


REQUIRED_COLUMNS = [
    "beneficiary_id",
    "full_name",
    "phone",
    "email",
    "gender",
    "age",
    "address",
    "community",
    "program_applied",
    "date_registered",
    "support_received",
]

RISK_ORDER = ["Low", "Medium", "High"]
RISK_COLORS = {
    "Low": "#15803d",
    "Medium": "#b7791f",
    "High": "#b42318",
}

FLAG_WEIGHTS = {
    "Exact duplicate row": 40,
    "Repeated beneficiary ID": 35,
    "Repeated full name": 20,
    "Repeated phone number": 30,
    "Repeated email address": 30,
    "Same phone used by different names": 35,
    "Same email used by different names": 35,
    "Similar beneficiary name": 20,
    "Same person appears across programs": 15,
}

FLAG_EXPLANATIONS = {
    "Exact duplicate row": "The full record matches another row, which usually means a repeated import or duplicate registration.",
    "Repeated beneficiary ID": "The beneficiary ID appears more than once and should be checked against the source register.",
    "Repeated full name": "The same normalized full name appears in multiple records.",
    "Repeated phone number": "The phone number appears in multiple records.",
    "Repeated email address": "The email address appears in multiple records.",
    "Same phone used by different names": "One phone number is linked to more than one beneficiary name.",
    "Same email used by different names": "One email address is linked to more than one beneficiary name.",
    "Similar beneficiary name": "A fuzzy name match found another record with a very similar spelling.",
    "Same person appears across programs": "The same name and phone combination appears across multiple support programs.",
}

OUTPUT_COLUMNS = REQUIRED_COLUMNS + [
    "fraud_score",
    "risk_level",
    "review_action",
    "fraud_flags",
    "score_breakdown",
    "risk_explanation",
    "similar_name_matches",
]

TABLE_COLUMNS = [
    "beneficiary_id",
    "full_name",
    "phone",
    "email",
    "community",
    "program_applied",
    "fraud_score",
    "risk_level",
    "review_action",
    "fraud_flags",
    "risk_explanation",
    "similar_name_matches",
]


def normalize_text(value: object) -> str:
    """Return lowercase alphanumeric-ish text for reliable comparisons."""
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9\s@._+-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_phone(value: object) -> str:
    """Normalize common phone formats while keeping enough digits to compare."""
    if pd.isna(value):
        return ""
    digits = re.sub(r"\D", "", str(value))
    if digits.startswith("234") and len(digits) == 13:
        return "0" + digits[3:]
    if digits.startswith("234") and len(digits) == 14:
        return "0" + digits[4:]
    return digits


def normalize_email(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_text(col).replace(" ", "_") for col in df.columns]
    for column in REQUIRED_COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df[REQUIRED_COLUMNS].copy()


def unique_non_empty(values: Iterable[object]) -> set[str]:
    return {normalize_text(value) for value in values if normalize_text(value)}


def append_flag(df: pd.DataFrame, indexes: pd.Index, flag_label: str, score: int) -> None:
    if len(indexes) == 0:
        return
    df.loc[indexes, "fraud_score"] += score
    df.loc[indexes, "_flag_list"] = df.loc[indexes, "_flag_list"].apply(
        lambda flags: flags + [flag_label]
    )
    df.loc[indexes, "_score_list"] = df.loc[indexes, "_score_list"].apply(
        lambda scores: scores + [f"{flag_label} (+{score})"]
    )


def add_group_flag(
    df: pd.DataFrame,
    group_column: str,
    flag_label: str,
    score: int,
    require_multiple_names: bool = False,
    min_group_size: int = 2,
) -> None:
    valid = df[group_column] != ""
    group_sizes = df.loc[valid].groupby(group_column)[group_column].transform("size")
    flagged_index = group_sizes[group_sizes >= min_group_size].index

    if require_multiple_names:
        name_counts = (
            df.loc[valid]
            .groupby(group_column)["_normalized_name"]
            .transform(lambda names: len(unique_non_empty(names)))
        )
        flagged_index = name_counts[(name_counts >= 2) & (group_sizes >= min_group_size)].index

    append_flag(df, flagged_index, flag_label, score)


def detect_similar_names(df: pd.DataFrame, threshold: int) -> None:
    names = (
        df[["_normalized_name", "full_name"]]
        .drop_duplicates("_normalized_name")
        .query("_normalized_name != ''")
        .to_dict("records")
    )
    matches_by_name: dict[str, list[str]] = {}

    for first, second in combinations(names, 2):
        first_name = first["_normalized_name"]
        second_name = second["_normalized_name"]
        if first_name == second_name:
            continue

        score = fuzz.token_sort_ratio(first_name, second_name)
        if score >= threshold:
            first_label = str(first["full_name"])
            second_label = str(second["full_name"])
            matches_by_name.setdefault(first_name, []).append(f"{second_label} ({score:.0f}%)")
            matches_by_name.setdefault(second_name, []).append(f"{first_label} ({score:.0f}%)")

    similar_mask = df["_normalized_name"].isin(matches_by_name)
    df.loc[similar_mask, "similar_name_matches"] = df.loc[similar_mask, "_normalized_name"].map(
        lambda name: "; ".join(matches_by_name.get(name, []))
    )
    append_flag(
        df,
        df.index[similar_mask],
        "Similar beneficiary name",
        FLAG_WEIGHTS["Similar beneficiary name"],
    )


def explain_flag(flag: str) -> str:
    if flag.startswith("Same address used by"):
        return "The same address is linked to several beneficiary names and may need household verification."
    return FLAG_EXPLANATIONS.get(flag, "This record matched a configured fraud or duplicate rule.")


def assign_risk_level(score: int) -> str:
    if score >= 60:
        return "High"
    if score >= 25:
        return "Medium"
    return "Low"


def recommend_action(risk_level: str) -> str:
    if risk_level == "High":
        return "Hold and verify before support"
    if risk_level == "Medium":
        return "Manual review recommended"
    return "Proceed with normal checks"


def build_explanation(row: pd.Series) -> str:
    flags = list(dict.fromkeys(row["_flag_list"]))
    if not flags:
        return "No strong duplicate or fraud indicators were detected by the configured rules."

    explanations = [explain_flag(flag) for flag in flags[:4]]
    if len(flags) > 4:
        explanations.append(f"{len(flags) - 4} additional rule(s) also contributed to the score.")
    if row.get("similar_name_matches"):
        explanations.append(f"Similar name match: {row['similar_name_matches']}.")

    return " ".join(explanations)


def analyze_data(
    raw_df: pd.DataFrame,
    name_threshold: int = 88,
    address_name_limit: int = 3,
) -> pd.DataFrame:
    df = ensure_columns(raw_df)

    for column in REQUIRED_COLUMNS:
        df[column] = df[column].fillna("").astype(str).str.strip()

    df["_normalized_id"] = df["beneficiary_id"].map(normalize_text)
    df["_normalized_name"] = df["full_name"].map(normalize_text)
    df["_normalized_phone"] = df["phone"].map(normalize_phone)
    df["_normalized_email"] = df["email"].map(normalize_email)
    df["_normalized_address"] = df["address"].map(normalize_text)

    df["fraud_score"] = 0
    df["_flag_list"] = [[] for _ in range(len(df))]
    df["_score_list"] = [[] for _ in range(len(df))]
    df["similar_name_matches"] = ""

    duplicated_full_rows = df[REQUIRED_COLUMNS].duplicated(keep=False)
    append_flag(
        df,
        df.index[duplicated_full_rows],
        "Exact duplicate row",
        FLAG_WEIGHTS["Exact duplicate row"],
    )

    add_group_flag(df, "_normalized_id", "Repeated beneficiary ID", FLAG_WEIGHTS["Repeated beneficiary ID"])
    add_group_flag(df, "_normalized_name", "Repeated full name", FLAG_WEIGHTS["Repeated full name"])
    add_group_flag(df, "_normalized_phone", "Repeated phone number", FLAG_WEIGHTS["Repeated phone number"])
    add_group_flag(df, "_normalized_email", "Repeated email address", FLAG_WEIGHTS["Repeated email address"])
    add_group_flag(
        df,
        "_normalized_phone",
        "Same phone used by different names",
        FLAG_WEIGHTS["Same phone used by different names"],
        require_multiple_names=True,
    )
    add_group_flag(
        df,
        "_normalized_email",
        "Same email used by different names",
        FLAG_WEIGHTS["Same email used by different names"],
        require_multiple_names=True,
    )
    add_group_flag(
        df,
        "_normalized_address",
        f"Same address used by {address_name_limit}+ names",
        25,
        require_multiple_names=True,
        min_group_size=address_name_limit,
    )

    person_programs = (
        df.groupby(["_normalized_name", "_normalized_phone"])["program_applied"]
        .transform(lambda values: len(unique_non_empty(values)))
    )
    repeated_program_mask = (
        (df["_normalized_name"] != "")
        & (df["_normalized_phone"] != "")
        & (person_programs >= 2)
    )
    append_flag(
        df,
        df.index[repeated_program_mask],
        "Same person appears across programs",
        FLAG_WEIGHTS["Same person appears across programs"],
    )

    detect_similar_names(df, name_threshold)

    df["fraud_score"] = df["fraud_score"].clip(upper=100)
    df["risk_level"] = df["fraud_score"].map(assign_risk_level)
    df["review_action"] = df["risk_level"].map(recommend_action)
    df["fraud_flags"] = df["_flag_list"].apply(
        lambda flags: "; ".join(dict.fromkeys(flags)) if flags else "No major flags"
    )
    df["score_breakdown"] = df["_score_list"].apply(
        lambda scores: "; ".join(dict.fromkeys(scores)) if scores else "No score penalties"
    )
    df["risk_explanation"] = df.apply(build_explanation, axis=1)

    helper_columns = [column for column in df.columns if column.startswith("_")]
    return df.drop(columns=helper_columns)


def convert_df_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def load_sample_data() -> pd.DataFrame:
    return pd.read_csv(Path(__file__).with_name("sample_data.csv"), dtype=str)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        .app-kicker {
            color: #475467;
            font-size: 0.98rem;
            margin-bottom: 1.1rem;
        }
        .metric-card {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 1rem 1.05rem;
            background: #ffffff;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
            min-height: 118px;
        }
        .metric-card.low { border-top: 4px solid #15803d; }
        .metric-card.medium { border-top: 4px solid #b7791f; }
        .metric-card.high { border-top: 4px solid #b42318; }
        .metric-card.neutral { border-top: 4px solid #475467; }
        .metric-label {
            color: #667085;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
            text-transform: uppercase;
        }
        .metric-value {
            color: #101828;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-top: 0.35rem;
        }
        .metric-caption {
            color: #667085;
            font-size: 0.82rem;
            margin-top: 0.5rem;
        }
        .explanation-panel {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            background: #ffffff;
            padding: 1rem 1.1rem;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
        }
        .risk-pill {
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 0.25rem 0.65rem;
            color: #ffffff;
            font-size: 0.78rem;
            font-weight: 700;
        }
        .risk-pill.low { background: #15803d; }
        .risk-pill.medium { background: #b7791f; }
        .risk-pill.high { background: #b42318; }
        .panel-title {
            color: #101828;
            font-size: 1rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
        }
        .panel-meta {
            color: #475467;
            font-size: 0.88rem;
            margin-bottom: 0.65rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: object, caption: str, tone: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div class="metric-label">{html.escape(label)}</div>
            <div class="metric-value">{html.escape(str(value))}</div>
            <div class="metric-caption">{html.escape(caption)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_flag_counts(df: pd.DataFrame) -> pd.DataFrame:
    exploded_flags = (
        df.assign(flag=df["fraud_flags"].str.split("; "))
        .explode("flag")
        .query("flag != 'No major flags'")
    )
    if exploded_flags.empty:
        return pd.DataFrame(columns=["flag", "records"])
    flag_counts = exploded_flags["flag"].value_counts().head(10).reset_index()
    flag_counts.columns = ["flag", "records"]
    return flag_counts


def filter_results(
    df: pd.DataFrame,
    search_query: str,
    selected_risks: list[str],
    selected_programs: list[str],
    selected_communities: list[str],
    selected_flags: list[str],
    score_range: tuple[int, int],
) -> pd.DataFrame:
    filtered = df.copy()
    filtered = filtered[filtered["risk_level"].isin(selected_risks)]
    filtered = filtered[
        filtered["fraud_score"].between(score_range[0], score_range[1], inclusive="both")
    ]

    if selected_programs:
        filtered = filtered[filtered["program_applied"].isin(selected_programs)]
    if selected_communities:
        filtered = filtered[filtered["community"].isin(selected_communities)]
    if selected_flags:
        pattern = "|".join(re.escape(flag) for flag in selected_flags)
        filtered = filtered[filtered["fraud_flags"].str.contains(pattern, case=False, na=False)]
    if search_query.strip():
        query = normalize_text(search_query)
        search_columns = [
            "beneficiary_id",
            "full_name",
            "phone",
            "email",
            "address",
            "community",
            "program_applied",
            "fraud_flags",
        ]
        haystack = filtered[search_columns].fillna("").agg(" ".join, axis=1).map(normalize_text)
        filtered = filtered[haystack.str.contains(re.escape(query), na=False)]

    return filtered.sort_values(["fraud_score", "risk_level"], ascending=[False, True])


def render_charts(results_df: pd.DataFrame) -> None:
    risk_counts = (
        results_df["risk_level"]
        .value_counts()
        .reindex(RISK_ORDER, fill_value=0)
        .reset_index()
    )
    risk_counts.columns = ["risk_level", "records"]
    flag_counts = get_flag_counts(results_df)

    tab_overview, tab_flags, tab_hotspots, tab_timeline = st.tabs(
        ["Risk Overview", "Flag Insights", "Program Hotspots", "Registration Trend"]
    )

    with tab_overview:
        left, right = st.columns([0.9, 1.1])
        with left:
            st.subheader("Risk Mix")
            if px:
                fig = px.pie(
                    risk_counts,
                    names="risk_level",
                    values="records",
                    hole=0.58,
                    color="risk_level",
                    color_discrete_map=RISK_COLORS,
                    category_orders={"risk_level": RISK_ORDER},
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(margin=dict(t=12, r=12, b=12, l=12), legend_title_text="")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(risk_counts.set_index("risk_level"))

        with right:
            st.subheader("Fraud Score Distribution")
            if px:
                fig = px.histogram(
                    results_df,
                    x="fraud_score",
                    nbins=10,
                    color="risk_level",
                    color_discrete_map=RISK_COLORS,
                    category_orders={"risk_level": RISK_ORDER},
                )
                fig.update_layout(
                    bargap=0.08,
                    xaxis_title="Fraud score",
                    yaxis_title="Records",
                    legend_title_text="Risk",
                    margin=dict(t=12, r=12, b=12, l=12),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(results_df["fraud_score"].value_counts().sort_index())

    with tab_flags:
        st.subheader("Most Common Fraud Flags")
        if flag_counts.empty:
            st.success("No suspicious flags found in this dataset.")
        elif px:
            fig = px.bar(
                flag_counts.sort_values("records"),
                x="records",
                y="flag",
                orientation="h",
                text="records",
                color="records",
                color_continuous_scale="Reds",
            )
            fig.update_layout(
                xaxis_title="Records",
                yaxis_title="",
                coloraxis_showscale=False,
                margin=dict(t=12, r=12, b=12, l=12),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.bar_chart(flag_counts.set_index("flag"))

    with tab_hotspots:
        left, right = st.columns(2)
        chart_df = results_df.copy()
        chart_df["is_suspicious"] = chart_df["risk_level"].isin(["Medium", "High"])
        chart_df["program_applied"] = chart_df["program_applied"].replace("", "Unknown")
        chart_df["community"] = chart_df["community"].replace("", "Unknown")

        program_summary = (
            chart_df.groupby("program_applied")
            .agg(
                records=("beneficiary_id", "size"),
                suspicious=("is_suspicious", "sum"),
                avg_score=("fraud_score", "mean"),
            )
            .reset_index()
            .sort_values(["suspicious", "avg_score"], ascending=False)
            .head(8)
        )
        community_summary = (
            chart_df.groupby("community")
            .agg(
                records=("beneficiary_id", "size"),
                suspicious=("is_suspicious", "sum"),
                avg_score=("fraud_score", "mean"),
            )
            .reset_index()
            .sort_values(["suspicious", "avg_score"], ascending=False)
            .head(8)
        )

        with left:
            st.subheader("Suspicious Records by Program")
            if px and not program_summary.empty:
                fig = px.bar(
                    program_summary.sort_values("suspicious"),
                    x="suspicious",
                    y="program_applied",
                    orientation="h",
                    color="avg_score",
                    color_continuous_scale="YlOrRd",
                    text="suspicious",
                )
                fig.update_layout(
                    xaxis_title="Suspicious records",
                    yaxis_title="",
                    coloraxis_colorbar_title="Avg score",
                    margin=dict(t=12, r=12, b=12, l=12),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(program_summary.set_index("program_applied")["suspicious"])

        with right:
            st.subheader("Suspicious Records by Community")
            if px and not community_summary.empty:
                fig = px.bar(
                    community_summary.sort_values("suspicious"),
                    x="suspicious",
                    y="community",
                    orientation="h",
                    color="avg_score",
                    color_continuous_scale="YlOrRd",
                    text="suspicious",
                )
                fig.update_layout(
                    xaxis_title="Suspicious records",
                    yaxis_title="",
                    coloraxis_colorbar_title="Avg score",
                    margin=dict(t=12, r=12, b=12, l=12),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.bar_chart(community_summary.set_index("community")["suspicious"])

    with tab_timeline:
        st.subheader("Registration Risk Trend")
        trend_df = results_df.copy()
        trend_df["_date"] = pd.to_datetime(trend_df["date_registered"], errors="coerce")
        trend_df = trend_df.dropna(subset=["_date"])
        if trend_df.empty:
            st.info("No valid registration dates were available for a trend chart.")
        else:
            trend_df["registration_period"] = trend_df["_date"].dt.to_period("M").astype(str)
            trend_counts = (
                trend_df.groupby(["registration_period", "risk_level"])
                .size()
                .reset_index(name="records")
            )
            if px:
                fig = px.line(
                    trend_counts,
                    x="registration_period",
                    y="records",
                    color="risk_level",
                    markers=True,
                    color_discrete_map=RISK_COLORS,
                    category_orders={"risk_level": RISK_ORDER},
                )
                fig.update_layout(
                    xaxis_title="Registration month",
                    yaxis_title="Records",
                    legend_title_text="Risk",
                    margin=dict(t=12, r=12, b=12, l=12),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(trend_counts.pivot(index="registration_period", columns="risk_level", values="records"))


def render_explanation_card(record: pd.Series) -> None:
    risk_level = str(record["risk_level"])
    risk_class = risk_level.lower()
    flags = [
        flag
        for flag in str(record["fraud_flags"]).split("; ")
        if flag and flag != "No major flags"
    ]
    flag_items = (
        "".join(f"<li>{html.escape(explain_flag(flag))}</li>" for flag in flags)
        if flags
        else "<li>No configured fraud rules were triggered.</li>"
    )
    similar_matches = html.escape(str(record.get("similar_name_matches", "")) or "None")

    st.markdown(
        f"""
        <div class="explanation-panel">
            <div class="panel-title">{html.escape(str(record["full_name"]) or "Unnamed record")}</div>
            <div class="panel-meta">
                <span class="risk-pill {risk_class}">{html.escape(risk_level)} risk</span>
                &nbsp; Fraud score: <strong>{int(record["fraud_score"])}/100</strong>
                &nbsp; Action: <strong>{html.escape(str(record["review_action"]))}</strong>
            </div>
            <ul>{flag_items}</ul>
            <div class="panel-meta"><strong>Similar names:</strong> {similar_matches}</div>
            <div>{html.escape(str(record["risk_explanation"]))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="NGO Fraud & Duplicate Detection",
        layout="wide",
    )
    inject_styles()

    st.title("NGO Fraud & Duplicate Detection System")
    st.markdown(
        '<div class="app-kicker">Upload beneficiary data, score fraud risk, explain each flag, '
        "and export clean or suspicious records for review.</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Data Input")
        uploaded_file = st.file_uploader("Upload beneficiary CSV", type=["csv"])
        use_sample = st.checkbox("Use included sample data", value=uploaded_file is None)

        st.header("Detection Settings")
        name_threshold = st.slider(
            "Similar name sensitivity",
            min_value=70,
            max_value=100,
            value=88,
            help="Lower values catch more possible spelling variations but may add false positives.",
        )
        address_name_limit = st.number_input(
            "Flag address after this many names",
            min_value=2,
            max_value=20,
            value=3,
            step=1,
        )

    if uploaded_file is not None:
        source_df = pd.read_csv(uploaded_file, dtype=str)
        source_label = uploaded_file.name
    elif use_sample:
        source_df = load_sample_data()
        source_label = "sample_data.csv"
    else:
        source_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        source_label = "No dataset loaded"

    if source_df.empty:
        st.info("Upload a CSV file or enable the sample data to begin.")
        st.stop()

    results_df = analyze_data(
        source_df,
        name_threshold=name_threshold,
        address_name_limit=int(address_name_limit),
    )

    flagged_df = results_df[results_df["risk_level"].isin(["Medium", "High"])].copy()
    clean_df = results_df[results_df["risk_level"] == "Low"].copy()
    duplicate_df = results_df[
        results_df["fraud_flags"].str.contains("duplicate|Repeated", case=False, na=False)
    ].copy()
    high_risk_df = results_df[results_df["risk_level"] == "High"].copy()
    average_score = round(float(results_df["fraud_score"].mean()), 1) if not results_df.empty else 0

    st.subheader(f"Dashboard Summary: {source_label}")
    metric_columns = st.columns(5)
    with metric_columns[0]:
        metric_card("Total records", f"{len(results_df):,}", "Rows processed", "neutral")
    with metric_columns[1]:
        metric_card("Suspicious", f"{len(flagged_df):,}", "Medium or high risk", "medium")
    with metric_columns[2]:
        metric_card("High risk", f"{len(high_risk_df):,}", "Hold before support", "high")
    with metric_columns[3]:
        metric_card("Clean", f"{len(clean_df):,}", "Low-risk records", "low")
    with metric_columns[4]:
        metric_card("Avg score", average_score, "Fraud score out of 100", "neutral")

    secondary_columns = st.columns(3)
    with secondary_columns[0]:
        metric_card("Duplicate records", f"{len(duplicate_df):,}", "Repeated IDs, names, phones, emails, or rows", "neutral")
    with secondary_columns[1]:
        metric_card("Max score", int(results_df["fraud_score"].max()), "Highest record score", "high")
    with secondary_columns[2]:
        metric_card("Review rate", f"{(len(flagged_df) / len(results_df) * 100):.1f}%", "Share needing manual review", "medium")

    render_charts(results_df)

    st.subheader("Search and Filters")
    all_programs = sorted(value for value in results_df["program_applied"].dropna().unique() if value)
    all_communities = sorted(value for value in results_df["community"].dropna().unique() if value)
    all_flags = get_flag_counts(results_df)["flag"].tolist()

    filter_top = st.columns([1.4, 1, 1, 1])
    with filter_top[0]:
        search_query = st.text_input("Search records", placeholder="Name, phone, email, ID, address, flag")
    with filter_top[1]:
        selected_risks = st.multiselect("Risk level", RISK_ORDER, default=RISK_ORDER)
    with filter_top[2]:
        score_range = st.slider("Fraud score range", 0, 100, (0, 100))
    with filter_top[3]:
        selected_flags = st.multiselect("Flag type", all_flags)

    filter_bottom = st.columns(2)
    with filter_bottom[0]:
        selected_programs = st.multiselect("Program", all_programs)
    with filter_bottom[1]:
        selected_communities = st.multiselect("Community", all_communities)

    filtered_df = filter_results(
        results_df,
        search_query=search_query,
        selected_risks=selected_risks,
        selected_programs=selected_programs,
        selected_communities=selected_communities,
        selected_flags=selected_flags,
        score_range=score_range,
    )
    filtered_flagged_df = filtered_df[filtered_df["risk_level"].isin(["Medium", "High"])]

    st.subheader(f"Investigation Queue ({len(filtered_df):,} records)")
    st.dataframe(
        filtered_df[TABLE_COLUMNS],
        use_container_width=True,
        hide_index=True,
        column_config={
            "fraud_score": st.column_config.ProgressColumn(
                "fraud_score",
                help="Weighted fraud score from 0 to 100.",
                min_value=0,
                max_value=100,
            ),
        },
    )

    if not filtered_df.empty:
        st.subheader("Explanation Engine")
        selected_index = st.selectbox(
            "Open record explanation",
            filtered_df.index.tolist(),
            format_func=lambda index: (
                f"{filtered_df.at[index, 'full_name']} | "
                f"{filtered_df.at[index, 'risk_level']} | "
                f"{int(filtered_df.at[index, 'fraud_score'])}/100"
            ),
        )
        render_explanation_card(filtered_df.loc[selected_index])

    st.subheader("Downloads")
    download_columns = st.columns(4)
    with download_columns[0]:
        st.download_button(
            "Download Filtered Review",
            data=convert_df_to_csv(filtered_df[OUTPUT_COLUMNS]),
            file_name="filtered_review_report.csv",
            mime="text/csv",
        )
    with download_columns[1]:
        st.download_button(
            "Download Flagged Report",
            data=convert_df_to_csv(flagged_df[OUTPUT_COLUMNS]),
            file_name="flagged_report.csv",
            mime="text/csv",
        )
    with download_columns[2]:
        st.download_button(
            "Download Cleaned Data",
            data=convert_df_to_csv(clean_df[REQUIRED_COLUMNS]),
            file_name="cleaned_data.csv",
            mime="text/csv",
        )
    with download_columns[3]:
        st.download_button(
            "Download Filtered Flagged",
            data=convert_df_to_csv(filtered_flagged_df[OUTPUT_COLUMNS]),
            file_name="filtered_flagged_report.csv",
            mime="text/csv",
        )

    with st.expander("Expected CSV Columns", expanded=False):
        st.code("\n".join(REQUIRED_COLUMNS), language="text")


if __name__ == "__main__":
    main()
