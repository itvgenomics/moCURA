"""Read-level QC from OrganPipe fastp reports.

OrganPipe keeps one fastp report per sample at
``{organpipe_dir}/resources/{sample}/rawreads/fastp.json``. Older layouts may
keep it next to the results, so ``{results_dir}/{sample}/rawreads/fastp.json``
and ``{results_dir}/{sample}/fastp.json`` are also checked.
"""

import asyncio
import json
import logging
import os

import pandas as pd

from ..utils.gather_records import gather_records
from ..utils.read_text_async import read_text_async


FASTP_COLUMNS = [
    "Project name", "Reads before filtering", "Reads after filtering", "Bases before filtering",
    "Bases after filtering", "Q30 rate before", "Q30 rate after", "GC content before", "GC content after",
    "Duplication rate", "Passed filter reads", "Low quality reads", "Too many N reads", "Too short reads",
    "Mean read length after", "fastp report",
]


def fastp_candidates(**kwargs):
    project = kwargs.get("project")
    results_dir = kwargs.get("results_dir")
    organpipe_dir = kwargs.get("organpipe_dir")
    candidates = []
    if organpipe_dir:
        candidates.append(os.path.join(organpipe_dir, "resources", project, "rawreads", "fastp.json"))
    candidates.append(os.path.join(results_dir, project, "rawreads", "fastp.json"))
    candidates.append(os.path.join(results_dir, project, "fastp.json"))
    return candidates


def parse_fastp_json(**kwargs):
    """Flatten the fields moCURA reports from a fastp JSON document."""

    document = kwargs.get("document", {}) or {}
    summary = document.get("summary", {})
    before = summary.get("before_filtering", {})
    after = summary.get("after_filtering", {})
    filtering = document.get("filtering_result", {})

    return {
        "Reads before filtering": before.get("total_reads"),
        "Reads after filtering": after.get("total_reads"),
        "Bases before filtering": before.get("total_bases"),
        "Bases after filtering": after.get("total_bases"),
        "Q30 rate before": before.get("q30_rate"),
        "Q30 rate after": after.get("q30_rate"),
        "GC content before": before.get("gc_content"),
        "GC content after": after.get("gc_content"),
        "Duplication rate": document.get("duplication", {}).get("rate"),
        "Passed filter reads": filtering.get("passed_filter_reads"),
        "Low quality reads": filtering.get("low_quality_reads"),
        "Too many N reads": filtering.get("too_many_N_reads"),
        "Too short reads": filtering.get("too_short_reads"),
        "Mean read length after": after.get("read1_mean_length"),
    }


async def parse_fastp_report(**kwargs):
    path = kwargs.get("path")
    project = kwargs.get("project")
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        text = await read_text_async(file_path=path)
    return {"Project name": project, **parse_fastp_json(document=json.loads(text)), "fastp report": path}


async def load_fastp_data(**kwargs):
    projects = kwargs.get("projects", [])
    results_dir = kwargs.get("results_dir")
    organpipe_dir = kwargs.get("organpipe_dir")
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))

    tasks = []
    for project in projects:
        path = next((p for p in fastp_candidates(project=project, results_dir=results_dir, organpipe_dir=organpipe_dir) if os.path.isfile(p)), None)
        if path is None:
            logging.debug("fastp report not found for %s", project)
            continue
        tasks.append(parse_fastp_report(path=path, project=project, semaphore=semaphore))

    if len(tasks) < len(projects):
        logging.warning("fastp reports missing for %d of %d projects; their read QC is NA", len(projects) - len(tasks), len(projects))

    records = await gather_records(tasks=tasks, source_name="fastp report")
    return pd.DataFrame(records, columns=FASTP_COLUMNS)
