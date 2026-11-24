"""Read support for the circularization junction of each assembly.

NOVOPlasty closes a circular genome by joining the end of the contig to its
start. OrganPipe then rotates the polished genome (``genbanks/{asm}.gb``) so it
starts at rrnS (``genbanks/{asm}.rotated.gb``) and maps the reads again on the
rotated sequence (``images/{seed}_kmer{k}/{asm}.rotated_mapping.bam``). In the
rotated sequence the original junction is an internal position, so reads that
cross it can be counted:

* spanning reads: one alignment covering at least ``min_flank`` bases on each
  side of the junction;
* flanking pairs: proper pairs with one mate ending before the junction and the
  other starting after it.

When NOVOPlasty already wrote the genome starting at rrnS (it does so when run
with a reference), the original junction coincides with (or lies within
``min_flank`` bases of) the rotated origin, the two ends of the linear BAM. There the evidence is read from the same mapping:

* spanning reads: reads that bwa-mem split into a part ending at the last base
  and a part starting at the first base (primary + supplementary alignment),
  each with at least ``min_flank`` bases;
* flanking pairs: forward reads in the last ``max_insert_size`` bases whose
  reverse mate maps in the first ``max_insert_size`` bases.

The BAM holds the ``Assembled_reads`` NOVOPlasty recruited for that same
assembly, so support tends to be optimistic. ``bam_template`` in ``config.yml``
already accepts another BAM (for example raw reads mapped on the rotated
genome) for when such a mapping exists.
"""

import asyncio
import logging
import os

import pandas as pd
from Bio import SeqIO
from Bio.Seq import Seq

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity

JUNCTION_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Genome length", "Orientation", "Junction position", "Junction mode", "BAM source", "Reads in BAM",
    "Reads at junction", "Spanning reads", "Flanking pairs", "Spanning fraction", "Junction support", "Note",
]


def read_sequence(**kwargs):
    path = kwargs.get("path")
    if not path or not os.path.isfile(path):
        return None
    record = next(SeqIO.parse(path, "genbank"), None)
    return str(record.seq).upper() if record is not None else None


def junction_position(**kwargs):
    """Boundary in the rotated sequence where the original contig starts.

    Returns ``{"position": J, "orientation": "+"|"-"}``; the junction lies
    between rotated bases J and J + 1 (1-based), i.e. 0-based index J is the
    first base after it. ``None`` when the original start is not found.
    """

    original = (kwargs.get("original") or "").upper()
    rotated = (kwargs.get("rotated") or "").upper()
    k = int(kwargs.get("k", 60))
    if not original or not rotated or len(original) < k:
        return None

    doubled = rotated + rotated
    length = len(rotated)
    start = doubled.find(original[:k])
    if 0 <= start < length:
        return {"position": start, "orientation": "+"}

    reverse = str(Seq(original[:k]).reverse_complement())
    start = doubled.find(reverse)
    if 0 <= start < length:
        return {"position": (start + k) % length, "orientation": "-"}
    return None


def count_origin_support(**kwargs):
    """Junction on the rotated origin: split reads and pairs wrapping around the ends."""

    import pysam

    bam_path = kwargs.get("bam_path")
    flank = int(kwargs.get("min_flank", 20))
    min_mapq = int(kwargs.get("min_mapping_quality", 20))
    max_insert = int(kwargs.get("max_insert_size", 1000))
    edge = 5

    counts = {"Reads in BAM": 0, "Reads at junction": 0, "Spanning reads": 0, "Flanking pairs": 0}
    pieces = {}
    with pysam.AlignmentFile(bam_path, "rb", check_sq=False) as handle:
        length = handle.lengths[0] if handle.lengths else 0
        for read in handle.fetch(until_eof=True):
            if read.is_unmapped or read.is_secondary or read.is_duplicate or read.reference_end is None:
                continue
            if not read.is_supplementary:
                counts["Reads in BAM"] += 1
            if read.mapping_quality < min_mapq:
                continue
            start, end = read.reference_start, read.reference_end
            if end - start >= flank and (end >= length - edge or start <= edge):
                key = (read.query_name, read.is_read1)
                pieces.setdefault(key, [False, False])
                if end >= length - edge:
                    pieces[key][0] = True
                if start <= edge:
                    pieces[key][1] = True
            if read.is_supplementary:
                continue
            if start == 0 or end == length:
                counts["Reads at junction"] += 1
            if (
                read.is_paired and not read.mate_is_unmapped and read.next_reference_id == read.reference_id
                and not read.is_reverse and read.mate_is_reverse
                and start >= length - max_insert and read.next_reference_start <= max_insert
            ):
                counts["Flanking pairs"] += 1
    # Reads at junction: primary alignments touching either end of the linear sequence.
    counts["Spanning reads"] = sum(1 for at_end, at_start in pieces.values() if at_end and at_start)
    return counts


def count_junction_support(**kwargs):
    """Count reads crossing a junction at 0-based boundary ``junction``."""

    import pysam

    bam_path = kwargs.get("bam_path")
    junction = int(kwargs.get("junction"))
    flank = int(kwargs.get("min_flank", 20))
    min_mapq = int(kwargs.get("min_mapping_quality", 20))
    if junction == 0:
        return count_origin_support(**kwargs)

    counts = {"Reads in BAM": 0, "Reads at junction": 0, "Spanning reads": 0, "Flanking pairs": 0}
    with pysam.AlignmentFile(bam_path, "rb", check_sq=False) as handle:
        for read in handle.fetch(until_eof=True):
            if read.is_unmapped or read.is_secondary or read.is_supplementary or read.is_duplicate:
                continue
            counts["Reads in BAM"] += 1
            if read.mapping_quality < min_mapq:
                continue
            start, end = read.reference_start, read.reference_end
            if end is None:
                continue
            if start < junction < end:
                counts["Reads at junction"] += 1
                if start <= junction - flank and end >= junction + flank:
                    counts["Spanning reads"] += 1
            if (
                read.is_proper_pair
                and read.template_length > 0
                and read.next_reference_id == read.reference_id
                and end <= junction <= read.next_reference_start
            ):
                counts["Flanking pairs"] += 1
    return counts


def classify_junction(**kwargs):
    spanning = kwargs.get("spanning")
    pairs = kwargs.get("pairs")
    supported = int(kwargs.get("supported_min_spanning_reads", 10))
    weak_spanning = int(kwargs.get("weak_min_spanning_reads", 3))
    weak_pairs = int(kwargs.get("weak_min_flanking_pairs", 3))
    if spanning is None:
        return "NA"
    if spanning >= supported:
        return "Supported"
    if spanning >= weak_spanning or (pairs or 0) >= weak_pairs:
        return "Weak"
    return "Unsupported"


def resolve_bam(**kwargs):
    job = kwargs.get("job", {})
    template = kwargs.get("bam_template")
    if template:
        path = str(template).format(
            project=job.get("Project name"), assembly=job.get("Assembly"),
            results_dir=job.get("results_dir", ""), seed_directory=job.get("seed_directory", ""),
        )
        return (path if os.path.isfile(path) else None), "Custom BAM (bam_template)"
    return job.get("paths", {}).get("rotated_bam"), "Assembled_reads (OrganPipe rotated BAM)"


def junction_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    settings = kwargs.get("settings", {})
    circular = kwargs.get("circular")
    paths = job.get("paths", {})
    record = {**assembly_identity(job=job)}
    record.update({column: None for column in JUNCTION_COLUMNS if column not in record})
    record["Junction support"] = "NA"

    bam_path, source = resolve_bam(job=job, bam_template=settings.get("bam_template"))
    record["BAM source"] = source
    if circular is False:
        record["Note"] = "Assembly not circularized: there is no circularization junction."
        return record

    rotated = read_sequence(path=paths.get("rotated_genbank"))
    original = read_sequence(path=paths.get("genbank"))
    if rotated is None or original is None:
        record["Note"] = "Rotated or unrotated GenBank missing: junction position unknown."
        return record
    record["Genome length"] = len(rotated)

    located = junction_position(original=original, rotated=rotated)
    if located is None:
        record["Note"] = "Start of the original contig not found in the rotated genome."
        return record
    junction = located["position"]
    record["Orientation"] = located["orientation"]
    record["Junction position"] = junction
    # A junction closer than min_flank to either end cannot be spanned inside the linear
    # BAM; the reads crossing it come through the ends, so it is tested as an origin junction.
    flank = int(settings.get("min_flank", 20))
    near_origin = junction < flank or junction > len(rotated) - flank
    record["Junction mode"] = "Rotated origin (split reads and wrap-around pairs)" if near_origin else "Internal position"
    if not bam_path or not os.path.isfile(bam_path):
        record["Note"] = "BAM not found."
        return record

    counts = count_junction_support(
        bam_path=bam_path, junction=0 if near_origin else junction,
        min_flank=settings.get("min_flank", 20), min_mapping_quality=settings.get("min_mapping_quality", 20),
        max_insert_size=settings.get("max_insert_size", 1000),
    )
    record.update(counts)
    record["Spanning fraction"] = round(counts["Spanning reads"] / counts["Reads at junction"], 4) if counts["Reads at junction"] else None
    record["Junction support"] = classify_junction(
        spanning=counts["Spanning reads"], pairs=counts["Flanking pairs"],
        supported_min_spanning_reads=settings.get("supported_min_spanning_reads", 10),
        weak_min_spanning_reads=settings.get("weak_min_spanning_reads", 3),
        weak_min_flanking_pairs=settings.get("weak_min_flanking_pairs", 3),
    )
    return record


async def junction_assembly(**kwargs):
    async with kwargs.get("semaphore"):
        return await asyncio.to_thread(
            junction_assembly_sync, job=kwargs.get("job"), settings=kwargs.get("settings"), circular=kwargs.get("circular"),
        )


async def load_junction_support(**kwargs):
    """Return one row per assembly with the junction support class."""

    jobs = kwargs.get("jobs", [])
    settings = kwargs.get("settings", {}) or {}
    circular_lookup = kwargs.get("circular_lookup", {}) or {}
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))

    try:
        import pysam  # noqa: F401
    except ImportError:
        logging.warning("pysam is not installed; circularization junctions are NA")
        return pd.DataFrame(
            [{**assembly_identity(job=job), "Junction support": "NA", "Note": "pysam not installed."} for job in jobs],
            columns=JUNCTION_COLUMNS,
        )

    results = await asyncio.gather(
        *[
            junction_assembly(
                job=job, settings=settings, semaphore=semaphore,
                circular=circular_lookup.get((job["Project name"], job["Seed Input"], job["K-mer"])),
            )
            for job in jobs
        ],
        return_exceptions=True,
    )
    records = []
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            logging.error("Junction support failed for %s: %s", job.get("Assembly"), result)
            records.append({**assembly_identity(job=job), "Junction support": "NA", "Note": f"Error: {result}"})
            continue
        records.append(result)

    dataframe = pd.DataFrame(records, columns=JUNCTION_COLUMNS)
    missing_bam = int((dataframe["Note"] == "BAM not found.").sum())
    if missing_bam:
        logging.warning("Rotated BAM missing for %d of %d assemblies; their junction support is NA", missing_bam, len(jobs))
    logging.info("Junction support: %s", dataframe["Junction support"].value_counts().to_dict())
    return dataframe
