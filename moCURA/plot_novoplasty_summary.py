import logging

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import seaborn as sns
import pandas as pd

from .build_plot_styles import build_plot_styles
from mpl_toolkits.axes_grid1 import make_axes_locatable

RANGE_LINE = "#B0E4CC"
ROW_BACKGROUND = "#EEEEEE"

def add_marginal_distribution(**kwargs):
    axis = kwargs.get("axis", None)
    data: pd.DataFrame = kwargs.get("data", pd.DataFrame())
    x_variable = str(kwargs["x_variable"])

    marginal_axis = make_axes_locatable(axis).append_axes(
        "top",
        size="15%",
        pad=0.1,
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
    marginal_axis.tick_params(bottom=False, labelbottom=False)
    for spine_name in ("top", "right", "left"):
        marginal_axis.spines[spine_name].set_visible(False)
    marginal_axis.grid(False)


def build_legend_handles(**kwargs):
    seed_palette = kwargs.get("seed_palette", None)
    kmer_markers = kwargs.get("kmer_markers", None)
    range_line = kwargs.get("range_line", RANGE_LINE)

    seed_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            label=seed,
            markerfacecolor=color,
            markeredgecolor="#202020",
            markersize=15,
        )
        for seed, color in seed_palette.items()
    ]
    kmer_handles = [
        Line2D(
            [0],
            [0],
            marker=marker,
            color="#202020",
            label=f"K-mer {kmer}",
            linestyle="None",
            markersize=15,
        )
        for kmer, marker in kmer_markers.items()
    ]
    range_handle = Line2D(
        [0],
        [0],
        color=range_line,
        linewidth=2.5,
        label="Genome Range",
    )
    return seed_handles, kmer_handles, range_handle

def plot_points(**kwargs):
    """Add seed colored and K-mer shaped points to one axis."""
    axis = kwargs["axis"]
    data = kwargs["data"]
    x_variable = str(kwargs["x_variable"])
    seed_palette = kwargs["seed_palette"]
    kmer_markers = kwargs["kmer_markers"]
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
    axis = kwargs["axis"]
    row_background = kwargs.get("row_background", ROW_BACKGROUND)

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
    dataframe = kwargs.get("dataframe", pd.DataFrame())
    output_file = kwargs.get("output_file", "novoplasty_summary")
    dpi = int(kwargs.get("dpi", 300))
    fig_format = kwargs.get("fig_format", "png")
    range_line = kwargs.get("range_line", RANGE_LINE)
    row_background = kwargs.get("row_background", ROW_BACKGROUND)

    if dataframe.empty:
        logging.warning("No data available for plotting NOVOPlasty summary")
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

    seed_palette, kmer_markers = build_plot_styles(dataframe=dataframe)

    grid = sns.PairGrid(
        dataframe,
        x_vars=metrics,
        y_vars=["Project name"],
        height=max(0.45 * dataframe["Project name"].nunique(), 15),
        aspect=0.25,
    )

    for axis, x_variable in zip(grid.axes.flat, metrics):
        columns = [
            x_variable,
            "Project name",
            "Seed Input",
            "K-mer",
            "Genome range start",
            "Genome range end",
        ]
        data = grid.data[columns].copy()
        data[x_variable] = pd.to_numeric(data[x_variable], errors="coerce")
        data = data.dropna(subset=[x_variable, "K-mer"])

        if data.empty:
            logging.warning(f"Skipping plot for {x_variable} because there are no valid rows")
            continue

        if x_variable == "Total contigs":
            data[x_variable] = data[x_variable].clip(upper=6)

        plot_points(
            axis=axis,
            data=data,
            x_variable=x_variable,
            seed_palette=seed_palette,
            kmer_markers=kmer_markers,
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
            axis.set_xticklabels(["1", "2", "3", "4", "5", ">5"])
            axis.set_xlim(0.5, 6.5)

        if x_variable in {"Largest contig", "Smallest contig"}:
            ranges = data.dropna(
                subset=["Genome range start", "Genome range end"]
            ).drop_duplicates(
                subset=["Genome range start", "Genome range end"]
            )
            for _, row in ranges.iterrows():
                start = row["Genome range start"]
                end = row["Genome range end"]
                axis.axvspan(start, end, color=range_line, alpha=0.75, zorder=-1)
                axis.axvline(start, color=range_line, linewidth=2, zorder=0)
                axis.axvline(end, color=range_line, linewidth=2, zorder=0)

        if x_variable == "Smallest contig":
            axis.xaxis.set_major_locator(MaxNLocator(nbins=6, integer=True))

        axis.grid(False)
        add_marginal_distribution(
            axis=axis,
            data=data,
            x_variable=x_variable,
        )

    seed_handles, kmer_handles, range_handle = build_legend_handles(
        seed_palette=seed_palette,
        kmer_markers=kmer_markers,
        range_line=range_line,
    )
    all_handles = seed_handles + kmer_handles + [range_handle]

    grid.figure.legend(
        handles=all_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.015),
        ncol=min(10, len(all_handles)),
        title="Seed Input (Color) / K-mer (Marker) / Genome range (Line)",
        labelspacing=1.5,
        handletextpad=0.5,
        columnspacing=1.0,
        frameon=False,
    )
    grid.figure.tight_layout(rect=(0, 0.10, 1, 1))

    grid.savefig(f"{output_file}.{fig_format}", dpi=dpi, bbox_inches="tight")
    plt.close(grid.figure)

    logging.info(f"NOVOPlasty summary plot saved to: {output_file}.{fig_format}")
    return f"{output_file}.{fig_format}"