"""Read recruitment from OrganPipe BLAST tables.

``images/{seed}_kmer{k}/{asm}.rotated.blastn.out`` (or ``{asm}.blastn.out``)
is BLAST outfmt 6: query read, subject, percent identity (column 3), ..., subject
start and end (columns 9 and 10). The queries are NOVOPlasty ``Assembled_reads``
of the same run, so these numbers describe how well the reads used to build the
assembly agree with it; they are not an independent validation.
"""

import asyncio
import logging
import os

import pandas as pd

from ..utils.gather_records import gather_records
from .organpipe_layout import assembly_identity


IDENTITY_BINS = [90 + 0.5 * index for index in range(21)]

RECRUITMENT_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Coordinate system", "Recruited reads", "Mean identity", "Median identity",
    "Identity threshold", "Reads below threshold", "Percent below threshold",
    "Target length", "Target bases covered", "Target coverage %", "BLAST file",
    "OrganPipe recruitment plot",
]


def identity_bin(**kwargs):
    """Index of the 0.5% identity bin; values below 90% go to the first bin."""

    identity = float(kwargs.get("identity"))
    if identity < 90:
        return 0
    return min(len(IDENTITY_BINS) - 1, int((identity - 90) * 2))


def summarize_blast_table(**kwargs):
    """Summarize a BLAST outfmt 6 table. ``target_length`` may be None."""

    path = kwargs.get("path")
    threshold = float(kwargs.get("threshold", 98))
    target_length = kwargs.get("target_length")

    identities = []
    histogram = [0] * len(IDENTITY_BINS)
    intervals = []
    max_end = 0

    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 10:
                continue
            try:
                identity = float(parts[2])
                start, end = sorted((int(parts[8]), int(parts[9])))
            except ValueError:
                continue
            identities.append(identity)
            histogram[identity_bin(identity=identity)] += 1
            intervals.append((start, end))
            max_end = max(max_end, end)

    length = int(target_length) if target_length else max_end
    covered = 0
    last_end = 0
    for start, end in sorted(intervals):
        start = max(start, last_end + 1)
        if end >= start:
            covered += end - start + 1
            last_end = end

    if not identities:
        return None, histogram

    identities.sort()
    middle = len(identities) // 2
    median = identities[middle] if len(identities) % 2 else (identities[middle - 1] + identities[middle]) / 2
    below = sum(1 for value in identities if value < threshold)

    return {
        "Recruited reads": len(identities),
        "Mean identity": round(sum(identities) / len(identities), 3),
        "Median identity": round(median, 3),
        "Identity threshold": threshold,
        "Reads below threshold": below,
        "Percent below threshold": round(100 * below / len(identities), 3),
        "Target length": length,
        "Target bases covered": covered,
        "Target coverage %": round(100 * covered / length, 3) if length else None,
    }, histogram


def parse_recruitment_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    threshold = kwargs.get("threshold", 98)
    target_lengths = kwargs.get("target_lengths", {})
    paths = job.get("paths", {})
    results_dir = job.get("results_dir", "")

    path, system, plot = paths.get("rotated_blastn"), "C (rotated)", paths.get("rotated_recruitment_plot")
    if not path:
        path, system, plot = paths.get("blastn"), "B (after Pilon)", paths.get("recruitment_plot")
    if not path:
        logging.debug("BLAST recruitment table not found for %s", job.get("Assembly"))
        return None

    summary, histogram = summarize_blast_table(
        path=path, threshold=threshold, target_length=target_lengths.get(job.get("Assembly")),
    )
    if summary is None:
        logging.warning("BLAST recruitment table is empty: %s", path)
        return None

    identity = assembly_identity(job=job)
    return {
        "summary": {
            **identity,
            "Coordinate system": system,
            **summary,
            "BLAST file": os.path.relpath(path, results_dir),
            "OrganPipe recruitment plot": os.path.relpath(plot, results_dir) if plot else None,
        },
        "histogram": {**identity, "Identity bins": IDENTITY_BINS, "Counts": histogram},
    }


async def parse_recruitment_assembly(**kwargs):
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        return await asyncio.to_thread(
            parse_recruitment_assembly_sync,
            job=kwargs.get("job"),
            threshold=kwargs.get("threshold"),
            target_lengths=kwargs.get("target_lengths"),
        )


async def load_recruitment_data(**kwargs):
    """Return (recruitment summary dataframe, identity histograms)."""

    jobs = kwargs.get("jobs", [])
    threshold = float(kwargs.get("identity_threshold", 98))
    target_lengths = kwargs.get("target_lengths", {}) or {}
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))

    results = await gather_records(
        tasks=[
            parse_recruitment_assembly(job=job, threshold=threshold, target_lengths=target_lengths, semaphore=semaphore)
            for job in jobs
        ],
        source_name="BLAST recruitment table",
    )

    summary = pd.DataFrame([r["summary"] for r in results], columns=RECRUITMENT_COLUMNS)
    if len(summary) < len(jobs):
        logging.warning("BLAST recruitment tables missing for %d of %d assemblies; their recruitment is NA", len(jobs) - len(summary), len(jobs))
    histograms = [r["histogram"] for r in results]
    logging.info("Read recruitment tables: %d", len(summary))
    return summary, histograms
