"""Transparent score to choose which assembly to keep in each sample.

Every indicator is turned into a component between 0 and 1. The score is the
weighted mean of the components, times 100. An indicator that is NA for an
assembly (for example no BAM, or no rotated genome) counts as ``na_value``
(default 0.5): missing evidence is neither as good as a supported result nor as
bad as a failed one, and when a component is NA for every assembly of a project
it shifts all of them equally. Set ``na_value: null`` to leave NA components
out of the weighted mean instead. Weights come from ``assembly_score.weights``
in ``config.yml``.

Components:

* completeness: genes present / 37;
* integrity: 1 / (1 + errors and warnings of the annotation checks);
* junction: Supported 1, Weak 0.5, Unsupported 0;
* coverage: (1 - min(CV, 1)) x (1 - share of bases below the depth threshold);
* pilon: Pilon Confirmed % / 100;
* concordance: 1 inside the majority group of the sample, 0 outside;
* length: 1 at the modal genome length of the project, falling linearly to 0 at
  ``length_tolerance_percent`` away from it.

Circularization is eliminatory: only circularized assemblies can be
recommended. Assemblies that are not circularized still get a score and a rank
below the eligible ones; nothing is removed.
"""

import logging
from collections import Counter

import pandas as pd

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity

DEFAULT_WEIGHTS = {
    "completeness": 3, "integrity": 2, "junction": 2, "coverage": 1,
    "pilon": 1, "concordance": 2, "length": 1,
}
COMPONENT_LABELS = {
    "completeness": "Annotation completeness", "integrity": "Integrity alerts", "junction": "Junction support",
    "coverage": "Coverage uniformity", "pilon": "Pilon confirmed bases", "concordance": "Majority concordance group",
    "length": "Closeness to modal length",
}
SCORE_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Circularized", "Eligible", "Score", "Rank in project", "Recommended",
    *[f"{label} (0-1)" for label in COMPONENT_LABELS.values()],
    "Genome length", "Modal genome length", "Score breakdown",
]


def by_assembly(**kwargs):
    dataframe = kwargs.get("dataframe")
    if dataframe is None or dataframe.empty or "Assembly" not in dataframe.columns:
        return {}
    return {row["Assembly"]: row for _, row in dataframe.iterrows()}


def value(row, column):
    if row is None:
        return None
    item = row.get(column)
    return None if item is None or (isinstance(item, float) and pd.isna(item)) else item


def weighted_score(**kwargs):
    """Score (0-100) and the components that entered it."""

    components = kwargs.get("components", {})
    weights = kwargs.get("weights", DEFAULT_WEIGHTS)
    na_value = kwargs.get("na_value", 0.5)
    if na_value is not None:
        components = {name: (float(na_value) if component is None else component) for name, component in components.items()}
    used = {name: component for name, component in components.items() if component is not None and float(weights.get(name, 0)) > 0}
    total = sum(float(weights[name]) for name in used)
    if not total:
        return None, used
    return round(100 * sum(float(weights[name]) * component for name, component in used.items()) / total, 2), used


def build_assembly_score(**kwargs):
    jobs = kwargs.get("jobs", [])
    weights = {**DEFAULT_WEIGHTS, **(kwargs.get("weights") or {})}
    tolerance = float(kwargs.get("length_tolerance_percent", 5))
    na_value = kwargs.get("na_value", 0.5)
    expected = int(kwargs.get("expected_genes", 37))
    circular_lookup = kwargs.get("circular_lookup", {}) or {}
    pilon_lookup = kwargs.get("pilon_lookup", {}) or {}
    completeness = by_assembly(dataframe=kwargs.get("completeness_dataframe"))
    integrity = by_assembly(dataframe=kwargs.get("integrity_dataframe"))
    junction = by_assembly(dataframe=kwargs.get("junction_dataframe"))
    coverage = by_assembly(dataframe=kwargs.get("coverage_dataframe"))
    concordance = by_assembly(dataframe=kwargs.get("concordance_dataframe"))

    lengths = {}
    for job in jobs:
        name = job["Assembly"]
        length = value(integrity.get(name), "Genome length") or value(coverage.get(name), "Genome length")
        lengths[name] = int(length) if length else None

    modal = {}
    for project in {job["Project name"] for job in jobs}:
        values = [lengths[job["Assembly"]] for job in jobs if job["Project name"] == project and lengths[job["Assembly"]]
                  and circular_lookup.get((job["Project name"], job["Seed Input"], job["K-mer"])) is True]
        modal[project] = Counter(values).most_common(1)[0][0] if values else None

    rows = []
    for job in jobs:
        name = job["Assembly"]
        key = (job["Project name"], job["Seed Input"], job["K-mer"])
        circular = circular_lookup.get(key)
        components = {name_: None for name_ in DEFAULT_WEIGHTS}

        present = value(completeness.get(name), "Genes present")
        if present is not None:
            components["completeness"] = min(1.0, float(present) / expected)
        alerts = value(integrity.get(name), "Integrity alerts")
        if alerts is not None:
            components["integrity"] = 1 / (1 + float(alerts))
        support = value(junction.get(name), "Junction support")
        components["junction"] = {"Supported": 1.0, "Weak": 0.5, "Unsupported": 0.0}.get(support)
        cv = value(coverage.get(name), "Coefficient of variation")
        below = value(coverage.get(name), "Percent below threshold")
        if cv is not None:
            components["coverage"] = (1 - min(float(cv), 1.0)) * (1 - float(below or 0) / 100)
        confirmed = pilon_lookup.get(key)
        if confirmed is not None:
            components["pilon"] = max(0.0, min(1.0, float(confirmed) / 100))
        member = value(concordance.get(name), "In majority group")
        if member is not None:
            components["concordance"] = 1.0 if bool(member) else 0.0
        mode = modal.get(job["Project name"])
        if lengths[name] and mode:
            deviation = 100 * abs(lengths[name] - mode) / mode
            components["length"] = max(0.0, 1 - deviation / tolerance) if tolerance > 0 else float(deviation == 0)

        score, used = weighted_score(components=components, weights=weights, na_value=na_value)
        breakdown = "; ".join(
            f"{COMPONENT_LABELS[item]} {used[item]:.2f} x {float(weights[item]):g}" for item in DEFAULT_WEIGHTS if item in used
        )
        missing = [COMPONENT_LABELS[item] for item in DEFAULT_WEIGHTS if components[item] is None and float(weights.get(item, 0)) > 0]
        if missing:
            breakdown += f" | NA, {'counted as ' + format(float(na_value), 'g') if na_value is not None else 'not counted'}: {', '.join(missing)}"
        rows.append({
            **assembly_identity(job=job),
            "Circularized": circular,
            "Eligible": circular is True,
            "Score": score,
            **{f"{COMPONENT_LABELS[item]} (0-1)": round(components[item], 4) if components[item] is not None else None for item in DEFAULT_WEIGHTS},
            "Genome length": lengths[name],
            "Modal genome length": mode,
            "Score breakdown": breakdown,
        })

    dataframe = pd.DataFrame(rows)
    if dataframe.empty:
        return pd.DataFrame(columns=SCORE_COLUMNS)
    dataframe["_score"] = dataframe["Score"].fillna(-1)
    dataframe["_eligible"] = dataframe["Eligible"].astype(int)
    dataframe = dataframe.sort_values(
        ["Project name", "_eligible", "_score", "Assembly copy", "K-mer"], ascending=[True, False, False, True, True],
    )
    dataframe["Rank in project"] = dataframe.groupby("Project name").cumcount() + 1
    dataframe["Recommended"] = (dataframe["Rank in project"] == 1) & dataframe["Eligible"] & dataframe["Score"].notna()
    dataframe = dataframe.drop(columns=["_score", "_eligible"])
    logging.info("Assembly score: %d assemblies ranked, %d recommended", len(dataframe), int(dataframe["Recommended"].sum()))
    return dataframe[SCORE_COLUMNS].reset_index(drop=True)
