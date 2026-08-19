import asyncio
import logging
import os
import re

import pandas as pd

from ..utils.read_text_async import read_text_async
from ..utils.to_integer import to_integer
from ..standardization.standardized_gene_name import standardized_gene_name
from ..utils.gather_records import gather_records

NOVOPLASTY_COLUMNS = [
    "Project name",
    "K-mer",
    "Genome range",
    "Seed Input",
    "Total contigs",
    "Largest contig",
    "Smallest contig",
    "Average organelle coverage",
    "Circularized",
]

def extract_last_match(text: str, pattern: str) -> str | None:
    """Return the last regex match found in a log."""
    matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    return matches[-1].strip() if matches else None

def parse_novoplasty_text(text):
    """Parse the content of one NOVOPlasty log."""
    patterns = {
        "Project name": r"^\s*Project name\s*=\s*(.*?)\s*$",
        "K-mer": r"^\s*K-mer\s*=\s*(\d+)\s*$",
        "Genome range": r"^\s*Genome range\s*=\s*(.*?)\s*$",
        "Seed Input": r"^\s*Seed Input\s*=\s*(.*?)\s*$",
        "Total contigs": r"^\s*Total contigs\s*:\s*(\d+)\s*$",
        "Largest contig": r"^\s*Largest contig\s*:\s*(\d+)\s*bp\s*$",
        "Smallest contig": r"^\s*Smallest contig\s*:\s*(\d+)\s*bp\s*$",
        "Average organelle coverage": (
            r"^\s*Average organelle coverage\s*:\s*([\d.,]+)\s*(?:x|X)?\s*$"
        ),
    }

    values = {
        column: extract_last_match(text, pattern)
        for column, pattern in patterns.items()
    }
    coverage = values["Average organelle coverage"]

    return {
        "Project name": values["Project name"] or "-",
        "K-mer": to_integer(value=values["K-mer"]),
        "Genome range": values["Genome range"] or "-",
        "Seed Input": (
            standardized_gene_name(
                value=values["Seed Input"]
            )
            if values["Seed Input"]
            else "-"
        ),
        "Total contigs": to_integer(value=values["Total contigs"]),
        "Largest contig": to_integer(value=values["Largest contig"], maximum=10_000_000),
        "Smallest contig": to_integer(value=values["Smallest contig"], maximum=10_000_000),
        "Average organelle coverage": (
            float(coverage.replace(",", ".")) if coverage else None
        ),
        "Circularized": bool(
            re.search(
                r"genome has been circularized",
                text,
                flags=re.IGNORECASE,
            )
        ),
    }

def find_novoplasty_logs(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    log_files = []

    for root, _, files in os.walk(results_dir):
        directory_parts = [
            directory_name.lower()
            for directory_name in os.path.normpath(root).split(os.sep)
        ]

        if "novoplasty" not in directory_parts:
            continue

        for file_name in files:
            file_name_lower = file_name.lower()

            if not file_name_lower.startswith("log_"):
                continue

            if not file_name_lower.endswith(".txt"):
                continue

            if "extended" in file_name_lower:
                continue

            log_files.append(
                os.path.join(root, file_name)
            )

    return sorted(set(log_files))

async def parse_novoplasty_log(**kwargs):
    log_file = kwargs.get("log_file", None)
    semaphore: asyncio.Semaphore = kwargs.get(
        "semaphore",
        asyncio.Semaphore(8),
    )

    async with semaphore:
        text = await read_text_async(file_path=log_file)

    record = parse_novoplasty_text(text)
    #logging.info(f"Parsed NOVOPlasty log: {log_file} -> {record}")

    return record

async def load_novoplasty_data(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    concurrency = int(kwargs.get("concurrency", 8))
    semaphore = asyncio.Semaphore(concurrency)

    log_files = find_novoplasty_logs(results_dir=results_dir)

    logging.info(f"Found {len(log_files)} NOVOPlasty log files", )

    tasks = [
        parse_novoplasty_log(log_file=log_file, semaphore=semaphore)
        for log_file in log_files
    ]

    records = await gather_records(tasks=tasks, source_name="NOVOPlasty log")

    dataframe = pd.DataFrame(records, columns=NOVOPLASTY_COLUMNS)

    if dataframe.empty:
        logging.warning("No valid NOVOPlasty records were found")
        return dataframe

    dataframe = dataframe.sort_values(
        ["Project name", "K-mer", "Seed Input", "Largest contig"],
        na_position="last",
    ).reset_index(drop=True)

    logging.info("NOVOPlasty records parsed: %d", len(dataframe))

    return dataframe