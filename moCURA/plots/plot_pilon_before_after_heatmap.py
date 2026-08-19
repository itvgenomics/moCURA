import logging
import os
import string

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

from .plot_pilon_heatmap import (
    add_panel_header,
    build_metric_normalization,
    draw_top_group_bar,
    prepare_pilon_heatmap_data,
    resolve_colormap,
    split_seed_inputs,
    style_colorbar,
)


DEFAULT_PILON_COMPARISON_METRICS = [
    {
        "name": "Genome length comparison",
        "title": "Genome length before and after Pilon (bp)",
        "type": "before_after",
        "before_column": "Largest contig",
        "after_column": "Pilon Total bases",
        "format": ".0f",
        "cmap": "cividis",
    },
    {
        "name": "Pilon Confirmed %",
        "title": "Confirmed bases after Pilon (%)",
        "type": "single",
        "column": "Pilon Confirmed %",
        "format": ".1f",
        "cmap": "viridis",
    },
    {
        "name": "Pilon Corrected bases",
        "title": "Bases corrected by Pilon",
        "type": "single",
        "column": "Pilon Corrected bases",
        "format": ".0f",
        "cmap": "YlOrRd",
    },
    {
        "name": "Pilon Size change",
        "title": "Genome length change after Pilon (bp)",
        "type": "single",
        "column": "Pilon Size change",
        "format": "+.0f",
        "cmap": "coolwarm",
        "center": 0,
    },
]


def prepare_before_after_data(**kwargs):
    """Prepare the long table used by the paired genome length heatmap."""

    dataframe = kwargs.get("dataframe")
    plot_data = prepare_pilon_heatmap_data(dataframe=dataframe)

    if plot_data.empty:
        return plot_data, pd.DataFrame()

    before_data = plot_data[
        [
            "Project name",
            "Seed Input",
            "K-mer",
            "Largest contig",
        ]
    ].copy()
    before_data = before_data.rename(
        columns={"Largest contig": "Genome length"}
    )
    before_data["Stage"] = "Before"

    after_data = plot_data[
        [
            "Project name",
            "Seed Input",
            "K-mer",
            "Pilon Total bases",
        ]
    ].copy()
    after_data = after_data.rename(
        columns={"Pilon Total bases": "Genome length"}
    )
    after_data["Stage"] = "After"

    comparison_data = pd.concat(
        [before_data, after_data],
        ignore_index=True,
    )
    comparison_data["Genome length"] = pd.to_numeric(
        comparison_data["Genome length"],
        errors="coerce",
    )
    comparison_data = comparison_data.dropna(
        subset=[
            "Project name",
            "Seed Input",
            "K-mer",
            "Genome length",
            "Stage",
        ]
    ).copy()
    comparison_data["K-mer"] = comparison_data["K-mer"].astype(int)
    comparison_data["Stage"] = pd.Categorical(
        comparison_data["Stage"],
        categories=["Before", "After"],
        ordered=True,
    )

    return plot_data, comparison_data


def build_paired_row_order(**kwargs):
    """Return Project and Stage rows in Before then After order."""

    project_order = kwargs.get("project_order", [])

    return pd.MultiIndex.from_tuples(
        [
            (project_name, stage_name)
            for project_name in project_order
            for stage_name in ("Before", "After")
        ],
        names=["Project name", "Stage"],
    )


def configure_paired_project_axis(**kwargs):
    """Center each project label between its Before and After rows."""

    axis = kwargs.get("axis")
    paired_row_order = kwargs.get("paired_row_order")
    stage_palette = kwargs.get("stage_palette", {})
    show_labels = bool(kwargs.get("show_labels", False))
    label_size = float(kwargs.get("label_size", 9))
    y_label_fontsize = float(kwargs.get("y_label_fontsize", 11))
    bar_linewidth = float(kwargs.get("bar_linewidth", 10))
    stage_bar_offset = float(kwargs.get("stage_bar_offset", 0.030))

    if axis is None or paired_row_order is None:
        return

    if not show_labels:
        axis.tick_params(
            axis="y",
            left=False,
            labelleft=False,
        )
        axis.set_ylabel("")
        return

    project_names = [
        str(paired_row_order[row_position][0])
        for row_position in range(0, len(paired_row_order), 2)
    ]
    project_tick_positions = [
        row_position + 1
        for row_position in range(0, len(paired_row_order), 2)
    ]

    axis.set_yticks(project_tick_positions)
    axis.set_yticklabels(
        project_names,
        rotation=0,
        fontsize=label_size,
        verticalalignment="center",
    )
    axis.tick_params(
        axis="y",
        left=False,
        labelleft=True,
        pad=5,
    )
    axis.set_ylabel(
        "Project name",
        fontsize=y_label_fontsize,
    )

    stage_transform = blended_transform_factory(
        axis.transAxes,
        axis.transData,
    )

    for row_position, (_, stage_name) in enumerate(paired_row_order):
        axis.plot(
            [-stage_bar_offset, -stage_bar_offset],
            [row_position, row_position + 1],
            transform=stage_transform,
            color=stage_palette[stage_name],
            linewidth=bar_linewidth,
            solid_capstyle="butt",
            clip_on=False,
            zorder=6,
        )

    number_of_projects = len(paired_row_order) // 2

    for project_position in range(1, number_of_projects):
        axis.axhline(
            project_position * 2,
            color="white",
            linewidth=1.2,
            zorder=7,
        )


def configure_single_project_axis(**kwargs):
    """Configure the Y axis for metrics with one row per project."""

    axis = kwargs.get("axis")
    project_order = kwargs.get("project_order", [])
    show_labels = bool(kwargs.get("show_labels", False))
    label_size = float(kwargs.get("label_size", 9))
    y_label_fontsize = float(kwargs.get("y_label_fontsize", 11))

    if axis is None:
        return

    if show_labels:
        axis.set_yticks(
            [
                row_position + 0.5
                for row_position in range(len(project_order))
            ]
        )
        axis.set_yticklabels(
            project_order,
            rotation=0,
            fontsize=label_size,
        )
        axis.tick_params(
            axis="y",
            left=True,
            labelleft=True,
            length=3,
            pad=5,
        )
        axis.set_ylabel(
            "Project name",
            fontsize=y_label_fontsize,
        )
    else:
        axis.tick_params(
            axis="y",
            left=False,
            labelleft=False,
        )
        axis.set_ylabel("")


def build_before_after_reference(**kwargs):
    """Build the modal length for each Project and Stage pair."""

    comparison_data = kwargs.get("comparison_data")

    if comparison_data is None or comparison_data.empty:
        return pd.Series(dtype=float)

    return (
        comparison_data.groupby(
            ["Project name", "Stage"],
            observed=True,
        )["Genome length"]
        .apply(
            lambda values: (
                values.dropna().mode().iloc[0]
                if not values.dropna().empty
                else None
            )
        )
    )


def add_paired_mismatch_alpha(**kwargs):
    """Fade paired length cells that differ from the stage modal value."""

    axis = kwargs.get("axis")
    pivot = kwargs.get("pivot")
    reference_values = kwargs.get("reference_values")
    mismatch_alpha = float(kwargs.get("mismatch_alpha", 0.15))

    if axis is None or pivot is None or pivot.empty or reference_values is None:
        return

    mismatch_alpha = min(max(mismatch_alpha, 0), 1)

    for row_position, row_key in enumerate(pivot.index):
        reference_value = reference_values.get(row_key)

        if reference_value is None or pd.isna(reference_value):
            continue

        for column_position in range(pivot.shape[1]):
            current_value = pivot.iloc[row_position, column_position]

            if pd.isna(current_value) or current_value == reference_value:
                continue

            axis.add_patch(
                Rectangle(
                    (column_position, row_position),
                    1,
                    1,
                    facecolor="white",
                    alpha=1 - mismatch_alpha,
                    edgecolor="none",
                    linewidth=0,
                    zorder=2,
                )
            )


def build_metric_values(**kwargs):
    """Return values used to calculate one metric color scale."""

    plot_data = kwargs.get("plot_data")
    comparison_data = kwargs.get("comparison_data")
    metric_settings = kwargs.get("metric_settings", {})

    if metric_settings.get("type") == "before_after":
        return comparison_data["Genome length"]

    return plot_data[metric_settings["column"]]


def plot_pilon_before_after_heatmap(**kwargs):
    """Plot paired genome lengths and the main Pilon metrics."""

    dataframe = kwargs.get("dataframe")
    output_file = kwargs.get(
        "output_file",
        "pilon_before_after_heatmap",
    )
    fig_format = str(kwargs.get("fig_format", "png")).lower()
    dpi = int(kwargs.get("dpi", 300))
    annotate = bool(kwargs.get("annotate", True))
    mismatch_alpha = float(kwargs.get("mismatch_alpha", 0.15))
    metrics_per_row = max(1, int(kwargs.get("metrics_per_row", 2)))
    gene_rows_per_metric = max(1, int(kwargs.get("gene_rows_per_metric", 2)))

    category_column_spacing = float(
        kwargs.get("category_column_spacing", 0.08)
    )
    category_row_spacing = float(
        kwargs.get("category_row_spacing", 0.16)
    )
    gene_row_spacing = float(
        kwargs.get("gene_row_spacing", 0.18)
    )
    gene_block_spacing = float(
        kwargs.get("gene_block_spacing", 0.025)
    )
    category_title_height = float(
        kwargs.get("category_title_height", 0.13)
    )
    colorbar_width = float(
        kwargs.get("colorbar_width", 0.025)
    )

    bar_linewidth = float(kwargs.get("bar_linewidth", 10))
    stage_bar_offset = float(kwargs.get("stage_bar_offset", 0.030))
    x_tick_pad = float(kwargs.get("x_tick_pad", 6))
    x_label_pad = float(kwargs.get("x_label_pad", 10))
    plot_height_scale = float(kwargs.get("plot_height_scale", 1.25))

    panel_title_fontsize = float(
        kwargs.get("panel_title_fontsize", 24)
    )
    panel_letter_fontsize = float(
        kwargs.get("panel_letter_fontsize", 17)
    )
    legend_fontsize = float(kwargs.get("legend_fontsize", 13))
    legend_title_fontsize = float(
        kwargs.get("legend_title_fontsize", 15)
    )
    figure_title_fontsize = float(
        kwargs.get("figure_title_fontsize", 19)
    )
    axis_label_fontsize = float(
        kwargs.get("axis_label_fontsize", 11)
    )
    colorbar_label_fontsize = float(
        kwargs.get("colorbar_label_fontsize", 11)
    )
    colorbar_tick_fontsize = float(
        kwargs.get("colorbar_tick_fontsize", 10)
    )

    metrics = kwargs.get(
        "metrics",
        DEFAULT_PILON_COMPARISON_METRICS,
    )
    figure_title = kwargs.get(
        "figure_title",
        "Genome assembly comparison before and after Pilon",
    )
    panel_letters = kwargs.get("panel_letters", string.ascii_uppercase)

    plot_data, comparison_data = prepare_before_after_data(
        dataframe=dataframe,
    )

    if plot_data.empty or comparison_data.empty:
        logging.warning(
            "Before and after Pilon heatmap skipped because no valid rows were found"
        )
        return None

    project_order = (
        plot_data["Project name"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    seed_order = sorted(
        plot_data["Seed Input"]
        .dropna()
        .unique()
    )

    available_metrics = []

    for metric_settings in metrics:
        if metric_settings.get("type") == "before_after":
            if comparison_data["Genome length"].notna().any():
                available_metrics.append(metric_settings)
            continue

        metric_column = metric_settings.get("column")

        if (
            metric_column in plot_data.columns
            and plot_data[metric_column].notna().any()
        ):
            available_metrics.append(metric_settings)

    if not project_order or not seed_order or not available_metrics:
        logging.warning(
            "Before and after Pilon heatmap skipped because required values are missing"
        )
        return None

    metrics_per_row = min(metrics_per_row, len(available_metrics))
    number_of_metric_rows = (
        len(available_metrics) + metrics_per_row - 1
    ) // metrics_per_row

    seed_groups = split_seed_inputs(
        seed_order=seed_order,
        number_of_rows=gene_rows_per_metric,
    )

    seed_widths = {}

    for seed_name in seed_order:
        number_of_kmers = (
            plot_data.loc[
                plot_data["Seed Input"] == seed_name,
                "K-mer",
            ]
            .dropna()
            .astype(int)
            .nunique()
        )
        seed_widths[seed_name] = max(number_of_kmers, 1)

    maximum_group_width = max(
        sum(seed_widths[seed_name] for seed_name in seed_group)
        for seed_group in seed_groups
    )

    paired_row_order = build_paired_row_order(
        project_order=project_order,
    )
    largest_row_count = len(paired_row_order)

    panel_width = max(8, maximum_group_width * 0.60)
    internal_row_height = max(
        5.0,
        largest_row_count * 0.30 + 1.5,
    ) * plot_height_scale
    panel_height = (
        0.45
        + len(seed_groups) * internal_row_height
    )

    figure_width = max(14, panel_width * metrics_per_row)
    figure_height = max(
        10,
        panel_height * number_of_metric_rows,
    )

    annotation_size = max(
        4,
        min(8, 280 / max(maximum_group_width, 1)),
    )
    x_tick_size = max(
        5,
        min(8, 310 / max(maximum_group_width, 1)),
    )
    project_label_size = max(
        7,
        min(11, 90 / max(len(project_order), 1)),
    )

    seed_palette = dict(
        zip(
            seed_order,
            sns.color_palette("colorblind", len(seed_order)),
        )
    )
    stage_colors = sns.color_palette("colorblind", 2)
    stage_palette = {
        "Before": stage_colors[0],
        "After": stage_colors[1],
    }

    paired_reference = build_before_after_reference(
        comparison_data=comparison_data,
    )

    figure = plt.figure(
        figsize=(figure_width, figure_height)
    )
    outer_grid = figure.add_gridspec(
        number_of_metric_rows,
        metrics_per_row,
        wspace=category_column_spacing,
        hspace=category_row_spacing,
    )

    for metric_index, metric_settings in enumerate(available_metrics):
        metric_row = metric_index // metrics_per_row
        metric_column = metric_index % metrics_per_row

        metric_grid = outer_grid[
            metric_row,
            metric_column,
        ].subgridspec(
            len(seed_groups) + 1,
            2,
            height_ratios=[
                category_title_height,
                *([1] * len(seed_groups)),
            ],
            width_ratios=[1, colorbar_width],
            wspace=0.04,
            hspace=gene_row_spacing,
        )

        title_axis = figure.add_subplot(metric_grid[0, :])
        panel_letter = (
            panel_letters[metric_index]
            if metric_index < len(panel_letters)
            else str(metric_index + 1)
        )
        add_panel_header(
            ax=title_axis,
            letter=panel_letter,
            title=metric_settings["title"],
            title_fontsize=panel_title_fontsize,
            letter_fontsize=panel_letter_fontsize,
        )

        colorbar_axis = figure.add_subplot(metric_grid[1:, 1])
        metric_values = build_metric_values(
            plot_data=plot_data,
            comparison_data=comparison_data,
            metric_settings=metric_settings,
        )
        metric_normalization = build_metric_normalization(
            values=metric_values,
            settings=metric_settings,
        )
        metric_colormap = resolve_colormap(
            colormap_name=metric_settings.get("cmap", "cividis")
        )

        for internal_row_index, seed_group in enumerate(seed_groups):
            current_width_ratios = [
                seed_widths[seed_name]
                for seed_name in seed_group
            ]
            current_group_width = sum(current_width_ratios)
            missing_width = maximum_group_width - current_group_width
            include_spacer = missing_width > 0

            if include_spacer:
                row_width_ratios = [
                    *current_width_ratios,
                    missing_width,
                ]
                number_of_columns = len(seed_group) + 1
            else:
                row_width_ratios = current_width_ratios
                number_of_columns = len(seed_group)

            gene_grid = metric_grid[
                internal_row_index + 1,
                0,
            ].subgridspec(
                1,
                number_of_columns,
                width_ratios=row_width_ratios,
                wspace=gene_block_spacing,
            )

            for seed_index, seed_name in enumerate(seed_group):
                axis = figure.add_subplot(gene_grid[0, seed_index])
                kmer_order = sorted(
                    plot_data.loc[
                        plot_data["Seed Input"] == seed_name,
                        "K-mer",
                    ]
                    .dropna()
                    .astype(int)
                    .unique()
                )

                if not kmer_order:
                    axis.set_visible(False)
                    continue

                if metric_settings.get("type") == "before_after":
                    seed_subset = comparison_data[
                        comparison_data["Seed Input"] == seed_name
                    ].copy()
                    pivot = seed_subset.pivot_table(
                        index=["Project name", "Stage"],
                        columns="K-mer",
                        values="Genome length",
                        aggfunc="mean",
                        observed=False,
                    )
                    pivot = pivot.reindex(
                        index=paired_row_order,
                        columns=kmer_order,
                    )
                else:
                    seed_subset = plot_data[
                        plot_data["Seed Input"] == seed_name
                    ].copy()
                    pivot = seed_subset.pivot_table(
                        index="Project name",
                        columns="K-mer",
                        values=metric_settings["column"],
                        aggfunc="mean",
                    )
                    pivot = pivot.reindex(
                        index=project_order,
                        columns=kmer_order,
                    )

                sns.heatmap(
                    pivot,
                    ax=axis,
                    cmap=metric_colormap,
                    norm=metric_normalization,
                    annot=annotate,
                    fmt=metric_settings.get("format", ".1f"),
                    annot_kws={"size": annotation_size},
                    linewidths=0.5,
                    linecolor="white",
                    mask=pivot.isna(),
                    cbar=False,
                    yticklabels=False,
                )

                if metric_settings.get("type") == "before_after":
                    add_paired_mismatch_alpha(
                        axis=axis,
                        pivot=pivot,
                        reference_values=paired_reference,
                        mismatch_alpha=mismatch_alpha,
                    )
                    configure_paired_project_axis(
                        axis=axis,
                        paired_row_order=paired_row_order,
                        stage_palette=stage_palette,
                        show_labels=seed_index == 0,
                        label_size=project_label_size,
                        y_label_fontsize=axis_label_fontsize,
                        bar_linewidth=bar_linewidth,
                        stage_bar_offset=stage_bar_offset,
                    )
                else:
                    configure_single_project_axis(
                        axis=axis,
                        project_order=project_order,
                        show_labels=seed_index == 0,
                        label_size=project_label_size,
                        y_label_fontsize=axis_label_fontsize,
                    )

                draw_top_group_bar(
                    axis=axis,
                    color=seed_palette[seed_name],
                    linewidth=bar_linewidth,
                )

                axis.set_xlabel(
                    "K-mer",
                    fontsize=axis_label_fontsize,
                    labelpad=x_label_pad,
                )
                axis.tick_params(
                    axis="x",
                    rotation=90,
                    labelsize=x_tick_size,
                    pad=x_tick_pad,
                )

            if include_spacer:
                spacer_axis = figure.add_subplot(
                    gene_grid[0, len(seed_group)]
                )
                spacer_axis.set_axis_off()

        scalar_mappable = ScalarMappable(
            norm=metric_normalization,
            cmap=metric_colormap,
        )
        scalar_mappable.set_array([])
        colorbar = figure.colorbar(
            scalar_mappable,
            cax=colorbar_axis,
        )
        style_colorbar(
            colorbar=colorbar,
            label=metric_settings["title"],
            label_fontsize=colorbar_label_fontsize,
            tick_fontsize=colorbar_tick_fontsize,
        )

    total_panel_count = number_of_metric_rows * metrics_per_row

    for empty_metric_index in range(len(available_metrics), total_panel_count):
        empty_row = empty_metric_index // metrics_per_row
        empty_column = empty_metric_index % metrics_per_row
        empty_axis = figure.add_subplot(
            outer_grid[empty_row, empty_column]
        )
        empty_axis.set_axis_off()

    stage_handles = [
        Line2D(
            [0],
            [0],
            color=stage_palette[stage_name],
            linewidth=bar_linewidth,
            solid_capstyle="butt",
            label=stage_name,
        )
        for stage_name in ("Before", "After")
    ]
    seed_handles = [
        Line2D(
            [0],
            [0],
            color=seed_palette[seed_name],
            linewidth=bar_linewidth,
            solid_capstyle="butt",
            label=seed_name,
        )
        for seed_name in seed_order
    ]

    figure.suptitle(
        figure_title,
        fontsize=figure_title_fontsize,
        fontweight="bold",
        y=0.995,
    )

    stage_legend = figure.legend(
        handles=stage_handles,
        loc="upper left",
        bbox_to_anchor=(0.060, 0.968),
        ncol=2,
        frameon=False,
        title="Genome stage",
        fontsize=legend_fontsize,
        title_fontsize=legend_title_fontsize,
        handlelength=2.8,
        handletextpad=0.7,
        columnspacing=1.2,
    )
    figure.add_artist(stage_legend)

    figure.legend(
        handles=seed_handles,
        loc="upper center",
        bbox_to_anchor=(0.62, 0.968),
        ncol=min(len(seed_handles), 8),
        frameon=False,
        title="Seed Input",
        fontsize=legend_fontsize,
        title_fontsize=legend_title_fontsize,
        handlelength=2.8,
        handletextpad=0.7,
        columnspacing=1.2,
        labelspacing=0.7,
    )

    figure.subplots_adjust(
        top=0.90,
        bottom=0.060,
        left=0.070,
        right=0.975,
    )

    output_directory = os.path.dirname(output_file)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True)

    output_path = f"{output_file}.{fig_format}"
    figure.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
    )
    plt.close(figure)

    logging.info(
        "Before and after Pilon heatmap written: %s",
        output_path,
    )
    return output_path
