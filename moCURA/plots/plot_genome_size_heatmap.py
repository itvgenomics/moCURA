import logging
import os

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from .build_plot_styles import build_plot_styles
from .plot_pilon_heatmap import (add_panel_header, draw_top_group_bar, style_colorbar)


def row_mode_or_none(**kwargs):
    """Return the most frequent non-null value in one row."""

    row = kwargs.get("row")
    valid_values = pd.to_numeric(
        row,
        errors="coerce",
    ).dropna()

    if valid_values.empty:
        return None

    return valid_values.mode().iloc[0]


def plot_genome_size_heatmap(**kwargs):
    """Plot largest-contig lengths grouped by Seed Input and K-mer."""

    dataframe = kwargs.get("dataframe")
    output_file = kwargs.get(
        "output_file",
        "genome_size_heatmap",
    )
    fig_format = str(kwargs.get("fig_format", "png")).lower()
    metric = str(kwargs.get("metric", "Largest contig"))
    heatmap_cmap = str(kwargs.get("cmap", "viridis"))
    mismatch_alpha = float(kwargs.get("mismatch_alpha", 0.25))
    dpi = int(kwargs.get("dpi", 300))
    annotate = bool(kwargs.get("annotate", True))

    bar_linewidth = float(kwargs.get("bar_linewidth", 10))
    x_tick_pad = float(kwargs.get("x_tick_pad", 7.5))
    x_label_pad = float(kwargs.get("x_label_pad", 15))
    plot_height_scale = float(kwargs.get("plot_height_scale", 1.5))
    panel_title_fontsize = float(
        kwargs.get("panel_title_fontsize", 20)
    )
    panel_letter_fontsize = float(
        kwargs.get("panel_letter_fontsize", 15)
    )
    legend_fontsize = float(kwargs.get("legend_fontsize", 13))
    legend_title_fontsize = float(
        kwargs.get("legend_title_fontsize", 15)
    )
    colorbar_label_fontsize = float(
        kwargs.get("colorbar_label_fontsize", 11)
    )
    colorbar_tick_fontsize = float(
        kwargs.get("colorbar_tick_fontsize", 10)
    )
    project_label_fontsize = float(
        kwargs.get("project_label_fontsize", 9)
    )
    axis_label_fontsize = float(
        kwargs.get("axis_label_fontsize", 11)
    )

    if dataframe is None or dataframe.empty:
        logging.warning(
            "Genome-size heatmap skipped because no data were provided"
        )
        return None

    heat_data = dataframe.dropna(
        subset=[
            metric,
            "Seed Input",
            "K-mer",
        ]
    ).copy()

    if heat_data.empty:
        logging.warning(
            "Genome-size heatmap skipped because there are no valid rows"
        )
        return None

    heat_data["K-mer"] = pd.to_numeric(
        heat_data["K-mer"],
        errors="coerce",
    )
    heat_data[metric] = pd.to_numeric(
        heat_data[metric],
        errors="coerce",
    )
    heat_data = heat_data.dropna(
        subset=["K-mer", metric]
    ).copy()
    heat_data["K-mer"] = heat_data["K-mer"].astype(int)

    seed_palette, _ = build_plot_styles(
        dataframe=heat_data
    )

    pivot_full = heat_data.pivot_table(
        index="Project name",
        columns=["Seed Input", "K-mer"],
        values=metric,
        aggfunc="mean",
    )

    if pivot_full.empty:
        logging.warning(
            "Genome-size heatmap skipped because the pivot table is empty"
        )
        return None

    project_order = [
        project_name
        for project_name in dataframe["Project name"].drop_duplicates()
        if project_name in pivot_full.index
    ]
    pivot_full = pivot_full.reindex(index=project_order)

    seeds_in_pivot = pivot_full.columns.get_level_values(0)
    seed_order = [
        seed_name
        for seed_name in sorted(heat_data["Seed Input"].unique())
        if seed_name in seeds_in_pivot
    ]

    if not seed_order:
        logging.warning(
            "Genome-size heatmap skipped because no seed groups were found"
        )
        return None

    minimum_value = heat_data[metric].min()
    maximum_value = heat_data[metric].max()
    width_ratios = [
        pivot_full[seed_name].shape[1]
        for seed_name in seed_order
    ]

    figure_width = max(
        sum(width_ratios) * 0.72,
        10,
    )
    figure_height = max(
        7,
        (0.46 * len(project_order) + 2.0)
        * plot_height_scale,
    )

    figure = plt.figure(
        figsize=(figure_width, figure_height)
    )
    main_grid = figure.add_gridspec(
        2,
        1,
        height_ratios=[0.12, 1],
        hspace=0.10,
    )

    title_axis = figure.add_subplot(main_grid[0, 0])
    add_panel_header(
        ax=title_axis,
        letter="A",
        title=(
            "Length of the largest contig per project, Seed Input, and K-mer"
        ),
        title_fontsize=panel_title_fontsize,
        letter_fontsize=panel_letter_fontsize,
        wrap_width=70,
    )

    heatmap_grid = main_grid[1, 0].subgridspec(
        1,
        len(seed_order),
        width_ratios=width_ratios,
        wspace=0.05,
    )

    axes = [
        figure.add_subplot(heatmap_grid[0, index])
        for index in range(len(seed_order))
    ]

    row_reference = pivot_full.apply(
        lambda row: row_mode_or_none(row=row),
        axis=1,
    )

    colorbar = None

    for index, (seed_name, axis) in enumerate(
        zip(seed_order, axes)
    ):
        subset = pivot_full[seed_name].sort_index(axis=1)
        is_last_axis = index == len(seed_order) - 1

        heatmap = sns.heatmap(
            subset,
            ax=axis,
            cmap=heatmap_cmap,
            vmin=minimum_value,
            vmax=maximum_value,
            annot=annotate,
            fmt=".0f",
            annot_kws={"size": 7},
            linewidths=0.5,
            linecolor="white",
            cbar=is_last_axis,
            cbar_kws=(
                {"label": "Genome size (bp)"}
                if is_last_axis
                else None
            ),
            yticklabels=False,
        )

        if is_last_axis and heatmap.collections:
            colorbar = heatmap.collections[0].colorbar

        axis.tick_params(
            axis="y",
            left=False,
            labelleft=False,
        )

        for row_index, project_name in enumerate(subset.index):
            reference_value = row_reference.get(project_name)

            for column_index in range(subset.shape[1]):
                value = subset.iloc[row_index, column_index]

                if (
                    pd.isna(value)
                    or reference_value is None
                    or value == reference_value
                ):
                    continue

                axis.add_patch(
                    Rectangle(
                        (column_index, row_index),
                        1,
                        1,
                        facecolor="white",
                        alpha=1 - mismatch_alpha,
                        edgecolor="none",
                        linewidth=0,
                        zorder=2,
                    )
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
        axis.set_ylabel("")
        axis.tick_params(
            axis="x",
            rotation=0,
            labelsize=project_label_fontsize,
            pad=x_tick_pad,
        )

    axes[0].set_yticks(
        [
            position + 0.5
            for position in range(len(project_order))
        ]
    )
    axes[0].set_yticklabels(
        project_order,
        rotation=0,
        fontsize=project_label_fontsize,
    )
    axes[0].tick_params(
        axis="y",
        left=True,
        labelleft=True,
        pad=5,
    )
    axes[0].set_ylabel(
        "Project name",
        fontsize=axis_label_fontsize,
    )

    style_colorbar(
        colorbar=colorbar,
        label="Genome size (bp)",
        label_fontsize=colorbar_label_fontsize,
        tick_fontsize=colorbar_tick_fontsize,
    )

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

    figure.legend(
        handles=seed_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.96),
        ncol=min(len(seed_handles), 7),
        frameon=False,
        title="Seed Input",
        fontsize=legend_fontsize,
        title_fontsize=legend_title_fontsize,
        handlelength=2.2,
        handletextpad=0.6,
        columnspacing=1.0,
    )

    figure.subplots_adjust(
        top=0.88,
        bottom=0.08,
        left=0.10,
        right=0.97,
    )

    output_directory = os.path.dirname(output_file)
    if output_directory:
        os.makedirs(
            output_directory,
            exist_ok=True,
            mode=0o755,
        )

    output_path = f"{output_file}.{fig_format}"
    figure.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
    )
    plt.close(figure)

    logging.info(
        "Genome-size heatmap written: %s",
        output_path,
    )

    return output_path
