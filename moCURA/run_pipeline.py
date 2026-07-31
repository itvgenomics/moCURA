import asyncio
import logging
import os

import pandas as pd

from .load_novoplasty_data import load_novoplasty_data
from .load_pilon_data import load_pilon_data
from .generate_excel import generate_excel
from .prepare_plot_dataframe import prepare_plot_dataframe
from .plot_genome_size_heatmap import plot_genome_size_heatmap
from .plot_novoplasty_summary import plot_novoplasty_summary
from .plot_pilon_heatmap import plot_pilon_heatmap
from .pilon_columns import PILON_COLUMNS


async def build_summary_dataframe(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    concurrency = int(kwargs.get("concurrency", 8))

    novoplasty_task = load_novoplasty_data(
        results_dir=results_dir,
        concurrency=concurrency,
    )

    pilon_task = load_pilon_data(
        results_dir=results_dir,
        concurrency=concurrency,
    )

    novoplasty_df, pilon_df = await asyncio.gather(novoplasty_task, pilon_task)

    if novoplasty_df.empty:
        return novoplasty_df

    if pilon_df.empty:
        for column in PILON_COLUMNS:
            if column not in {"Project name", "K-mer", "Seed Input"}:
                novoplasty_df[column] = pd.NA

        logging.warning("No Pilon records were found")

        return novoplasty_df

    merged_df = novoplasty_df.merge(
        pilon_df,
        on=["Project name", "K-mer", "Seed Input"],
        how="left",
        validate="many_to_one",
    )

    logging.info(f"Merged summary rows: {len(merged_df)}")

    return merged_df

async def run_pipeline(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    output_dir = kwargs.get("output_dir", "example_output")
    concurrency = int(kwargs.get("concurrency", 8))
    only_circularized = bool(kwargs.get("only_circularized", True))
    dpi = int(kwargs.get("dpi", 300))
    fig_format = kwargs.get("fig_format", "png")

    if not os.path.exists(results_dir):
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True, mode=0o755)

    logging.info(f"Reading results from: {results_dir}")
    logging.info(f"Output directory: {output_dir}")
    logging.info(f"Maximum concurrent file reads: {concurrency}")

    summary_df = await build_summary_dataframe(
        results_dir=results_dir,
        concurrency=concurrency,
    )

    if summary_df.empty:
        raise RuntimeError("No NOVOPlasty records were found, so no report was generated")

    plot_df = prepare_plot_dataframe(
        dataframe=summary_df,
        only_circularized=only_circularized,
    )

    excel_path = generate_excel(
        dataframe=summary_df,
        output_file=os.path.join(output_dir, "moCURA_summary.xlsx"),
        separate_groups=True,
    )

    summary_plot_path = plot_novoplasty_summary(
        dataframe=plot_df,
        output_file=os.path.join(output_dir, "novoplasty_summary"),
        dpi=dpi,
        fig_format=fig_format,
    )
    
    heatmap_path = plot_genome_size_heatmap(
        dataframe=plot_df,
        output_file=os.path.join(output_dir, "genome_size_heatmap"),
        dpi=dpi,
        fig_format=fig_format,
    )

    pilon_heatmap_path = plot_pilon_heatmap(
        dataframe=plot_df,
        output_file=os.path.join(
            output_dir,
            "pilon_metrics_heatmap",
        ),
        dpi=dpi,
        fig_format=fig_format,
        annotate=True,
        mismatch_alpha=0.15,
        metrics_per_row=1,
        gene_rows_per_metric=2,
        category_column_spacing=0.025,
        category_row_spacing=0.05,
        gene_row_spacing=0.5,
        category_title_height=0.045,
    )

    logging.info("Pipeline completed successfully")

    return {
        "excel": excel_path,
        "summary_plot": summary_plot_path,
        "heatmap": heatmap_path,
        "pilon_heatmap": pilon_heatmap_path,
    }