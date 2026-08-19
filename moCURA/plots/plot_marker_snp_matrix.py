import csv
import json
import logging
import math
import os
import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from Bio import SeqIO
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


CANONICAL_BASES = {
    "A",
    "C",
    "G",
    "T",
}


DEFAULT_BASE_COLORS = {
    "A": "#4daf4a",
    "C": "#377eb8",
    "G": "#ff7f00",
    "T": "#e41a1c",
    "-": "#bdbdbd",
    "N": "#f0f0f0",
    "?": "#f0f0f0",
}


def sanitize_file_token(**kwargs):
    """Return a filesystem-safe token."""

    value = str(
        kwargs.get(
            "value",
            "",
        )
    ).strip()

    sanitized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        value,
    )

    sanitized = sanitized.strip(
        "._-"
    )

    return sanitized or "unknown"


def read_labels(**kwargs):
    """Read the optional name,label CSV created with the marker FASTA."""

    labels_path = kwargs.get(
        "labels_path"
    )

    if (
        not labels_path
        or not os.path.isfile(
            labels_path
        )
    ):
        return {}

    labels = {}

    with open(
        labels_path,
        "r",
        encoding="utf-8",
        newline="",
    ) as input_handle:
        reader = csv.DictReader(
            input_handle
        )

        for row in reader:
            sequence_name = str(
                row.get(
                    "name",
                    "",
                )
            ).strip()

            sequence_label = str(
                row.get(
                    "label",
                    sequence_name,
                )
            ).strip()

            if sequence_name:
                labels[
                    sequence_name
                ] = sequence_label

    return labels


def parse_sequence_id(**kwargs):
    """
    Parse the project and K-mer from an ID such as ITV38290__kmer_20.
    """

    sequence_id = str(
        kwargs.get(
            "sequence_id",
            "",
        )
    )

    match = re.search(
        r"^(?P<project>.+?)__kmer_(?P<kmer>\d+)",
        sequence_id,
    )

    if match:
        return {
            "project": match.group(
                "project"
            ),
            "kmer": int(
                match.group(
                    "kmer"
                )
            ),
        }

    reverse_match = re.search(
        r"^kmer_(?P<kmer>\d+)__(?P<project>.+)",
        sequence_id,
    )

    if reverse_match:
        return {
            "project": reverse_match.group(
                "project"
            ),
            "kmer": int(
                reverse_match.group(
                    "kmer"
                )
            ),
        }

    return {
        "project": sequence_id,
        "kmer": 0,
    }


def build_metadata_lookup(**kwargs):
    """Build a metadata lookup indexed by sequence ID."""

    sequence_metadata = kwargs.get(
        "sequence_metadata",
        [],
    )

    metadata_lookup = {}

    for item in sequence_metadata:
        sequence_id = str(
            item.get(
                "sequence_id",
                "",
            )
        )

        if sequence_id:
            metadata_lookup[
                sequence_id
            ] = dict(item)

    return metadata_lookup


def load_alignment(**kwargs):
    """Read and validate one aligned FASTA."""

    alignment_path = kwargs.get(
        "alignment_path"
    )

    records = list(
        SeqIO.parse(
            alignment_path,
            "fasta",
        )
    )

    if not records:
        raise ValueError(
            f"Alignment is empty: {alignment_path}"
        )

    alignment_lengths = {
        len(record.seq)
        for record in records
    }

    if len(
        alignment_lengths
    ) != 1:
        raise ValueError(
            "Aligned FASTA contains sequences with different lengths: "
            f"{alignment_path}"
        )

    sequence_ids = [
        record.id
        for record in records
    ]

    duplicate_ids = sorted(
        {
            sequence_id
            for sequence_id in sequence_ids
            if sequence_ids.count(
                sequence_id
            )
            > 1
        }
    )

    if duplicate_ids:
        raise ValueError(
            "Duplicate alignment IDs: "
            + ", ".join(
                duplicate_ids
            )
        )

    return records


def resolve_row_metadata(**kwargs):
    """Resolve project, K-mer and display label for each alignment row."""

    records = kwargs.get(
        "records",
        [],
    )

    sequence_metadata = kwargs.get(
        "sequence_metadata",
        [],
    )

    labels = kwargs.get(
        "labels",
        {},
    )

    project_labels = kwargs.get(
        "project_labels",
        {},
    )

    label_template = str(
        kwargs.get(
            "label_template",
            "{project_label} | K-mer {kmer}",
        )
    )

    metadata_lookup = build_metadata_lookup(
        sequence_metadata=sequence_metadata
    )

    resolved_rows = []

    for record in records:
        sequence_id = record.id

        metadata = dict(
            metadata_lookup.get(
                sequence_id,
                {},
            )
        )

        if not metadata:
            metadata = parse_sequence_id(
                sequence_id=sequence_id
            )

        project_name = str(
            metadata.get(
                "project",
                sequence_id,
            )
        )

        kmer = int(
            metadata.get(
                "kmer",
                0,
            )
        )

        project_label = str(
            project_labels.get(
                project_name,
                project_name,
            )
        )

        format_values = {
            "project": project_name,
            "project_label": project_label,
            "kmer": kmer,
            "sequence_id": sequence_id,
            "seed": str(
                metadata.get(
                    "seed",
                    "",
                )
            ),
            "assembly_copy": str(
                metadata.get(
                    "assembly_copy",
                    "",
                )
            ),
        }

        try:
            display_label = label_template.format(
                **format_values
            )
        except KeyError as error:
            raise ValueError(
                "Unknown field in SNP matrix label_template: "
                f"{error}"
            ) from error

        if sequence_id in labels:
            display_label = labels[
                sequence_id
            ]

        resolved_rows.append(
            {
                "sequence_id": sequence_id,
                "sequence": str(
                    record.seq
                ).upper(),
                "project": project_name,
                "project_label": project_label,
                "kmer": kmer,
                "seed": str(metadata.get("seed", "")),
                "assembly_copy": str(metadata.get("assembly_copy", "")),
                "display_label": display_label,
            }
        )

    return resolved_rows


def sort_rows(**kwargs):
    """Sort rows by project and K-mer while preserving project groups."""

    rows = list(
        kwargs.get(
            "rows",
            [],
        )
    )

    project_order = [
        str(value)
        for value in kwargs.get(
            "project_order",
            [],
        )
    ]

    project_sort_ascending = bool(
        kwargs.get(
            "project_sort_ascending",
            True,
        )
    )

    kmer_sort_ascending = bool(
        kwargs.get(
            "kmer_sort_ascending",
            True,
        )
    )

    project_rank = {
        project_name: rank
        for rank, project_name in enumerate(
            project_order
        )
    }

    unknown_project_rank = len(
        project_rank
    )

    def row_sort_key(row):
        project_name = str(
            row["project"]
        )

        explicit_rank = project_rank.get(
            project_name,
            unknown_project_rank,
        )

        fallback_project = (
            project_name
            if project_sort_ascending
            else "".join(
                chr(
                    255 - ord(character)
                )
                for character in project_name
            )
        )

        kmer_value = int(
            row["kmer"]
        )

        if not kmer_sort_ascending:
            kmer_value *= -1

        return (
            explicit_rank,
            fallback_project,
            kmer_value,
            row["sequence_id"],
        )

    return sorted(
        rows,
        key=row_sort_key,
    )


def column_has_true_snp(**kwargs):
    """
    Return True when a column has at least two canonical nucleotide states.

    Gaps and ambiguous symbols are ignored for deciding whether the column
    contains a true SNP.
    """

    column_values = kwargs.get(
        "column_values",
        [],
    )

    canonical_states = {
        str(value).upper()
        for value in column_values
        if str(value).upper()
        in CANONICAL_BASES
    }

    return len(
        canonical_states
    ) >= 2


def find_snp_columns(**kwargs):
    """
    Return alignment columns containing true SNPs.

    Gap-only variation does not generate an image. When a true SNP column also
    contains gaps, the gap is retained and displayed as '-'.
    """

    sequences = kwargs.get(
        "sequences",
        [],
    )

    if not sequences:
        return []

    alignment_length = len(
        sequences[0]
    )

    snp_columns = []

    for column_index in range(
        alignment_length
    ):
        column_values = [
            sequence[
                column_index
            ]
            for sequence in sequences
        ]

        if column_has_true_snp(
            column_values=column_values
        ):
            snp_columns.append(
                column_index
            )

    return snp_columns


def build_reference_positions(**kwargs):
    """
    Convert alignment columns to reference coordinates.

    Insertions relative to the reference are represented as 120+1, 120+2, etc.
    """

    reference_sequence = str(
        kwargs.get(
            "reference_sequence",
            "",
        )
    ).upper()

    selected_columns = kwargs.get(
        "selected_columns",
        [],
    )

    reference_position = 0
    insertion_count = {}

    labels_by_column = {}

    for column_index, base in enumerate(
        reference_sequence
    ):
        if base != "-":
            reference_position += 1

            labels_by_column[
                column_index
            ] = str(
                reference_position
            )
        else:
            insertion_count[
                reference_position
            ] = (
                insertion_count.get(
                    reference_position,
                    0,
                )
                + 1
            )

            labels_by_column[
                column_index
            ] = (
                f"{reference_position}+"
                f"{insertion_count[reference_position]}"
            )

    return [
        labels_by_column.get(
            column_index,
            str(
                column_index + 1
            ),
        )
        for column_index in selected_columns
    ]


def resolve_reference_row(**kwargs):
    """Resolve the reference row used for coordinate labels."""

    rows = kwargs.get(
        "rows",
        [],
    )

    reference_project = kwargs.get(
        "reference_project"
    )

    reference_kmer = kwargs.get(
        "reference_kmer"
    )

    reference_sequence_id = kwargs.get(
        "reference_sequence_id"
    )

    if reference_sequence_id:
        for row in rows:
            if row[
                "sequence_id"
            ] == reference_sequence_id:
                return row

    candidates = list(
        rows
    )

    if reference_project is not None:
        project_candidates = [
            row
            for row in candidates
            if str(
                row["project"]
            )
            == str(
                reference_project
            )
        ]

        if project_candidates:
            candidates = project_candidates

    if reference_kmer is not None:
        kmer_candidates = [
            row
            for row in candidates
            if int(
                row["kmer"]
            )
            == int(
                reference_kmer
            )
        ]

        if kmer_candidates:
            candidates = kmer_candidates

    return candidates[0]


def normalize_display_base(**kwargs):
    """Normalize one alignment character for plotting."""

    value = str(
        kwargs.get(
            "value",
            "N",
        )
    ).upper()

    if value in {
        "A",
        "C",
        "G",
        "T",
        "-",
    }:
        return value

    return "N"


def build_base_encoding(**kwargs):
    """Build categorical codes, colors and display labels."""

    base_colors = dict(
        DEFAULT_BASE_COLORS
    )

    base_colors.update(
        kwargs.get(
            "base_colors",
            {},
        )
    )

    base_order = [
        "A",
        "C",
        "G",
        "T",
        "-",
        "N",
    ]

    base_to_code = {
        base: index
        for index, base in enumerate(
            base_order
        )
    }

    colors = [
        base_colors[
            base
        ]
        for base in base_order
    ]

    colormap = ListedColormap(
        colors
    )

    normalization = BoundaryNorm(
        np.arange(
            -0.5,
            len(
                base_order
            )
            + 0.5,
            1,
        ),
        colormap.N,
    )

    return {
        "base_order": base_order,
        "base_to_code": base_to_code,
        "colormap": colormap,
        "normalization": normalization,
        "base_colors": base_colors,
    }


def build_project_groups(**kwargs):
    """Return consecutive row blocks for each project."""

    rows = kwargs.get(
        "rows",
        [],
    )

    if not rows:
        return []

    groups = []
    current_project = rows[
        0
    ]["project"]
    start_index = 0

    for row_index, row in enumerate(
        rows[
            1:
        ],
        start=1,
    ):
        if row[
            "project"
        ] == current_project:
            continue

        groups.append(
            {
                "project": current_project,
                "start": start_index,
                "end": row_index - 1,
            }
        )

        current_project = row[
            "project"
        ]

        start_index = row_index

    groups.append(
        {
            "project": current_project,
            "start": start_index,
            "end": len(
                rows
            ) - 1,
        }
    )

    return groups


def add_project_group_borders(**kwargs):
    """
    Draw one border around alternating project blocks.

    All K-mers from the same project are enclosed by the same rectangle.
    The next project has no rectangle, the following project has one, and so on.
    """

    axis = kwargs.get(
        "axis"
    )

    rows = kwargs.get(
        "rows",
        [],
    )

    number_of_columns = int(
        kwargs.get(
            "number_of_columns",
            0,
        )
    )

    enabled = bool(
        kwargs.get(
            "enabled",
            True,
        )
    )

    first_project_has_border = bool(
        kwargs.get(
            "first_project_has_border",
            True,
        )
    )

    border_color = str(
        kwargs.get(
            "border_color",
            "#111111",
        )
    )

    border_linewidth = float(
        kwargs.get(
            "border_linewidth",
            2.0,
        )
    )

    if (
        axis is None
        or not enabled
        or number_of_columns <= 0
    ):
        return

    project_groups = build_project_groups(
        rows=rows
    )

    for group_index, group in enumerate(
        project_groups
    ):
        should_draw = (
            group_index % 2 == 0
            if first_project_has_border
            else group_index % 2 == 1
        )

        if not should_draw:
            continue

        axis.add_patch(
            Rectangle(
                (
                    -0.5,
                    group[
                        "start"
                    ]
                    - 0.5,
                ),
                number_of_columns,
                (
                    group[
                        "end"
                    ]
                    - group[
                        "start"
                    ]
                    + 1
                ),
                fill=False,
                edgecolor=border_color,
                linewidth=border_linewidth,
                clip_on=False,
                zorder=12,
            )
        )


def add_project_separators(**kwargs):
    """Draw subtle separators between all project blocks."""

    axis = kwargs.get(
        "axis"
    )

    rows = kwargs.get(
        "rows",
        [],
    )

    separator_color = str(
        kwargs.get(
            "separator_color",
            "#d0d0d0",
        )
    )

    separator_linewidth = float(
        kwargs.get(
            "separator_linewidth",
            0.7,
        )
    )

    if axis is None:
        return

    project_groups = build_project_groups(
        rows=rows
    )

    for group in project_groups[
        :-1
    ]:
        axis.axhline(
            group[
                "end"
            ]
            + 0.5,
            color=separator_color,
            linewidth=separator_linewidth,
            zorder=10,
        )


def split_columns(**kwargs):
    """Split SNP columns into horizontal panels inside one image."""

    selected_columns = list(
        kwargs.get(
            "selected_columns",
            [],
        )
    )

    columns_per_panel = max(
        1,
        int(
            kwargs.get(
                "columns_per_panel",
                60,
            )
        ),
    )

    return [
        selected_columns[
            start_index:
            start_index
            + columns_per_panel
        ]
        for start_index in range(
            0,
            len(
                selected_columns
            ),
            columns_per_panel,
        )
    ]


def write_snp_table(**kwargs):
    """Write the displayed SNP matrix as TSV beside the image."""

    output_path = kwargs.get(
        "output_path"
    )

    rows = kwargs.get(
        "rows",
        [],
    )

    sequences = kwargs.get(
        "sequences",
        [],
    )

    selected_columns = kwargs.get(
        "selected_columns",
        [],
    )

    position_labels = kwargs.get(
        "position_labels",
        [],
    )

    table_rows = []

    for row, sequence in zip(
        rows,
        sequences,
    ):
        table_row = {
            "Sequence ID": row["sequence_id"],
            "Project": row["project"],
            "Seed Input": row.get("seed", ""),
            "Assembly copy": row.get("assembly_copy", ""),
            "K-mer": row["kmer"],
            "Label": row["display_label"],
            "Alignment columns": json.dumps([int(column_index) + 1 for column_index in selected_columns]),
            "Reference positions": json.dumps(build_reference_positions(reference_sequence=sequence, selected_columns=selected_columns)),
        }

        for column_index, position_label in zip(
            selected_columns,
            position_labels,
        ):
            table_row[
                str(
                    position_label
                )
            ] = normalize_display_base(
                value=sequence[
                    column_index
                ]
            )

        table_rows.append(
            table_row
        )

    pandas_dataframe = pd.DataFrame(
        table_rows
    )

    pandas_dataframe.to_csv(
        output_path,
        sep="\t",
        index=False,
    )


def plot_marker_snp_matrix(**kwargs):
    """
    Plot all bases for true SNP columns of one marker alignment.

    No image is created when the alignment has no true SNP, even if it has
    gap-only variation.
    """

    alignment_path = kwargs.get(
        "alignment_path"
    )

    output_dir = kwargs.get(
        "output_dir",
        "snp_matrices",
    )

    marker = str(
        kwargs.get(
            "marker",
            "marker",
        )
    )

    sequence_metadata = kwargs.get(
        "sequence_metadata",
        [],
    )

    labels_path = kwargs.get(
        "labels_path"
    )

    config = kwargs.get(
        "config",
        {},
    )

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    records = load_alignment(
        alignment_path=alignment_path
    )

    labels = read_labels(
        labels_path=labels_path
    )

    rows = resolve_row_metadata(
        records=records,
        sequence_metadata=sequence_metadata,
        labels=labels,
        project_labels=config.get(
            "project_labels",
            {},
        ),
        label_template=config.get(
            "label_template",
            "{project_label} | K-mer {kmer}",
        ),
    )

    rows = sort_rows(
        rows=rows,
        project_order=config.get(
            "project_order",
            [],
        ),
        project_sort_ascending=bool(
            config.get(
                "project_sort_ascending",
                True,
            )
        ),
        kmer_sort_ascending=bool(
            config.get(
                "kmer_sort_ascending",
                True,
            )
        ),
    )

    sequence_by_id = {
        record.id: str(
            record.seq
        ).upper()
        for record in records
    }

    sequences = [
        sequence_by_id[
            row[
                "sequence_id"
            ]
        ]
        for row in rows
    ]

    snp_columns = find_snp_columns(
        sequences=sequences
    )

    if not snp_columns:
        logging.info(
            "SNP matrix skipped for %s because no true SNP was found",
            marker,
        )

        return {
            "marker": marker,
            "generated": False,
            "reason": "no_true_snp",
            "snp_count": 0,
            "image_path": None,
            "table_path": None,
        }

    reference_row = resolve_reference_row(
        rows=rows,
        reference_project=config.get(
            "reference_project"
        ),
        reference_kmer=config.get(
            "reference_kmer"
        ),
        reference_sequence_id=config.get(
            "reference_sequence_id"
        ),
    )

    reference_sequence = sequence_by_id[
        reference_row[
            "sequence_id"
        ]
    ]

    position_labels = build_reference_positions(
        reference_sequence=reference_sequence,
        selected_columns=snp_columns,
    )

    marker_slug = sanitize_file_token(
        value=marker
    )

    figure_format = str(
        config.get(
            "format",
            "png",
        )
    ).lower()

    image_path = os.path.join(
        output_dir,
        (
            f"{marker_slug}_"
            f"snp_matrix."
            f"{figure_format}"
        ),
    )

    table_path = os.path.join(
        output_dir,
        (
            f"{marker_slug}_"
            "snp_matrix.tsv"
        ),
    )

    save_image = bool(
        config.get(
            "save_image",
            True,
        )
    )

    save_table = bool(
        config.get(
            "save_table",
            True,
        )
    )

    if not save_image:
        if save_table:
            write_snp_table(
                output_path=table_path,
                rows=rows,
                sequences=sequences,
                selected_columns=snp_columns,
                position_labels=position_labels,
            )
        else:
            table_path = None

        logging.info(
            "SNP data written for %s without static image: %s",
            marker,
            table_path,
        )

        return {
            "marker": marker,
            "generated": True,
            "reason": "true_snp_found",
            "snp_count": len(snp_columns),
            "reference_sequence_id": reference_row["sequence_id"],
            "image_path": None,
            "table_path": table_path,
        }

    encoding = build_base_encoding(
        base_colors=config.get(
            "base_colors",
            {},
        )
    )

    column_panels = split_columns(
        selected_columns=snp_columns,
        columns_per_panel=int(
            config.get(
                "columns_per_panel",
                60,
            )
        ),
    )

    number_of_panels = len(
        column_panels
    )

    row_height = float(
        config.get(
            "row_height",
            0.42,
        )
    )

    cell_width = float(
        config.get(
            "cell_width",
            0.62,
        )
    )

    minimum_panel_width = float(
        config.get(
            "minimum_panel_width",
            8,
        )
    )

    maximum_figure_width = float(
        config.get(
            "maximum_figure_width",
            32,
        )
    )

    panel_widths = [
        min(
            maximum_figure_width,
            max(
                minimum_panel_width,
                len(
                    panel_columns
                )
                * cell_width
                + 5,
            ),
        )
        for panel_columns in column_panels
    ]

    figure_width = max(
        panel_widths
    )

    panel_height = max(
        3.5,
        len(
            rows
        )
        * row_height
        + 1.8,
    )

    figure_height = (
        panel_height
        * number_of_panels
    )

    figure, axes = plt.subplots(
        number_of_panels,
        1,
        figsize=(
            figure_width,
            figure_height,
        ),
        squeeze=False,
    )

    flat_axes = axes.flatten()

    annotation_fontsize = float(
        config.get(
            "annotation_fontsize",
            8,
        )
    )

    x_tick_fontsize = float(
        config.get(
            "x_tick_fontsize",
            8,
        )
    )

    y_tick_fontsize = float(
        config.get(
            "y_tick_fontsize",
            9,
        )
    )

    for panel_index, (
        axis,
        panel_columns,
    ) in enumerate(
        zip(
            flat_axes,
            column_panels,
        )
    ):
        panel_codes = []

        panel_text = []

        for sequence in sequences:
            row_codes = []

            row_text = []

            for column_index in panel_columns:
                display_base = normalize_display_base(
                    value=sequence[
                        column_index
                    ]
                )

                row_codes.append(
                    encoding[
                        "base_to_code"
                    ][
                        display_base
                    ]
                )

                row_text.append(
                    display_base
                )

            panel_codes.append(
                row_codes
            )

            panel_text.append(
                row_text
            )

        matrix = np.asarray(
            panel_codes,
            dtype=float,
        )

        axis.imshow(
            matrix,
            cmap=encoding[
                "colormap"
            ],
            norm=encoding[
                "normalization"
            ],
            aspect="auto",
            interpolation="nearest",
        )

        for row_index in range(
            matrix.shape[
                0
            ]
        ):
            for column_position in range(
                matrix.shape[
                    1
                ]
            ):
                base = panel_text[
                    row_index
                ][
                    column_position
                ]

                axis.text(
                    column_position,
                    row_index,
                    base,
                    ha="center",
                    va="center",
                    fontsize=annotation_fontsize,
                    fontweight="bold",
                    color=(
                        "#111111"
                        if base
                        in {
                            "A",
                            "C",
                            "G",
                            "T",
                            "-",
                        }
                        else "#666666"
                    ),
                    zorder=8,
                )

        panel_position_labels = [
            position_labels[
                snp_columns.index(
                    column_index
                )
            ]
            for column_index in panel_columns
        ]

        axis.set_xticks(
            np.arange(
                len(
                    panel_columns
                )
            )
        )

        axis.set_xticklabels(
            panel_position_labels,
            rotation=90,
            fontsize=x_tick_fontsize,
        )

        axis.xaxis.tick_top()

        axis.tick_params(
            axis="x",
            top=True,
            bottom=False,
            labeltop=True,
            labelbottom=False,
            length=0,
            pad=4,
        )

        axis.set_yticks(
            np.arange(
                len(
                    rows
                )
            )
        )

        axis.set_yticklabels(
            [
                row[
                    "display_label"
                ]
                for row in rows
            ],
            fontsize=y_tick_fontsize,
        )

        axis.tick_params(
            axis="y",
            length=0,
            pad=6,
        )

        axis.set_xlim(
            -0.5,
            len(
                panel_columns
            )
            - 0.5,
        )

        axis.set_ylim(
            len(
                rows
            )
            - 0.5,
            -0.5,
        )

        axis.set_xlabel("")

        axis.set_ylabel("")

        axis.set_title(
            (
                f"Variable sites "
                f"{panel_index + 1}/"
                f"{number_of_panels}"
            )
            if number_of_panels > 1
            else "",
            fontsize=float(
                config.get(
                    "panel_title_fontsize",
                    11,
                )
            ),
            pad=30,
        )

        add_project_separators(
            axis=axis,
            rows=rows,
            separator_color=config.get(
                "separator_color",
                "#d0d0d0",
            ),
            separator_linewidth=float(
                config.get(
                    "separator_linewidth",
                    0.7,
                )
            ),
        )

        add_project_group_borders(
            axis=axis,
            rows=rows,
            number_of_columns=len(
                panel_columns
            ),
            enabled=bool(
                config.get(
                    "alternate_project_border",
                    True,
                )
            ),
            first_project_has_border=bool(
                config.get(
                    "first_project_has_border",
                    True,
                )
            ),
            border_color=config.get(
                "project_border_color",
                "#111111",
            ),
            border_linewidth=float(
                config.get(
                    "project_border_linewidth",
                    2.0,
                )
            ),
        )

        for spine in axis.spines.values():
            spine.set_visible(
                False
            )

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="s",
            linestyle="",
            markersize=10,
            markerfacecolor=encoding[
                "base_colors"
            ][
                base
            ],
            markeredgecolor="none",
            label=(
                "Gap"
                if base == "-"
                else (
                    "Ambiguous"
                    if base == "N"
                    else base
                )
            ),
        )
        for base in encoding[
            "base_order"
        ]
    ]

    figure.suptitle(
        (
            f"{marker}: nucleotide states "
            "at true SNP positions"
        ),
        fontsize=float(
            config.get(
                "title_fontsize",
                18,
            )
        ),
        fontweight="bold",
        y=0.995,
    )

    figure.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(
            0.5,
            0.977,
        ),
        ncol=len(
            legend_handles
        ),
        frameon=False,
        fontsize=float(
            config.get(
                "legend_fontsize",
                10,
            )
        ),
    )

    figure.subplots_adjust(
        top=float(
            config.get(
                "top",
                0.91,
            )
        ),
        bottom=float(
            config.get(
                "bottom",
                0.04,
            )
        ),
        left=float(
            config.get(
                "left",
                0.22,
            )
        ),
        right=float(
            config.get(
                "right",
                0.98,
            )
        ),
        hspace=float(
            config.get(
                "hspace",
                0.30,
            )
        ),
    )

    figure.savefig(
        image_path,
        dpi=int(
            config.get(
                "dpi",
                300,
            )
        ),
        bbox_inches="tight",
    )

    plt.close(
        figure
    )

    if bool(
        config.get(
            "save_table",
            True,
        )
    ):
        write_snp_table(
            output_path=table_path,
            rows=rows,
            sequences=sequences,
            selected_columns=snp_columns,
            position_labels=position_labels,
        )
    else:
        table_path = None

    logging.info(
        "SNP matrix written for %s: %s",
        marker,
        image_path,
    )

    return {
        "marker": marker,
        "generated": True,
        "reason": "true_snp_found",
        "snp_count": len(
            snp_columns
        ),
        "reference_sequence_id": reference_row[
            "sequence_id"
        ],
        "image_path": image_path,
        "table_path": table_path,
    }
