import base64
import json
import logging
import math
import mimetypes
import os
import re
from collections import defaultdict

import pandas as pd
from Bio import SeqIO
import seaborn as sns
from matplotlib.colors import to_hex


ASSEMBLY_KEY_COLUMNS = ["Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Record ID"]


def clean_scalar(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def dataframe_records(**kwargs):
    dataframe = kwargs.get("dataframe")
    if dataframe is None or dataframe.empty:
        return []
    return [{str(key): clean_scalar(value) for key, value in row.items()} for row in dataframe.to_dict("records")]


def assembly_key_from_row(**kwargs):
    row = kwargs.get("row", {})
    values = []
    for column in ASSEMBLY_KEY_COLUMNS:
        value = row.get(column)
        if value is None:
            continue
        if column in {"Seed order", "K-mer", "Assembly copy"}:
            try:
                value = int(float(value))
            except (TypeError, ValueError):
                pass
        values.append(str(value))
    return " | ".join(values)


def clean_consensus(**kwargs):
    sequence = str(kwargs.get("sequence", "")).upper()
    return re.sub(r"[^ACGTN]", "", sequence)


def reverse_complement(**kwargs):
    sequence = clean_consensus(sequence=kwargs.get("sequence", ""))
    return sequence.translate(str.maketrans("ACGTN", "TGCAN"))[::-1]


def minimum_rotation(sequence):
    if not sequence:
        return ""
    doubled = sequence + sequence
    best = sequence
    for index in range(1, len(sequence)):
        candidate = doubled[index:index + len(sequence)]
        if candidate < best:
            best = candidate
    return best


def canonical_repeat_consensus(**kwargs):
    sequence = clean_consensus(sequence=kwargs.get("sequence", ""))
    if not sequence:
        return ""
    forward = minimum_rotation(sequence)
    reverse = minimum_rotation(reverse_complement(sequence=sequence))
    return min(forward, reverse)


def repeat_family_label(**kwargs):
    sequence = str(kwargs.get("sequence", ""))
    maximum_length = int(kwargs.get("maximum_length", 14))
    if len(sequence) <= maximum_length:
        return sequence
    return f"{sequence[:maximum_length - 3]}... ({len(sequence)} bp)"


def overlap_length(start_a, end_a, start_b, end_b):
    return max(0, min(end_a, end_b) - max(start_a, start_b) + 1)


def build_marker_lookup(**kwargs):
    marker_dataframe = kwargs.get("marker_dataframe")
    lookup = defaultdict(list)
    if marker_dataframe is None or marker_dataframe.empty:
        return lookup

    for row in marker_dataframe.to_dict("records"):
        key = assembly_key_from_row(row=row)
        start = pd.to_numeric(row.get("Start"), errors="coerce")
        end = pd.to_numeric(row.get("End"), errors="coerce")
        if pd.isna(start) or pd.isna(end):
            continue
        lookup[key].append({**row, "Start": int(start), "End": int(end)})

    for key in lookup:
        lookup[key].sort(key=lambda item: (item["Start"], item["End"], str(item.get("Marker", ""))))
    return lookup


def repeat_gene_context(**kwargs):
    repeat_row = kwargs.get("repeat_row", {})
    markers = kwargs.get("markers", [])
    start = int(float(repeat_row.get("Start", 0)))
    end = int(float(repeat_row.get("End", 0)))

    overlaps = []
    for marker in markers:
        overlap = overlap_length(start, end, marker["Start"], marker["End"])
        if overlap > 0:
            overlaps.append((str(marker.get("Marker", "unknown")), overlap, str(marker.get("Strand", "."))))

    if overlaps:
        overlaps.sort(key=lambda item: (-item[1], item[0]))
        return ", ".join(f"{name} ({strand}; {overlap} bp)" for name, overlap, strand in overlaps), "overlap"

    if not markers:
        return "Unannotated", "unannotated"

    previous_marker = None
    next_marker = None
    for marker in markers:
        if marker["End"] < start:
            previous_marker = marker
        if marker["Start"] > end and next_marker is None:
            next_marker = marker

    if previous_marker and next_marker:
        return f"Between {previous_marker.get('Marker', 'unknown')} and {next_marker.get('Marker', 'unknown')}", "intergenic"
    if previous_marker:
        return f"After {previous_marker.get('Marker', 'unknown')}", "intergenic"
    if next_marker:
        return f"Before {next_marker.get('Marker', 'unknown')}", "intergenic"
    return "Intergenic", "intergenic"


def enrich_trf_repeats(**kwargs):
    repeats_dataframe = kwargs.get("repeats_dataframe")
    marker_dataframe = kwargs.get("marker_dataframe")
    if repeats_dataframe is None or repeats_dataframe.empty:
        return pd.DataFrame() if repeats_dataframe is None else repeats_dataframe.copy()

    marker_lookup = build_marker_lookup(marker_dataframe=marker_dataframe)
    enriched_records = []

    for row in repeats_dataframe.to_dict("records"):
        key = assembly_key_from_row(row=row)
        canonical = canonical_repeat_consensus(sequence=row.get("Consensus", ""))
        context, context_type = repeat_gene_context(repeat_row=row, markers=marker_lookup.get(key, []))
        context_label = context
        if context_type == "overlap":
            context_label = ", ".join(part.split(" (")[0] for part in context.split(", "))
        enriched_records.append({
            **row,
            "Assembly key": key,
            "Repeat family": canonical,
            "Repeat family label": repeat_family_label(sequence=canonical),
            "Gene context": context,
            "Gene context label": context_label,
            "Context type": context_type,
        })

    return pd.DataFrame(enriched_records)


def relative_path(**kwargs):
    path = kwargs.get("path")
    output_dir = kwargs.get("output_dir")
    if not path:
        return None
    try:
        return os.path.relpath(path, output_dir).replace(os.sep, "/")
    except (TypeError, ValueError):
        return str(path).replace(os.sep, "/")


def collect_existing_images(**kwargs):
    paths = kwargs.get("paths", [])
    output_dir = kwargs.get("output_dir", ".")
    images = []
    for path in paths:
        if not path:
            continue
        if isinstance(path, (list, tuple)):
            images.extend(collect_existing_images(paths=path, output_dir=output_dir))
            continue
        if os.path.isfile(path):
            images.append(relative_path(path=path, output_dir=output_dir))
    return sorted(set(images))


def image_data_uri(**kwargs):
    path = kwargs.get("path")
    if not path or not os.path.isfile(path):
        return None

    mime_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as handle:
        encoded = base64.b64encode(handle.read()).decode("ascii")

    return f"data:{mime_type};base64,{encoded}"


def collect_embedded_images(**kwargs):
    paths = kwargs.get("paths", [])
    images = []

    for path in paths:
        if not path:
            continue

        if isinstance(path, (list, tuple)):
            images.extend(collect_embedded_images(paths=path))
            continue

        if not os.path.isfile(path):
            continue

        data_uri = image_data_uri(path=path)
        if data_uri:
            stem = os.path.splitext(os.path.basename(path))[0]
            label = stem.replace("_snp_matrix", "").replace("_", " ").strip()
            images.append({
                "name": os.path.basename(path),
                "label": label,
                "data_uri": data_uri,
            })

    unique = {}
    for image in images:
        unique[image["name"]] = image

    return [unique[name] for name in sorted(unique)]



def alignment_sequence_spans(**kwargs):
    """Ungapped length and first/last aligned base (1-based columns) per sequence.

    Leading and trailing gaps are where a sequence ends inside the alignment;
    the HTML report shows them as missing data instead of deletions.
    """

    path = kwargs.get("path")
    spans = {}
    if not path or not os.path.isfile(path):
        return spans, None

    alignment_length = None
    try:
        for record in SeqIO.parse(path, "fasta"):
            sequence = str(record.seq).upper()
            alignment_length = len(sequence)
            positions = [index for index, base in enumerate(sequence) if base not in "-."]
            spans[record.id] = {
                "ungapped_length": len(positions),
                "first_column": positions[0] + 1 if positions else None,
                "last_column": positions[-1] + 1 if positions else None,
            }
    except (OSError, ValueError) as error:
        logging.warning("Could not read SNP alignment %s: %s", path, error)
        return {}, None

    return spans, alignment_length


def collect_snp_matrices(**kwargs):
    marker_snp_results = kwargs.get("marker_snp_results", {}) or {}
    matrices = []

    for result in marker_snp_results.get("matrix_results", []):
        if not isinstance(result, dict) or not result.get("generated", False):
            continue

        table_path = result.get("table_path")
        if not table_path or not os.path.isfile(table_path):
            logging.warning("SNP table not found for HTML report: %s", table_path)
            continue

        dataframe = pd.read_csv(table_path, sep="\t", dtype=str, keep_default_na=False)
        spans, alignment_length = alignment_sequence_spans(path=result.get("alignment_path"))
        metadata_columns = ["Sequence ID", "Project", "Seed Input", "Assembly copy", "K-mer", "Label", "Alignment columns", "Reference positions"]
        position_columns = [column for column in dataframe.columns if column not in metadata_columns]

        rows = []
        for record in dataframe.to_dict("records"):
            try:
                alignment_columns = json.loads(record.get("Alignment columns", "[]") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                alignment_columns = []
            try:
                reference_positions = json.loads(record.get("Reference positions", "[]") or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                reference_positions = []

            rows.append({
                "sequence_id": str(record.get("Sequence ID", "")),
                "project": str(record.get("Project", "")),
                "seed": str(record.get("Seed Input", "")),
                "assembly_copy": str(record.get("Assembly copy", "")),
                "kmer": clean_scalar(pd.to_numeric(record.get("K-mer"), errors="coerce")),
                "label": str(record.get("Label", "")),
                "states": [str(record.get(position, "N")).upper() for position in position_columns],
                "alignment_columns": alignment_columns,
                "position_labels": [str(value) for value in reference_positions],
                **spans.get(str(record.get("Sequence ID", "")), {}),
            })

        matrices.append({
            "marker": str(result.get("marker", "")),
            "snp_count": int(result.get("snp_count", len(position_columns)) or len(position_columns)),
            "reference_sequence_id": str(result.get("reference_sequence_id", "")),
            "positions": [str(position) for position in position_columns],
            "alignment_length": alignment_length,
            "rows": rows,
        })

    matrices.sort(key=lambda item: item["marker"])
    return matrices


def parse_genome_range_value(value):
    match = re.search(r"(\d[\d,.]*)\s*[-–]\s*(\d[\d,.]*)", str(value))
    if not match:
        return None, None
    start, end = (
        int(part.replace(",", "").replace(".", ""))
        for part in match.groups()
    )
    return start, end


def enrich_summary_records(records):
    enriched = []
    for record in records:
        item = dict(record)
        start, end = parse_genome_range_value(item.get("Genome range"))
        item["Genome range start"] = start
        item["Genome range end"] = end
        item["Run key"] = " | ".join(
            [
                str(item.get("Project name", "")),
                str(item.get("Seed Input", "")),
                str(item.get("K-mer", "")),
            ]
        )
        enriched.append(item)
    return enriched


def build_html_plot_style(summary_records):
    seed_inputs = sorted(
        {
            str(row.get("Seed Input"))
            for row in summary_records
            if row.get("Seed Input") not in (None, "")
        }
    )
    colors = sns.color_palette("colorblind", max(1, len(seed_inputs)))
    seed_colors = {
        seed: to_hex(colors[index])
        for index, seed in enumerate(seed_inputs)
    }

    marker_cycle = [
        "circle",
        "square",
        "diamond",
        "triangle-up",
        "triangle-down",
        "cross",
        "x",
        "triangle-left",
        "triangle-right",
        "hexagon",
    ]
    kmer_values = sorted(
        {
            int(float(row.get("K-mer")))
            for row in summary_records
            if row.get("K-mer") not in (None, "")
        }
    )
    kmer_markers = {
        str(kmer): marker_cycle[index % len(marker_cycle)]
        for index, kmer in enumerate(kmer_values)
    }

    return {
        "seed_colors": seed_colors,
        "kmer_markers": kmer_markers,
        "density_fill": "#E76F51",
        "genome_range": "#B0E4CC",
        "row_background": "#EEEEEE",
        "dark": "#202020",
        "ui_primary": "#0173B2",
        "ui_secondary": "#029E73",
        "ui_accent": "#E76F51",
    }


def parse_coordinate_value(value):
    if value in (None, ""):
        return None
    try:
        numeric = float(value)
        if math.isfinite(numeric):
            return numeric
    except (TypeError, ValueError):
        pass

    source = str(value).strip().replace(",", ".")
    match = re.match(r"\s*(\d+)°(\d+)'([\d.]+)\"?\s*([NSEOW])\s*$", source, flags=re.IGNORECASE)
    if not match:
        return None

    degree, minute, second, direction = match.groups()
    decimal = float(degree) + float(minute) / 60 + float(second) / 3600
    if direction.upper() in {"S", "W", "O"}:
        decimal *= -1
    return decimal


def normalize_metadata_columns(dataframe):
    if dataframe is None or dataframe.empty:
        return pd.DataFrame()

    normalized = dataframe.copy()
    normalized.columns = [str(column).strip().lower() for column in normalized.columns]
    rename = {}
    for column in normalized.columns:
        compact = column.replace("_", " ").strip()
        if compact == "project name":
            rename[column] = "Project name"
        elif compact == "species":
            rename[column] = "Species"
        elif compact == "location":
            rename[column] = "Location"
        elif compact == "latitude":
            rename[column] = "Latitude"
        elif compact == "longitude":
            rename[column] = "Longitude"
    normalized = normalized.rename(columns=rename)

    for column in ["Project name", "Species", "Location", "Latitude", "Longitude"]:
        if column not in normalized.columns:
            normalized[column] = None

    normalized["Project name"] = normalized["Project name"].astype(str).str.strip()
    normalized["Species"] = normalized["Species"].apply(clean_scalar)
    normalized["Location"] = normalized["Location"].apply(clean_scalar)
    normalized["Latitude decimal"] = normalized["Latitude"].apply(parse_coordinate_value)
    normalized["Longitude decimal"] = normalized["Longitude"].apply(parse_coordinate_value)
    normalized = normalized[normalized["Project name"] != ""]
    return normalized[["Project name", "Species", "Location", "Latitude", "Longitude", "Latitude decimal", "Longitude decimal"]]


def load_metadata_dataframe(**kwargs):
    dataframe = kwargs.get("dataframe")
    path = kwargs.get("path")

    if dataframe is not None and not dataframe.empty:
        return normalize_metadata_columns(dataframe)

    if not path:
        return pd.DataFrame()
    if not os.path.isfile(path):
        logging.warning("Metadata file not found for HTML report: %s", path)
        return pd.DataFrame()

    suffix = os.path.splitext(path)[1].lower()
    if suffix in {".xlsx", ".xls", ".ods"}:
        dataframe = pd.read_excel(path)
    elif suffix in {".tsv", ".txt"}:
        dataframe = pd.read_csv(path, sep="\t")
    else:
        dataframe = pd.read_csv(path)
    return normalize_metadata_columns(dataframe)


def build_metadata_lookup(**kwargs):
    dataframe = kwargs.get("dataframe")
    lookup = {}
    if dataframe is None or dataframe.empty:
        return lookup
    for row in dataframe.to_dict("records"):
        project = str(row.get("Project name", "")).strip()
        if not project:
            continue
        lookup[project] = {key: clean_scalar(value) for key, value in row.items()}
    return lookup


def apply_metadata_to_records(records, metadata_lookup):
    enriched = []
    for record in records:
        item = dict(record)
        metadata = metadata_lookup.get(str(item.get("Project name", "")).strip(), {})
        if metadata:
            item.update(metadata)
        enriched.append(item)
    return enriched


def collect_metadata_points(summary_records, metadata_lookup):
    projects = {str(row.get("Project name", "")).strip() for row in summary_records if row.get("Project name") not in (None, "")}
    points = []
    for project in sorted(projects):
        metadata = metadata_lookup.get(project, {})
        latitude = metadata.get("Latitude decimal")
        longitude = metadata.get("Longitude decimal")
        if latitude is None or longitude is None:
            continue
        points.append({
            "Project name": project,
            "Species": metadata.get("Species"),
            "Location": metadata.get("Location"),
            "Latitude": metadata.get("Latitude"),
            "Longitude": metadata.get("Longitude"),
            "Latitude decimal": latitude,
            "Longitude decimal": longitude,
        })
    return points


def augment_snp_matrices(**kwargs):
    matrices = kwargs.get("matrices", [])
    metadata_lookup = kwargs.get("metadata_lookup", {})
    marker_records = kwargs.get("marker_records", [])

    marker_lookup = defaultdict(list)
    for record in marker_records:
        key = (
            str(record.get("Project name", "")).strip(),
            str(record.get("Seed Input", "")).strip(),
            str(record.get("K-mer", "")).strip(),
            str(record.get("Marker", "")).strip(),
        )
        marker_lookup[key].append(record)

    for matrix in matrices:
        span_starts = []
        span_ends = []
        span_lengths = []
        for row in matrix.get("rows", []):
            project = str(row.get("project", "")).strip()
            metadata = metadata_lookup.get(project, {})
            if metadata:
                row["species"] = metadata.get("Species")
                row["location"] = metadata.get("Location")
                row["latitude"] = metadata.get("Latitude")
                row["longitude"] = metadata.get("Longitude")

            exact_key = (project, str(row.get("seed", "")).strip(), str(row.get("kmer", "")).strip(), str(matrix.get("marker", "")).strip())
            candidates = marker_lookup.get(exact_key, [])
            if candidates:
                starts = [clean_scalar(pd.to_numeric(item.get("Start"), errors="coerce")) for item in candidates]
                ends = [clean_scalar(pd.to_numeric(item.get("End"), errors="coerce")) for item in candidates]
                lengths = [clean_scalar(pd.to_numeric(item.get("Marker length"), errors="coerce")) for item in candidates]
                starts = [value for value in starts if value is not None]
                ends = [value for value in ends if value is not None]
                lengths = [value for value in lengths if value is not None]
                if starts:
                    row["marker_start"] = min(starts)
                    span_starts.extend(starts)
                if ends:
                    row["marker_end"] = max(ends)
                    span_ends.extend(ends)
                if lengths:
                    row["marker_length"] = lengths[0]
                    span_lengths.extend(lengths)

        matrix["marker_start"] = min(span_starts) if span_starts else None
        matrix["marker_end"] = max(span_ends) if span_ends else None
        matrix["marker_length_min"] = min(span_lengths) if span_lengths else None
        matrix["marker_length_max"] = max(span_lengths) if span_lengths else None
    return matrices

ORGANPIPE_TABLES = (
    "completeness", "origin", "coverage", "pilon_changes", "pilon_breaks", "recruitment",
    "nhmmer", "read_qc", "benchmarks", "alerts", "provenance",
    "junction", "integrity", "integrity_issues", "concordance", "concordance_pairs", "composition", "scores",
    "heteroplasmy", "heteroplasmy_sites", "species", "species_hits", "reference", "reference_genes", "reference_genomes",
    "reference_gene_lengths", "reference_composition", "validation", "validation_messages",
)
# Tables keyed by RefSeq accession: the project metadata does not apply to them.
REFERENCE_TABLES = {"reference_gene_lengths", "reference_composition"}


def compact_rscu(**kwargs):
    """One record per assembly with the RSCU values in a fixed codon order."""

    dataframe = kwargs.get("dataframe")
    if dataframe is None or dataframe.empty:
        return {"codons": [], "amino_acids": [], "assemblies": []}
    order = dataframe[["Codon", "Amino acid"]].drop_duplicates().sort_values(["Amino acid", "Codon"])
    codons = order["Codon"].tolist()
    identity = ["Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly"]
    assemblies = []
    for _, group in dataframe.groupby("Assembly", sort=False):
        values = dict(zip(group["Codon"], group["RSCU"]))
        counts = dict(zip(group["Codon"], group["Count"]))
        first = group.iloc[0]
        assemblies.append({
            **{column: clean_scalar(first[column]) for column in identity},
            "RSCU": [clean_scalar(values.get(codon)) for codon in codons],
            "Counts": [clean_scalar(counts.get(codon)) for codon in codons],
        })
    return {"codons": codons, "amino_acids": order["Amino acid"].tolist(), "assemblies": assemblies}


def compact_reference_rscu(**kwargs):
    """One record per RefSeq genome with its RSCU values, in the codon order of the assemblies."""

    dataframe = kwargs.get("dataframe")
    codons = kwargs.get("codons") or []
    if dataframe is None or dataframe.empty or not codons:
        return []
    records = []
    for accession, group in dataframe.groupby("Accession", sort=True):
        values = dict(zip(group["Codon"], group["RSCU"]))
        counts = dict(zip(group["Codon"], group["Count"]))
        records.append({
            "Accession": clean_scalar(accession), "Organism": clean_scalar(group.iloc[0]["Organism"]),
            "RSCU": [clean_scalar(values.get(codon)) for codon in codons],
            "Counts": [clean_scalar(counts.get(codon)) for codon in codons],
        })
    return records


def organpipe_report_data(**kwargs):
    """Records of the Phase 1 OrganPipe analyses for the HTML report."""

    organpipe = kwargs.get("organpipe_results") or {}
    metadata_lookup = kwargs.get("metadata_lookup") or {}

    output = {
        "expected_markers": list(organpipe.get("expected_markers", [])),
        "identity_bins": list(organpipe.get("identity_bins", [])),
        "coverage_windows": [
            {key: clean_scalar(value) if not isinstance(value, list) else value for key, value in item.items()}
            for item in organpipe.get("coverage_windows", []) or []
        ],
        "identity_histograms": list(organpipe.get("identity_histograms", []) or []),
        "settings": dict(organpipe.get("settings", {}) or {}),
        "settings_phase2": dict(organpipe.get("settings_phase2", {}) or {}),
        "settings_phase3": dict(organpipe.get("settings_phase3", {}) or {}),
        "rscu": compact_rscu(dataframe=organpipe.get("rscu")),
    }
    output["reference_rscu"] = compact_reference_rscu(dataframe=organpipe.get("reference_rscu"), codons=output["rscu"]["codons"])

    for key in ORGANPIPE_TABLES:
        value = organpipe.get(key)
        records = dataframe_records(dataframe=value) if isinstance(value, pd.DataFrame) else []
        # species_hits has its own Species column (the hit), which the metadata must not overwrite.
        if key not in {"provenance", "benchmarks", "species_hits"} | REFERENCE_TABLES:
            records = apply_metadata_to_records(records, metadata_lookup)
        output[key] = records

    output["available"] = any(output[key] for key in ORGANPIPE_TABLES if key != "provenance")
    return output


def prepare_html_report_data(**kwargs):
    summary_dataframe = kwargs.get("summary_dataframe")
    plot_dataframe = kwargs.get("plot_dataframe")
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe")
    marker_dataframe = kwargs.get("marker_dataframe")
    trf_summary_dataframe = kwargs.get("trf_summary_dataframe")
    trf_repeats_dataframe = kwargs.get("trf_repeats_dataframe")
    marker_snp_results = kwargs.get("marker_snp_results", {}) or {}
    output_dir = kwargs.get("output_dir", ".")
    static_plot_paths = kwargs.get("static_plot_paths", [])
    metadata_dataframe = kwargs.get("metadata_dataframe")
    metadata_path = kwargs.get("metadata_path")

    metadata_frame = load_metadata_dataframe(dataframe=metadata_dataframe, path=metadata_path)
    metadata_lookup = build_metadata_lookup(dataframe=metadata_frame)

    enriched_repeats = enrich_trf_repeats(repeats_dataframe=trf_repeats_dataframe, marker_dataframe=marker_dataframe)
    snp_matrices = collect_snp_matrices(marker_snp_results=marker_snp_results)

    summary_records = enrich_summary_records(dataframe_records(dataframe=summary_dataframe))
    plot_records = dataframe_records(dataframe=plot_dataframe)
    genbank_records = dataframe_records(dataframe=genbank_files_dataframe)
    marker_records = dataframe_records(dataframe=marker_dataframe)
    trf_summary_records = dataframe_records(dataframe=trf_summary_dataframe)
    repeat_records = dataframe_records(dataframe=enriched_repeats)

    summary_records = apply_metadata_to_records(summary_records, metadata_lookup)
    plot_records = apply_metadata_to_records(plot_records, metadata_lookup)
    genbank_records = apply_metadata_to_records(genbank_records, metadata_lookup)
    marker_records = apply_metadata_to_records(marker_records, metadata_lookup)
    trf_summary_records = apply_metadata_to_records(trf_summary_records, metadata_lookup)
    repeat_records = apply_metadata_to_records(repeat_records, metadata_lookup)
    snp_matrices = augment_snp_matrices(matrices=snp_matrices, metadata_lookup=metadata_lookup, marker_records=marker_records)
    metadata_points = collect_metadata_points(summary_records, metadata_lookup)

    projects = sorted({str(row.get("Project name")) for row in summary_records if row.get("Project name") is not None})
    html_style = build_html_plot_style(summary_records)
    circularized_count = sum(1 for row in summary_records if row.get("Circularized") is True)
    assemblies = len(summary_records)
    total_repeats = len(repeat_records)
    repeat_families = len({row.get("Repeat family") for row in repeat_records if row.get("Repeat family")})

    for row in genbank_records:
        row["Assembly key"] = assembly_key_from_row(row=row)
    for row in marker_records:
        row["Assembly key"] = assembly_key_from_row(row=row)
    for row in trf_summary_records:
        row["Assembly key"] = assembly_key_from_row(row=row)

    downloads = []
    for filename, label in [
        ("moCURA_summary.xlsx", "Excel workbook"),
        (os.path.join("trf_analysis", "trf_summary.tsv"), "TRF summary TSV"),
        (os.path.join("trf_analysis", "trf_repeats.tsv"), "TRF repeats TSV"),
        (os.path.join("trf_analysis", "trf_consensus.fasta"), "TRF consensus FASTA"),
    ]:
        absolute = os.path.join(output_dir, filename)
        if os.path.isfile(absolute):
            downloads.append({"label": label, "path": filename.replace(os.sep, "/")})

    return {
        "metrics": {
            "projects": len(projects),
            "assemblies": assemblies,
            "circularized": circularized_count,
            "repeats": total_repeats,
            "repeat_families": repeat_families,
            "snp_plots": len(snp_matrices),
        },
        "projects": projects,
        "summary": summary_records,
        "plot": plot_records,
        "genbanks": genbank_records,
        "markers": marker_records,
        "trf_summary": trf_summary_records,
        "repeats": repeat_records,
        "snp_matrices": snp_matrices,
        "downloads": downloads,
        "metadata_points": metadata_points,
        "metadata_available": bool(metadata_lookup),
        "style": html_style,
        "organpipe": organpipe_report_data(
            organpipe_results=kwargs.get("organpipe_results"),
            metadata_lookup=metadata_lookup,
        ),
    }
