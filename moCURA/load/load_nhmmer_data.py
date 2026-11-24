"""Intergenic nhmmer hits reported by OrganPipe.

OrganPipe searches tRNA, rRNA and origin models in the regions MITOS2 left
unannotated (``nhmmer/{seed}_kmer{k}/{asm}/intergenes_filter.tblout.out``,
HMMER ``--tblout`` format). Each hit that does not overlap an annotated feature
becomes an alert for the assembly: a gene MITOS2 may have missed.
"""

import asyncio
import logging
import os

import pandas as pd

from ..utils.gather_records import gather_records
from ..utils.read_text_async import read_text_file
from .load_mitos2_data import parse_mitos_table
from .organpipe_layout import assembly_identity


NHMMER_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Target", "Query model", "Alignment start", "Alignment end", "Strand", "E-value", "Score",
    "Overlaps annotation", "Alert",
]


def parse_tblout(**kwargs):
    """Parse an nhmmer ``--tblout`` table. Comment lines start with ``#``."""

    text = kwargs.get("text", "") or ""
    hits = []

    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 15:
            continue
        try:
            ali_from, ali_to = int(parts[6]), int(parts[7])
            evalue, score = float(parts[12]), float(parts[13])
        except ValueError:
            continue
        hits.append(
            {
                "Target": parts[0],
                "Query model": parts[2],
                "Alignment start": min(ali_from, ali_to),
                "Alignment end": max(ali_from, ali_to),
                "Strand": parts[11],
                "E-value": evalue,
                "Score": score,
            }
        )

    return hits


def overlaps(**kwargs):
    """True when a 1-based hit overlaps any 0-based inclusive MITOS2 feature."""

    start, end = kwargs.get("start"), kwargs.get("end")
    for feature in kwargs.get("features", []):
        f_start, f_end = feature["start"] + 1, feature["stop"] + 1
        if f_start <= f_end and start <= f_end and end >= f_start:
            return True
    return False


def parse_nhmmer_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    max_evalue = float(kwargs.get("max_evalue", 1e-3))
    paths = job.get("paths", {})
    table = paths.get("nhmmer_table")

    if not table:
        return None

    features = []
    mitos2_dir = paths.get("mitos2_dir")
    if mitos2_dir and os.path.isfile(os.path.join(mitos2_dir, "result.mitos")):
        features = parse_mitos_table(text=read_text_file(file_path=os.path.join(mitos2_dir, "result.mitos")))

    identity = assembly_identity(job=job)
    rows = []
    for hit in parse_tblout(text=read_text_file(file_path=table)):
        if hit["E-value"] > max_evalue:
            continue
        inside = overlaps(start=hit["Alignment start"], end=hit["Alignment end"], features=features)
        rows.append({
            **identity,
            **hit,
            "Overlaps annotation": inside,
            "Alert": "" if inside else f"Unannotated {hit['Query model']} hit at {hit['Alignment start']}-{hit['Alignment end']}",
        })
    return rows


async def parse_nhmmer_assembly(**kwargs):
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        return await asyncio.to_thread(parse_nhmmer_assembly_sync, job=kwargs.get("job"), max_evalue=kwargs.get("max_evalue"))


async def load_nhmmer_data(**kwargs):
    jobs = kwargs.get("jobs", [])
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))
    max_evalue = kwargs.get("max_evalue", 1e-3)

    with_tables = [job for job in jobs if job.get("paths", {}).get("nhmmer_table")]
    if not with_tables:
        logging.warning("No nhmmer intergenic tables were found; intergenic alerts are NA")
        return pd.DataFrame(columns=NHMMER_COLUMNS)

    results = await gather_records(
        tasks=[parse_nhmmer_assembly(job=job, max_evalue=max_evalue, semaphore=semaphore) for job in with_tables],
        source_name="nhmmer table",
    )
    dataframe = pd.DataFrame([row for rows in results for row in rows], columns=NHMMER_COLUMNS)
    logging.info("nhmmer hits: %d (%d outside annotated features)", len(dataframe), int((~dataframe["Overlaps annotation"]).sum()) if not dataframe.empty else 0)
    return dataframe
