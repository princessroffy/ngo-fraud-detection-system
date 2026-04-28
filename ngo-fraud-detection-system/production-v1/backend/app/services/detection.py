from __future__ import annotations

import re
from itertools import combinations
from typing import Iterable

import pandas as pd
from rapidfuzz import fuzz


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


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9\s@._+-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_phone(value: object) -> str:
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


def rule(weights: dict[str, dict[str, int | str]], rule_key: str) -> tuple[str, int]:
    config = weights[rule_key]
    return str(config["label"]), int(config["score"])


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


def detect_similar_names(
    df: pd.DataFrame,
    weights: dict[str, dict[str, int | str]],
    threshold: int,
) -> None:
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
    label, score = rule(weights, "similar_beneficiary_name")
    append_flag(df, df.index[similar_mask], label, score)


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


def explain_flag(flag: str) -> str:
    if flag.startswith("Same address"):
        return "The same address is linked to several beneficiary names and may need household verification."
    return FLAG_EXPLANATIONS.get(flag, "This record matched a configured fraud or duplicate rule.")


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


def analyze_records(
    raw_df: pd.DataFrame,
    weights: dict[str, dict[str, int | str]],
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
    append_flag(df, df.index[duplicated_full_rows], *rule(weights, "exact_duplicate_row"))

    add_group_flag(df, "_normalized_id", *rule(weights, "repeated_beneficiary_id"))
    add_group_flag(df, "_normalized_name", *rule(weights, "repeated_full_name"))
    add_group_flag(df, "_normalized_phone", *rule(weights, "repeated_phone_number"))
    add_group_flag(df, "_normalized_email", *rule(weights, "repeated_email_address"))
    add_group_flag(
        df,
        "_normalized_phone",
        *rule(weights, "phone_many_names"),
        require_multiple_names=True,
    )
    add_group_flag(
        df,
        "_normalized_email",
        *rule(weights, "email_many_names"),
        require_multiple_names=True,
    )
    address_label, address_score = rule(weights, "address_many_names")
    add_group_flag(
        df,
        "_normalized_address",
        f"{address_label} ({address_name_limit}+)",
        address_score,
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
    append_flag(df, df.index[repeated_program_mask], *rule(weights, "same_person_across_programs"))

    detect_similar_names(df, weights, name_threshold)

    df["fraud_score"] = df["fraud_score"].clip(upper=100)
    df["risk_level"] = df["fraud_score"].map(assign_risk_level)
    df["review_action"] = df["risk_level"].map(recommend_action)
    df["fraud_flags"] = df["_flag_list"].apply(lambda flags: list(dict.fromkeys(flags)))
    df["score_breakdown"] = df["_score_list"].apply(lambda scores: list(dict.fromkeys(scores)))
    df["risk_explanation"] = df.apply(build_explanation, axis=1)

    helper_columns = [column for column in df.columns if column.startswith("_")]
    return df.drop(columns=helper_columns)
