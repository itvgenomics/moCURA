import asyncio
import logging
import os
import re

import pandas as pd
from ..standardization.standardized_gene_name import standardized_gene_name
from ..utils.gather_records import gather_records
from ..utils.pilon_columns import PILON_COLUMNS
from ..utils.read_text_async import read_text_async
from ..utils.to_integer import to_integer
from .organpipe_layout import is_assembler_directory, step_directories

def parse_pilon_text(**kwargs):
    text = kwargs.get("text", None)

    if text is None:
        raise ValueError("No text provided for parsing")

    genome_match = re.search(
        r"^\s*Genome:\s*(.*?)\s*$",
        text,
        flags=re.MULTILINE,
    )

    reads_match = re.search(
        r"(?P<reads>\d+)\s+reads,\s*(?P<filtered>\d+)\s+filtered,\s*"
        r"(?P<mapped>\d+)\s+mapped,\s*(?P<proper>\d+)\s+proper,\s*"
        r"(?P<stray>\d+)\s+stray,\s*FR\s+(?P<fr_percent>\d+)%\s+"
        r"(?P<insert_mean>\d+)\+/-(?P<insert_stddev>\d+),\s*"
        r"max\s+(?P<max_frags>\d+)\s+frags",
        text,
    )

    totals_match = re.search(
        r"Total Reads:\s*(?P<total_reads>\d+),\s*Coverage:\s*(?P<coverage>\d+),\s*"
        r"minDepth:\s*(?P<min_depth>\d+)",
        text,
    )

    confirmed_match = re.search(
        r"Confirmed\s+(?P<confirmed_bases>\d+)\s+of\s+"
        r"(?P<total_bases>\d+)\s+bases\s*"
        r"\((?P<confirmed_percent>[\d.]+)%\)",
        text,
    )

    corrected_match = re.search(
        r"Corrected\s+(?P<snps>\d+)\s+snps;\s*"
        r"(?P<ambiguous>\d+)\s+ambiguous bases;\s*"
        r"corrected\s+(?P<ins_count>\d+)\s+small insertions totaling\s+"
        r"(?P<ins_bases>\d+)\s+bases,\s*"
        r"(?P<del_count>\d+)\s+small deletions totaling\s+"
        r"(?P<del_bases>\d+)\s+bases",
        text,
    )
    

    def group_integer(match: re.Match[str] | None, group_name: str) -> int | None:
        return (
            to_integer(value=match.group(group_name))
            if match
            else None
        )

    return {
        "Pilon Genome": genome_match.group(1) if genome_match else "-",
        "Pilon Reads": group_integer(reads_match, "reads"),
        "Pilon Filtered": group_integer(reads_match, "filtered"),
        "Pilon Mapped": group_integer(reads_match, "mapped"),
        "Pilon Proper": group_integer(reads_match, "proper"),
        "Pilon Stray": group_integer(reads_match, "stray"),
        "Pilon FR %": group_integer(reads_match, "fr_percent"),
        "Pilon Insert size mean": group_integer(reads_match, "insert_mean"),
        "Pilon Insert size stddev": group_integer(reads_match, "insert_stddev"),
        "Pilon Max frags": group_integer(reads_match, "max_frags"),
        "Pilon Total Reads": group_integer(totals_match, "total_reads"),
        "Pilon Coverage": group_integer(totals_match, "coverage"),
        "Pilon minDepth": group_integer(totals_match, "min_depth"),
        "Pilon Confirmed bases": group_integer(confirmed_match, "confirmed_bases"),
        "Pilon Total bases": group_integer(confirmed_match, "total_bases"),
        "Pilon Confirmed %": (
            float(confirmed_match.group("confirmed_percent"))
            if confirmed_match
            else None
        ),
        "Pilon Corrected snps": group_integer(corrected_match, "snps"),
        "Pilon Ambiguous bases": group_integer(corrected_match, "ambiguous"),
        "Pilon Corrected insertions": group_integer(corrected_match, "ins_count"),
        "Pilon Corrected insertions bases": group_integer(corrected_match, "ins_bases"),
        "Pilon Corrected deletions": group_integer(corrected_match, "del_count"),
        "Pilon Corrected deletions bases": group_integer(corrected_match, "del_bases"),
    }

async def parse_pilon_log(**kwargs):
    pilon_file = kwargs.get("pilon_file", None)
    project = kwargs.get("project", None)
    seed_input = kwargs.get("seed_input", None)
    kmer = kwargs.get("kmer", None)
    semaphore: asyncio.Semaphore = kwargs.get(
        "semaphore",
        asyncio.Semaphore(8),
    )

    if pilon_file is None or not os.path.isfile(pilon_file):
        raise FileNotFoundError(f"Pilon log file not found: {pilon_file}")

    async with semaphore:
        text = await read_text_async(file_path=pilon_file)

    record = parse_pilon_text(text=text)

    record.update(
        {
            "Project name": project,
            "K-mer": kmer,
            "Seed Input": seed_input,
        }
    )

    logging.info(f"Parsed Pilon log for project: {project}, seed: {seed_input}, k-mer: {kmer}")

    return record

def parse_pilon_dir_name(**kwargs):
    directory_name = kwargs.get("directory_name", None)
    project = kwargs.get("project", None)

    match = re.match(
        rf"^[A-Za-z]+_\d+_{re.escape(project)}_(?P<seed>.+)_(?P<kmer>\d+)_\d+$",
        directory_name,
    )
    if not match:
        return None, None

    seed_input = standardized_gene_name(
        value=match.group("seed")
    )

    kmer = to_integer(
        value=match.group("kmer")
    )

    return seed_input, kmer

def find_pilon_jobs(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    jobs = []

    if not os.path.isdir(results_dir):
        logging.warning(
            "Results directory does not exist: %s",
            results_dir,
        )
        return jobs

    for project_name in sorted(os.listdir(results_dir)):
        project_dir = os.path.join(
            results_dir,
            project_name,
        )

        if not os.path.isdir(project_dir):
            continue

        # Older OrganPipe runs use pilon/{asm}; current runs add pilon/{assembler}/{asm}.
        run_dirs = [
            (os.path.join(pilon_dir, run_dir_name), run_dir_name)
            for pilon_dir in step_directories(project_dir=project_dir, step="pilon")
            for run_dir_name in sorted(os.listdir(pilon_dir))
            if not is_assembler_directory(name=run_dir_name)
        ]

        for run_dir, run_dir_name in run_dirs:
            if not os.path.isdir(run_dir):
                continue

            seed_input, kmer = parse_pilon_dir_name(
                directory_name=run_dir_name,
                project=project_name,
            )

            if seed_input is None or kmer is None:
                logging.warning(
                    "Skipping Pilon run due to unrecognized directory name: %s",
                    run_dir,
                )
                continue

            pilon_file = None

            for file_name in ("pilon.log", "pilon.txt"):
                candidate_file = os.path.join(
                    run_dir,
                    file_name,
                )

                if os.path.isfile(candidate_file):
                    pilon_file = candidate_file
                    break

            if pilon_file is None:
                logging.info(
                    "Pilon log not found in: %s",
                    run_dir,
                )
                continue

            jobs.append(
                {
                    "pilon_file": pilon_file,
                    "project": project_name,
                    "seed_input": seed_input,
                    "kmer": kmer,
                }
            )

    return jobs

async def load_pilon_data(**kwargs):
    results_dir = kwargs.get("results_dir", "example_results")
    concurrency = int(kwargs.get("concurrency", 8))
    semaphore = asyncio.Semaphore(concurrency)

    jobs = find_pilon_jobs(results_dir=results_dir)
    logging.info(f"Found {len(jobs)} Pilon jobs in {results_dir}")

    tasks = [parse_pilon_log(**job, semaphore=semaphore) for job in jobs]
    records = await gather_records(tasks=tasks, source_name="Pilon log")

    dataframe = pd.DataFrame(records, columns=PILON_COLUMNS)

    if dataframe.empty:
        logging.warning("No Pilon records were successfully parsed")
        return dataframe

    dataframe["Pilon Total bases"] = pd.to_numeric(
        dataframe["Pilon Total bases"],
        errors="coerce",
    )

    dataframe = (
        dataframe.sort_values("Pilon Total bases", ascending=False, na_position="last")
        .drop_duplicates(subset=["Project name", "K-mer", "Seed Input"])
        .reset_index(drop=True)
    )

    logging.info(f"Unique Pilon records retained: {len(dataframe)}")

    return dataframe