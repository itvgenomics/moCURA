"""Assembly-level alerts collected from the Phase 1 analyses.

Alerts never remove an assembly. They list conditions a curator should check:
"circularized" runs with more than one contig, assemblies annotated but not
rotated, genes MITOS2 kept only as a fragment at the origin, missing genes,
unresolved Pilon breaks, low coverage and unannotated nhmmer hits.
"""

import os

import pandas as pd

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity


ALERT_COLUMNS = ASSEMBLY_ID_COLUMNS + ["Alert type", "Severity", "Detail"]


def summary_lookup(**kwargs):
    dataframe = kwargs.get("dataframe")
    lookup = {}
    if dataframe is None or dataframe.empty:
        return lookup
    for _, row in dataframe.iterrows():
        try:
            key = (str(row["Project name"]), str(row["Seed Input"]), int(float(row["K-mer"])))
        except (TypeError, ValueError, KeyError):
            continue
        lookup[key] = row
    return lookup


def rows_by_assembly(**kwargs):
    dataframe = kwargs.get("dataframe")
    if dataframe is None or dataframe.empty or "Assembly" not in dataframe.columns:
        return {}
    return {name: group for name, group in dataframe.groupby("Assembly")}


def build_assembly_alerts(**kwargs):
    """Return one row per alert."""

    jobs = kwargs.get("jobs", [])
    summary = summary_lookup(dataframe=kwargs.get("summary_dataframe"))
    completeness = rows_by_assembly(dataframe=kwargs.get("completeness_dataframe"))
    origin = rows_by_assembly(dataframe=kwargs.get("origin_dataframe"))
    coverage = rows_by_assembly(dataframe=kwargs.get("coverage_dataframe"))
    breaks = rows_by_assembly(dataframe=kwargs.get("breaks_dataframe"))
    nhmmer = rows_by_assembly(dataframe=kwargs.get("nhmmer_dataframe"))
    junction = rows_by_assembly(dataframe=kwargs.get("junction_dataframe"))
    integrity = rows_by_assembly(dataframe=kwargs.get("integrity_dataframe"))
    concordance = rows_by_assembly(dataframe=kwargs.get("concordance_dataframe"))
    low_coverage_percent = float(kwargs.get("low_coverage_percent", 5))
    rows = []

    def add(job, alert_type, severity, detail):
        rows.append({**assembly_identity(job=job), "Alert type": alert_type, "Severity": severity, "Detail": detail})

    for job in jobs:
        name = job["Assembly"]
        paths = job.get("paths", {})
        run = summary.get((job["Project name"], job["Seed Input"], job["K-mer"]))

        if run is not None and bool(run.get("Circularized")) and pd.notna(run.get("Total contigs")) and int(run.get("Total contigs")) > 1:
            add(job, "Circularized with several contigs", "warning",
                f"NOVOPlasty reports a circularized genome with {int(run.get('Total contigs'))} contigs; check whether they overlap and merge them manually.")

        if paths.get("genbank") and not paths.get("rotated_genbank"):
            add(job, "Annotated but not rotated", "warning",
                f"{os.path.basename(paths['genbank'])} has no rotated GenBank: MITOS2 annotated no rrnS, so this assembly is missing from marker analyses.")

        for _, item in origin.get(name, pd.DataFrame()).iterrows():
            add(job, "Gene crosses the origin", "info",
                f"{item['Marker']} annotated with {item['Annotated length']} bp; the origin-crossing hit in ignored.mitos gives {item['Origin-corrected length']} bp.")

        for _, item in completeness.get(name, pd.DataFrame()).iterrows():
            if item.get("Genes absent", 0):
                add(job, "Missing genes", "warning", f"{int(item['Genes absent'])} of 37 genes absent: {item['Missing genes']}.")
            if item.get("Genes duplicated", 0):
                add(job, "Duplicated genes", "info", f"{int(item['Genes duplicated'])} genes annotated more than once.")
            if item.get("Gene order matches modal") is False:
                add(job, "Gene order differs", "warning", "Gene order differs from the most common order in this project.")

        for _, item in breaks.get(name, pd.DataFrame()).iterrows():
            where = f"{item['Rotated start']}-{item['Rotated end']} (rotated)" if pd.notna(item.get("Rotated start")) else f"{item['Break start before Pilon']}-{item['Break end before Pilon']} (before Pilon)"
            add(job, "Unresolved Pilon break", "info", f"Pilon could not close a local break at {where}: {item['Pilon message']}.")

        for _, item in coverage.get(name, pd.DataFrame()).iterrows():
            if pd.notna(item.get("Percent below threshold")) and float(item["Percent below threshold"]) > low_coverage_percent:
                add(job, "Low coverage", "warning",
                    f"{item['Percent below threshold']}% of positions below {item['Low-depth threshold']}x.")

        for _, item in nhmmer.get(name, pd.DataFrame()).iterrows():
            if item.get("Alert"):
                add(job, "Unannotated intergenic hit", "warning", str(item["Alert"]))

        for _, item in junction.get(name, pd.DataFrame()).iterrows():
            if item.get("Junction support") == "Unsupported":
                add(job, "Junction without support", "warning",
                    f"{item['Spanning reads']} reads span the circularization junction at {item['Junction position']} (rotated) and {item['Flanking pairs']} pairs flank it.")
            elif item.get("Junction support") == "Weak":
                add(job, "Weak junction support", "info",
                    f"Only {item['Spanning reads']} reads span the circularization junction at {item['Junction position']} (rotated).")

        for _, item in integrity.get(name, pd.DataFrame()).iterrows():
            if item.get("Errors", 0):
                add(job, "Annotation integrity errors", "warning", f"{int(item['Errors'])} error(s): {item['Checks']}.")

        for _, item in concordance.get(name, pd.DataFrame()).iterrows():
            if item.get("In majority group") is False or item.get("In majority group") == False:  # noqa: E712
                add(job, "Outside the majority group", "warning",
                    f"Concordance group {item['Group']} ({item['Group size']} assemblies); the majority group of the sample is {item['Majority group']}.")

    return pd.DataFrame(rows, columns=ALERT_COLUMNS)
