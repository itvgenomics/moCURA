import asyncio
import csv
import logging
import os
import re
from collections import Counter

import pandas as pd
from Bio import SeqIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord

from ..standardization.standardized_marker_name import first_qualifier_value, standardized_marker_name

CONTROL_REGION_LABEL = "Control Region"

CONTROL_REGION_TERMS = (
    "control region",
    "d-loop",
    "d loop",
    "dloop",
    "displacement loop",
    "mitochondrial control region",
)

def sanitize_file_token(**kwargs):
    value = str(kwargs.get("value", "")).strip()

     # Replace any character that is not alphanumeric, dot, underscore, or hyphen with an underscore
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    sanitized = sanitized.strip("._-")
    return sanitized or "unknown"

def wrap_fasta_sequence(**kwargs):
    sequence = str(kwargs.get("sequence", ""))
    width = max(1, int(kwargs.get("width", 80)))

    return "\n".join(sequence[index:index + width] for index in range(0, len(sequence), width))

def feature_text(**kwargs):
    qualifiers = kwargs.get("qualifiers", {})

    values = [
        first_qualifier_value(qualifiers=qualifiers, qualifier_name=qualifier_name)
        for qualifier_name in ("gene", "product", "label", "note")
        ]

    return " | ".join(value for value in values if value)

def is_control_region_feature(**kwargs):
    feature = kwargs.get("feature", None)

    if feature is None:
        return False

    text = feature_text(qualifiers=feature.qualifiers).lower()

    return any(term in text for term in CONTROL_REGION_TERMS)

def feature_interval_parts(**kwargs):
    feature = kwargs.get("feature", None)
    record_length = int(kwargs.get("record_length", 0))

    if feature is None or record_length <= 0:
        return []

    parts = getattr(feature.location, "parts", None)

    if parts is None:
        parts = [feature.location]
    intervals = []

    for part in parts:
        start = int(part.start) + 1
        end = int(part.end)

        start = max(1, min(start, record_length))
        end = max(1, min(end, record_length))

        if end >= start:
            intervals.append((start, end))

    return intervals

def merge_intervals(**kwargs):
    intervals = sorted(kwargs.get("intervals", []))

    merged = []

    for start, end in intervals:
        if not merged:
            merged.append([start, end])
            continue

        previous_start, previous_end = merged[-1]

        if start <= previous_end + 1:
            merged[-1][1] = max(previous_end, end)
        else:
            merged.append([start, end])

    return merged

def infer_largest_circular_gap(**kwargs):
    intervals = kwargs.get("intervals", [])
    record_length = int(kwargs.get("record_length", 0))

    if not intervals or record_length <= 0:
        return None

    merged = merge_intervals(intervals=intervals)

    if not merged:
        return None

    gap_candidates = []

    for interval_index in range(len(merged) - 1):
        gap_start = (merged[interval_index][1] + 1)
        gap_end = (merged[interval_index + 1][0] - 1)

        if gap_end >= gap_start:
            gap_candidates.append({"start": gap_start, "end": gap_end, "length": (gap_end - gap_start + 1)})

    circular_gap_length = (record_length - merged[-1][1] + merged[0][0] - 1)

    if circular_gap_length > 0:
        gap_candidates.append({"start": (merged[-1][1] + 1), "end": (merged[0][0] - 1), "length": circular_gap_length})

    if not gap_candidates:
        return None

    return max(gap_candidates, key=lambda item: item["length"])

def extract_circular_sequence(**kwargs):
    sequence = kwargs.get("sequence")
    start = int(kwargs.get("start", 1))
    end = int(kwargs.get("end", 0))

    if sequence is None:
        return ""

    sequence = Seq(str(sequence))
    sequence_length = len(sequence)

    if sequence_length == 0:
        return ""

    start = max(1, min(start, sequence_length))
    end = max(0, min(end, sequence_length))

    if end >= start:
        return str(sequence[start - 1:end]).upper()

    return str(sequence[start - 1:] + sequence[:end]).upper()

def parse_genbank_candidates_sync(**kwargs):
    file_metadata = kwargs.get("file_metadata", {})
    results_dir = kwargs.get("results_dir", ".")
    feature_types = set(kwargs.get("feature_types", ["CDS", "rRNA", "tRNA"]))
    infer_control_region = bool(kwargs.get("infer_control_region", True))

    relative_path = str(file_metadata.get("Relative path", ""))

    genbank_file = os.path.join(results_dir, relative_path)

    if not os.path.isfile(genbank_file):
        raise FileNotFoundError(f"Rotated GenBank file not found: {genbank_file}")

    candidate_records = []

    for record in SeqIO.parse(genbank_file, "genbank"):
        annotated_intervals = []
        file_marker_candidates = []
        control_region_found = False

        for feature in record.features:
            if feature.type == "source":
                continue

            if feature.type not in feature_types:
                continue

            marker_name = standardized_marker_name(feature_type=feature.type, qualifiers=feature.qualifiers)

            if (marker_name is None and is_control_region_feature(feature=feature)):
                marker_name = CONTROL_REGION_LABEL

            if marker_name is None:
                continue

            if marker_name != CONTROL_REGION_LABEL:
                annotated_intervals.extend(feature_interval_parts(feature=feature, record_length=len(record.seq)))

            marker_sequence = str(feature.extract(record.seq)).upper()

            if not marker_sequence:
                continue

            if marker_name == CONTROL_REGION_LABEL:
                control_region_found = True

            file_marker_candidates.append(
                {
                    **file_metadata,
                    "Record ID": record.id,
                    "Record length": len(record.seq),
                    "Marker": marker_name,
                    "Marker length": len(marker_sequence),
                    "Marker sequence": marker_sequence,
                    "Marker source": "annotated_feature",
                    "Feature type": feature.type,
                    "Location": str(feature.location),
                }
            )

        if (infer_control_region and not control_region_found):
            inferred_gap = infer_largest_circular_gap(intervals=annotated_intervals, record_length=len(record.seq))

            if inferred_gap is not None:
                control_sequence = extract_circular_sequence(sequence=record.seq, start=inferred_gap["start"], end=inferred_gap["end"])

                if control_sequence:
                    file_marker_candidates.append(
                        {
                            **file_metadata,
                            "Record ID": record.id,
                            "Record length": len(record.seq),
                            "Marker": CONTROL_REGION_LABEL,
                            "Marker length": len(control_sequence),
                            "Marker sequence": control_sequence,
                            "Marker source": "inferred_largest_gap",
                            "Feature type": CONTROL_REGION_LABEL,
                            "Location": (
                                f"{inferred_gap['start']}.."
                                f"{inferred_gap['end']}"
                            ),
                        }
                    )

        longest_candidates = {}

        for candidate in file_marker_candidates:
            marker_name = candidate["Marker"]
            current = longest_candidates.get(marker_name, None)

            if (current is None or candidate["Marker length"] > current["Marker length"]):
                longest_candidates[marker_name] = candidate
        candidate_records.extend(longest_candidates.values())
    return candidate_records

async def parse_genbank_candidates(**kwargs):
    semaphore = kwargs.get("semaphore", None)

    if semaphore is None:
        semaphore = asyncio.Semaphore(5)

    async with semaphore:
        return await asyncio.to_thread(
            parse_genbank_candidates_sync, 
            file_metadata=kwargs.get("file_metadata", {}),
            results_dir=kwargs.get("results_dir", "."),
            feature_types=kwargs.get("feature_types", []), infer_control_region=kwargs.get("infer_control_region", True)
            )

def build_file_metadata_records(**kwargs):
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe", None)
    marker_dataframe = kwargs.get("marker_dataframe", None)

    source_dataframe = None

    if (genbank_files_dataframe is not None and not genbank_files_dataframe.empty):
        source_dataframe = (genbank_files_dataframe.copy())
    elif (marker_dataframe is not None and not marker_dataframe.empty):
        source_dataframe = (marker_dataframe.copy())

    if (source_dataframe is None or source_dataframe.empty):
        return []

    required_columns = {
        "Project name",
        "Seed order",
        "Seed Input",
        "K-mer",
        "Assembly copy",
        "GenBank file",
        "Relative path",
    }

    missing_columns = sorted(required_columns.difference(source_dataframe.columns))
    if missing_columns:
        raise ValueError(f"Missing GenBank metadata columns: {', '.join(missing_columns)}")

    return (source_dataframe[sorted(required_columns)].drop_duplicates(subset=[
        "Project name",
        "Seed order",
        "Seed Input",
        "K-mer",
        "Assembly copy",
        "Relative path",
        ]).sort_values(["Project name", "K-mer", "Seed order", "Assembly copy"]).to_dict(orient="records"))

def select_representative_candidate(**kwargs):
    group_dataframe = kwargs.get("group_dataframe")
    strategy = str(kwargs.get("strategy", "matching_seed_then_modal")).lower()
    preferred_seed_inputs = [str(value) for value in kwargs.get("preferred_seed_inputs", [])]

    marker_name = str(group_dataframe["Marker"].iloc[0])
    candidates = (group_dataframe.copy())

    candidates["_preferred_rank"] = len(preferred_seed_inputs) + 1

    for rank, seed_input in enumerate(preferred_seed_inputs):
        candidates.loc[candidates["Seed Input"].astype(str) == seed_input, "_preferred_rank"] = rank

    candidates["_matching_seed"] = (candidates["Seed Input"].astype(str) == marker_name)

    marker_lengths = pd.to_numeric(candidates["Marker length"], errors="coerce")
    modal_lengths = marker_lengths.dropna().mode()

    modal_length = (float(modal_lengths.iloc[0]) if not modal_lengths.empty else None)
    candidates["_modal_length"] = (marker_lengths == modal_length if modal_length is not None else False)

    base_sort = ["Seed order", "Assembly copy", "GenBank file"]

    if strategy == "preferred_seed_then_modal":
        sort_columns = ["_preferred_rank", "_modal_length", "_matching_seed", *base_sort]
        ascending = [True, False, False, True, True, True]
    elif strategy == "modal_length":
        sort_columns = ["_modal_length", "_matching_seed", *base_sort]
        ascending = [False, False, True, True, True]
    elif strategy == "first":
        sort_columns = base_sort
        ascending = [True, True, True]
    else:
        sort_columns = ["_matching_seed", "_modal_length", "_preferred_rank", *base_sort]
        ascending = [False, False, True, True, True, True]

    selected = (candidates.sort_values(sort_columns, ascending=ascending).iloc[0].drop(labels=["_preferred_rank", "_matching_seed", "_modal_length"]).to_dict())
    return selected

def select_representatives(**kwargs):
    """Select one representative sequence for each Marker, K-mer and Project."""
    candidates_dataframe = kwargs.get("candidates_dataframe")
    strategy = str(kwargs.get("strategy", "matching_seed_then_modal")).lower()
    preferred_seed_inputs = kwargs.get("preferred_seed_inputs", [])
    sequence_id_order = str(kwargs.get("sequence_id_order", "project_then_kmer")).lower()

    if candidates_dataframe is None or candidates_dataframe.empty:
        return pd.DataFrame()

    if strategy == "all":
        output = candidates_dataframe.copy()
        def build_all_sequence_id(row):
            project = sanitize_file_token(value=row["Project name"])
            seed = sanitize_file_token(value=row["Seed Input"])
            kmer = int(row["K-mer"])
            copy = int(row["Assembly copy"])
            if sequence_id_order == "kmer_then_project":
                return f"kmer_{kmer}__{project}__{seed}__copy_{copy}"
            return f"{project}__kmer_{kmer}__{seed}__copy_{copy}"
        output["Sequence ID"] = output.apply(build_all_sequence_id, axis=1)
        return output

    selected_records = []
    for _, group_dataframe in candidates_dataframe.groupby(["Marker", "K-mer", "Project name"], sort=True, dropna=False):
        selected_records.append(select_representative_candidate(group_dataframe=group_dataframe, strategy=strategy, preferred_seed_inputs=preferred_seed_inputs))
    output = pd.DataFrame(selected_records)
    if output.empty:
        return output

    def build_sequence_id(row):
        project = sanitize_file_token(value=row["Project name"])
        kmer = int(row["K-mer"])
        if sequence_id_order == "kmer_then_project":
            return f"kmer_{kmer}__{project}"
        return f"{project}__kmer_{kmer}"

    output["Sequence ID"] = output.apply(build_sequence_id, axis=1)
    return output

def build_project_label(**kwargs):
    """Build a user-facing label that can show Project and K-mer."""
    record = kwargs.get("record", {})
    project_labels = kwargs.get("project_labels", {})
    label_template = str(kwargs.get("label_template", "{project_label} | K-mer {kmer}"))
    project_name = str(record.get("Project name", ""))
    values = {
        "project": project_name,
        "project_label": str(project_labels.get(project_name, project_name)),
        "seed": str(record.get("Seed Input", "")),
        "kmer": str(record.get("K-mer", "")),
        "marker": str(record.get("Marker", "")),
        "assembly_copy": str(record.get("Assembly copy", "")),
    }
    try:
        return label_template.format(**values)
    except KeyError as error:
        raise ValueError(f"Unknown field in label_template: {error}") from error

def write_marker_fastas(**kwargs):
    """Write one FASTA per marker containing all Projects and all K-mers."""
    selected_dataframe = kwargs.get("selected_dataframe")
    output_dir = kwargs.get("output_dir", "marker_snp_analysis")
    project_labels = kwargs.get("project_labels", {})
    label_template = kwargs.get("label_template", "{project_label} | K-mer {kmer}")
    minimum_sequences = max(1, int(kwargs.get("minimum_sequences", 2)))
    minimum_projects = max(1, int(kwargs.get("minimum_projects", 2)))
    sequence_id_order = str(kwargs.get("sequence_id_order", "project_then_kmer")).lower()

    if selected_dataframe is None or selected_dataframe.empty:
        return []

    fasta_root = os.path.join(output_dir, "fastas")
    os.makedirs(fasta_root, exist_ok=True, mode=0o755)
    jobs = []

    for marker_name, group_dataframe in selected_dataframe.groupby("Marker", sort=True, dropna=False):
        marker_slug = sanitize_file_token(value=marker_name)
        marker_directory = os.path.join(fasta_root, marker_slug)
        os.makedirs(marker_directory, exist_ok=True, mode=0o755)
        fasta_path = os.path.join(marker_directory, f"{marker_slug}_all_kmers.fasta")
        labels_path = os.path.join(marker_directory, f"{marker_slug}_all_kmers.labels.csv")

        sort_columns = (
            ["K-mer", "Project name", "Seed order", "Assembly copy"]
            if sequence_id_order == "kmer_then_project"
            else ["Project name", "K-mer", "Seed order", "Assembly copy"]
        )
        sorted_group = group_dataframe.sort_values(sort_columns).reset_index(drop=True)

        used_sequence_ids = Counter()
        sequence_records = []
        label_rows = []
        sequence_metadata = []

        for _, row in sorted_group.iterrows():
            base_sequence_id = str(row["Sequence ID"])
            used_sequence_ids[base_sequence_id] += 1
            sequence_id = base_sequence_id
            if used_sequence_ids[base_sequence_id] > 1:
                sequence_id = f"{base_sequence_id}__{used_sequence_ids[base_sequence_id]}"

            kmer_value = int(row["K-mer"])
            sequence_records.append(SeqRecord(Seq(str(row["Marker sequence"])), id=sequence_id, description=(
                f"project={row['Project name']} kmer={kmer_value} "
                f"seed={row['Seed Input']} marker={marker_name} "
                f"source={row['GenBank file']}"
                )))
            
            label_rows.append({
                "name": sequence_id,
                "label": build_project_label(record=row.to_dict(), project_labels=project_labels, label_template=label_template)})

            sequence_metadata.append({
                "sequence_id": sequence_id,
                "project": str(row["Project name"]),
                "kmer": kmer_value,
                "seed": str(row["Seed Input"]),
                "assembly_copy": int(row["Assembly copy"]),
                "genbank_file": str(row["GenBank file"]),
            })

        SeqIO.write(sequence_records, fasta_path, "fasta")
        with open(labels_path, "w", encoding="utf-8", newline="") as output_handle:
            writer = csv.DictWriter(output_handle, fieldnames=["name", "label"])
            writer.writeheader()
            writer.writerows(label_rows)

        project_count = len({item["project"] for item in sequence_metadata})

        jobs.append({
            "marker": str(marker_name),
            "marker_slug": marker_slug,
            "fasta_path": fasta_path,
            "labels_path": labels_path,
            "sequence_count": len(sequence_records),
            "project_count": project_count,
            "kmer_values": sorted({item["kmer"] for item in sequence_metadata}),
            "sequence_metadata": sequence_metadata,
            "ready": len(sequence_records) >= minimum_sequences and project_count >= minimum_projects,
        })

    return jobs

async def export_marker_fastas(**kwargs):
    results_dir = kwargs.get("results_dir", None)
    output_dir = kwargs.get("output_dir", "marker_snp_analysis")
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe", None)
    marker_dataframe = kwargs.get("marker_dataframe", None)
    concurrency = max(1, int(kwargs.get("concurrency", 5)))
    feature_types = kwargs.get("feature_types", ["CDS", "rRNA", "tRNA"])
    infer_control_region = bool(kwargs.get("infer_control_region", True))
    representative_strategy = kwargs.get("representative_strategy", None)
    preferred_seed_inputs = kwargs.get("preferred_seed_inputs", [])
    project_labels = kwargs.get("project_labels", {})
    label_template = kwargs.get("label_template", None)
    minimum_sequences = int(kwargs.get("minimum_sequences", 2))
    minimum_projects = int(kwargs.get("minimum_projects", 2))
    sequence_id_order = str(kwargs.get("sequence_id_order", None))

    os.makedirs(output_dir, exist_ok=True, mode=0o755)

    file_metadata_records = build_file_metadata_records(genbank_files_dataframe=genbank_files_dataframe, marker_dataframe=marker_dataframe)

    if not file_metadata_records:
        logging.warning("No rotated GenBank files were available for marker FASTA export")

        return {
            "jobs": [],
            "candidate_dataframe": pd.DataFrame(),
            "selected_dataframe": pd.DataFrame(),
            "candidate_manifest": None,
            "selected_manifest": None,
        }

    semaphore = asyncio.Semaphore(concurrency)

    tasks = [
        parse_genbank_candidates(
            file_metadata=file_metadata,
            results_dir=results_dir,
            feature_types=feature_types,
            infer_control_region=infer_control_region,
            semaphore=semaphore,
        )
        for file_metadata in file_metadata_records
    ]

    parsed_results = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    candidate_records = []

    for file_metadata, parsed_result in zip(file_metadata_records, parsed_results):
        if isinstance(parsed_result, Exception):
            logging.error(f"Could not extract marker sequences from {file_metadata.get('Relative path', 'unknown')}: {parsed_result}")
            continue

        candidate_records.extend(parsed_result)
    candidates_dataframe = pd.DataFrame(candidate_records)

    if candidates_dataframe.empty:
        logging.warning("No marker sequences were extracted from rotated GenBank files")

        return {
            "jobs": [],
            "candidate_dataframe": candidates_dataframe,
            "selected_dataframe": pd.DataFrame(),
            "candidate_manifest": None,
            "selected_manifest": None,
        }

    selected_dataframe = select_representatives(
        candidates_dataframe=candidates_dataframe,
        strategy=representative_strategy,
        preferred_seed_inputs=preferred_seed_inputs,
        sequence_id_order=sequence_id_order,
    )

    manifest_dir = os.path.join(output_dir, "manifests")

    os.makedirs(manifest_dir, exist_ok=True, mode=0o755)

    candidate_manifest = os.path.join(manifest_dir, "marker_sequence_candidates.tsv")
    selected_manifest = os.path.join(manifest_dir, "marker_sequence_representatives.tsv")

    candidate_export = candidates_dataframe.drop(columns=["Marker sequence"], errors="ignore")
    selected_export = selected_dataframe.drop(columns=["Marker sequence"], errors="ignore")
    candidate_export.to_csv(candidate_manifest, sep="\t", index=False)
    selected_export.to_csv(selected_manifest, sep="\t", index=False)

    jobs = write_marker_fastas(
        selected_dataframe=selected_dataframe,
        output_dir=output_dir,
        project_labels=project_labels,
        label_template=label_template,
        minimum_sequences=minimum_sequences,
        minimum_projects=minimum_projects,
        sequence_id_order=sequence_id_order,
    )

    logging.info(f"Marker FASTA export completed: {len(jobs)} all-K-mer marker FASTAs")

    return {
        "jobs": jobs,
        "candidate_dataframe": candidates_dataframe,
        "selected_dataframe": selected_dataframe,
        "candidate_manifest": candidate_manifest,
        "selected_manifest": selected_manifest,
    }
