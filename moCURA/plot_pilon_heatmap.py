import logging
import os

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
    """
    Prepare the Pilon data used in the heatmap.

    Derived columns
    ---------------
    Pilon Size change
        Difference between the final Pilon genome length and the
        largest NOVOPlasty contig.

    Pilon Corrected bases
        Sum of corrected SNPs, ambiguous bases, insertion bases
        and deletion bases.
    """

    dataframe = kwargs.get("dataframe")

    if dataframe is None:
        logging.warning(
            "No dataframe was provided for the Pilon heatmap"
        )
        return pd.DataFrame()

    if dataframe.empty:
        logging.warning(
            "The dataframe provided for the Pilon heatmap is empty"
        )
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

    missing_columns = sorted(
        required_columns.difference(
            dataframe.columns
        )
    )

    if missing_columns:
        raise ValueError(
            "Missing columns required for the Pilon heatmap: "
            + ", ".join(missing_columns)
        )

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
        plot_data[column_name] = pd.to_numeric(
            plot_data[column_name],
            errors="coerce",
        )

    plot_data = plot_data.dropna(
        subset=[
            "Project name",
            "Seed Input",
            "K-mer",
            "Pilon Total bases",
        ]
    ).copy()

    if plot_data.empty:
        logging.warning(
            "No valid Pilon rows were found after filtering"
        )
        return plot_data

    plot_data["Project name"] = (
        plot_data["Project name"]
        .astype(str)
    )

    plot_data["Seed Input"] = (
        plot_data["Seed Input"]
        .astype(str)
    )

    plot_data["K-mer"] = (
        plot_data["K-mer"]
        .astype(int)
    )

    plot_data["Pilon Size change"] = (
        plot_data["Pilon Total bases"]
        - plot_data["Largest contig"]
    )

    correction_columns = [
        "Pilon Corrected snps",
        "Pilon Ambiguous bases",
        "Pilon Corrected insertions bases",
        "Pilon Corrected deletions bases",
    ]

    plot_data["Pilon Corrected bases"] = (
        plot_data[correction_columns]
        .fillna(0)
        .sum(axis=1)
    )

    return plot_data


def split_seed_inputs(**kwargs):
    """
    Divide Seed Input values into a configurable number of rows.

    The genes are distributed as evenly as possible.
    """

    seed_order = kwargs.get(
        "seed_order",
        [],
    )

    number_of_rows = max(
        1,
        int(
            kwargs.get(
                "number_of_rows",
                2,
            )
        ),
    )

    if not seed_order:
        return []

    number_of_rows = min(
        number_of_rows,
        len(seed_order),
    )

    minimum_group_size = (
        len(seed_order)
        // number_of_rows
    )

    remaining_seeds = (
        len(seed_order)
        % number_of_rows
    )

    seed_groups = []
    start_index = 0

    for row_index in range(number_of_rows):
        current_group_size = minimum_group_size

        if row_index < remaining_seeds:
            current_group_size += 1

        end_index = (
            start_index
            + current_group_size
        )

        seed_groups.append(
            seed_order[
                start_index:end_index
            ]
        )

        start_index = end_index

    return seed_groups


def build_metric_normalization(**kwargs):
    """
    Build the color normalization used by one Pilon metric.
    """

    values = kwargs.get("values")

    settings = kwargs.get(
        "settings",
        {},
    )

    numeric_values = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if numeric_values.empty:
        return Normalize(
            vmin=0,
            vmax=1,
        )

    minimum_value = settings.get(
        "vmin",
        numeric_values.min(),
    )

    maximum_value = settings.get(
        "vmax",
        numeric_values.max(),
    )

    center_value = settings.get(
        "center"
    )

    if minimum_value == maximum_value:
        minimum_value -= 0.5
        maximum_value += 0.5

    if center_value is not None:
        maximum_distance = max(
            abs(
                minimum_value
                - center_value
            ),
            abs(
                maximum_value
                - center_value
            ),
        )

        if maximum_distance == 0:
            maximum_distance = 1

        return TwoSlopeNorm(
            vmin=(
                center_value
                - maximum_distance
            ),
            vcenter=center_value,
            vmax=(
                center_value
                + maximum_distance
            ),
        )

    return Normalize(
        vmin=minimum_value,
        vmax=maximum_value,
    )


def resolve_colormap(**kwargs):
    """
    Return a Matplotlib compatible colormap.
    """

    colormap_name = kwargs.get(
        "colormap_name",
        "cividis",
    )

    try:
        return plt.get_cmap(
            colormap_name
        )

    except ValueError:
        return sns.color_palette(
            colormap_name,
            as_cmap=True,
        )


def add_mismatch_alpha(**kwargs):
    """
    Reduce the visible alpha of final genome lengths that differ
    from the reference length calculated for each project.
    """

    axis = kwargs.get("axis")
    pivot = kwargs.get("pivot")

    reference_values = kwargs.get(
        "reference_values"
    )

    mismatch_alpha = float(
        kwargs.get(
            "mismatch_alpha",
            0.15,
        )
    )

    if axis is None:
        return

    if pivot is None or pivot.empty:
        return

    if reference_values is None:
        return

    mismatch_alpha = min(
        max(
            mismatch_alpha,
            0,
        ),
        1,
    )

    for row_position, project_name in enumerate(
        pivot.index
    ):
        reference_value = reference_values.get(
            project_name
        )

        if reference_value is None:
            continue

        if pd.isna(reference_value):
            continue

        for column_position in range(
            pivot.shape[1]
        ):
            current_value = pivot.iloc[
                row_position,
                column_position,
            ]

            if pd.isna(current_value):
                continue

            if current_value == reference_value:
                continue

            axis.add_patch(
                Rectangle(
                    (
                        column_position,
                        row_position,
                    ),
                    1,
                    1,
                    facecolor="white",
                    alpha=(
                        1
                        - mismatch_alpha
                    ),
                    edgecolor="none",
                    zorder=2,
                )
            )


def configure_project_axis(**kwargs):
    """
    Configure the sample names displayed on the Y axis.
    """

    axis = kwargs.get("axis")

    project_order = kwargs.get(
        "project_order",
        [],
    )

    show_labels = bool(
        kwargs.get(
            "show_labels",
            False,
        )
    )

    label_size = float(
        kwargs.get(
            "label_size",
            8,
        )
    )

    if axis is None:
        return

    if show_labels:
        axis.set_yticks(
            [
                row_position + 0.5
                for row_position in range(
                    len(project_order)
                )
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
        )

        axis.set_ylabel(
            "Project name",
            fontsize=9,
        )

    else:
        axis.tick_params(
            axis="y",
            left=False,
            labelleft=False,
        )

        axis.set_ylabel("")


def plot_pilon_heatmap(**kwargs):
    """
    Plot the main Pilon metrics as grouped heatmaps.

    Parameters accepted through kwargs
    ----------------------------------
    dataframe
        DataFrame containing NOVOPlasty and Pilon results.

    output_file
        Output path without the file extension.

    fig_format
        Figure format, such as png, svg or pdf.

    dpi
        Figure resolution.

    annotate
        Add numeric values inside the heatmap cells.

    mismatch_alpha
        Visible alpha retained for final genome lengths that differ
        from the modal value of the corresponding project.

    metrics_per_row
        Number of metric categories displayed side by side.

    gene_rows_per_metric
        Number of gene rows inside each metric category.

    category_column_spacing
        Horizontal spacing between metric categories.

    category_row_spacing
        Vertical spacing between rows of metric categories.

    gene_row_spacing
        Vertical spacing between gene rows inside the same category.

    gene_block_spacing
        Horizontal spacing between genes inside the same row.

    category_title_height
        Relative height reserved for the category title.

    colorbar_width
        Relative width reserved for the color bar.

    metrics
        Dictionary containing the metrics and visual settings.
    """

    dataframe = kwargs.get("dataframe")

    output_file = kwargs.get(
        "output_file",
        "pilon_metrics_heatmap",
    )

    fig_format = str(
        kwargs.get(
            "fig_format",
            "png",
        )
    ).lower()

    dpi = int(
        kwargs.get(
            "dpi",
            300,
        )
    )

    annotate = bool(
        kwargs.get(
            "annotate",
            True,
        )
    )

    mismatch_alpha = float(
        kwargs.get(
            "mismatch_alpha",
            0.15,
        )
    )

    metrics_per_row = max(
        1,
        int(
            kwargs.get(
                "metrics_per_row",
                2,
            )
        ),
    )

    gene_rows_per_metric = max(
        1,
        int(
            kwargs.get(
                "gene_rows_per_metric",
                2,
            )
        ),
    )

    category_column_spacing = float(
        kwargs.get(
            "category_column_spacing",
            0.04,
        )
    )

    category_row_spacing = float(
        kwargs.get(
            "category_row_spacing",
            0.10,
        )
    )

    gene_row_spacing = float(
        kwargs.get(
            "gene_row_spacing",
            0.12,
        )
    )

    gene_block_spacing = float(
        kwargs.get(
            "gene_block_spacing",
            0.025,
        )
    )

    category_title_height = float(
        kwargs.get(
            "category_title_height",
            0.035,
        )
    )

    colorbar_width = float(
        kwargs.get(
            "colorbar_width",
            0.022,
        )
    )

    metrics = kwargs.get(
        "metrics",
        DEFAULT_PILON_METRICS,
    )

    figure_title = kwargs.get(
        "figure_title",
        "Main Pilon metrics after genome polishing",
    )

    plot_data = prepare_pilon_heatmap_data(
        dataframe=dataframe
    )

    if plot_data.empty:
        logging.warning(
            "Pilon heatmap skipped because there are no valid Pilon rows"
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

    if not project_order:
        logging.warning(
            "Pilon heatmap skipped because no project names were found"
        )
        return None

    if not seed_order:
        logging.warning(
            "Pilon heatmap skipped because no Seed Input values were found"
        )
        return None

    available_metrics = {
        metric_name: settings
        for metric_name, settings in metrics.items()
        if metric_name in plot_data.columns
        and plot_data[metric_name].notna().any()
    }

    if not available_metrics:
        logging.warning(
            "Pilon heatmap skipped because no selected metric contains values"
        )
        return None

    metric_items = list(
        available_metrics.items()
    )

    number_of_metrics = len(
        metric_items
    )

    metrics_per_row = min(
        metrics_per_row,
        number_of_metrics,
    )

    number_of_metric_rows = (
        number_of_metrics
        + metrics_per_row
        - 1
    ) // metrics_per_row

    seed_groups = split_seed_inputs(
        seed_order=seed_order,
        number_of_rows=gene_rows_per_metric,
    )

    gene_rows_per_metric = len(
        seed_groups
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

        seed_widths[seed_name] = max(
            number_of_kmers,
            1,
        )

    maximum_group_width = max(
        sum(
            seed_widths[seed_name]
            for seed_name in seed_group
        )
        for seed_group in seed_groups
    )

    panel_width = max(
        8,
        maximum_group_width * 0.60,
    )

    internal_row_height = max(
        3.2,
        len(project_order) * 0.38 + 1.2,
    )

    panel_height = (
        0.25
        + gene_rows_per_metric
        * internal_row_height
    )

    figure_width = max(
        14,
        panel_width * metrics_per_row,
    )

    figure_height = max(
        7,
        panel_height * number_of_metric_rows,
    )

    annotation_size = max(
        3.5,
        min(
            7,
            260
            / max(
                maximum_group_width,
                1,
            ),
        ),
    )

    x_tick_size = max(
        4,
        min(
            7,
            280
            / max(
                maximum_group_width,
                1,
            ),
        ),
    )

    project_label_size = max(
        6,
        min(
            9,
            65
            / max(
                len(project_order),
                1,
            ),
        ),
    )

    seed_palette = dict(
        zip(
            seed_order,
            sns.color_palette(
                "colorblind",
                len(seed_order),
            ),
        )
    )

    pilon_size_reference = (
        plot_data.groupby(
            "Project name"
        )["Pilon Total bases"]
        .apply(
            lambda values: (
                values.dropna().mode().iloc[0]
                if not values.dropna().empty
                else None
            )
        )
    )

    figure = plt.figure(
        figsize=(
            figure_width,
            figure_height,
        )
    )

    outer_grid = figure.add_gridspec(
        number_of_metric_rows,
        metrics_per_row,
        wspace=category_column_spacing + 0.15,
        hspace=category_row_spacing,
    )

    for metric_index, (
        metric_name,
        metric_settings,
    ) in enumerate(metric_items):

        metric_row = (
            metric_index
            // metrics_per_row
        )

        metric_column = (
            metric_index
            % metrics_per_row
        )

        metric_grid = outer_grid[
            metric_row,
            metric_column,
        ].subgridspec(
            gene_rows_per_metric + 1,
            2,
            height_ratios=[
                category_title_height,
                *(
                    [1]
                    * gene_rows_per_metric
                ),
            ],
            width_ratios=[
                1,
                colorbar_width,
            ],
            wspace=0.03,
            hspace=gene_row_spacing,
        )

        title_axis = figure.add_subplot(
            metric_grid[
                0,
                :,
            ]
        )

        title_axis.set_axis_off()

        title_axis.text(
            0,
            -4.5,
            metric_settings.get(
                "title",
                metric_name,
            ),
            transform=title_axis.transAxes,
            fontsize=20,
            fontweight="bold",
            horizontalalignment="left",
            verticalalignment="center",
        )

        colorbar_axis = figure.add_subplot(
            metric_grid[
                1:,
                1,
            ]
        )

        metric_normalization = build_metric_normalization(
            values=plot_data[metric_name],
            settings=metric_settings,
        )

        metric_colormap = resolve_colormap(
            colormap_name=metric_settings.get(
                "cmap",
                "cividis",
            )
        )

        for internal_row_index, seed_group in enumerate(
            seed_groups
        ):

            current_width_ratios = [
                seed_widths[seed_name]
                for seed_name in seed_group
            ]

            current_group_width = sum(
                current_width_ratios
            )

            missing_width = (
                maximum_group_width
                - current_group_width
            )

            include_spacer = (
                missing_width > 0
            )

            if include_spacer:
                row_width_ratios = [
                    *current_width_ratios,
                    missing_width,
                ]

                number_of_row_columns = (
                    len(seed_group)
                    + 1
                )

            else:
                row_width_ratios = (
                    current_width_ratios
                )

                number_of_row_columns = len(
                    seed_group
                )

            gene_grid = metric_grid[
                internal_row_index + 1,
                0,
            ].subgridspec(
                1,
                number_of_row_columns,
                width_ratios=row_width_ratios,
                wspace=gene_block_spacing,
            )

            for seed_index, seed_name in enumerate(
                seed_group
            ):

                axis = figure.add_subplot(
                    gene_grid[
                        0,
                        seed_index,
                    ]
                )

                seed_subset = plot_data[
                    plot_data["Seed Input"]
                    == seed_name
                ].copy()

                kmer_order = sorted(
                    seed_subset["K-mer"]
                    .dropna()
                    .astype(int)
                    .unique()
                )

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
                    fmt=metric_settings.get(
                        "format",
                        ".1f",
                    ),
                    annot_kws={
                        "size": annotation_size,
                    },
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

                axis.add_patch(
                    Rectangle(
                        (
                            0,
                            1.018,
                        ),
                        1,
                        0.035,
                        transform=axis.transAxes,
                        facecolor=seed_palette[
                            seed_name
                        ],
                        clip_on=False,
                        zorder=5,
                    )
                )

                axis.set_xlabel(
                    "K-mer",
                    fontsize=8,
                    labelpad=2,
                )

                axis.tick_params(
                    axis="x",
                    rotation=90,
                    labelsize=x_tick_size,
                    pad=1,
                )

                configure_project_axis(
                    axis=axis,
                    project_order=project_order,
                    show_labels=(
                        seed_index == 0
                    ),
                    label_size=project_label_size,
                )

            if include_spacer:
                spacer_axis = figure.add_subplot(
                    gene_grid[
                        0,
                        len(seed_group),
                    ]
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

        colorbar.set_label(
            metric_settings.get(
                "title",
                metric_name,
            ),
            fontsize=8,
            labelpad=4,
        )

        colorbar.ax.tick_params(
            labelsize=7,
            pad=2,
        )

    total_panel_count = (
        number_of_metric_rows
        * metrics_per_row
    )

    for empty_metric_index in range(
        number_of_metrics,
        total_panel_count,
    ):

        empty_row = (
            empty_metric_index
            // metrics_per_row
        )

        empty_column = (
            empty_metric_index
            % metrics_per_row
        )

        empty_axis = figure.add_subplot(
            outer_grid[
                empty_row,
                empty_column,
            ]
        )

        empty_axis.set_axis_off()

    seed_handles = [
        Line2D(
            [0],
            [0],
            color=seed_palette[seed_name],
            linewidth=8,
            label=seed_name,
        )
        for seed_name in seed_order
    ]

    figure.suptitle(
        figure_title,
        fontsize=15,
        y=0.995,
    )

    figure.legend(
        handles=seed_handles,
        loc="upper center",
        bbox_to_anchor=(
            0.5,
            0.973,
        ),
        ncol=min(
            len(seed_handles),
            8,
        ),
        frameon=False,
        title="Seed Input",
        handlelength=2,
        handletextpad=0.5,
        columnspacing=0.9,
        labelspacing=0.5,
    )

    figure.subplots_adjust(
        top=0.91,
        bottom=0.045,
        left=0.055,
        right=0.975,
    )

    output_directory = os.path.dirname(
        output_file
    )

    if output_directory:
        os.makedirs(
            output_directory,
            exist_ok=True,
        )

    output_path = (
        f"{output_file}.{fig_format}"
    )

    figure.savefig(
        output_path,
        dpi=dpi,
        bbox_inches="tight",
    )

    plt.close(
        figure
    )

    logging.info(
        "Pilon heatmap written: %s",
        output_path,
    )

    return output_path