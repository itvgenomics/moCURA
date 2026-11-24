"""Locate OrganPipe outputs in both the older and the current directory layouts.

Older OrganPipe runs write ``results/{sample}/{step}/...``. Current runs add an
assembler level: ``results/{sample}/{step}/{assembler}/...``. Every helper in
this module accepts both layouts so that callers never need to know which one
produced the files.
"""

import functools
import logging
import os
import re

from ..standardization.standardized_gene_name import standardized_gene_name


ASSEMBLER_DIRECTORIES = ("novoplasty", "getorganelle", "mitohifi")

ASSEMBLY_NAME_PATTERN = (
    r"^(?P<prefix>[A-Za-z]+)_(?P<prefix_index>\d+)_{project}_"
    r"(?P<seed_order>\d+)-(?P<seed_name>.+)_(?P<kmer>\d+)_(?P<assembly_copy>\d+)$"
)


@functools.lru_cache(maxsize=None)
def directory_listing(path):
    """Cached set of names in a directory (slow network or WSL file systems)."""

    try:
        return frozenset(os.listdir(path))
    except OSError:
        return frozenset()


def is_assembler_directory(**kwargs):
    """Return True when a directory name is an OrganPipe assembler level."""

    name = str(kwargs.get("name", ""))
    return name.lower() in ASSEMBLER_DIRECTORIES


def step_directories(**kwargs):
    """Return existing directories for one OrganPipe step, old layout first."""

    return list(_step_directories(str(kwargs.get("project_dir")), str(kwargs.get("step"))))


@functools.lru_cache(maxsize=None)
def _step_directories(project_dir, step):
    directories = []

    if step not in directory_listing(project_dir):
        return tuple(directories)

    base_dir = os.path.join(str(project_dir), str(step))
    if os.path.isdir(base_dir):
        directories.append(base_dir)
        names = directory_listing(base_dir)
        for assembler in ASSEMBLER_DIRECTORIES:
            assembler_dir = os.path.join(base_dir, assembler)
            if assembler in names and os.path.isdir(assembler_dir):
                directories.append(assembler_dir)

    return tuple(directories)


def infer_organpipe_dir(**kwargs):
    """Infer the OrganPipe root from ``--results-dir``.

    The root is the parent of ``results/`` when ``workflow/reports/`` and
    ``benchmarks/`` are siblings of it. Returns None otherwise.
    """

    results_dir = kwargs.get("results_dir")
    if not results_dir:
        return None

    parent = os.path.dirname(os.path.abspath(str(results_dir)))
    has_reports = os.path.isdir(os.path.join(parent, "workflow", "reports"))
    has_benchmarks = os.path.isdir(os.path.join(parent, "benchmarks"))

    if has_reports and has_benchmarks:
        return parent

    return None


def parse_assembly_name(**kwargs):
    """Parse an OrganPipe assembly header such as ``CA_1_ITV38290_1-NADH..._20_1``."""

    name = str(kwargs.get("name", ""))
    project_name = str(kwargs.get("project_name", ""))

    if not name or not project_name:
        return None

    match = re.match(ASSEMBLY_NAME_PATTERN.format(project=re.escape(project_name)), name)
    if match is None:
        return None

    seed_order = int(match.group("seed_order"))
    seed_name = match.group("seed_name")
    kmer = int(match.group("kmer"))

    return {
        "Project name": project_name,
        "Seed order": seed_order,
        "Seed Input": standardized_gene_name(value=seed_name),
        "K-mer": kmer,
        "Assembly copy": int(match.group("assembly_copy")),
        "Assembly": name,
        "Assembly prefix": match.group("prefix"),
        "seed_directory": f"{seed_order}-{seed_name}_kmer{kmer}",
    }


def first_existing(**kwargs):
    """Return the first existing path from a list, or None."""

    for path in kwargs.get("paths", []):
        if path and os.path.basename(path) in directory_listing(os.path.dirname(path)):
            return path
    return None


def assembly_paths(**kwargs):
    """Resolve every OrganPipe file of one assembly in either layout."""

    project_dir = kwargs.get("project_dir")
    assembly = kwargs.get("assembly")
    seed_directory = kwargs.get("seed_directory")

    def candidates(step, *parts):
        return [os.path.join(directory, *parts) for directory in step_directories(project_dir=project_dir, step=step)]

    images = lambda suffix: first_existing(paths=candidates("images", seed_directory, f"{assembly}{suffix}"))

    return {
        "mitos2_dir": first_existing(paths=candidates("mitos2", seed_directory, assembly)),
        "pilon_dir": first_existing(paths=candidates("pilon", assembly)),
        "genbank": first_existing(paths=candidates("genbanks", f"{assembly}.gb")),
        "rotated_genbank": first_existing(paths=candidates("genbanks", f"{assembly}.rotated.gb")),
        "depth": images(".depth"),
        "rotated_depth": images(".rotated.depth"),
        "blastn": images(".blastn.out"),
        "rotated_blastn": images(".rotated.blastn.out"),
        "rotated_bam": images(".rotated_mapping.bam"),
        "depth_plot": images(".depth.png"),
        "rotated_depth_plot": images(".rotated.depth.png"),
        "recruitment_plot": images("_recruitment_plot.png"),
        "rotated_recruitment_plot": images(".rotated_recruitment_plot.png"),
        "nhmmer_table": first_existing(paths=candidates("nhmmer", seed_directory, assembly, "intergenes_filter.tblout.out")),
    }


def find_organpipe_assemblies(**kwargs):
    """List every assembly produced by OrganPipe under ``results_dir``.

    Assemblies are discovered from Pilon run folders, MITOS2 run folders and
    GenBank files, so a missing step does not hide an assembly. ``allowed_keys``
    (project, seed, K-mer) restricts the result, as in the GenBank loader.
    """

    results_dir = kwargs.get("results_dir")
    allowed_keys = kwargs.get("allowed_keys")
    assemblies = {}

    if not results_dir or not os.path.isdir(results_dir):
        logging.warning("Results directory does not exist: %s", results_dir)
        return []

    for project_name in sorted(os.listdir(results_dir)):
        project_dir = os.path.join(results_dir, project_name)
        if not os.path.isdir(project_dir):
            continue

        names = set()
        for pilon_dir in step_directories(project_dir=project_dir, step="pilon"):
            names.update(name for name in directory_listing(pilon_dir) if "." not in name)
        for mitos_dir in step_directories(project_dir=project_dir, step="mitos2"):
            for seed_dir in directory_listing(mitos_dir):
                if "_kmer" in seed_dir and not is_assembler_directory(name=seed_dir):
                    names.update(name for name in directory_listing(os.path.join(mitos_dir, seed_dir)) if "." not in name)
        for genbank_dir in step_directories(project_dir=project_dir, step="genbanks"):
            for file_name in directory_listing(genbank_dir):
                if file_name.endswith(".gb") and not file_name.endswith(".rotated.gb"):
                    names.add(file_name[: -len(".gb")])

        for name in sorted(names):
            if is_assembler_directory(name=name):
                continue
            metadata = parse_assembly_name(name=name, project_name=project_name)
            if metadata is None:
                continue
            key = (metadata["Project name"], metadata["Seed Input"], metadata["K-mer"])
            if allowed_keys is not None and key not in allowed_keys:
                continue
            assemblies[name] = {
                **metadata,
                "project_dir": project_dir,
                "results_dir": results_dir,
                "paths": assembly_paths(
                    project_dir=project_dir,
                    assembly=name,
                    seed_directory=metadata["seed_directory"],
                ),
            }

    return [assemblies[name] for name in sorted(assemblies, key=lambda n: (
        assemblies[n]["Project name"], assemblies[n]["Seed order"], assemblies[n]["K-mer"], assemblies[n]["Assembly copy"], n
    ))]


ASSEMBLY_ID_COLUMNS = ["Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly"]


def assembly_identity(**kwargs):
    """Return the identification columns shared by every Phase 1 table."""

    job = kwargs.get("job", {})
    return {column: job.get(column) for column in ASSEMBLY_ID_COLUMNS}
