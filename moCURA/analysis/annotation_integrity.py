"""Integrity checks of the annotated genes of each assembly.

Read from the rotated GenBank (``genbanks/{asm}.rotated.gb``; the unrotated
``{asm}.gb`` when MITOS2 could not rotate). Protein-coding genes are translated
with the genetic code taken from ``annotation_integrity.genetic_code`` in
``config.yml``, or from ``genetic_code`` in the OrganPipe ``config/config.yaml``
when that file exists.

Checks and severities:

* internal stop codon: error;
* CDS length not a multiple of 3 that is not an incomplete stop: error;
* start codon outside the start codons of the genetic code: warning;
* no stop codon at all: warning;
* incomplete stop codon (T or TA): info. In animal mitochondria these are
  completed to TAA by polyadenylation of the transcript, so they are expected;
* gene crossing the contig origin: warning;
* length deviating more than ``length_deviation_percent`` from the modal length
  of the same marker in the same project: warning.
"""

import asyncio
import logging
import os
from collections import Counter, defaultdict

import pandas as pd
import yaml
from Bio import SeqIO
from Bio.Data import CodonTable

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity
from ..standardization.standardized_marker_name import standardized_marker_name

ISSUE_COLUMNS = ASSEMBLY_ID_COLUMNS + ["Marker", "Feature type", "Start", "End", "Strand", "Length", "Check", "Severity", "Detail"]
SUMMARY_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "GenBank source", "Genome length", "Genetic code", "Annotated genes", "Protein-coding genes",
    "Errors", "Warnings", "Informative", "Integrity alerts", "Checks",
]


def find_key(**kwargs):
    """Depth-first search for a key in a nested mapping."""

    data = kwargs.get("data")
    key = kwargs.get("key")
    if isinstance(data, dict):
        if key in data:
            return data[key]
        for value in data.values():
            found = find_key(data=value, key=key)
            if found is not None:
                return found
    if isinstance(data, list):
        for value in data:
            found = find_key(data=value, key=key)
            if found is not None:
                return found
    return None


def genetic_code_from_organpipe(**kwargs):
    organpipe_dir = kwargs.get("organpipe_dir")
    if not organpipe_dir:
        return None
    for name in ("config.yaml", "config.yml"):
        path = os.path.join(organpipe_dir, "config", name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                value = find_key(data=yaml.safe_load(handle), key="genetic_code")
            return int(value) if value is not None else None
        except (OSError, ValueError, TypeError, yaml.YAMLError) as error:
            logging.warning("Could not read genetic_code from %s: %s", path, error)
    return None


def check_cds(**kwargs):
    """Return (check, severity, detail) tuples for one coding sequence."""

    sequence = str(kwargs.get("sequence", "")).upper()
    table_id = int(kwargs.get("table", 2))
    table = CodonTable.unambiguous_dna_by_id[table_id]
    issues = []
    if len(sequence) < 3:
        return [("Too short", "error", f"{len(sequence)} bp")]

    start = sequence[:3]
    if start not in table.start_codons:
        issues.append(("Non-standard start codon", "warning", f"{start} is not a start codon in genetic code {table_id}"))

    remainder = len(sequence) % 3
    complete = sequence[: len(sequence) - remainder]
    codons = [complete[i:i + 3] for i in range(0, len(complete), 3)]
    stops = [index for index, codon in enumerate(codons) if codon in table.stop_codons]
    terminal_stop = bool(codons) and codons[-1] in table.stop_codons
    internal = [index for index in stops if index != len(codons) - 1]
    if internal:
        issues.append(("Internal stop codon", "error", f"stop at codon {internal[0] + 1} of {len(codons)}"))

    tail = sequence[len(sequence) - remainder:]
    if remainder and tail in ("T", "TA"):
        issues.append(("Incomplete stop codon", "info", f"ends with {tail}; completed to TAA by polyadenylation"))
    elif remainder:
        issues.append(("Length not a multiple of 3", "error", f"{len(sequence)} bp ends with {tail}, not an incomplete stop"))
    elif not terminal_stop:
        issues.append(("No stop codon", "warning", f"last codon {codons[-1]} is not a stop codon in genetic code {table_id}"))
    return issues


def crosses_origin(**kwargs):
    feature = kwargs.get("feature")
    length = kwargs.get("length")
    parts = getattr(feature.location, "parts", [feature.location])
    if len(parts) < 2:
        return False
    return any(int(part.end) == length for part in parts) and any(int(part.start) == 0 for part in parts)


def integrity_assembly_sync(**kwargs):
    """Per-feature records and issues of one assembly (length deviation is added later)."""

    job = kwargs.get("job", {})
    genetic_code = int(kwargs.get("genetic_code", 2))
    origin_markers = kwargs.get("origin_markers", set())
    paths = job.get("paths", {})
    path, source = paths.get("rotated_genbank"), "rotated"
    if not path:
        path, source = paths.get("genbank"), "unrotated"
    if not path:
        return None

    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return None
    identity = assembly_identity(job=job)
    length = len(record.seq)
    features, issues = [], []

    for feature in record.features:
        if feature.type not in ("CDS", "rRNA", "tRNA"):
            continue
        marker = standardized_marker_name(feature_type=feature.type, qualifiers=feature.qualifiers)
        if not marker:
            continue
        strand = "-" if feature.location.strand == -1 else "+"
        base = {
            **identity, "Marker": marker, "Feature type": feature.type,
            "Start": int(feature.location.start) + 1, "End": int(feature.location.end), "Strand": strand,
            "Length": len(feature.location),
        }
        features.append(base)
        if crosses_origin(feature=feature, length=length) or marker in origin_markers:
            issues.append({**base, "Check": "Gene crosses the origin", "Severity": "warning",
                           "Detail": "the gene spans the start/end of the contig; its annotation may be split"})
        if feature.type == "CDS":
            table = genetic_code
            if feature.qualifiers.get("transl_table"):
                try:
                    table = int(feature.qualifiers["transl_table"][0])
                except (TypeError, ValueError):
                    pass
            for check, severity, detail in check_cds(sequence=feature.extract(record.seq), table=table):
                issues.append({**base, "Check": check, "Severity": severity, "Detail": detail})

    return {"identity": identity, "source": source, "length": length, "features": features, "issues": issues}


async def integrity_assembly(**kwargs):
    async with kwargs.get("semaphore"):
        return await asyncio.to_thread(
            integrity_assembly_sync, job=kwargs.get("job"), genetic_code=kwargs.get("genetic_code"),
            origin_markers=kwargs.get("origin_markers"),
        )


def length_deviation_issues(**kwargs):
    """Flag genes whose length deviates from the modal length of the marker in the project."""

    features = kwargs.get("features", [])
    percent = float(kwargs.get("length_deviation_percent", 10))
    lengths = defaultdict(list)
    for feature in features:
        lengths[(feature["Project name"], feature["Marker"])].append(feature["Length"])
    modal = {key: Counter(values).most_common(1)[0][0] for key, values in lengths.items() if len(values) >= 2}

    issues = []
    for feature in features:
        mode = modal.get((feature["Project name"], feature["Marker"]))
        if not mode:
            continue
        deviation = 100 * abs(feature["Length"] - mode) / mode
        if deviation > percent:
            issues.append({**feature, "Check": "Length differs from the project mode", "Severity": "warning",
                           "Detail": f"{feature['Length']} bp vs modal {mode} bp ({deviation:.1f}% off)"})
    return issues


async def load_annotation_integrity(**kwargs):
    """Return (issues dataframe, per-assembly summary dataframe)."""

    jobs = kwargs.get("jobs", [])
    genetic_code = int(kwargs.get("genetic_code", 2))
    origin_dataframe = kwargs.get("origin_dataframe")
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))

    origin = defaultdict(set)
    if origin_dataframe is not None and not origin_dataframe.empty:
        for _, row in origin_dataframe.iterrows():
            if bool(row.get("Crosses origin", True)):
                origin[row["Assembly"]].add(str(row["Marker"]))

    results = await asyncio.gather(
        *[integrity_assembly(job=job, genetic_code=genetic_code, origin_markers=origin.get(job["Assembly"], set()), semaphore=semaphore) for job in jobs],
        return_exceptions=True,
    )
    parsed = []
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            logging.error("Annotation integrity failed for %s: %s", job.get("Assembly"), result)
        elif result is not None:
            parsed.append(result)
    if len(parsed) < len(jobs):
        logging.warning("GenBank missing for %d of %d assemblies; their annotation integrity is NA", len(jobs) - len(parsed), len(jobs))

    features = [feature for item in parsed for feature in item["features"]]
    issues = [issue for item in parsed for issue in item["issues"]]
    issues.extend(length_deviation_issues(features=features, length_deviation_percent=kwargs.get("length_deviation_percent", 10)))
    issues_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)

    by_assembly = defaultdict(list)
    for issue in issues:
        by_assembly[issue["Assembly"]].append(issue)
    summary = []
    for item in parsed:
        name = item["identity"]["Assembly"]
        found = by_assembly.get(name, [])
        severities = Counter(issue["Severity"] for issue in found)
        summary.append({
            **item["identity"],
            "GenBank source": item["source"],
            "Genome length": item["length"],
            "Genetic code": genetic_code,
            "Annotated genes": len({feature["Marker"] for feature in item["features"]}),
            "Protein-coding genes": len({feature["Marker"] for feature in item["features"] if feature["Feature type"] == "CDS"}),
            "Errors": severities.get("error", 0),
            "Warnings": severities.get("warning", 0),
            "Informative": severities.get("info", 0),
            "Integrity alerts": severities.get("error", 0) + severities.get("warning", 0),
            "Checks": "; ".join(sorted({f"{issue['Marker']}: {issue['Check']}" for issue in found if issue["Severity"] != "info"})),
        })
    summary_df = pd.DataFrame(summary, columns=SUMMARY_COLUMNS)
    logging.info("Annotation integrity: %d assemblies, %d issues", len(summary_df), len(issues_df))
    return issues_df, summary_df
