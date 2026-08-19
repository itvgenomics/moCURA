import logging
import os
import string

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
from mpl_toolkits.axes_grid1 import make_axes_locatable

from .build_plot_styles import build_plot_styles
from .plot_pilon_heatmap import annoletter


RANGE_LINE = "#B0E4CC"
ROW_BACKGROUND = "#EEEEEE"


def add_marginal_distribution(**kwargs):
    """Add and return a marginal density axis above the main plot."""

    axis = kwargs.get("axis")
    data = kwargs.get("data", pd.DataFrame())
    x_variable = str(kwargs.get("x_variable"))

    marginal_axis = make_axes_locatable(axis).append_axes(
        "top",
        size="15%",
        pad=0.12,
        sharex=axis,
    )

    sns.kdeplot(
        data=data,
        x=x_variable,
        ax=marginal_axis,
        fill=True,
        color="#E76F51",
        alpha=0.75,
        linewidth=1,
        warn_singular=False,
    )

    marginal_axis.set_ylabel("")
    marginal_axis.set_xlabel("")
    marginal_axis.set_yticks([])
    marginal_axis.tick_params(
        bottom=False,
        labelbottom=False,
    )

    for spine_name in (
        "top",
        "right",
        "left",
    ):
        marginal_axis.spines[spine_name].set_visible(False)

    marginal_axis.grid(False)

    return marginal_axis


def build_legend_handles(**kwargs):
    seed_palette = kwargs.get("seed_palette", {})
    kmer_markers = kwargs.get("kmer_markers", {})
    range_line = kwargs.get("range_line", RANGE_LINE)
    marker_size = float(kwargs.get("marker_size", 15))

    seed_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=seed_name,
            markerfacecolor=color,
            markeredgecolor="#202020",
            markersize=marker_size,
        )
        for seed_name, color in seed_palette.items()
    ]

    kmer_handles = [
        Line2D(
            [0],
            [0],
            marker=marker,
            color="#202020",
            label=f"K-mer {kmer}",
            linestyle="None",
            markersize=marker_size,
        )
        for kmer, marker in kmer_markers.items()
    ]

    range_handle = Line2D(
        [0],
        [0],
        color=range_line,
        linewidth=4,
        solid_capstyle="butt",
        label="Genome range",
    )

    return seed_handles, kmer_handles, range_handle


def plot_points(**kwargs):
    """Add Seed Input colored and K-mer shaped points to one axis."""

    axis = kwargs.get("axis")
    data = kwargs.get("data")
    x_variable = str(kwargs.get("x_variable"))
    seed_palette = kwargs.get("seed_palette", {})
    kmer_markers = kwargs.get("kmer_markers", {})
    point_size = float(kwargs.get("point_size", 15))

    for kmer, subset in data.groupby("K-mer", sort=True):
        sns.stripplot(
            data=subset,
            x=x_variable,
            y="Project name",
            hue="Seed Input",
            palette=seed_palette,
            dodge=True,
            marker=kmer_markers[int(kmer)],
            size=point_size,
            edgecolor="#202020",
            linewidth=0.5,
            ax=axis,
        )

    if axis.legend_:
        axis.legend_.remove()


def add_alternating_row_background(**kwargs):
    axis = kwargs.get("axis")
    row_background = kwargs.get(
        "row_background",
        ROW_BACKGROUND,
    )

    for row_index, y_position in enumerate(axis.get_yticks()):
        if row_index % 2 == 0:
            axis.axhspan(
                y_position - 0.5,
                y_position + 0.5,
                color=row_background,
                alpha=1,
                zorder=-1,
            )


def plot_novoplasty_summary(**kwargs):
    """Plot standardized NOVOPlasty summary panels."""

    dataframe = kwargs.get("dataframe", pd.DataFrame())
    output_file = kwargs.get(
        "output_file",
        "novoplasty_summary",
    )
    dpi = int(kwargs.get("dpi", 300))
    fig_format = str(kwargs.get("fig_format", "png")).lower()
    range_line = kwargs.get("range_line", RANGE_LINE)
    row_background = kwargs.get(
        "row_background",
        ROW_BACKGROUND,
    )
    point_size = float(kwargs.get("point_size", 15))
    title_fontsize = float(kwargs.get("title_fontsize", 18))
    panel_letter_fontsize = float(
        kwargs.get("panel_letter_fontsize", 15)
    )
    legend_fontsize = float(kwargs.get("legend_fontsize", 12))
    legend_title_fontsize = float(
        kwargs.get("legend_title_fontsize", 14)
    )
    plot_height_scale = float(
        kwargs.get("plot_height_scale", 1.0)
    )

    if dataframe.empty:
        logging.warning(
            "No data available for plotting NOVOPlasty summary"
        )
        return None

    metrics = kwargs.get(
        "metrics",
        [
            "Total contigs",
            "Largest contig",
            "Smallest contig",
            "Average organelle coverage",
        ],
    )

    seed_palette, kmer_markers = build_plot_styles(
        dataframe=dataframe
    )

    grid = sns.PairGrid(
        dataframe,
        x_vars=metrics,
        y_vars=["Project name"],
        height=max(
            0.48 * dataframe["Project name"].nunique()
            * plot_height_scale,
            15,
        ),
        aspect=0.25,
    )

    for panel_index, (axis, x_variable) in enumerate(
        zip(grid.axes.flat, metrics)
    ):
        columns = [
            x_variable,
            "Project name",
            "Seed Input",
            "K-mer",
            "Genome range start",
            "Genome range end",
        ]
        data = grid.data[columns].copy()
        data[x_variable] = pd.to_numeric(
            data[x_variable],
            errors="coerce",
        )
        data = data.dropna(
            subset=[x_variable, "K-mer"]
        )

        if data.empty:
            logging.warning(
                "Skipping plot for %s because there are no valid rows",
                x_variable,
            )
            axis.set_visible(False)
            continue

        if x_variable == "Total contigs":
            data[x_variable] = data[x_variable].clip(upper=6)

        plot_points(
            axis=axis,
            data=data,
            x_variable=x_variable,
            seed_palette=seed_palette,
            kmer_markers=kmer_markers,
            point_size=point_size,
        )

        add_alternating_row_background(
            axis=axis,
            row_background=row_background,
        )

        left_limit, _ = axis.get_xlim()
        if left_limit < 0:
            axis.set_xlim(left=0)

        if x_variable == "Total contigs":
            axis.set_xticks(range(1, 7))
            axis.set_xticklabels(
                ["1", "2", "3", "4", "5", ">5"]
            )
            axis.set_xlim(0.5, 6.5)

        if x_variable in {
            "Largest contig",
            "Smallest contig",
        }:
            ranges = data.dropna(
                subset=[
                    "Genome range start",
                    "Genome range end",
                ]
            ).drop_duplicates(
                subset=[
                    "Genome range start",
                    "Genome range end",
                ]
            )

            for _, row in ranges.iterrows():
                start = row["Genome range start"]
                end = row["Genome range end"]
                axis.axvspan(
                    start,
                    end,
                    color=range_line,
                    alpha=0.75,
                    zorder=-1,
                )
                axis.axvline(
                    start,
                    color=range_line,
                    linewidth=2,
                    zorder=0,
                )
                axis.axvline(
                    end,
                    color=range_line,
                    linewidth=2,
                    zorder=0,
                )

        if x_variable == "Smallest contig":
            axis.xaxis.set_major_locator(
                MaxNLocator(
                    nbins=6,
                    integer=True,
                )
            )

        axis.grid(False)
        axis.set_xlabel("")

        marginal_axis = add_marginal_distribution(
            axis=axis,
            data=data,
            x_variable=x_variable,
        )

        marginal_axis.set_title(
            x_variable,
            fontsize=title_fontsize,
            fontweight="bold",
            loc="left",
            pad=16,
        )

        annoletter(
            ax=marginal_axis,
            letter=string.ascii_uppercase[panel_index],
            x=-0.10,
            y=1.32,
            fontsize=panel_letter_fontsize,
        )

    seed_handles, kmer_handles, range_handle = build_legend_handles(
        seed_palette=seed_palette,
        kmer_markers=kmer_markers,
        range_line=range_line,
        marker_size=point_size,
    )
    all_handles = seed_handles + kmer_handles + [range_handle]

    grid.figure.legend(
        handles=all_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.02),
        ncol=min(8, len(all_handles)),
        title=(
            "Seed Input (color), K-mer (marker), and genome range (line)"
        ),
        fontsize=legend_fontsize,
        title_fontsize=legend_title_fontsize,
        labelspacing=1.0,
        handletextpad=0.5,
        columnspacing=1.0,
        frameon=False,
    )

    grid.figure.subplots_adjust(
        top=0.82,
        bottom=0.06,
        left=0.08,
        right=0.98,
        wspace=0.30,
    )

    output_directory = os.path.dirname(output_file)
    if output_directory:
        os.makedirs(
            output_directory,
            exist_ok=True,
            mode=0o755,
        )

    output_path = f"{output_file}.{fig_format}"
    grid.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
    )
    plt.close(grid.figure)

    logging.info(
        "NOVOPlasty summary plot saved to: %s",
        output_path,
    )

    return output_path
