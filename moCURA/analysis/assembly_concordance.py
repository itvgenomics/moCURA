"""Concordance among the assemblies of the same sample.

For each project the rotated genomes (``genbanks/{asm}.rotated.gb``) are
aligned together with MAFFT (``--adjustdirection``, so genomes rotated on the
minus strand are reverse-complemented). For every pair:

* identity = identical bases / columns where both have a base (gaps excluded);
* coverage = those columns / length of the longer genome, so a fragment that
  matches perfectly over 1 kb is not taken as concordant with a 16 kb genome;
* indels = gap events, counting a run of consecutive gap columns once.

Two assemblies are linked when identity >= ``group_identity_threshold`` and
coverage >= ``group_min_coverage``. Groups are the connected components of
these links; the largest group is the majority group.

Many assemblies of a sample are identical (the same genome reached from
different seeds). Only one copy of each distinct sequence is aligned; its
copies receive the same aligned row, which keeps MAFFT fast.
"""

import asyncio
import logging
import os

import numpy as np
import pandas as pd
from Bio import SeqIO

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity
from .run_marker_snp_analysis import build_mafft_mode_args, require_executable, run_subprocess

PAIR_COLUMNS = ["Project name", "Assembly A", "Assembly B", "Identity %", "Compared columns", "Coverage %", "Indels"]
MEMBER_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Genome length", "Reverse-complemented", "Group", "Group size", "Majority group", "In majority group",
    "Mean identity to majority %", "Alignment",
]


def pairwise_identity(**kwargs):
    """Identity, compared columns and indel events between two aligned sequences."""

    first = kwargs.get("first")
    second = kwargs.get("second")
    a = np.frombuffer(first.upper().encode("ascii"), dtype=np.uint8)
    b = np.frombuffer(second.upper().encode("ascii"), dtype=np.uint8)
    gap = ord("-")
    gap_a, gap_b = a == gap, b == gap
    informative = ~(gap_a & gap_b)
    both = ~gap_a & ~gap_b
    compared = int(both.sum())
    identical = int((both & (a == b)).sum())
    one_gap = (gap_a ^ gap_b)[informative]
    indels = int(one_gap[0]) + int((one_gap[1:] & ~one_gap[:-1]).sum()) if one_gap.size else 0
    longer = max(int((~gap_a).sum()), int((~gap_b).sum())) or 1
    return {
        "Identity %": round(100 * identical / compared, 4) if compared else None,
        "Compared columns": compared,
        "Coverage %": round(100 * compared / longer, 2),
        "Indels": indels,
    }


def concordance_groups(**kwargs):
    """Connected components of the pairs passing both thresholds."""

    names = list(kwargs.get("names", []))
    pairs = kwargs.get("pairs", [])
    identity = float(kwargs.get("identity_threshold", 99.5))
    coverage = float(kwargs.get("min_coverage", 95))
    parent = {name: name for name in names}

    def root(name):
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for pair in pairs:
        if (pair["Identity %"] or 0) >= identity and pair["Coverage %"] >= coverage:
            parent[root(pair["Assembly A"])] = root(pair["Assembly B"])

    components = {}
    for name in names:
        components.setdefault(root(name), []).append(name)
    ordered = sorted(components.values(), key=lambda members: (-len(members), sorted(members)[0]))
    return {name: index + 1 for index, members in enumerate(ordered) for name in members}


async def align_project(**kwargs):
    project = kwargs.get("project")
    jobs = kwargs.get("jobs", [])
    output_dir = kwargs.get("output_dir")
    mafft_binary = kwargs.get("mafft_binary")
    mafft_config = kwargs.get("mafft_config", {})
    semaphore = kwargs.get("semaphore")
    overwrite = bool(kwargs.get("overwrite", False))

    os.makedirs(os.path.join(output_dir, "alignments"), exist_ok=True)
    fasta_path = os.path.join(output_dir, "alignments", f"{project}_rotated_genomes.fasta")
    alignment_path = os.path.join(output_dir, "alignments", f"{project}_rotated_genomes.aligned.fasta")
    log_path = os.path.join(output_dir, "alignments", f"{project}_mafft.log")

    lengths, representatives, copies = {}, {}, {}
    with open(fasta_path, "w", encoding="utf-8") as handle:
        for job in jobs:
            record = next(SeqIO.parse(job["paths"]["rotated_genbank"], "genbank"), None)
            if record is None or not len(record.seq):
                continue
            sequence = str(record.seq).upper()
            lengths[job["Assembly"]] = len(sequence)
            if sequence in representatives:
                copies[job["Assembly"]] = representatives[sequence]
                continue
            representatives[sequence] = job["Assembly"]
            copies[job["Assembly"]] = job["Assembly"]
            handle.write(f">{job['Assembly']}\n{sequence}\n")

    if len(lengths) < 2:
        return None
    if len(representatives) < 2:
        only = next(iter(representatives))
        with open(alignment_path, "w", encoding="utf-8") as handle:
            handle.write(f">{representatives[only]}\n{only}\n")
        return {"project": project, "alignment_path": alignment_path, "lengths": lengths, "copies": copies}
    if overwrite or not os.path.isfile(alignment_path) or os.path.getsize(alignment_path) == 0:
        command = [
            mafft_binary, *build_mafft_mode_args(mode=mafft_config.get("mode", "fftns2")), "--adjustdirection",
            "--thread", str(max(1, int(mafft_config.get("threads_per_job", 2)))),
            *[str(argument) for argument in mafft_config.get("extra_args", [])], fasta_path,
        ]
        await run_subprocess(command=command, stdout_path=alignment_path, stderr_path=log_path, semaphore=semaphore)
    return {"project": project, "alignment_path": alignment_path, "lengths": lengths, "copies": copies}


def concordance_from_alignment_sync(**kwargs):
    aligned = kwargs.get("aligned")
    jobs_by_name = kwargs.get("jobs_by_name")
    identity_threshold = kwargs.get("identity_threshold")
    min_coverage = kwargs.get("min_coverage")
    project = aligned["project"]

    aligned_rows, reversed_names = {}, set()
    for record in SeqIO.parse(aligned["alignment_path"], "fasta"):
        name = record.id
        if name.startswith("_R_"):
            name = name[3:]
            reversed_names.add(name)
        aligned_rows[name] = str(record.seq)

    copies = aligned.get("copies") or {name: name for name in aligned_rows}
    names = sorted(name for name in copies if copies[name] in aligned_rows)
    reversed_names = {name for name in names if copies[name] in reversed_names}
    cache = {}
    pairs = []
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            key = tuple(sorted((copies[first], copies[second])))
            if key not in cache:
                if key[0] == key[1]:
                    cache[key] = {"Identity %": 100.0, "Compared columns": aligned["lengths"][first], "Coverage %": 100.0, "Indels": 0}
                else:
                    cache[key] = pairwise_identity(first=aligned_rows[key[0]], second=aligned_rows[key[1]])
            pairs.append({"Project name": project, "Assembly A": first, "Assembly B": second, **cache[key]})

    groups = concordance_groups(names=names, pairs=pairs, identity_threshold=identity_threshold, min_coverage=min_coverage)
    sizes = pd.Series(groups).value_counts().to_dict()
    majority = min(groups.values()) if groups else None
    majority_members = {name for name, group in groups.items() if group == majority}

    members = []
    for name in names:
        identities = [
            pair["Identity %"] for pair in pairs
            if name in (pair["Assembly A"], pair["Assembly B"])
            and ({pair["Assembly A"], pair["Assembly B"]} - {name}) <= majority_members
            and pair["Identity %"] is not None
        ]
        members.append({
            **assembly_identity(job=jobs_by_name[name]),
            "Genome length": aligned["lengths"].get(name),
            "Reverse-complemented": name in reversed_names,
            "Group": groups[name],
            "Group size": sizes[groups[name]],
            "Majority group": majority,
            "In majority group": groups[name] == majority,
            "Mean identity to majority %": round(float(np.mean(identities)), 4) if identities else None,
            "Alignment": aligned["alignment_path"],
        })
    return pairs, members


async def run_assembly_concordance(**kwargs):
    """Return (pairwise dataframe, membership dataframe)."""

    jobs = [job for job in kwargs.get("jobs", []) if job.get("paths", {}).get("rotated_genbank")]
    output_dir = kwargs.get("output_dir")
    mafft_config = kwargs.get("mafft_config", {}) or {}
    max_sequences = int(kwargs.get("max_sequences", 150))
    empty = pd.DataFrame(columns=PAIR_COLUMNS), pd.DataFrame(columns=MEMBER_COLUMNS)

    by_project = {}
    for job in jobs:
        by_project.setdefault(job["Project name"], []).append(job)
    by_project = {project: items for project, items in by_project.items() if len(items) >= 2}
    if not by_project:
        logging.warning("Fewer than two rotated genomes per project; concordance is NA")
        return empty

    try:
        mafft_binary = require_executable(executable=mafft_config.get("binary", "mafft"))
    except Exception as error:
        logging.warning("MAFFT unavailable, concordance skipped: %s", error)
        return empty

    for project, items in by_project.items():
        if len(items) > max_sequences:
            logging.warning("%s has %d rotated genomes; only the first %d enter the concordance alignment", project, len(items), max_sequences)
            by_project[project] = items[:max_sequences]

    semaphore = asyncio.Semaphore(max(1, int(mafft_config.get("concurrency", 2))))
    aligned = await asyncio.gather(
        *[align_project(project=project, jobs=items, output_dir=output_dir, mafft_binary=mafft_binary, mafft_config=mafft_config,
                        semaphore=semaphore, overwrite=kwargs.get("overwrite", False)) for project, items in by_project.items()],
        return_exceptions=True,
    )

    jobs_by_name = {job["Assembly"]: job for job in jobs}
    pair_rows, member_rows = [], []
    for project, result in zip(by_project, aligned):
        if isinstance(result, Exception):
            logging.error("Concordance alignment failed for %s: %s", project, result)
            continue
        if result is None:
            continue
        pairs, members = await asyncio.to_thread(
            concordance_from_alignment_sync, aligned=result, jobs_by_name=jobs_by_name,
            identity_threshold=kwargs.get("group_identity_threshold", 99.5), min_coverage=kwargs.get("group_min_coverage", 95),
        )
        pair_rows.extend(pairs)
        member_rows.extend(members)

    members_df = pd.DataFrame(member_rows, columns=MEMBER_COLUMNS)
    logging.info("Assembly concordance: %d projects, %d assemblies, %d outside the majority group",
                 members_df["Project name"].nunique() if not members_df.empty else 0, len(members_df),
                 int((~members_df["In majority group"].astype(bool)).sum()) if not members_df.empty else 0)
    return pd.DataFrame(pair_rows, columns=PAIR_COLUMNS), members_df
