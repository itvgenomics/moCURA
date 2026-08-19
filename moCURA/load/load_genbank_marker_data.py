import asyncio
import logging
import os
import re

import pandas as pd
from Bio import SeqIO

from ..standardization.standardized_gene_name import standardized_gene_name
from ..standardization.standardized_marker_name import (
    first_qualifier_value,
    standardized_marker_name,
)
from ..utils.gather_records import gather_records


GENBANK_FILE_COLUMNS = [
    "Project name",
    "Seed order",
    "Seed Input",
    "K-mer",
    "Assembly copy",
    "GenBank file",
    "Relative path",
    "Record ID",
    "Record length",
    "Feature count",
]

GENBANK_MARKER_COLUMNS = [
    "Project name",
    "Seed order",
    "Seed Input",
    "K-mer",
    "Assembly copy",
    "GenBank file",
    "Relative path",
    "Record ID",
    "Record length",
    "Feature type",
    "Marker",
    "Raw marker",
    "Start",
    "End",
    "Strand",
    "Marker length",
    "Location parts",
    "Location",
]


def parse_rotated_genbank_filename(**kwargs):
    """Parse project, seed, K-mer, and assembly copy from a rotated file."""

    file_name = kwargs.get("file_name")
    project_name = kwargs.get("project_name")
    suffix = str(kwargs.get("suffix", ".rotated.gb"))

    if not file_name or not project_name:
        return None

    if not str(file_name).endswith(suffix):
        return None

    stem = str(file_name)[:-len(suffix)]

    match = re.match(
        rf"^.+?_{re.escape(str(project_name))}_"
        rf"(?P<seed_order>\d+)-"
        rf"(?P<seed_name>.+)_"
        rf"(?P<kmer>\d+)_"
        rf"(?P<assembly_copy>\d+)$",
        stem,
    )

    if match is None:
        return None

    return {
        "Project name": str(project_name),
        "Seed order": int(match.group("seed_order")),
        "Seed Input": standardized_gene_name(value=match.group("seed_name")),
        "K-mer": int(match.group("kmer")),
        "Assembly copy": int(match.group("assembly_copy")),
    }


def build_allowed_assembly_keys(**kwargs):
    """Create normalized keys used to filter rotated GenBank files."""

    dataframe = kwargs.get("dataframe")

    if dataframe is None or dataframe.empty:
        return None

    required_columns = {
        "Project name",
        "Seed Input",
        "K-mer",
    }

    if not required_columns.issubset(dataframe.columns):
        return None

    allowed_keys = set()

    for _, row in dataframe.iterrows():
        project_name = str(row["Project name"])
        seed_input = standardized_gene_name(
            value=row["Seed Input"]
        )
        kmer = pd.to_numeric(
            row["K-mer"],
            errors="coerce",
        )

        if pd.isna(kmer):
            continue

        allowed_keys.add(
            (
                project_name,
                seed_input,
                int(kmer),
            )
        )

    return allowed_keys


def find_rotated_genbank_jobs(**kwargs):
    """Find rotated GenBank files and map them to assembly metadata."""

    results_dir = kwargs.get("results_dir", "example_results")
    folder_name = str(kwargs.get("folder_name", "genbanks"))
    suffix = str(kwargs.get("suffix", ".rotated.gb"))
    allowed_keys = kwargs.get("allowed_keys")

    jobs = []

    if not os.path.isdir(results_dir):
        return jobs

    for project_name in sorted(os.listdir(results_dir)):
        project_dir = os.path.join(
            results_dir,
            project_name,
        )

        if not os.path.isdir(project_dir):
            continue

        genbank_dir = os.path.join(
            project_dir,
            folder_name,
        )

        if not os.path.isdir(genbank_dir):
            continue

        for file_name in sorted(os.listdir(genbank_dir)):
            if not file_name.endswith(suffix):
                continue

            metadata = parse_rotated_genbank_filename(
                file_name=file_name,
                project_name=project_name,
                suffix=suffix,
            )

            if metadata is None:
                logging.warning(
                    "Skipping unrecognized rotated GenBank filename: %s",
                    os.path.join(genbank_dir, file_name),
                )
                continue

            assembly_key = (
                metadata["Project name"],
                metadata["Seed Input"],
                metadata["K-mer"],
            )

            if allowed_keys is not None and assembly_key not in allowed_keys:
                continue

            genbank_file = os.path.join(
                genbank_dir,
                file_name,
            )

            jobs.append(
                {
                    **metadata,
                    "genbank_file": genbank_file,
                    "relative_path": os.path.relpath(
                        genbank_file,
                        results_dir,
                    ),
                }
            )

    return jobs


def feature_strand(**kwargs):
    """Return a readable strand symbol from a Biopython feature."""

    feature = kwargs.get("feature")
    strand = getattr(feature.location, "strand", None)

    if strand == 1:
        return "+"

    if strand == -1:
        return "-"

    return "."


def parse_genbank_file_sync(**kwargs):
    job = kwargs.get("job", {})
    feature_types = set(kwargs.get("feature_types", []))
    include_unknown_markers = bool(kwargs.get("include_unknown_markers", False))

    genbank_file = job.get("genbank_file")

    if not genbank_file or not os.path.isfile(genbank_file):
        raise FileNotFoundError(f"Rotated GenBank file not found: {genbank_file}")

    file_records = []
    marker_records = []

    for record in SeqIO.parse(genbank_file, "genbank"):
        parsed_feature_count = 0

        for feature in record.features:
            if feature.type not in feature_types:
                continue

            marker_name = standardized_marker_name(
                feature_type=feature.type,
                qualifiers=feature.qualifiers,
            )

            if marker_name is None and not include_unknown_markers:
                continue

            raw_marker = " | ".join(
                value
                for value in (
                    first_qualifier_value(
                        qualifiers=feature.qualifiers,
                        qualifier_name="gene",
                    ),
                    first_qualifier_value(
                        qualifiers=feature.qualifiers,
                        qualifier_name="product",
                    ),
                    first_qualifier_value(
                        qualifiers=feature.qualifiers,
                        qualifier_name="label",
                    ),
                    first_qualifier_value(
                        qualifiers=feature.qualifiers,
                        qualifier_name="note",
                    ),
                )
                if value
            )

            if marker_name is None:
                marker_name = raw_marker or feature.type

            try:
                start = int(feature.location.start) + 1
                end = int(feature.location.end)
                marker_length = len(feature.location)
            except (TypeError, ValueError):
                start = None
                end = None
                marker_length = None

            location_parts = getattr(
                feature.location,
                "parts",
                None,
            )

            marker_records.append(
                {
                    "Project name": job["Project name"],
                    "Seed order": job["Seed order"],
                    "Seed Input": job["Seed Input"],
                    "K-mer": job["K-mer"],
                    "Assembly copy": job["Assembly copy"],
                    "GenBank file": os.path.basename(genbank_file),
                    "Relative path": job["relative_path"],
                    "Record ID": record.id,
                    "Record length": len(record.seq),
                    "Feature type": feature.type,
                    "Marker": marker_name,
                    "Raw marker": raw_marker,
                    "Start": start,
                    "End": end,
                    "Strand": feature_strand(feature=feature),
                    "Marker length": marker_length,
                    "Location parts": (
                        len(location_parts)
                        if location_parts is not None
                        else 1
                    ),
                    "Location": str(feature.location),
                }
            )

            parsed_feature_count += 1

        file_records.append(
            {
                "Project name": job["Project name"],
                "Seed order": job["Seed order"],
                "Seed Input": job["Seed Input"],
                "K-mer": job["K-mer"],
                "Assembly copy": job["Assembly copy"],
                "GenBank file": os.path.basename(genbank_file),
                "Relative path": job["relative_path"],
                "Record ID": record.id,
                "Record length": len(record.seq),
                "Feature count": parsed_feature_count,
            }
        )

    return {
        "files": file_records,
        "markers": marker_records,
    }


async def parse_genbank_file(**kwargs):
    job = kwargs.get("job", {})
    feature_types = kwargs.get("feature_types", [])
    include_unknown_markers = bool(kwargs.get("include_unknown_markers", False))
    semaphore = kwargs.get("semaphore", asyncio.Semaphore(5))

    async with semaphore:
        return await asyncio.to_thread(
            parse_genbank_file_sync,
            job=job,
            feature_types=feature_types,
            include_unknown_markers=include_unknown_markers,
        )

async def load_genbank_marker_data(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    concurrency = max(1, int(kwargs.get("concurrency", 8)))
    folder_name = str(kwargs.get("folder_name", "genbanks"))
    suffix = str(kwargs.get("suffix", ".rotated.gb"))
    feature_types = list(kwargs.get("feature_types", ["CDS", "rRNA", "tRNA", "D-loop"]))
    include_unknown_markers = bool(kwargs.get("include_unknown_markers", False))
    assembly_dataframe = kwargs.get("assembly_dataframe")

    allowed_keys = build_allowed_assembly_keys(
        dataframe=assembly_dataframe,
    )

    jobs = find_rotated_genbank_jobs(
        results_dir=results_dir,
        folder_name=folder_name,
        suffix=suffix,
        allowed_keys=allowed_keys,
    )

    logging.info(f"Found {len(jobs)} rotated GenBank files")

    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        parse_genbank_file(
            job=job,
            feature_types=feature_types,
            include_unknown_markers=include_unknown_markers,
            semaphore=semaphore,
        )
        for job in jobs
    ]

    parsed_results = await gather_records(tasks=tasks, source_name="rotated GenBank file")

    file_records = []
    marker_records = []

    for parsed_result in parsed_results:
        file_records.extend(parsed_result.get("files", []))
        marker_records.extend(parsed_result.get("markers", []))

    files_dataframe = pd.DataFrame(file_records, columns=GENBANK_FILE_COLUMNS)
    markers_dataframe = pd.DataFrame(marker_records, columns=GENBANK_MARKER_COLUMNS)

    if not files_dataframe.empty:
        files_dataframe = files_dataframe.sort_values(["Project name", "Seed order", "K-mer", "Assembly copy"]).reset_index(drop=True)

    if not markers_dataframe.empty:
        markers_dataframe["Marker length"] = pd.to_numeric(markers_dataframe["Marker length"], errors="coerce")
        markers_dataframe = markers_dataframe.sort_values(["Project name", "Seed order", "K-mer", "Marker", "Start"], na_position="last").reset_index(drop=True)

    logging.info(f"GenBank records parsed: {len(files_dataframe)} files and {len(markers_dataframe)} markers")

    return files_dataframe, markers_dataframe
