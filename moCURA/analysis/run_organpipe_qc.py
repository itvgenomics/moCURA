"""Phase 1: read what OrganPipe already produces and turn it into curation tables.

Each analysis has its own ``config.yml`` section with an ``enabled`` key. A
missing file logs a warning and leaves the corresponding values empty; it never
stops the run. Outputs:

* one Excel sheet per analysis (returned in ``excel_sheets``);
* reusable TSV files in subfolders of ``--output-dir``;
* records for the HTML report (returned in ``html``).
"""

import logging
import os

import pandas as pd

from ..load.load_coverage_data import load_coverage_data
from ..load.load_fastp_data import load_fastp_data
from ..load.load_mitos2_data import EXPECTED_MARKERS, load_mitos2_data
from ..load.load_nhmmer_data import load_nhmmer_data
from ..load.load_recruitment_data import IDENTITY_BINS, load_recruitment_data
from ..load.organpipe_layout import find_organpipe_assemblies
from .assembly_alerts import build_assembly_alerts
from .provenance import load_benchmarks


def write_tsv(**kwargs):
    """Write a dataframe as TSV inside ``output_dir/folder``; skip empty tables."""

    dataframe = kwargs.get("dataframe")
    output_dir = kwargs.get("output_dir")
    folder = kwargs.get("folder")
    file_name = kwargs.get("file_name")

    if dataframe is None or dataframe.empty:
        return None

    directory = os.path.join(output_dir, folder)
    os.makedirs(directory, exist_ok=True, mode=0o755)
    path = os.path.join(directory, file_name)
    dataframe.to_csv(path, sep="\t", index=False)
    return path


def windows_long_table(**kwargs):
    """Coverage windows in long format: one row per assembly window."""

    windows = kwargs.get("windows", [])
    rows = []
    for item in windows:
        size = item["Window size"]
        for index, value in enumerate(item["Windows"]):
            rows.append({
                **{key: item[key] for key in ("Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly")},
                "Coordinate system": item["Coordinate system"],
                "Window start": index * size + 1,
                "Window end": (index + 1) * size,
                "Mean depth": value,
            })
    return pd.DataFrame(rows)


def histograms_long_table(**kwargs):
    rows = []
    for item in kwargs.get("histograms", []):
        for low, count in zip(item["Identity bins"], item["Counts"]):
            rows.append({
                **{key: item[key] for key in ("Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly")},
                "Identity bin start": low,
                "Identity bin end": low + 0.5,
                "Reads": count,
            })
    return pd.DataFrame(rows)


def target_lengths_from_jobs(**kwargs):
    """Rotated sequence length per assembly, used for the BLAST target coverage."""

    from ..load.load_coverage_data import genbank_length_and_offset

    lengths = {}
    for job in kwargs.get("jobs", []):
        path = job["paths"].get("rotated_genbank") or job["paths"].get("genbank")
        length, _ = genbank_length_and_offset(path=path)
        if length:
            lengths[job["Assembly"]] = length
    return lengths


async def run_organpipe_qc(**kwargs):
    """Run the enabled Phase 1 analyses. Returns tables for Excel, TSV and HTML."""

    results_dir = kwargs.get("results_dir")
    output_dir = kwargs.get("output_dir")
    organpipe_dir = kwargs.get("organpipe_dir")
    concurrency = int(kwargs.get("concurrency", 8))
    allowed_keys = kwargs.get("allowed_keys")
    summary_dataframe = kwargs.get("summary_dataframe")
    config = kwargs.get("config", {}) or {}

    section = lambda name: config.get(name, {}) or {}
    enabled = lambda name: bool(section(name).get("enabled", True))
    folder = lambda name, default: section(name).get("output_folder", default)

    jobs = find_organpipe_assemblies(results_dir=results_dir, allowed_keys=allowed_keys)
    logging.info("OrganPipe assemblies found for Phase 1 analyses: %d", len(jobs))

    tables = {}
    html = {"expected_markers": EXPECTED_MARKERS, "identity_bins": IDENTITY_BINS}
    tsv_files = []

    def save(name, file_name, key, dataframe):
        tables[key] = dataframe
        path = write_tsv(dataframe=dataframe, output_dir=output_dir, folder=folder(name, name), file_name=file_name)
        if path:
            tsv_files.append(os.path.relpath(path, output_dir))

    completeness = origin = coverage = changes = breaks = nhmmer = pd.DataFrame()
    windows, histograms = [], []

    if jobs and enabled("mitos2_completeness"):
        completeness, origin = await load_mitos2_data(jobs=jobs, concurrency=concurrency)
        save("mitos2_completeness", "mitos2_completeness.tsv", "completeness", completeness)
        save("mitos2_completeness", "origin_check.tsv", "origin", origin)

    if jobs and (enabled("coverage_profile") or enabled("pilon_changes")):
        coverage_config = section("coverage_profile")
        coverage, windows, changes, breaks = await load_coverage_data(
            jobs=jobs,
            concurrency=concurrency,
            window_size=coverage_config.get("window_size", 50),
            low_depth_threshold=coverage_config.get("low_depth_threshold", 10),
        )
        if enabled("coverage_profile"):
            save("coverage_profile", "coverage_metrics.tsv", "coverage", coverage)
            save("coverage_profile", "coverage_windows.tsv", "coverage_windows", windows_long_table(windows=windows))
        else:
            coverage, windows = pd.DataFrame(), []
        if enabled("pilon_changes"):
            save("pilon_changes", "pilon_changes.tsv", "pilon_changes", changes)
            save("pilon_changes", "pilon_unresolved_breaks.tsv", "pilon_breaks", breaks)
        else:
            changes, breaks = pd.DataFrame(), pd.DataFrame()

    if jobs and enabled("read_recruitment"):
        recruitment, histograms = await load_recruitment_data(
            jobs=jobs,
            concurrency=concurrency,
            identity_threshold=section("read_recruitment").get("identity_threshold", 98),
            target_lengths=target_lengths_from_jobs(jobs=jobs),
        )
        save("read_recruitment", "read_recruitment.tsv", "recruitment", recruitment)
        save("read_recruitment", "identity_histograms.tsv", "identity_histograms", histograms_long_table(histograms=histograms))

    if jobs and enabled("nhmmer_alerts"):
        nhmmer = await load_nhmmer_data(jobs=jobs, concurrency=concurrency, max_evalue=section("nhmmer_alerts").get("max_evalue", 1e-3))
        save("nhmmer_alerts", "nhmmer_hits.tsv", "nhmmer", nhmmer)

    projects = sorted({job["Project name"] for job in jobs})
    if enabled("read_qc"):
        fastp = await load_fastp_data(projects=projects, results_dir=results_dir, organpipe_dir=organpipe_dir, concurrency=concurrency)
        save("read_qc", "read_qc.tsv", "read_qc", fastp)

    if enabled("provenance"):
        benchmarks = load_benchmarks(organpipe_dir=organpipe_dir, projects=projects)
        save("provenance", "benchmarks.tsv", "benchmarks", benchmarks)

    if jobs and enabled("assembly_alerts"):
        alerts = build_assembly_alerts(
            jobs=jobs,
            summary_dataframe=summary_dataframe,
            completeness_dataframe=completeness,
            origin_dataframe=origin,
            coverage_dataframe=coverage,
            breaks_dataframe=breaks,
            nhmmer_dataframe=nhmmer,
            low_coverage_percent=section("coverage_profile").get("low_coverage_alert_percent", 5),
        )
        save("assembly_alerts", "assembly_alerts.tsv", "alerts", alerts)

    sheet_names = [
        ("completeness", "MITOS2 Completeness"),
        ("origin", "Origin Check"),
        ("coverage", "Coverage"),
        ("pilon_changes", "Pilon Changes"),
        ("pilon_breaks", "Pilon Breaks"),
        ("recruitment", "Read Recruitment"),
        ("nhmmer", "nhmmer Hits"),
        ("read_qc", "Read QC"),
        ("benchmarks", "Benchmarks"),
        ("alerts", "Assembly Alerts"),
    ]
    excel_sheets = [(sheet, tables[key]) for key, sheet in sheet_names if key in tables and not tables[key].empty]

    html.update({key: tables.get(key, pd.DataFrame()) for key in ("completeness", "origin", "coverage", "pilon_changes", "pilon_breaks", "recruitment", "nhmmer", "read_qc", "benchmarks", "alerts")})
    html["coverage_windows"] = windows
    html["identity_histograms"] = histograms

    return {"excel_sheets": excel_sheets, "html": html, "tsv_files": tsv_files, "organpipe_dir": organpipe_dir}
