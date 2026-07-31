import logging
import os

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import seaborn as sns
import pandas as pd

from .build_plot_styles import build_plot_styles

def row_mode_or_none(row: pd.Series):
    """Return the most frequent non-null value in one row."""
    valid_values = row.dropna()
    if valid_values.empty:
        return None
    return valid_values.mode().iloc[0]

def plot_genome_size_heatmap(**kwargs):

    dataframe= kwargs.get("dataframe", None)
    output_file = kwargs.get("output_file", "genome_size_heatmap")
    fig_format = kwargs.get("fig_format", "png")
    metric = str(kwargs.get("metric", "Largest contig"))
    heatmap_cmap = str(kwargs.get("cmap", 'viridis'))
    mismatch_alpha = float(kwargs.get("mismatch_alpha", 0.5))
    dpi = int(kwargs.get("dpi", 300))

    heat_data = dataframe.dropna(subset=[metric, "Seed Input", "K-mer"]).copy()

    if heat_data.empty:
        logging.warning("Heatmap skipped because there are no valid rows")
        return None

    heat_data["K-mer"] = heat_data["K-mer"].astype(int)
    seed_palette, _ = build_plot_styles(dataframe=heat_data)

    pivot_full = heat_data.pivot_table(
        index="Project name",
        columns=["Seed Input", "K-mer"],
        values=metric,
        aggfunc="mean",
    )

    if pivot_full.empty:
        logging.warning("Heatmap skipped because the pivot table is empty")
        return None

    project_order = [
        project
        for project in dataframe["Project name"].drop_duplicates()
        if project in pivot_full.index
    ]
    pivot_full = pivot_full.reindex(index=project_order)

    seeds_in_pivot = pivot_full.columns.get_level_values(0)
    seed_order = [
        seed
        for seed in sorted(heat_data["Seed Input"].unique())
        if seed in seeds_in_pivot
    ]
    if not seed_order:
        logging.warning("Heatmap skipped because no seed groups were found")
        return None

    minimum = heat_data[metric].min()
    maximum = heat_data[metric].max()
    width_ratios = [pivot_full[seed].shape[1] for seed in seed_order]
    figure_width = max(sum(width_ratios) * 0.7, 8)
    figure_height = max(0.4 * len(project_order), 6)

    figure, axes = plt.subplots(
        1,
        len(seed_order),
        sharey=True,
        figsize=(figure_width, figure_height),
        gridspec_kw={"width_ratios": width_ratios, "wspace": 0.05},
    )
    if len(seed_order) == 1:
        axes = [axes]

    row_reference = pivot_full.apply(row_mode_or_none, axis=1)

    for index, (seed, axis) in enumerate(zip(seed_order, axes)):
        subset = pivot_full[seed].sort_index(axis=1)
        is_last_axis = index == len(seed_order) - 1

        sns.heatmap(
            subset,
            ax=axis,
            cmap=heatmap_cmap,
            vmin=minimum,
            vmax=maximum,
            annot=True,
            fmt=".0f",
            annot_kws={"size": 7},
            linewidths=0.5,
            linecolor="white",
            cbar=is_last_axis,
            cbar_kws={"label": "Genome size (bp)"} if is_last_axis else None,
            yticklabels=False,
        )

        axis.tick_params(axis="y", left=False, labelleft=False)

        for row_index, project in enumerate(subset.index):
            reference = row_reference.get(project)
            for column_index in range(subset.shape[1]):
                value = subset.iloc[row_index, column_index]
                if pd.isna(value) or reference is None or value == reference:
                    continue

                axis.add_patch(
                    Rectangle(
                        (column_index, row_index),
                        1,
                        1,
                        facecolor="white",
                        alpha=1 - mismatch_alpha,
                        edgecolor="none",
                        zorder=2,
                    )
                )

        axis.add_patch(
            Rectangle(
                (0, 1.02),
                1,
                0.05,
                transform=axis.transAxes,
                facecolor=seed_palette[seed],
                clip_on=False,
                zorder=5,
            )
        )
        axis.set_xlabel("K-mer")
        axis.set_ylabel("")
        axis.tick_params(axis="x", rotation=0)

    axes[0].set_yticks([position + 0.5 for position in range(len(project_order))])
    axes[0].set_yticklabels(project_order, rotation=0)
    axes[0].tick_params(axis="y", left=True, labelleft=True)
    axes[0].set_ylabel("Project name")

    seed_handles = [
        Line2D(
            [0],
            [0],
            marker="s",
            color="w",
            label=seed,
            markerfacecolor=seed_palette[seed],
            markersize=12,
        )
        for seed in seed_order
    ]

    figure.legend(
        handles=seed_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.08),
        ncol=max(1, len(seed_handles)),
        frameon=False,
        title="Seed Input (Color)",
    )

    figure.suptitle(
        "Length of the largest contig per project, seed input, and k-mer",
        y=1.16,
        fontsize=13,
    )

    os.makedirs(os.path.dirname(output_file), exist_ok=True, mode=0o755)

    figure.savefig(f"{output_file}.{fig_format}", dpi=dpi, bbox_inches="tight")
    plt.close(figure)

    logging.info("Heatmap written: %s", output_file)

    return output_file