"""NCBI submission check of the annotation with table2asn.

For each selected assembly (the recommended one per project by default) the
rotated GenBank, or the GenBank when the assembly was not rotated, is
converted into what a GenBank submission needs:

* ``{assembly}.fsa``: the sequence with source modifiers in the definition line
  (organism, location, genetic code, topology, completeness);
* ``{assembly}.tbl``: the 5-column feature table, with a gene feature for every
  CDS, rRNA and tRNA, NCBI product names (``cytochrome c oxidase subunit I``,
  ``tRNA-Leu``, ``12S ribosomal RNA``) and, for coding sequences ending in an
  incomplete stop codon (T or TA), a ``transl_except`` to TERM with the usual
  note that the stop codon is completed by polyadenylation.

table2asn then validates the record (``-V vb``) and writes the discrepancy
report (``-Z``). The ``.sqn`` and ``.gbf`` files are kept next to the inputs,
ready for review. Messages listed in ``ignore_codes`` (for example the missing
taxon ID of an offline run) are left out of the counts. The submission
template (``-t``) is optional; without it the messages about the missing
publication and citation (``TEMPLATE_CODES``) are ignored.
"""

import asyncio
import logging
import os
import re
import shutil

import pandas as pd
from Bio import SeqIO

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity
from ..standardization.standardized_marker_name import standardized_marker_name


SUMMARY_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Organism", "GenBank source", "Rejects", "Errors", "Warnings", "Infos", "Fatal discrepancies",
    "Discrepancies", "Incomplete stops completed", "Main issues", "Output folder",
]
MESSAGE_COLUMNS = ASSEMBLY_ID_COLUMNS + ["Source", "Severity", "Code", "Message", "Location"]

PRODUCTS = {
    "COI": ("COX1", "cytochrome c oxidase subunit I"),
    "COII": ("COX2", "cytochrome c oxidase subunit II"),
    "COIII": ("COX3", "cytochrome c oxidase subunit III"),
    "ATP6": ("ATP6", "ATP synthase F0 subunit 6"),
    "ATP8": ("ATP8", "ATP synthase F0 subunit 8"),
    "ND1": ("ND1", "NADH dehydrogenase subunit 1"),
    "ND2": ("ND2", "NADH dehydrogenase subunit 2"),
    "ND3": ("ND3", "NADH dehydrogenase subunit 3"),
    "ND4": ("ND4", "NADH dehydrogenase subunit 4"),
    "ND4L": ("ND4L", "NADH dehydrogenase subunit 4L"),
    "ND5": ("ND5", "NADH dehydrogenase subunit 5"),
    "ND6": ("ND6", "NADH dehydrogenase subunit 6"),
    "CYTB": ("CYTB", "cytochrome b"),
    "12S": ("rrnS", "12S ribosomal RNA"),
    "16S": ("rrnL", "16S ribosomal RNA"),
}

# Discrepancy tests that only count features or need a submission template.
INFORMATIONAL_DISCREPANCIES = {
    "COUNT_NUCLEOTIDES", "FEATURE_COUNT", "SOURCE_QUALS", "DUP_DEFLINE", "CITSUBAFFIL_CONFLICT",
    "AUTODEF_USER_OBJECT", "NO_ANNOTATION", "COUNT_PROTEINS", "MISSING_GENES",
}

# Without a submission template (-t) every record lacks a publication; not a problem of the assembly.
TEMPLATE_CODES = {"SEQ_DESCR.NoPubFound", "GENERIC.MissingPubRequirement", "SEQ_DESCR.NoSourceDescriptor"}

VALIDATION_LINE = re.compile(r"^(Info|Warning|Error|Reject|Fatal):\s+valid\s+\[([^\]]+)\]\s+(.*)$")
LOCATION = re.compile(r"\[lcl\|[^:\]]+:([^\]]+)\]")


def qualifier(feature, name):
    values = feature.qualifiers.get(name) or []
    return str(values[0]).strip() if values else ""


def interval_rows(feature):
    """(start, end) pairs in table order: minus-strand intervals are written end-first."""

    rows = []
    parts = list(feature.location.parts)
    if feature.location.strand == -1:
        parts = sorted(parts, key=lambda part: int(part.start), reverse=True)
    for part in parts:
        start, end = int(part.start) + 1, int(part.end)
        rows.append((end, start) if part.strand == -1 else (start, end))
    return rows


def incomplete_stop(**kwargs):
    """transl_except location of a CDS ending in T or TA, else None."""

    feature = kwargs.get("feature")
    sequence = str(feature.extract(kwargs.get("record").seq)).upper()
    remainder = len(sequence) % 3
    if remainder == 0 or sequence[-remainder:] not in ("T", "TA"):
        return None
    if feature.location.strand == -1:
        low = int(feature.location.start) + 1
        span = f"{low}" if remainder == 1 else f"{low}..{low + 1}"
        return f"complement({span})"
    high = int(feature.location.end)
    return f"{high}" if remainder == 1 else f"{high - 1}..{high}"


def feature_table(**kwargs):
    """Return (table text, incomplete stops completed) for one record."""

    record = kwargs.get("record")
    sequence_id = kwargs.get("sequence_id")
    genetic_code = int(kwargs.get("genetic_code", 2))
    lines = [f">Feature {sequence_id}"]
    completed = 0

    def write(feature, kind, values):
        for index, (start, end) in enumerate(interval_rows(feature)):
            lines.append(f"{start}\t{end}" + (f"\t{kind}" if index == 0 else ""))
        for key, value in values:
            if value not in (None, ""):
                lines.append(f"\t\t\t{key}\t{value}")

    for feature in record.features:
        if feature.type not in ("CDS", "rRNA", "tRNA", "D-loop", "rep_origin"):
            continue
        marker = standardized_marker_name(feature_type=feature.type, qualifiers=feature.qualifiers)
        if feature.type == "D-loop":
            write(feature, "D-loop", [("note", qualifier(feature, "note") or "control region")])
            continue
        if feature.type == "rep_origin":
            write(feature, "rep_origin", [("note", qualifier(feature, "note"))])
            continue
        gene_symbol, product = PRODUCTS.get(marker or "", (None, None))
        if feature.type == "tRNA":
            product = (marker or "tRNA-Xxx").split("-")
            product = "-".join(product[:2])
            raw = qualifier(feature, "gene") or qualifier(feature, "product")
            gene_symbol = raw.split("(")[0] if raw.lower().startswith("trn") else None
        gene_symbol = gene_symbol or qualifier(feature, "gene") or marker
        product = product or qualifier(feature, "product") or qualifier(feature, "gene") or marker
        write(feature, "gene", [("gene", gene_symbol)])
        values = [("product", product)]
        if feature.type == "CDS":
            values = [("gene", gene_symbol), ("product", product), ("codon_start", qualifier(feature, "codon_start") or "1"),
                      ("transl_table", str(genetic_code))]
            stop = incomplete_stop(feature=feature, record=record)
            if stop:
                completed += 1
                values += [("transl_except", f"(pos:{stop},aa:TERM)"),
                           ("note", "TAA stop codon is completed by the addition of 3' A residues to the mRNA")]
        write(feature, feature.type, values)
    return "\n".join(lines) + "\n", completed


def parse_validation(**kwargs):
    """Messages of a table2asn .val file."""

    path = kwargs.get("path")
    messages = []
    if not path or not os.path.isfile(path):
        return messages
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = VALIDATION_LINE.match(line.strip())
            if not match:
                continue
            severity, code, message = match.groups()
            location = LOCATION.search(message)
            text = re.sub(r"\s*\[lcl\|[^\]]*\]", "", message)
            text = re.sub(r"\s*BIOSEQ(-SET)?:.*$", "", text).strip()
            messages.append({"Source": "validation", "Severity": severity.lower(), "Code": code,
                             "Message": text, "Location": location.group(1) if location else ""})
    return messages


def parse_discrepancies(**kwargs):
    """Summary lines of a table2asn .dr file (informational tests left out)."""

    path = kwargs.get("path")
    messages = []
    if not path or not os.path.isfile(path):
        return messages
    in_summary = False
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip()
            if line.strip() == "Summary":
                in_summary = True
                continue
            if line.strip() == "Detailed Report":
                break
            if not in_summary or ":" not in line:
                continue
            fatal = line.startswith("FATAL:")
            text = line[len("FATAL:"):].strip() if fatal else line.strip()
            code, message = [part.strip() for part in text.split(":", 1)]
            if code in INFORMATIONAL_DISCREPANCIES:
                continue
            messages.append({"Source": "discrepancy report", "Severity": "fatal" if fatal else "discrepancy",
                             "Code": code, "Message": message, "Location": ""})
    return messages


async def validate_assembly(**kwargs):
    job = kwargs.get("job", {})
    settings = kwargs.get("settings", {}) or {}
    output_dir = kwargs.get("output_dir")
    organism = kwargs.get("organism") or "unidentified"
    organelle = kwargs.get("organelle", "mitochondrion")
    genetic_code = int(kwargs.get("genetic_code", 2))
    binary = kwargs.get("binary", "table2asn")
    semaphore = kwargs.get("semaphore")
    paths = job.get("paths", {})
    path, source = paths.get("rotated_genbank"), "rotated"
    if not path:
        path, source = paths.get("genbank"), "unrotated"
    if not path:
        return None

    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return None
    name = job["Assembly"]
    folder = os.path.join(output_dir, name)
    os.makedirs(folder, exist_ok=True, mode=0o755)
    sequence_id = re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:48]
    location = "chloroplast" if organelle == "chloroplast" else "mitochondrion"
    modifiers = [f"[organism={organism}]", f"[location={location}]"]
    if location == "mitochondrion":
        modifiers.append(f"[mgcode={genetic_code}]")
    if str(record.annotations.get("topology", "")).lower() == "circular":
        modifiers += ["[topology=circular]", "[completeness=complete]"]
    fasta_path = os.path.join(folder, f"{sequence_id}.fsa")
    table_path = os.path.join(folder, f"{sequence_id}.tbl")
    with open(fasta_path, "w", encoding="utf-8") as handle:
        handle.write(f">{sequence_id} {' '.join(modifiers)}\n{str(record.seq).upper()}\n")
    table, completed = feature_table(record=record, sequence_id=sequence_id, genetic_code=genetic_code)
    with open(table_path, "w", encoding="utf-8") as handle:
        handle.write(table)

    command = [binary, "-i", fasta_path, "-f", table_path, "-o", os.path.join(folder, f"{sequence_id}.sqn"), "-V", "vb", "-Z", "-a", "s"]
    if settings.get("template"):
        command += ["-t", str(settings["template"])]
    async with semaphore:
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=int(settings.get("timeout", 600)))
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logging.warning("table2asn timed out for %s", name)
            return None
    with open(os.path.join(folder, "table2asn.log"), "wb") as handle:
        handle.write(stdout + stderr)

    ignore = set(settings.get("ignore_codes", []) or [])
    if not settings.get("template"):
        ignore |= TEMPLATE_CODES
    messages = [message for message in parse_validation(path=os.path.join(folder, f"{sequence_id}.val")) + parse_discrepancies(path=os.path.join(folder, f"{sequence_id}.dr"))
                if message["Code"] not in ignore]
    identity = assembly_identity(job=job)
    count = lambda severity: sum(1 for message in messages if message["Severity"] == severity)
    main = pd.Series([message["Code"] for message in messages if message["Severity"] in ("reject", "fatal", "error")]).value_counts()
    summary = {
        **identity,
        "Organism": organism,
        "GenBank source": source,
        "Rejects": count("reject"),
        "Errors": count("error"),
        "Warnings": count("warning"),
        "Infos": count("info"),
        "Fatal discrepancies": count("fatal"),
        "Discrepancies": count("discrepancy"),
        "Incomplete stops completed": completed,
        "Main issues": ", ".join(f"{code} ×{number}" for code, number in main.items()),
        "Output folder": folder,
    }
    if process.returncode != 0 and not messages:
        logging.warning("table2asn exited with code %s for %s; see %s", process.returncode, name, os.path.join(folder, "table2asn.log"))
    return summary, [{**identity, **message} for message in messages]


def select_jobs(**kwargs):
    """Jobs to validate: the recommended assembly of each project, or all of them."""

    jobs = kwargs.get("jobs", [])
    scores = kwargs.get("scores_dataframe")
    scope = str(kwargs.get("scope", "recommended")).lower()
    if scope == "all" or scores is None or scores.empty or "Recommended" not in scores.columns:
        return jobs
    recommended = set(scores.loc[scores["Recommended"] == True, "Assembly"].astype(str))  # noqa: E712
    return [job for job in jobs if job["Assembly"] in recommended]


async def run_ncbi_validation(**kwargs):
    """Return (summary dataframe, messages dataframe)."""

    settings = kwargs.get("settings", {}) or {}
    binary = settings.get("binary", "table2asn")
    if not shutil.which(binary):
        logging.warning("table2asn not found (%s); NCBI validation skipped. Install it from bioconda (table2asn).", binary)
        return pd.DataFrame(columns=SUMMARY_COLUMNS), pd.DataFrame(columns=MESSAGE_COLUMNS)
    jobs = select_jobs(jobs=kwargs.get("jobs", []), scores_dataframe=kwargs.get("scores_dataframe"), scope=settings.get("assemblies", "recommended"))
    organisms = kwargs.get("organisms", {}) or {}
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 4))))
    results = await asyncio.gather(*[
        validate_assembly(job=job, settings=settings, output_dir=kwargs.get("output_dir"), organism=organisms.get(job["Project name"]),
                          organelle=kwargs.get("organelle", "mitochondrion"), genetic_code=kwargs.get("genetic_code", 2),
                          binary=binary, semaphore=semaphore)
        for job in jobs
    ])
    summaries, messages = [], []
    for result in results:
        if result:
            summaries.append(result[0])
            messages.extend(result[1])
    logging.info("NCBI validation: %d assemblies checked with table2asn", len(summaries))
    return pd.DataFrame(summaries, columns=SUMMARY_COLUMNS), pd.DataFrame(messages, columns=MESSAGE_COLUMNS)
