#!/usr/bin/env python3
import argparse
import asyncio
import logging
import textwrap
import sys

from moCURA import MultiQCHelpFormatter, CustomArgumentParser, run_pipeline

TOOL_NAME = "moCURA"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y/%m/%d - %H:%M:%S",
)

def main():
    parser = CustomArgumentParser(
        prog=TOOL_NAME,
        usage='%(prog)s [options]',
        description=f'{TOOL_NAME} - pipeline for generating curated reports from organellar assembly results.',
        #epilog=
        formatter_class=lambda prog: MultiQCHelpFormatter(prog=prog),
        add_help=False,
        )

    input = parser.add_argument_group(
        title="Input Arguments",
        description=textwrap.dedent(
            """\
            Input Arguments:
            --results-dir: Absolute directory containing the results.
            """
        ),
    )

    input.add_argument(
        "-i",
        "--results-dir", 
        required=True, 
        help="Directory containing the organpipe results.",
        default="example_results"
        )

    output = parser.add_argument_group(
        title="Output Arguments",
        description=textwrap.dedent(
            """\
            Output Arguments:
            --output-dir: Absolute directory to store the output.
            """
        ),
    )
    output.add_argument(
        "-o",
        "--output-dir", 
        required=True, 
        help="Directory to store the output.",
        default="example_output"
        )

    threads = parser.add_argument_group(
        title="Threading Arguments",
        description=textwrap.dedent(
            """\
            Threading Arguments:
            --threads: Number of concurrent tasks.
            """
        ),
    )
    threads.add_argument(
        "-t",
        "--threads", 
        type=int, 
        default=20, 
        help="Number of concurrent tasks."
    )

    miscellaneous = parser.add_argument_group(
        title="Miscellaneous Arguments",
        description=textwrap.dedent(
            """\
            Miscellaneous Arguments:
            --only-circularized: Process only circularized organelles in NOVOPlasty.
            --fig-format: Format for output figures (e.g., png, svg).
            --dpi: DPI for output figures.
            """
        ),
    )
    miscellaneous.add_argument(
        "--only-circularized", 
        action="store_true", 
        help="Process only circularized organelles in NOVOPlasty."
    )
    miscellaneous.add_argument(
        "--fig-format",
        type=str, 
        default="png", 
        help="Format for output figures (e.g., png, svg)."
    )
    miscellaneous.add_argument(
        "--dpi", 
        type=int, 
        default=300, 
        help="DPI for output figures."
    )
    
    arguments = parser.parse_args()

    try:
        asyncio.run(
            run_pipeline(
                results_dir=arguments.results_dir,
                output_dir=arguments.output_dir,
                concurrency=arguments.threads,
                only_circularized=arguments.only_circularized,
                dpi=arguments.dpi,
                fig_format=arguments.fig_format
                )
        )
    except Exception as error:
        logging.error(f"An error occurred: {error}")
        sys.exit(1)
#
if __name__ == "__main__":
    main()