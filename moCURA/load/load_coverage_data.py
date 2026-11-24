"""Coverage profiles from ``samtools depth`` files and Pilon change positions.

* ``images/{seed}_kmer{k}/{asm}.rotated.depth`` is in rotated coordinates (C),
  the same system as the rotated GenBank, so it is drawn directly under the
  genome-structure track. ``samtools depth`` was run without ``-a``: positions
  with no reads are missing and are filled with zero here.
* When the rotated depth is missing (assemblies MITOS2 could not rotate),
  ``{asm}.depth`` is used instead. It is in pre-Pilon coordinates (A) and the
  ``Coordinate system`` column says so.
* ``pilon/{asm}/{asm}.changes`` lists each correction with its position before
  (A) and after (B) Pilon. Positions are moved to C with the rotation offset,
  the start of ``rrnS`` in ``genbanks/{asm}.gb``.
"""

import asyncio
import logging
import os
import re
import statistics

import pandas as pd
from Bio import SeqIO

from ..utils.gather_records import gather_records
from ..utils.read_text_async import read_text_file
from .organpipe_layout import assembly_identity


COVERAGE_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Coordinate system", "Genome length", "Positions without reads", "Mean depth", "Median depth",
    "Coefficient of variation", "Low-depth threshold", "Positions below threshold",
    "Percent below threshold", "Window size", "Lowest window start", "Lowest window end",
    "Lowest window mean depth", "Depth file", "OrganPipe depth plot",
]

CHANGE_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Position before Pilon", "Position after Pilon", "Rotated position", "Change type",
    "Reference", "Replacement", "Length change",
]

BREAK_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Break start before Pilon", "Break end before Pilon", "Rotated start", "Rotated end", "Pilon message",
]


def read_depth(**kwargs):
    """Read a samtools depth file into a zero-filled list of length ``length``."""

    path = kwargs.get("path")
    length = kwargs.get("length")
    values = {}

    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                values[int(parts[1])] = int(float(parts[2]))
            except ValueError:
                continue

    if not length:
        length = max(values) if values else 0

    return [values.get(position, 0) for position in range(1, length + 1)]


def coverage_metrics(**kwargs):
    """Per-position metrics and fixed-size window means."""

    depth = kwargs.get("depth", [])
    window = max(1, int(kwargs.get("window", 50)))
    threshold = float(kwargs.get("threshold", 10))

    if not depth:
        return None, []

    mean = sum(depth) / len(depth)
    sd = statistics.pstdev(depth) if len(depth) > 1 else 0.0
    windows = [sum(depth[i:i + window]) / len(depth[i:i + window]) for i in range(0, len(depth), window)]
    lowest = min(range(len(windows)), key=lambda i: windows[i])
    below = sum(1 for value in depth if value < threshold)

    metrics = {
        "Genome length": len(depth),
        "Positions without reads": sum(1 for value in depth if value == 0),
        "Mean depth": round(mean, 2),
        "Median depth": statistics.median(depth),
        "Coefficient of variation": round(sd / mean, 4) if mean else None,
        "Low-depth threshold": threshold,
        "Positions below threshold": below,
        "Percent below threshold": round(100 * below / len(depth), 3),
        "Window size": window,
        "Lowest window start": lowest * window + 1,
        "Lowest window end": min(len(depth), (lowest + 1) * window),
        "Lowest window mean depth": round(windows[lowest], 2),
    }

    return metrics, [round(value, 1) for value in windows]


def genbank_length_and_offset(**kwargs):
    """Return (sequence length, 0-based start of rrnS) from a GenBank file."""

    path = kwargs.get("path")
    if not path or not os.path.isfile(path):
        return None, None

    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return None, None

    offset = None
    for feature in record.features:
        if feature.type == "rRNA" and "rrnS" in str(feature.qualifiers.get("product", "")):
            offset = int(feature.location.start)
            break

    return len(record.seq), offset


def rotation_offset_from_sequences(**kwargs):
    """Find the rotation offset by locating the rotated start inside ``B + B``."""

    genbank = kwargs.get("genbank")
    rotated = kwargs.get("rotated")
    k = int(kwargs.get("k", 60))

    if not genbank or not rotated or not os.path.isfile(genbank) or not os.path.isfile(rotated):
        return None

    original = next(SeqIO.parse(genbank, "genbank"), None)
    turned = next(SeqIO.parse(rotated, "genbank"), None)
    if original is None or turned is None:
        return None

    sequence = str(original.seq).upper()
    position = (sequence + sequence).find(str(turned.seq).upper()[:k])
    return position if 0 <= position < len(sequence) else None


def parse_changes(**kwargs):
    """Parse a Pilon ``.changes`` file (``asm:posA asm_pilon:posB[-end] ref alt``)."""

    text = kwargs.get("text", "") or ""
    changes = []

    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        before = re.findall(r":(\d+)(?:-(\d+))?$", parts[0])
        after = re.findall(r":(\d+)(?:-(\d+))?$", parts[1])
        if not before or not after:
            continue
        reference = "" if parts[2] == "." else parts[2]
        replacement = "" if parts[3] == "." else parts[3]
        if not reference:
            change_type = "Insertion"
        elif not replacement:
            change_type = "Deletion"
        elif len(reference) == len(replacement):
            change_type = "Substitution"
        else:
            change_type = "Replacement"
        changes.append(
            {
                "Position before Pilon": int(before[0][0]),
                "Position after Pilon": int(after[0][0]),
                "Change type": change_type,
                "Reference": reference or ".",
                "Replacement": replacement or ".",
                "Length change": len(replacement) - len(reference),
            }
        )

    return changes


def parse_fix_breaks(**kwargs):
    """Unresolved local breaks reported by Pilon (``# fix break: ... NoSolution``)."""

    text = kwargs.get("text", "") or ""
    breaks = []

    for match in re.finditer(r"#\s*fix break:\s*\S+?:(\d+)-(\d+)\s+(.*NoSolution.*)$", text, flags=re.MULTILINE):
        breaks.append({"start": int(match.group(1)), "end": int(match.group(2)), "message": match.group(3).strip()})

    return breaks


def a_to_b(**kwargs):
    """Move a pre-Pilon position to the post-Pilon sequence using the changes list."""

    position = kwargs.get("position")
    changes = kwargs.get("changes", [])

    # Pilon inserts before the reported base, so a base at or after an indel moves by its length.
    shift = sum(change["Length change"] for change in changes if change["Position before Pilon"] <= position)
    return position + shift


def b_to_c(**kwargs):
    """Move a 1-based post-Pilon position to rotated coordinates."""

    position = kwargs.get("position")
    offset = kwargs.get("offset")
    length = kwargs.get("length")

    if position is None or offset is None or not length:
        return None

    return ((position - 1 - offset) % length) + 1


def parse_coverage_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    window = kwargs.get("window", 50)
    threshold = kwargs.get("threshold", 10)
    results_dir = job.get("results_dir", "")
    paths = job.get("paths", {})
    identity = assembly_identity(job=job)

    gb_length, offset = genbank_length_and_offset(path=paths.get("genbank"))
    if offset is None and paths.get("genbank") and paths.get("rotated_genbank"):
        offset = rotation_offset_from_sequences(genbank=paths["genbank"], rotated=paths["rotated_genbank"])
    rotated_length, _ = genbank_length_and_offset(path=paths.get("rotated_genbank"))

    record, windows = None, []
    depth_path = paths.get("rotated_depth")
    system, length, plot = "C (rotated)", rotated_length, paths.get("rotated_depth_plot")
    if not depth_path:
        depth_path, system, length, plot = paths.get("depth"), "A (before Pilon)", None, paths.get("depth_plot")

    if depth_path:
        depth = read_depth(path=depth_path, length=length)
        metrics, windows = coverage_metrics(depth=depth, window=window, threshold=threshold)
        if metrics:
            record = {
                **identity,
                "Coordinate system": system,
                **metrics,
                "Depth file": os.path.relpath(depth_path, results_dir),
                "OrganPipe depth plot": os.path.relpath(plot, results_dir) if plot else None,
            }
    else:
        logging.debug("Depth file not found for %s", job.get("Assembly"))

    changes = []
    breaks = []
    pilon_dir = paths.get("pilon_dir")
    if pilon_dir:
        changes_path = os.path.join(pilon_dir, f"{job.get('Assembly')}.changes")
        if os.path.isfile(changes_path):
            changes = parse_changes(text=read_text_file(file_path=changes_path))
        log_path = os.path.join(pilon_dir, "pilon.log")
        if os.path.isfile(log_path):
            breaks = parse_fix_breaks(text=read_text_file(file_path=log_path))

    length_b = gb_length or rotated_length
    change_rows = [
        {**identity, **change, "Rotated position": b_to_c(position=change["Position after Pilon"], offset=offset, length=length_b)}
        for change in changes
    ]
    break_rows = []
    for item in breaks:
        start_c = b_to_c(position=a_to_b(position=item["start"], changes=changes), offset=offset, length=length_b)
        end_c = b_to_c(position=a_to_b(position=item["end"], changes=changes), offset=offset, length=length_b)
        break_rows.append({
            **identity,
            "Break start before Pilon": item["start"],
            "Break end before Pilon": item["end"],
            "Rotated start": start_c,
            "Rotated end": end_c,
            "Pilon message": item["message"],
        })

    return {
        "coverage": record,
        "windows": {**identity, "Window size": window, "Coordinate system": system, "Windows": windows} if record else None,
        "changes": change_rows,
        "breaks": break_rows,
    }


async def parse_coverage_assembly(**kwargs):
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        return await asyncio.to_thread(
            parse_coverage_assembly_sync,
            job=kwargs.get("job"),
            window=kwargs.get("window"),
            threshold=kwargs.get("threshold"),
        )


async def load_coverage_data(**kwargs):
    """Return coverage metrics, window profiles, Pilon changes and Pilon breaks."""

    jobs = kwargs.get("jobs", [])
    window = int(kwargs.get("window_size", 50))
    threshold = float(kwargs.get("low_depth_threshold", 10))
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))

    results = await gather_records(
        tasks=[parse_coverage_assembly(job=job, window=window, threshold=threshold, semaphore=semaphore) for job in jobs],
        source_name="coverage files",
    )

    coverage = pd.DataFrame([r["coverage"] for r in results if r["coverage"]], columns=COVERAGE_COLUMNS)
    if len(coverage) < len(jobs):
        logging.warning("Depth files missing for %d of %d assemblies; their coverage is NA", len(jobs) - len(coverage), len(jobs))
    windows = [r["windows"] for r in results if r["windows"]]
    changes = pd.DataFrame([row for r in results for row in r["changes"]], columns=CHANGE_COLUMNS)
    breaks = pd.DataFrame([row for r in results for row in r["breaks"]], columns=BREAK_COLUMNS)

    logging.info("Coverage profiles: %d; Pilon changes: %d; Pilon unresolved breaks: %d", len(coverage), len(changes), len(breaks))
    return coverage, windows, changes, breaks
