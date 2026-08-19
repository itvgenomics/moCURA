import logging
import os
import re

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


CONTROL_REGION_LABEL = "Control Region"
GENOME_SIZE_LABEL = "Genome size"


def normalize_marker_name(**kwargs):
    """Normalize marker names for robust plotting."""

    value = kwargs.get("value")

    if value is None or pd.isna(value):
        return ""

    original_value = str(value).strip()

    if not original_value:
        return ""

    lowered = original_value.lower()

    if lowered in {
        "control region",
        "control-region",
        "control_region",
        "d-loop",
        "dloop",
        "displacement loop",
        "displacement-loop",
        "mitochondrial control region",
        "cr",
    }:
        return CONTROL_REGION_LABEL

    compact_value = re.sub(
        r"[^a-z0-9]+",
        "",
        lowered,
    )

    if compact_value in {
        "nd1",
        "nad1",
        "nadh1",
        "nadhdehydrogenasesubunit1",
    }:
        return "ND1"

    if compact_value in {
        "nd2",
        "nad2",
        "nadh2",
        "nadhdehydrogenasesubunit2",
    }:
        return "ND2"

    if compact_value in {
        "nd3",
        "nad3",
        "nadh3",
        "nadhdehydrogenasesubunit3",
    }:
        return "ND3"

    if compact_value in {
        "nd4",
        "nad4",
        "nadh4",
        "nadhdehydrogenasesubunit4",
    }:
        return "ND4"

    if compact_value in {
        "nd4l",
        "nad4l",
        "nadh4l",
        "nadhdehydrogenasesubunit4l",
    }:
        return "ND4L"

    if compact_value in {
        "nd5",
        "nad5",
        "nadh5",
        "nadhdehydrogenasesubunit5",
    }:
        return "ND5"

    if compact_value in {
        "nd6",
        "nad6",
        "nadh6",
        "nadhdehydrogenasesubunit6",
    }:
        return "ND6"

    if compact_value in {
        "atp6",
        "atpase6",
        "atpsynthasef0subunit6",
    }:
        return "ATP6"

    if compact_value in {
        "atp8",
        "atpase8",
        "atpsynthasef0subunit8",
    }:
        return "ATP8"

    if compact_value in {
        "coi",
        "cox1",
        "co1",
        "cytochromecoxidasesubuniti",
    }:
        return "COI"

    if compact_value in {
        "coii",
        "cox2",
        "co2",
        "cytochromecoxidasesubunitii",
    }:
        return "COII"

    if compact_value in {
        "coiii",
        "cox3",
        "co3",
        "cytochromecoxidasesubunitiii",
    }:
        return "COIII"

    if compact_value in {
        "cytb",
        "cob",
        "cytochromeb",
    }:
        return "CYTB"

    if compact_value in {
        "12s",
        "rrns",
        "12srrna",
        "smallsubunitribosomalrna",
    }:
        return "12S"

    if compact_value in {
        "16s",
        "rrnl",
        "16srrna",
        "largesubunitribosomalrna",
    }:
        return "16S"

    if original_value.startswith("tRNA-"):
        return original_value

    if lowered.startswith("trna-"):
        suffix = original_value.split("-", 1)[1]
        return f"tRNA-{suffix}"

    return original_value


def classify_marker_category(**kwargs):
    marker_name = normalize_marker_name(
        value=kwargs.get("marker_name"),
    )

    if marker_name in {
        "ATP6",
        "ATP8",
        "COI",
        "COII",
        "COIII",
        "CYTB",
        "ND1",
        "ND2",
        "ND3",
        "ND4",
        "ND4L",
        "ND5",
        "ND6",
    }:
        return "CDS"

    if marker_name in {
        "12S",
        "16S",
    }:
        return "rRNAs"

    if marker_name.startswith("tRNA-"):
        return "tRNAs"

    if marker_name == CONTROL_REGION_LABEL:
        return "Control Region"

    return "Other"


def infer_control_region_rows(**kwargs):
    dataframe = kwargs.get("dataframe")

    if dataframe is None or dataframe.empty:
        return pd.DataFrame()

    required_columns = {
        "Project name",
        "Seed Input",
        "K-mer",
        "Record length",
        "Start",
        "End",
        "Marker",
    }

    if not required_columns.issubset(dataframe.columns):
        return pd.DataFrame()

    inferred_rows = []

    for group_values, group_df in dataframe.groupby(
        [
            "Project name",
            "Seed Input",
            "K-mer",
        ],
        dropna=False,
    ):
        project_name, seed_input, kmer = group_values

        normalized_markers = group_df["Marker"].apply(
            lambda value: normalize_marker_name(
                value=value,
            )
        )

        if (normalized_markers == CONTROL_REGION_LABEL).any():
            continue

        record_lengths = pd.to_numeric(
            group_df["Record length"],
            errors="coerce",
        ).dropna()

        if record_lengths.empty:
            continue

        record_length = int(record_lengths.iloc[0])

        interval_df = group_df.copy()
        interval_df["Start"] = pd.to_numeric(
            interval_df["Start"],
            errors="coerce",
        )
        interval_df["End"] = pd.to_numeric(
            interval_df["End"],
            errors="coerce",
        )
        interval_df = interval_df.dropna(
            subset=[
                "Start",
                "End",
            ]
        )

        if interval_df.empty:
            continue

        intervals = []

        for _, row in interval_df.iterrows():
            start = int(row["Start"])
            end = int(row["End"])

            start = max(1, min(start, record_length))
            end = max(1, min(end, record_length))

            if start <= end:
                intervals.append((start, end))
            else:
                intervals.append((start, record_length))
                intervals.append((1, end))

        if not intervals:
            continue

        merged = []

        for start, end in sorted(intervals):
            if not merged:
                merged.append([start, end])
                continue

            previous_start, previous_end = merged[-1]

            if start <= previous_end + 1:
                merged[-1][1] = max(
                    previous_end,
                    end,
                )
            else:
                merged.append([start, end])

        gap_candidates = []

        for interval_index in range(len(merged) - 1):
            gap_start = merged[interval_index][1] + 1
            gap_end = merged[interval_index + 1][0] - 1

            if gap_end >= gap_start:
                gap_candidates.append(
                    (
                        gap_start,
                        gap_end,
                        gap_end - gap_start + 1,
                    )
                )

        circular_gap_length = (
            record_length
            - merged[-1][1]
            + merged[0][0]
            - 1
        )

        if circular_gap_length > 0:
            gap_candidates.append(
                (
                    merged[-1][1] + 1,
                    merged[0][0] - 1,
                    circular_gap_length,
                )
            )

        if not gap_candidates:
            continue

        best_gap_start, best_gap_end, best_gap_length = max(
            gap_candidates,
            key=lambda item: item[2],
        )

        inferred_rows.append(
            {
                "Project name": project_name,
                "Seed Input": seed_input,
                "K-mer": int(kmer),
                "Marker": CONTROL_REGION_LABEL,
                "Marker length": int(best_gap_length),
                "Feature type": CONTROL_REGION_LABEL,
                "Start": int(best_gap_start),
                "End": int(best_gap_end),
                "Record length": record_length,
                "Marker source": "inferred_largest_gap",
            }
        )

    return pd.DataFrame(inferred_rows)


def prepare_marker_length_plot_data(**kwargs):
    dataframe = kwargs.get("dataframe")

    if dataframe is None or dataframe.empty:
        return pd.DataFrame()

    required_columns = {
        "Project name",
        "Seed Input",
        "K-mer",
        "Marker",
        "Marker length",
    }

    missing_columns = sorted(
        required_columns.difference(dataframe.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing columns required for marker heatmap: "
            + ", ".join(missing_columns)
        )

    plot_data = dataframe.copy()

    plot_data["Project name"] = plot_data["Project name"].astype(str)
    plot_data["Seed Input"] = plot_data["Seed Input"].astype(str)
    plot_data["K-mer"] = pd.to_numeric(
        plot_data["K-mer"],
        errors="coerce",
    )
    plot_data["Marker length"] = pd.to_numeric(
        plot_data["Marker length"],
        errors="coerce",
    )

    for numeric_column in [
        "Start",
        "End",
        "Record length",
    ]:
        if numeric_column in plot_data.columns:
            plot_data[numeric_column] = pd.to_numeric(
                plot_data[numeric_column],
                errors="coerce",
            )

    plot_data = plot_data.dropna(
        subset=[
            "Project name",
            "Seed Input",
            "K-mer",
            "Marker",
            "Marker length",
        ]
    ).copy()

    if plot_data.empty:
        return plot_data

    plot_data["K-mer"] = plot_data["K-mer"].astype(int)
    plot_data["Marker"] = plot_data["Marker"].apply(
        lambda value: normalize_marker_name(
            value=value,
        )
    )

    inferred_control_region_df = infer_control_region_rows(
        dataframe=plot_data,
    )

    if not inferred_control_region_df.empty:
        plot_data = pd.concat(
            [
                plot_data,
                inferred_control_region_df,
            ],
            ignore_index=True,
            sort=False,
        )

    plot_data["Marker"] = plot_data["Marker"].apply(
        lambda value: normalize_marker_name(
            value=value,
        )
    )

    plot_data["Marker category"] = plot_data["Marker"].apply(
        lambda value: classify_marker_category(
            marker_name=value,
        )
    )

    plot_data = plot_data[
        plot_data["Marker category"].isin(
            [
                "CDS",
                "rRNAs",
                "tRNAs",
                "Control Region",
            ]
        )
    ].copy()

    plot_data["Column key"] = (
        plot_data["Seed Input"]
        + "||"
        + plot_data["K-mer"].astype(str)
    )

    return plot_data


def build_row_spec(**kwargs):
    markers = [
        normalize_marker_name(value=marker)
        for marker in kwargs.get("markers", [])
        if str(marker).strip()
    ]

    cds_markers = sorted(
        {
            marker
            for marker in markers
            if classify_marker_category(marker_name=marker) == "CDS"
        }
    )

    rrna_markers = sorted(
        {
            marker
            for marker in markers
            if classify_marker_category(marker_name=marker) == "rRNAs"
        }
    )

    trna_markers = sorted(
        {
            marker
            for marker in markers
            if classify_marker_category(marker_name=marker) == "tRNAs"
        }
    )

    control_region_markers = sorted(
        {
            marker
            for marker in markers
            if classify_marker_category(marker_name=marker) == "Control Region"
        }
    )

    groups = [
        cds_markers,
        rrna_markers,
        trna_markers,
        control_region_markers,
        [GENOME_SIZE_LABEL],
    ]

    row_spec = []

    nonempty_groups = [
        group
        for group in groups
        if group
    ]

    for group_index, marker_group in enumerate(nonempty_groups):
        for marker_name in marker_group:
            row_spec.append(
                {
                    "kind": "marker",
                    "name": marker_name,
                    "label": marker_name,
                }
            )

        if group_index < len(nonempty_groups) - 1:
            row_spec.append(
                {
                    "kind": "spacer",
                    "name": "",
                    "label": "",
                }
            )

    return row_spec


def add_global_seed_bar(**kwargs):
    axis = kwargs.get("axis")
    column_table = kwargs.get("column_table")
    seed_palette = kwargs.get("seed_palette", {})
    bar_height = float(
        kwargs.get("bar_height", 0.15)
    )
    bar_offset = float(
        kwargs.get("bar_offset", 0.30)
    )

    if axis is None or column_table is None or column_table.empty:
        return

    for seed_name, seed_group in column_table.groupby(
        "Seed Input",
        sort=False,
    ):
        positions = seed_group.index.tolist()
        start_position = min(positions)
        end_position = max(positions) + 1

        axis.add_patch(
            Rectangle(
                (
                    start_position,
                    -bar_offset,
                ),
                end_position - start_position,
                bar_height,
                transform=axis.transData,
                facecolor=seed_palette.get(seed_name, "#000000"),
                edgecolor="none",
                linewidth=0,
                clip_on=False,
                zorder=12,
            )
        )




def normalize_heatmap_row(**kwargs):
    """Normalize one marker row independently to the 0-1 color range."""

    row_values = kwargs.get("row_values")

    numeric_row = row_values.apply(
        pd.to_numeric,
        errors="coerce",
    )

    valid_values = numeric_row.stack().dropna()

    if valid_values.empty:
        return numeric_row

    minimum_value = float(valid_values.min())
    maximum_value = float(valid_values.max())

    if minimum_value == maximum_value:
        normalized_row = numeric_row.copy()
        normalized_row.loc[:, :] = 0.5
        return normalized_row.where(
            numeric_row.notna()
        )

    return (
        numeric_row - minimum_value
    ) / (
        maximum_value - minimum_value
    )


def get_modal_reference(**kwargs):
    """Return the modal base-pair value of one marker row."""

    row_values = kwargs.get("row_values")

    valid_values = pd.to_numeric(
        row_values.stack(),
        errors="coerce",
    ).dropna()

    if valid_values.empty:
        return None

    modal_values = valid_values.mode()

    if modal_values.empty:
        return float(valid_values.iloc[0])

    return float(modal_values.iloc[0])


def apply_mismatch_alpha(**kwargs):
    """
    Fade cells that differ from the modal value of the current marker row.

    mismatch_alpha is the visible opacity retained by different values.
    A value of 1.0 keeps them fully visible, while 0.2 makes them pale.
    """

    axis = kwargs.get("axis")
    row_values = kwargs.get("row_values")
    mismatch_alpha = float(
        kwargs.get(
            "mismatch_alpha",
            0.35,
        )
    )

    mismatch_alpha = min(
        max(mismatch_alpha, 0.0),
        1.0,
    )

    if axis is None:
        return

    reference_value = get_modal_reference(
        row_values=row_values,
    )

    if reference_value is None:
        return

    for column_position in range(row_values.shape[1]):
        current_value = row_values.iloc[
            0,
            column_position,
        ]

        if pd.isna(current_value):
            continue

        if float(current_value) == reference_value:
            continue

        axis.add_patch(
            Rectangle(
                (
                    column_position,
                    0,
                ),
                1,
                1,
                facecolor="white",
                edgecolor="none",
                linewidth=0,
                alpha=(1.0 - mismatch_alpha),
                zorder=4,
            )
        )


def plot_marker_length_heatmaps(**kwargs):
    """
    Plot one independently normalized heatmap row per marker.

    The figure uses one shared colorbar. Min and Max refer to the smallest
    and largest value inside each marker row, while the annotations retain
    the original values in base pairs.
    """

    dataframe = kwargs.get("dataframe")
    output_dir = kwargs.get(
        "output_dir",
        "marker_length_heatmaps",
    )
    fig_format = str(
        kwargs.get(
            "fig_format",
            "png",
        )
    ).lower()
    dpi = int(kwargs.get("dpi", 300))
    annotate = bool(kwargs.get("annotate", True))
    cmap = kwargs.get("cmap", "viridis")
    mismatch_alpha = float(
        kwargs.get(
            "mismatch_alpha",
            0.35,
        )
    )
    title_fontsize = int(kwargs.get("title_fontsize", 20))
    legend_fontsize = int(kwargs.get("legend_fontsize", 11))
    legend_title_fontsize = int(
        kwargs.get(
            "legend_title_fontsize",
            13,
        )
    )
    x_tick_size = int(kwargs.get("x_tick_size", 8))
    y_tick_size = int(kwargs.get("y_tick_size", 9))
    annotation_size = float(kwargs.get("annotation_size", 6))
    bar_linewidth = float(kwargs.get("bar_linewidth", 8))
    maximum_figure_width = float(
        kwargs.get(
            "maximum_figure_width",
            26,
        )
    )
    maximum_figure_height = float(
        kwargs.get(
            "maximum_figure_height",
            24,
        )
    )

    plot_data = prepare_marker_length_plot_data(
        dataframe=dataframe,
    )

    if plot_data.empty:
        logging.warning(
            "Marker length heatmaps skipped because the dataframe is empty"
        )
        return []

    os.makedirs(
        output_dir,
        exist_ok=True,
    )

    generated_files = []

    for project_name in sorted(
        plot_data["Project name"].dropna().unique()
    ):
        project_data = plot_data[
            plot_data["Project name"] == project_name
        ].copy()

        if project_data.empty:
            continue

        column_table = (
            project_data[
                [
                    "Seed Input",
                    "K-mer",
                    "Column key",
                ]
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "Seed Input",
                    "K-mer",
                ]
            )
            .reset_index(drop=True)
        )

        column_order = column_table["Column key"].tolist()
        x_tick_labels = column_table["K-mer"].astype(str).tolist()
        seed_order = column_table["Seed Input"].drop_duplicates().tolist()

        seed_palette = dict(
            zip(
                seed_order,
                sns.color_palette(
                    "colorblind",
                    len(seed_order),
                ),
            )
        )

        row_spec = build_row_spec(
            markers=project_data["Marker"].dropna().unique(),
        )

        biological_markers = [
            row["name"]
            for row in row_spec
            if row["kind"] == "marker"
            and row["name"] != GENOME_SIZE_LABEL
        ]

        marker_pivot = project_data.pivot_table(
            index="Marker",
            columns="Column key",
            values="Marker length",
            aggfunc="mean",
        )

        marker_pivot = marker_pivot.reindex(
            index=biological_markers,
            columns=column_order,
        )

        genome_size_values = marker_pivot.sum(
            axis=0,
            min_count=1,
        )

        marker_pivot.loc[
            GENOME_SIZE_LABEL
        ] = genome_size_values

        height_ratios = [
            0.30 if row["kind"] == "spacer" else 1.0
            for row in row_spec
        ]

        figure_width = min(
            maximum_figure_width,
            max(
                15,
                len(column_order) * 0.55 + 2.8,
            ),
        )

        figure_height = min(
            maximum_figure_height,
            max(
                10,
                len(row_spec) * 0.55 + 2.8,
            ),
        )

        figure = plt.figure(
            figsize=(
                figure_width,
                figure_height,
            )
        )

        grid = GridSpec(
            nrows=len(row_spec),
            ncols=2,
            figure=figure,
            width_ratios=[
                1.0,
                0.035,
            ],
            height_ratios=height_ratios,
            hspace=0.15,
            wspace=0.04,
        )

        colorbar_axis = figure.add_subplot(
            grid[:, 1]
        )

        scalar_mappable = ScalarMappable(
            norm=Normalize(
                vmin=0,
                vmax=1,
            ),
            cmap=plt.get_cmap(cmap),
        )
        scalar_mappable.set_array([])

        colorbar = figure.colorbar(
            scalar_mappable,
            cax=colorbar_axis,
        )
        colorbar.outline.set_visible(False)
        colorbar.set_ticks([0, 1])
        colorbar.set_ticklabels(["Min", "Max"])
        colorbar.ax.tick_params(
            labelsize=10,
            length=0,
            pad=3,
        )
        colorbar.set_label(
            "Relative length within each marker",
            fontsize=11,
            labelpad=8,
        )

        first_marker_axis = None
        last_marker_axis = None

        for row_index, row in enumerate(row_spec):
            if row["kind"] == "spacer":
                spacer_axis = figure.add_subplot(
                    grid[row_index, 0]
                )
                spacer_axis.set_axis_off()
                continue

            marker_name = row["name"]

            heatmap_axis = figure.add_subplot(
                grid[row_index, 0]
            )

            if first_marker_axis is None:
                first_marker_axis = heatmap_axis

            last_marker_axis = heatmap_axis

            raw_row_values = marker_pivot.loc[
                [marker_name],
                column_order,
            ]

            valid_values = raw_row_values.stack().dropna()

            if valid_values.empty:
                heatmap_axis.set_axis_off()
                continue

            normalized_row = normalize_heatmap_row(
                row_values=raw_row_values,
            )

            sns.heatmap(
                normalized_row,
                ax=heatmap_axis,
                cmap=cmap,
                vmin=0,
                vmax=1,
                annot=(
                    raw_row_values
                    if annotate
                    else False
                ),
                fmt=".0f",
                annot_kws={
                    "size": annotation_size,
                },
                linewidths=0.4,
                linecolor="white",
                mask=raw_row_values.isna(),
                cbar=False,
                xticklabels=x_tick_labels,
                yticklabels=[row["label"]],
            )

            apply_mismatch_alpha(
                axis=heatmap_axis,
                row_values=raw_row_values,
                mismatch_alpha=mismatch_alpha,
            )

            heatmap_axis.tick_params(
                axis="x",
                bottom=False,
                labelbottom=False,
            )
            heatmap_axis.tick_params(
                axis="y",
                rotation=0,
                labelsize=y_tick_size,
                length=0,
                pad=6,
            )
            heatmap_axis.set_ylabel("")

        if last_marker_axis is not None:
            last_marker_axis.tick_params(
                axis="x",
                rotation=0,
                labelsize=x_tick_size,
                pad=6,
                bottom=True,
                labelbottom=True,
            )
            last_marker_axis.set_xlabel(
                "K-mer",
                fontsize=12,
                labelpad=10,
            )

        if first_marker_axis is not None:
            add_global_seed_bar(
                axis=first_marker_axis,
                column_table=column_table,
                seed_palette=seed_palette,
            )

        figure.suptitle(
            (
                "Marker lengths across circularized "
                f"rotated assemblies, {project_name}"
            ),
            fontsize=title_fontsize,
            fontweight="bold",
            y=0.965,
        )

        legend_handles = [
            Line2D(
                [0],
                [0],
                color=seed_palette[seed_name],
                linewidth=bar_linewidth,
                label=seed_name,
                solid_capstyle="butt",
            )
            for seed_name in seed_order
        ]

        figure.legend(
            handles=legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.01),
            ncol=min(len(legend_handles), 8),
            frameon=False,
            title="Seed Input",
            fontsize=legend_fontsize,
            title_fontsize=legend_title_fontsize,
            handlelength=2.0,
            handletextpad=0.5,
            columnspacing=0.9,
        )

        figure.subplots_adjust(
            top=0.86,
            bottom=0.06,
            left=0.18,
            right=0.95,
        )

        output_path = os.path.join(
            output_dir,
            f"{project_name}_marker_lengths.{fig_format}",
        )

        figure.savefig(
            output_path,
            dpi=dpi,
            bbox_inches="tight",
        )

        plt.close(figure)

        logging.info(
            "Marker length heatmap written: %s",
            output_path,
        )

        generated_files.append(output_path)

    return generated_files