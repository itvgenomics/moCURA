import logging
import os
import string
import textwrap

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle


DEFAULT_PILON_METRICS = {
    "Pilon Total bases": {
        "title": "Genome length after Pilon (bp)",
        "format": ".0f",
        "cmap": "cividis",
    },
    "Pilon Size change": {
        "title": "Genome length change after Pilon (bp)",
        "format": "+.0f",
        "cmap": "coolwarm",
        "center": 0,
    },
    "Pilon Confirmed %": {
        "title": "Confirmed bases after Pilon (%)",
        "format": ".1f",
        "cmap": "viridis",
    },
    "Pilon Coverage": {
        "title": "Pilon coverage (x)",
        "format": ".0f",
        "cmap": "mako",
    },
    "Pilon Corrected bases": {
        "title": "Bases corrected by Pilon",
        "format": ".0f",
        "cmap": "YlOrRd",
    },
}


def prepare_pilon_heatmap_data(**kwargs):
    """Prepare the Pilon data and calculate derived metrics."""

    dataframe = kwargs.get("dataframe")

    if dataframe is None:
        logging.warning("No dataframe was provided for the Pilon heatmap")
        return pd.DataFrame()

    if dataframe.empty:
        logging.warning("The dataframe provided for the Pilon heatmap is empty")
        return pd.DataFrame()

    required_columns = {
        "Project name",
        "Seed Input",
        "K-mer",
        "Largest contig",
        "Pilon Total bases",
        "Pilon Confirmed %",
        "Pilon Coverage",
        "Pilon Corrected snps",
        "Pilon Ambiguous bases",
        "Pilon Corrected insertions bases",
        "Pilon Corrected deletions bases",
    }

    missing_columns = sorted(required_columns.difference(dataframe.columns))

    if missing_columns:
        raise ValueError("Missing columns required for the Pilon heatmap: " + ", ".join(missing_columns))

    plot_data = dataframe.copy()

    numeric_columns = [
        "K-mer",
        "Largest contig",
        "Pilon Total bases",
        "Pilon Confirmed %",
        "Pilon Coverage",
        "Pilon Corrected snps",
        "Pilon Ambiguous bases",
        "Pilon Corrected insertions bases",
        "Pilon Corrected deletions bases",
    ]

    for column_name in numeric_columns:
        plot_data[column_name] = pd.to_numeric(plot_data[column_name], errors="coerce")

    plot_data = plot_data.dropna(subset=["Project name", "Seed Input", "K-mer", "Pilon Total bases"]).copy()

    if plot_data.empty:
        logging.warning("No valid Pilon rows were found after filtering")
        return plot_data

    plot_data["Project name"] = plot_data["Project name"].astype(str)
    plot_data["Seed Input"] = plot_data["Seed Input"].astype(str)
    plot_data["K-mer"] = plot_data["K-mer"].astype(int)

    plot_data["Pilon Size change"] = (plot_data["Pilon Total bases"] - plot_data["Largest contig"])

    correction_columns = ["Pilon Corrected snps", "Pilon Ambiguous bases", "Pilon Corrected insertions bases", "Pilon Corrected deletions bases"]

    plot_data["Pilon Corrected bases"] = (plot_data[correction_columns].fillna(0).sum(axis=1))

    return plot_data


def split_seed_inputs(**kwargs):
    """Divide Seed Input values into balanced rows."""

    seed_order = list(kwargs.get("seed_order", []))
    number_of_rows = max(1, int(kwargs.get("number_of_rows", 2)))

    if not seed_order:
        return []

    number_of_rows = min(number_of_rows, len(seed_order))
    minimum_group_size = len(seed_order) // number_of_rows
    remaining_seeds = len(seed_order) % number_of_rows

    seed_groups = []
    start_index = 0

    for row_index in range(number_of_rows):
        current_group_size = minimum_group_size

        if row_index < remaining_seeds:
            current_group_size += 1

        end_index = start_index + current_group_size
        seed_groups.append(seed_order[start_index:end_index])
        start_index = end_index

    return seed_groups


def build_metric_normalization(**kwargs):
    """Build the color normalization used by one metric."""

    values = kwargs.get("values")
    settings = kwargs.get("settings", {})

    numeric_values = pd.to_numeric(values, errors="coerce").dropna()

    if numeric_values.empty:
        return Normalize(vmin=0, vmax=1)

    minimum_value = settings.get("vmin", numeric_values.min())
    maximum_value = settings.get("vmax", numeric_values.max())
    center_value = settings.get("center")

    if minimum_value == maximum_value:
        minimum_value -= 0.5
        maximum_value += 0.5

    if center_value is not None:
        maximum_distance = max(
            abs(minimum_value - center_value),
            abs(maximum_value - center_value),
        )

        if maximum_distance == 0:
            maximum_distance = 1

        return TwoSlopeNorm(vmin=center_value - maximum_distance, vcenter=center_value, vmax=center_value + maximum_distance)

    return Normalize(vmin=minimum_value, vmax=maximum_value)


def resolve_colormap(**kwargs):
    """Return a Matplotlib compatible colormap."""

    colormap_name = kwargs.get("colormap_name", "cividis")

    try:
        return plt.get_cmap(colormap_name)
    except ValueError:
        return sns.color_palette(colormap_name, as_cmap=True)


def annoletter(**kwargs):
    axis = kwargs.get("ax")
    letter = kwargs.get("letter")

    if axis is None:
        raise ValueError("ax is required")

    if letter is None:
        raise ValueError("letter is required")

    return axis.annotate(
        str(letter).lower(),
        xy=(0.02, 0.88),
        xycoords="axes fraction",
        fontsize=18,
        ha="center",
        va="center",
        fontweight="bold",
        color="white",
        bbox=dict(
            boxstyle="circle",
            fc="#191919",
            ec="none",
            lw=0,
            pad=0.45,
            alpha=1,
        ),
        zorder=20,
    )


def add_panel_header(**kwargs):
    """Add a panel letter and a wrapped title to the title axis."""

    axis = kwargs.get("ax")
    letter = kwargs.get("letter")
    title = kwargs.get("title", "")
    title_fontsize = float(kwargs.get("title_fontsize", 24))
    letter_fontsize = float(kwargs.get("letter_fontsize", 17))
    title_x = float(kwargs.get("title_x", 0.080))
    wrap_width = int(kwargs.get("wrap_width", 38))

    if axis is None:
        raise ValueError("ax is required")

    axis.set_axis_off()

    annoletter(
        ax=axis,
        letter=letter,
        x=0.025,
        y=0.50,
        fontsize=letter_fontsize,
    )

    wrapped_title = textwrap.fill(
        str(title),
        width=max(wrap_width, 10),
        break_long_words=False,
        break_on_hyphens=False,
    )

    axis.text(
        title_x,
        0.50,
        wrapped_title,
        transform=axis.transAxes,
        fontsize=title_fontsize,
        fontweight="bold",
        horizontalalignment="left",
        verticalalignment="center",
        linespacing=1.05,
    )


def draw_top_group_bar(**kwargs):
    """Draw a borderless bar above one Seed Input heatmap block."""

    axis = kwargs.get("axis")
    color = kwargs.get("color")
    linewidth = float(kwargs.get("linewidth", 10))
    y_position = float(kwargs.get("y_position", 1.025))

    if axis is None:
        return

    axis.plot(
        [0, 1],
        [y_position, y_position],
        transform=axis.transAxes,
        color=color,
        linewidth=linewidth,
        solid_capstyle="butt",
        clip_on=False,
        zorder=5,
    )


def style_colorbar(**kwargs):
    """Apply the common borderless style to a heatmap colorbar."""

    colorbar = kwargs.get("colorbar")
    label = kwargs.get("label", "")
    label_fontsize = float(kwargs.get("label_fontsize", 11))
    tick_fontsize = float(kwargs.get("tick_fontsize", 10))

    if colorbar is None:
        return

    colorbar.set_label(label, fontsize=label_fontsize, labelpad=6)
    colorbar.ax.tick_params(labelsize=tick_fontsize, pad=3)
    colorbar.outline.set_visible(False)

    if getattr(colorbar, "solids", None) is not None:
        colorbar.solids.set_edgecolor("face")


def add_mismatch_alpha(**kwargs):
    """Fade final genome lengths that differ from the project modal length."""

    axis = kwargs.get("axis")
    pivot = kwargs.get("pivot")
    reference_values = kwargs.get("reference_values")
    mismatch_alpha = float(kwargs.get("mismatch_alpha", 0.15))

    if axis is None or pivot is None or pivot.empty or reference_values is None:
        return

    mismatch_alpha = min(max(mismatch_alpha, 0), 1)

    for row_position, project_name in enumerate(pivot.index):
        reference_value = reference_values.get(project_name)

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


def configure_project_axis(**kwargs):
    """Configure the sample names displayed on the Y axis."""

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
            pad=4,
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


def plot_pilon_heatmap(**kwargs):
    """Plot the main Pilon metrics as standardized grouped heatmaps."""

    dataframe = kwargs.get("dataframe")
    output_file = kwargs.get("output_file", "pilon_metrics_heatmap")
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

    metrics = kwargs.get("metrics", DEFAULT_PILON_METRICS)
    figure_title = kwargs.get(
        "figure_title",
        "Main Pilon metrics after genome polishing",
    )
    panel_letters = kwargs.get("panel_letters", string.ascii_uppercase)

    plot_data = prepare_pilon_heatmap_data(dataframe=dataframe)

    if plot_data.empty:
        logging.warning("Pilon heatmap skipped because there are no valid Pilon rows")
        return None

    project_order = (plot_data["Project name"].dropna().drop_duplicates().tolist())
    seed_order = sorted(plot_data["Seed Input"].dropna().unique())

    if not project_order:
        logging.warning("Pilon heatmap skipped because no project names were found")
        return None

    if not seed_order:
        logging.warning("Pilon heatmap skipped because no Seed Input values were found")
        return None

    available_metrics = {
        metric_name: settings
        for metric_name, settings in metrics.items()
        if metric_name in plot_data.columns
        and plot_data[metric_name].notna().any()
    }

    if not available_metrics:
        logging.warning("Pilon heatmap skipped because no selected metric contains values")
        return None

    metric_items = list(available_metrics.items())
    number_of_metrics = len(metric_items)
    metrics_per_row = min(metrics_per_row, number_of_metrics)
    number_of_metric_rows = (
        number_of_metrics + metrics_per_row - 1
    ) // metrics_per_row

    seed_groups = split_seed_inputs(seed_order=seed_order, number_of_rows=gene_rows_per_metric)
    gene_rows_per_metric = len(seed_groups)

    seed_widths = {}

    for seed_name in seed_order:
        number_of_kmers = (plot_data.loc[plot_data["Seed Input"] == seed_name, "K-mer"].dropna().astype(int).nunique())
        seed_widths[seed_name] = max(number_of_kmers, 1)

    maximum_group_width = max(
        sum(seed_widths[seed_name] for seed_name in seed_group)
        for seed_group in seed_groups
    )

    panel_width = max(8, maximum_group_width * 0.60)
    internal_row_height = max(
        3.8,
        len(project_order) * 0.42 + 1.4,
    ) * plot_height_scale
    panel_height = (0.45 + gene_rows_per_metric * internal_row_height)

    figure_width = max(14, panel_width * metrics_per_row)
    figure_height = max(9, panel_height * number_of_metric_rows)
    annotation_size = max(4, min(8, 290 / max(maximum_group_width, 1)))
    x_tick_size = max(5, min(8, 310 / max(maximum_group_width, 1)))
    project_label_size = max(7, min(11, 80 / max(len(project_order), 1)))

    seed_palette = dict(zip(seed_order, sns.color_palette("colorblind", len(seed_order))))

    pilon_size_reference = (
        plot_data.groupby("Project name")["Pilon Total bases"]
        .apply(
            lambda values: (
                values.dropna().mode().iloc[0]
                if not values.dropna().empty
                else None
            )
        )
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

    for metric_index, (metric_name, metric_settings) in enumerate(metric_items):
        metric_row = metric_index // metrics_per_row
        metric_column = metric_index % metrics_per_row

        metric_grid = outer_grid[
            metric_row,
            metric_column,
        ].subgridspec(
            gene_rows_per_metric + 1,
            2,
            height_ratios=[
                category_title_height,
                *([1] * gene_rows_per_metric),
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
            title=metric_settings.get("title", metric_name),
            title_fontsize=panel_title_fontsize,
            letter_fontsize=panel_letter_fontsize,
        )

        colorbar_axis = figure.add_subplot(metric_grid[1:, 1])
        metric_normalization = build_metric_normalization(
            values=plot_data[metric_name],
            settings=metric_settings,
        )
        metric_colormap = resolve_colormap(colormap_name=metric_settings.get("cmap", "cividis"))

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
                number_of_row_columns = len(seed_group) + 1
            else:
                row_width_ratios = current_width_ratios
                number_of_row_columns = len(seed_group)

            gene_grid = metric_grid[
                internal_row_index + 1,
                0,
            ].subgridspec(
                1,
                number_of_row_columns,
                width_ratios=row_width_ratios,
                wspace=gene_block_spacing,
            )

            for seed_index, seed_name in enumerate(seed_group):
                axis = figure.add_subplot(gene_grid[0, seed_index])
                seed_subset = plot_data[plot_data["Seed Input"] == seed_name].copy()
                kmer_order = sorted(seed_subset["K-mer"].dropna().astype(int).unique())

                if not kmer_order:
                    axis.set_visible(False)
                    continue

                pivot = seed_subset.pivot_table(
                    index="Project name",
                    columns="K-mer",
                    values=metric_name,
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

                if metric_name == "Pilon Total bases":
                    add_mismatch_alpha(
                        axis=axis,
                        pivot=pivot,
                        reference_values=pilon_size_reference,
                        mismatch_alpha=mismatch_alpha,
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

                configure_project_axis(
                    axis=axis,
                    project_order=project_order,
                    show_labels=seed_index == 0,
                    label_size=project_label_size,
                    y_label_fontsize=axis_label_fontsize,
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
            label=metric_settings.get("title", metric_name),
            label_fontsize=colorbar_label_fontsize,
            tick_fontsize=colorbar_tick_fontsize,
        )

    total_panel_count = number_of_metric_rows * metrics_per_row

    for empty_metric_index in range(number_of_metrics, total_panel_count):
        empty_row = empty_metric_index // metrics_per_row
        empty_column = empty_metric_index % metrics_per_row
        empty_axis = figure.add_subplot(
            outer_grid[empty_row, empty_column]
        )
        empty_axis.set_axis_off()

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
    figure.legend(
        handles=seed_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.968),
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
        bottom=0.055,
        left=0.065,
        right=0.975,
    )

    output_directory = os.path.dirname(output_file)

    if output_directory:
        os.makedirs(output_directory, exist_ok=True, mode=0o755)

    output_path = f"{output_file}.{fig_format}"
    figure.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(figure)

    logging.info("Pilon heatmap written: %s", output_path)

    return output_path
