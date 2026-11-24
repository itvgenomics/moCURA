import asyncio
import logging
import os

import pandas as pd

from .generate.generate_excel import append_excel_sheets, generate_excel
from .generate.generate_html_report import generate_html_report
from .load.load_config import config_section, load_config
from .load.load_genbank_marker_data import build_allowed_assembly_keys, load_genbank_marker_data
from .load.organpipe_layout import infer_organpipe_dir
from .load.load_novoplasty_data import load_novoplasty_data
from .load.load_pilon_data import load_pilon_data
from .utils.pilon_columns import PILON_COLUMNS
from .plots.plot_genome_size_heatmap import plot_genome_size_heatmap
from .plots.plot_marker_length_heatmaps import plot_marker_length_heatmaps
from .plots.plot_novoplasty_summary import plot_novoplasty_summary
from .plots.plot_pilon_before_after_heatmap import (
    plot_pilon_before_after_heatmap,
)
from .plots.plot_pilon_heatmap import plot_pilon_heatmap
from .plots.prepare_plot_dataframe import prepare_plot_dataframe

from .analysis.run_marker_snp_analysis import run_marker_snp_analysis
from .analysis.run_trf_analysis import run_trf_analysis
from .analysis.provenance import build_provenance
from .analysis.run_organpipe_qc import run_organpipe_qc, write_tsv


async def build_summary_dataframe(**kwargs):
    """Read NOVOPlasty and Pilon logs and merge them by assembly key."""

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

    novoplasty_df, pilon_df = await asyncio.gather(
        novoplasty_task,
        pilon_task,
    )

    if novoplasty_df.empty:
        return novoplasty_df

    if pilon_df.empty:
        for column in PILON_COLUMNS:
            if column not in {
                "Project name",
                "K-mer",
                "Seed Input",
            }:
                novoplasty_df[column] = pd.NA

        logging.warning("No Pilon records were found")
        return novoplasty_df

    merged_df = novoplasty_df.merge(
        pilon_df,
        on=[
            "Project name",
            "K-mer",
            "Seed Input",
        ],
        how="left",
        validate="many_to_one",
    )

    logging.info(
        "Merged summary rows: %d",
        len(merged_df),
    )

    return merged_df


def build_plot_kwargs(**kwargs):
    """Combine global figure style and one plot configuration section."""

    common_style = kwargs.get("common_style", {})
    plot_config = kwargs.get("plot_config", {})

    output = {
        **common_style,
        **plot_config,
    }

    output.pop("enabled", None)

    return output


async def run_pipeline(**kwargs):
    """Run all moCURA readers, reports, and plots."""

    results_dir = kwargs.get("results_dir", "example_results")
    output_dir = kwargs.get("output_dir", "example_output")
    config_file = kwargs.get("config_file")

    config = load_config(
        config_file=config_file
    )

    pipeline_config = config_section(
        config=config,
        keys=["pipeline"],
    )
    figure_config = config_section(
        config=config,
        keys=["figures"],
    )
    common_style = config_section(
        config=config,
        keys=["figures", "style"],
    )
    plots_config = config_section(
        config=config,
        keys=["plots"],
    )
    genbank_config = config_section(
        config=config,
        keys=["genbank"],
    )
    marker_snp_config = config_section(
        config=config,
        keys=["marker_snp_analysis"],
    )
    trf_config = config_section(config=config, keys=["trf"])
    html_report_config = config_section(config=config, keys=["html_report"])

    metadata_path = kwargs.get("metadata_path") or html_report_config.get("metadata_path")
    config_directory = os.path.dirname(os.path.abspath(config_file)) if config_file else os.getcwd()

    if metadata_path and not os.path.isabs(str(metadata_path)):
        metadata_path = os.path.join(config_directory, str(metadata_path))

    if not metadata_path:
        for candidate_name in ("metadata.xlsx", "metadata.ods", "metadata.tsv", "metadata.csv"):
            candidate_path = os.path.join(config_directory, candidate_name)
            if os.path.isfile(candidate_path):
                metadata_path = candidate_path
                logging.info("Metadata automatically detected: %s", metadata_path)
                break

    if metadata_path:
        logging.info("HTML metadata source: %s", metadata_path)

    concurrency_override = kwargs.get("concurrency")
    circularized_override = kwargs.get("only_circularized")
    dpi_override = kwargs.get("dpi")
    format_override = kwargs.get("fig_format")

    concurrency = int(
        concurrency_override
        if concurrency_override is not None
        else pipeline_config.get("threads", 20)
    )
    only_circularized = bool(
        circularized_override
        if circularized_override is not None
        else pipeline_config.get("only_circularized", True)
    )
    dpi = int(
        dpi_override
        if dpi_override is not None
        else figure_config.get("dpi", 300)
    )
    fig_format = str(
        format_override
        if format_override is not None
        else figure_config.get("format", "png")
    ).lower()

    if not os.path.isdir(results_dir):
        raise FileNotFoundError(
            f"Results directory not found: {results_dir}"
        )

    os.makedirs(
        output_dir,
        exist_ok=True,
        mode=0o755,
    )

    logging.info(
        "Reading results from: %s",
        results_dir,
    )
    logging.info(
        "Output directory: %s",
        output_dir,
    )
    logging.info(
        "Maximum concurrent file reads: %d",
        concurrency,
    )
    logging.info(
        "Circularized-only filter: %s",
        only_circularized,
    )

    summary_df = await build_summary_dataframe(
        results_dir=results_dir,
        concurrency=concurrency,
    )

    if summary_df.empty:
        raise RuntimeError(
            "No NOVOPlasty records were found, so no report was generated"
        )

    plot_df = prepare_plot_dataframe(
        dataframe=summary_df,
        only_circularized=only_circularized,
    )

    genbank_files_df = pd.DataFrame()
    marker_df = pd.DataFrame()

    if genbank_config.get("enabled", True):
        genbank_files_df, marker_df = await load_genbank_marker_data(
            results_dir=results_dir,
            concurrency=concurrency,
            folder_name=genbank_config.get(
                "folder_name",
                "genbanks",
            ),
            suffix=genbank_config.get(
                "suffix",
                ".rotated.gb",
            ),
            feature_types=genbank_config.get(
                "feature_types",
                [
                    "CDS",
                    "rRNA",
                    "tRNA",
                    "D-loop",
                    "misc_feature",
                    "regulatory",
                ],
            ),
            include_unknown_markers=genbank_config.get(
                "include_unknown_markers",
                False,
            ),
            assembly_dataframe=plot_df,
        )

    trf_results = {}
    trf_summary_df = pd.DataFrame()
    trf_repeats_df = pd.DataFrame()

    if trf_config.get("enabled", False):
        if genbank_files_df.empty:
            logging.warning("TRF analysis skipped because no rotated GenBank data were loaded")
        else:
            trf_results = await run_trf_analysis(
                results_dir=results_dir,
                output_dir=os.path.join(output_dir, trf_config.get("output_folder", "trf_analysis")),
                genbank_files_dataframe=genbank_files_df,
                config=trf_config,
            )
            trf_summary_df = trf_results.get("summary_dataframe", pd.DataFrame())
            trf_repeats_df = trf_results.get("repeats_dataframe", pd.DataFrame())

    organpipe_dir = (
        kwargs.get("organpipe_dir")
        or config_section(config=config, keys=["organpipe"]).get("organpipe_dir")
        or infer_organpipe_dir(results_dir=results_dir)
    )
    if organpipe_dir:
        logging.info("OrganPipe directory: %s", organpipe_dir)
    else:
        logging.info("OrganPipe directory not found; read QC and benchmarks are skipped")

    organpipe_results = await run_organpipe_qc(
        results_dir=results_dir,
        output_dir=output_dir,
        organpipe_dir=organpipe_dir,
        concurrency=concurrency,
        allowed_keys=build_allowed_assembly_keys(dataframe=plot_df),
        summary_dataframe=summary_df,
        config=config,
    )

    excel_path = generate_excel(
        dataframe=summary_df,
        genbank_files_dataframe=genbank_files_df,
        marker_dataframe=marker_df,
        trf_summary_dataframe=trf_summary_df,
        trf_repeats_dataframe=trf_repeats_df,
        output_file=os.path.join(output_dir, "moCURA_summary.xlsx"),
        separate_groups=True,
        extra_sheets=organpipe_results.get("excel_sheets", []),
    )

    summary_plot_path = None
    heatmap_path = None
    pilon_heatmap_path = None
    pilon_before_after_heatmap_path = None
    marker_heatmap_paths = []
    marker_snp_results = {}

    novoplasty_plot_config = plots_config.get(
        "novoplasty_summary",
        {},
    )

    if novoplasty_plot_config.get("enabled", True):
        summary_plot_path = plot_novoplasty_summary(
            dataframe=plot_df,
            output_file=os.path.join(
                output_dir,
                "novoplasty_summary",
            ),
            dpi=dpi,
            fig_format=fig_format,
            **build_plot_kwargs(
                common_style=common_style,
                plot_config=novoplasty_plot_config,
            ),
        )

    genome_heatmap_config = plots_config.get(
        "genome_size_heatmap",
        {},
    )

    if genome_heatmap_config.get("enabled", True):
        heatmap_path = plot_genome_size_heatmap(
            dataframe=plot_df,
            output_file=os.path.join(
                output_dir,
                "genome_size_heatmap",
            ),
            dpi=dpi,
            fig_format=fig_format,
            **build_plot_kwargs(
                common_style=common_style,
                plot_config=genome_heatmap_config,
            ),
        )

    pilon_heatmap_config = plots_config.get(
        "pilon_heatmap",
        {},
    )

    if pilon_heatmap_config.get("enabled", True):
        pilon_heatmap_path = plot_pilon_heatmap(
            dataframe=plot_df,
            output_file=os.path.join(
                output_dir,
                "pilon_metrics_heatmap",
            ),
            dpi=dpi,
            fig_format=fig_format,
            **build_plot_kwargs(
                common_style=common_style,
                plot_config=pilon_heatmap_config,
            ),
        )

    before_after_config = plots_config.get(
        "pilon_before_after_heatmap",
        {},
    )

    if before_after_config.get("enabled", True):
        pilon_before_after_heatmap_path = (
            plot_pilon_before_after_heatmap(
                dataframe=plot_df,
                output_file=os.path.join(
                    output_dir,
                    "pilon_before_after_heatmap",
                ),
                dpi=dpi,
                fig_format=fig_format,
                **build_plot_kwargs(
                    common_style=common_style,
                    plot_config=before_after_config,
                ),
            )
        )

    marker_heatmap_config = plots_config.get(
        "marker_length_heatmaps",
        {},
    )

    if (
        marker_heatmap_config.get("enabled", True)
        and not marker_df.empty
    ):
        marker_heatmap_paths = plot_marker_length_heatmaps(
            dataframe=marker_df,
            output_dir=os.path.join(
                output_dir,
                "marker_length_heatmaps",
            ),
            fig_format=fig_format,
            dpi=dpi,
            **build_plot_kwargs(
                common_style=common_style,
                plot_config=marker_heatmap_config,
            ),
        )

    if marker_snp_config.get("enabled", False):
        only_when_circularized = bool(
            marker_snp_config.get(
                "only_when_circularized",
                True,
            )
        )

        if (
            only_when_circularized
            and not only_circularized
        ):
            logging.warning(
                "Marker SNP analysis skipped because "
                "only_circularized is False"
            )

        elif marker_df.empty or genbank_files_df.empty:
            logging.warning(
                "Marker SNP analysis skipped because "
                "no rotated GenBank data were loaded"
            )

        else:
            marker_snp_results = await run_marker_snp_analysis(
                results_dir=results_dir,
                output_dir=os.path.join(
                    output_dir,
                    "marker_snp_analysis",
                ),
                genbank_files_dataframe=genbank_files_df,
                marker_dataframe=marker_df,
                config=marker_snp_config,
            )

    provenance_enabled = bool(config_section(config=config, keys=["provenance"]).get("enabled", True))
    provenance_arguments = {
        "--results-dir": results_dir,
        "--output-dir": output_dir,
        "--config": config_file,
        "--organpipe-dir": organpipe_dir,
        "--threads": concurrency,
        "--only-circularized": only_circularized,
        "--metadata": metadata_path,
    }
    if provenance_enabled:
        organpipe_results["html"]["provenance"] = build_provenance(
            config=config, arguments=provenance_arguments, organpipe_dir=organpipe_dir,
        )

    html_report_path = None
    if html_report_config.get("enabled", True):
        html_report_path = generate_html_report(
            summary_dataframe=summary_df, plot_dataframe=plot_df, genbank_files_dataframe=genbank_files_df,
            marker_dataframe=marker_df, trf_summary_dataframe=trf_summary_df, trf_repeats_dataframe=trf_repeats_df,
            marker_snp_results=marker_snp_results, output_dir=output_dir, metadata_path=metadata_path,
            static_plot_paths=[summary_plot_path, heatmap_path, pilon_heatmap_path, pilon_before_after_heatmap_path, marker_heatmap_paths],
            output_file=os.path.join(output_dir, html_report_config.get("output_file", "moCURA_report.html")), config=html_report_config,
            organpipe_results=organpipe_results.get("html", {}),
        )

    if provenance_enabled:
        provenance_df = build_provenance(config=config, arguments=provenance_arguments, organpipe_dir=organpipe_dir)
        append_excel_sheets(output_file=excel_path, sheets=[("Provenance", provenance_df)])
        write_tsv(
            dataframe=provenance_df,
            output_dir=output_dir,
            folder=config_section(config=config, keys=["provenance"]).get("output_folder", "provenance"),
            file_name="provenance.tsv",
        )

    logging.info("Pipeline completed successfully")

    return {
        "excel": excel_path,
        "html_report": html_report_path,
        "summary_plot": summary_plot_path,
        "heatmap": heatmap_path,
        "pilon_heatmap": pilon_heatmap_path,
        "pilon_before_after_heatmap": (
            pilon_before_after_heatmap_path
        ),
        "marker_length_heatmaps": marker_heatmap_paths,
        "marker_snp_analysis": marker_snp_results,
        "trf_analysis": trf_results,
        "organpipe_qc": organpipe_results,
    }
