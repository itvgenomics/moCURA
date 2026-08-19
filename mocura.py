#!/usr/bin/env python3
import argparse
import asyncio
import logging
import os
import sys
import textwrap

os.environ.setdefault(
    "MPLBACKEND",
    "Agg",
)

try:
    from moCURA import (
        CustomArgumentParser,
        MultiQCHelpFormatter,
        run_pipeline,
    )
except ModuleNotFoundError as exc:
    if exc.name == "yaml":
        raise ModuleNotFoundError(
            "Missing dependency 'PyYAML'. Activate the moCURA environment "
            "and install pyyaml if needed: 'conda activate mocura_env && "
            "conda install -c conda-forge pyyaml'."
        ) from exc
    raise


TOOL_NAME = "moCURA"
DEFAULT_CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "config.yml",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y/%m/%d - %H:%M:%S",
)


def main():
    parser = CustomArgumentParser(
        prog=TOOL_NAME,
        usage="%(prog)s [options]",
        description=(
            f"{TOOL_NAME} - pipeline for generating curated reports "
            "from organellar assembly results."
        ),
        formatter_class=lambda prog: MultiQCHelpFormatter(
            prog=prog
        ),
        add_help=False,
    )

    input_group = parser.add_argument_group(
        title="Input Arguments",
        description=textwrap.dedent(
            """\
            Input Arguments:
            --results-dir: Directory containing the organpipe results.
            --config: YAML file containing report and plot settings.
            --metadata: Optional metadata table mapped by Project name.
            """
        ),
    )

    input_group.add_argument(
        "-i",
        "--results-dir",
        required=True,
        help="Directory containing the organpipe results.",
    )

    input_group.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help="YAML configuration file.",
    )

    input_group.add_argument(
        "--metadata",
        default=None,
        help=(
            "Optional CSV, TSV, XLSX or ODS metadata table with Project name, "
            "Species, Location, Latitude and Longitude columns."
        ),
    )

    output_group = parser.add_argument_group(
        title="Output Arguments",
        description=textwrap.dedent(
            """\
            Output Arguments:
            --output-dir: Directory used to store generated reports.
            """
        ),
    )

    output_group.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Directory used to store generated reports.",
    )

    threading_group = parser.add_argument_group(
        title="Threading Arguments",
        description=textwrap.dedent(
            """\
            Threading Arguments:
            --threads: Override the number of concurrent tasks from config.yml.
            """
        ),
    )

    threading_group.add_argument(
        "-t",
        "--threads",
        type=int,
        default=None,
        help="Override the number of concurrent tasks from config.yml.",
    )

    miscellaneous_group = parser.add_argument_group(
        title="Miscellaneous Arguments",
        description=textwrap.dedent(
            """\
            Miscellaneous Arguments:
            --only-circularized: Process only circularized NOVOPlasty assemblies.
            --no-only-circularized: Process circularized and non-circularized assemblies.
            --fig-format: Override the figure format from config.yml.
            --dpi: Override the figure DPI from config.yml.
            """
        ),
    )

    miscellaneous_group.add_argument(
        "--only-circularized",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Override the circularized-only setting from config.yml."
        ),
    )

    miscellaneous_group.add_argument(
        "--fig-format",
        type=str,
        default=None,
        help="Override the figure format from config.yml.",
    )

    miscellaneous_group.add_argument(
        "--dpi",
        type=int,
        default=None,
        help="Override the figure DPI from config.yml.",
    )

    arguments = parser.parse_args()

    try:
        asyncio.run(
            run_pipeline(
                results_dir=arguments.results_dir,
                output_dir=arguments.output_dir,
                config_file=arguments.config,
                concurrency=arguments.threads,
                only_circularized=arguments.only_circularized,
                dpi=arguments.dpi,
                fig_format=arguments.fig_format,
                metadata_path=arguments.metadata,
            )
        )
    except Exception as error:
        logging.exception(
            "An error occurred: %s",
            error,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
