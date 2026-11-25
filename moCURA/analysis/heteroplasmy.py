"""Candidate heteroplasmic sites from the rotated BAM of each assembly.

NOVOPlasty's heteroplasmy output (MAF) is empty in OrganPipe, so the minor
allele frequency is computed here from a pileup of the rotated BAM (or the BAM
given by ``bam_template``):

* depth: bases of reads that are mapped, primary, not duplicates and with
  mapping quality >= ``min_mapping_quality``; bases below ``min_base_quality``
  are skipped when the BAM stores base qualities (OrganPipe BAMs often do not);
* a site is a candidate when depth >= ``min_depth``, the second most frequent
  base has >= ``min_minor_reads`` reads and its frequency is >= ``min_frequency``.

Each candidate gets a confidence:

* low when it lies within ``edge_exclusion`` bp of the contig ends (reads are
  clipped there on a linear copy of a circular genome), when it has more than
  ``max_cluster_sites`` candidates within ``cluster_window`` bp (typical of
  misaligned repeats or NUMTs), when the minor base is seen on one strand only
  (``require_both_strands``) or when it falls inside a TRF tandem repeat;
* high otherwise.

The BAMs of OrganPipe hold the Assembled_reads of the same assembly, which
under-represent reads that differ from it: frequencies are a lower bound and
absence of sites is not proof of homoplasmy.

Indexes are written to ``index_dir`` (inside --output-dir); input folders are
never modified.
"""

import asyncio
import logging
import os

import numpy as np
import pandas as pd
import pysam
from Bio import SeqIO

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity
from ..standardization.standardized_marker_name import standardized_marker_name
from .junction_support import resolve_bam


BASES = "ACGT"
SITE_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Position", "Region", "Depth", "Major base", "Minor base", "Major reads", "Minor reads",
    "Minor frequency", "Minor reads forward", "Minor reads reverse", "Confidence", "Reason",
]
SUMMARY_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "BAM source", "Base qualities", "Median depth", "Positions tested", "Candidate sites",
    "High-confidence sites", "Highest minor frequency", "Sites in protein-coding genes", "Regions",
]


def genome_regions(**kwargs):
    """List of (start, end, marker) of annotated features, 1-based inclusive."""

    path = kwargs.get("path")
    regions = []
    if not path or not os.path.isfile(path):
        return regions
    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return regions
    for feature in record.features:
        if feature.type not in ("CDS", "rRNA", "tRNA", "D-loop", "misc_feature"):
            continue
        marker = standardized_marker_name(feature_type=feature.type, qualifiers=feature.qualifiers)
        if not marker:
            marker = "control region" if feature.type == "D-loop" else None
        if not marker:
            continue
        for part in feature.location.parts:
            regions.append((int(part.start) + 1, int(part.end), marker, feature.type))
    return regions


def region_of(position, regions):
    names = [marker for start, end, marker, _ in regions if start <= position <= end]
    return ", ".join(dict.fromkeys(names)) if names else "intergenic"


def has_base_qualities(handle):
    """True when the first mapped read carries base qualities (``*`` in the BAM gives None)."""

    for read in handle.fetch(until_eof=True):
        if not read.is_unmapped:
            return read.query_qualities is not None
    return False


def strand_counts(handle, contig, position, base, min_mapping_quality, min_base_quality):
    """Reads with ``base`` at 0-based ``position`` on each strand."""

    forward = reverse = 0
    for column in handle.pileup(contig, position, position + 1, truncate=True, min_base_quality=min_base_quality,
                                min_mapping_quality=min_mapping_quality, ignore_orphans=False, stepper="all", max_depth=1000000):
        for read in column.pileups:
            if read.is_del or read.is_refskip or read.query_position is None:
                continue
            alignment = read.alignment
            if alignment.is_secondary or alignment.is_supplementary or alignment.is_duplicate or alignment.is_qcfail:
                continue
            if alignment.query_sequence[read.query_position].upper() == base:
                if alignment.is_reverse:
                    reverse += 1
                else:
                    forward += 1
    return forward, reverse


def heteroplasmy_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    settings = kwargs.get("settings", {}) or {}
    index_dir = kwargs.get("index_dir")
    repeats = kwargs.get("repeats", []) or []
    identity = assembly_identity(job=job)
    bam_path, source = resolve_bam(job=job, bam_template=settings.get("bam_template"))
    if not bam_path or not os.path.isfile(bam_path):
        return None

    min_depth = int(settings.get("min_depth", 20))
    min_minor_reads = int(settings.get("min_minor_reads", 3))
    min_frequency = float(settings.get("min_frequency", 0.10))
    min_mapping_quality = int(settings.get("min_mapping_quality", 20))
    min_base_quality = int(settings.get("min_base_quality", 20))
    edge = int(settings.get("edge_exclusion", 50))
    window = int(settings.get("cluster_window", 20))
    max_cluster = int(settings.get("max_cluster_sites", 2))
    both_strands = bool(settings.get("require_both_strands", True))

    os.makedirs(index_dir, exist_ok=True, mode=0o755)
    index_path = os.path.join(index_dir, f"{os.path.basename(bam_path)}.bai")
    if not os.path.isfile(index_path) or os.path.getmtime(index_path) < os.path.getmtime(bam_path):
        pysam.index(bam_path, index_path)
        # htslib warns when the index looks older than the BAM (clock skew between file systems).
        stamp = max(os.path.getmtime(bam_path) + 1, os.path.getmtime(index_path))
        os.utime(index_path, (stamp, stamp))

    with pysam.AlignmentFile(bam_path, "rb", index_filename=index_path) as handle:
        if not handle.references:
            return None
        contig, length = handle.references[0], handle.lengths[0]
        qualities = has_base_qualities(handle)
        base_quality = min_base_quality if qualities else 0

        def keep(read):
            return (not read.is_unmapped and not read.is_secondary and not read.is_supplementary
                    and not read.is_duplicate and not read.is_qcfail and read.mapping_quality >= min_mapping_quality)

        counts = np.array(handle.count_coverage(contig, 0, length, quality_threshold=base_quality, read_callback=keep))
        depth = counts.sum(axis=0)
        order = np.argsort(counts, axis=0)
        major_index, minor_index = order[-1], order[-2]
        columns = np.arange(length)
        major = counts[major_index, columns]
        minor = counts[minor_index, columns]
        frequency = np.divide(minor, depth, out=np.zeros(length, dtype=float), where=depth > 0)
        candidates = np.where((depth >= min_depth) & (minor >= min_minor_reads) & (frequency >= min_frequency))[0]

        regions = genome_regions(path=job.get("paths", {}).get("rotated_genbank"))
        sites = []
        for position in candidates:
            minor_base = BASES[minor_index[position]]
            reasons = []
            if position < edge or position >= length - edge:
                reasons.append(f"within {edge} bp of the contig ends")
            neighbours = int(((candidates >= position - window) & (candidates <= position + window)).sum()) - 1
            if neighbours >= max_cluster:
                reasons.append(f"{neighbours} other candidate sites within {window} bp")
            forward, reverse = strand_counts(handle, contig, int(position), minor_base, min_mapping_quality, base_quality)
            if both_strands and (forward == 0 or reverse == 0):
                reasons.append("minor base on one strand only")
            one_based = int(position) + 1
            if any(start <= one_based <= end for start, end in repeats):
                reasons.append("inside a tandem repeat")
            sites.append({
                **identity,
                "Position": one_based,
                "Region": region_of(one_based, regions),
                "Depth": int(depth[position]),
                "Major base": BASES[major_index[position]],
                "Minor base": minor_base,
                "Major reads": int(major[position]),
                "Minor reads": int(minor[position]),
                "Minor frequency": round(float(frequency[position]), 4),
                "Minor reads forward": forward,
                "Minor reads reverse": reverse,
                "Confidence": "low" if reasons else "high",
                "Reason": "; ".join(reasons),
            })

    high = [site for site in sites if site["Confidence"] == "high"]
    coding = {marker for start, end, marker, kind in regions if kind == "CDS"}
    summary = {
        **identity,
        "BAM source": source,
        "Base qualities": "used" if qualities else "absent in BAM (not filtered)",
        "Median depth": float(np.median(depth)) if length else None,
        "Positions tested": int((depth >= min_depth).sum()),
        "Candidate sites": len(sites),
        "High-confidence sites": len(high),
        "Highest minor frequency": max((site["Minor frequency"] for site in high), default=None),
        "Sites in protein-coding genes": sum(1 for site in high if any(name in coding for name in site["Region"].split(", "))),
        "Regions": ", ".join(dict.fromkeys(site["Region"] for site in high)),
    }
    return summary, sites


def repeat_intervals(**kwargs):
    """(start, end) of the TRF repeats of every assembly, keyed by (project, seed, K-mer, copy)."""

    dataframe = kwargs.get("dataframe")
    intervals = {}
    if dataframe is None or dataframe.empty:
        return intervals
    for _, row in dataframe.iterrows():
        try:
            key = (str(row["Project name"]), str(row["Seed Input"]), int(row["K-mer"]), int(row["Assembly copy"]))
            intervals.setdefault(key, []).append((int(row["Start"]), int(row["End"])))
        except (KeyError, TypeError, ValueError):
            continue
    return intervals


async def heteroplasmy_assembly(**kwargs):
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        try:
            return await asyncio.to_thread(heteroplasmy_assembly_sync, **kwargs)
        except (OSError, ValueError) as error:
            logging.warning("Heteroplasmy scan failed for %s: %s", kwargs.get("job", {}).get("Assembly"), error)
            return None


async def load_heteroplasmy(**kwargs):
    """Return (summary dataframe, sites dataframe)."""

    jobs = kwargs.get("jobs", [])
    settings = kwargs.get("settings", {}) or {}
    concurrency = int(kwargs.get("concurrency", 8))
    index_dir = kwargs.get("index_dir")
    repeats = repeat_intervals(dataframe=kwargs.get("trf_repeats_dataframe"))
    semaphore = asyncio.Semaphore(max(1, concurrency))

    def key(job):
        try:
            return (str(job["Project name"]), str(job["Seed Input"]), int(job["K-mer"]), int(job["Assembly copy"]))
        except (KeyError, TypeError, ValueError):
            return None

    results = await asyncio.gather(*[
        heteroplasmy_assembly(job=job, settings=settings, index_dir=index_dir, semaphore=semaphore, repeats=repeats.get(key(job), []))
        for job in jobs
    ])
    summaries, sites = [], []
    for result in results:
        if result is None:
            continue
        summaries.append(result[0])
        sites.extend(result[1])
    missing = sum(1 for result in results if result is None)
    if missing:
        logging.warning("Heteroplasmy: %d assemblies without a BAM were skipped", missing)
    logging.info("Heteroplasmy: %d assemblies scanned, %d candidate sites (%d high confidence)",
                 len(summaries), len(sites), sum(1 for site in sites if site["Confidence"] == "high"))
    return pd.DataFrame(summaries, columns=SUMMARY_COLUMNS), pd.DataFrame(sites, columns=SITE_COLUMNS)
