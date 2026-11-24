"""Benchmarks and provenance for the Provenance sheet and report section.

* Snakemake benchmarks: ``{organpipe_dir}/benchmarks/{sample}/**`` files whose
  header starts with ``s\th:m:s``. They are aggregated per rule and per sample.
* moCURA's own wall time and peak memory, measured in this process.
* Tool versions pinned in ``environment.yml`` and the versions actually
  imported, the effective configuration, and the git commit when available.
"""

import collections
import datetime
import importlib.metadata
import logging
import os
import platform
import resource
import subprocess
import sys
import time

import pandas as pd
import yaml


BENCHMARK_COLUMNS = ["Project name", "Rule", "Runs", "Wall time (s)", "CPU time (s)", "Max RSS (MB)"]
PROVENANCE_COLUMNS = ["Category", "Item", "Value"]
RUNTIME_PACKAGES = ["biopython", "pandas", "numpy", "openpyxl", "pyyaml", "matplotlib", "seaborn", "SynGenes"]

_START_TIME = time.time()


def repository_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_benchmark_file(**kwargs):
    """Return the first data row of a Snakemake benchmark file as a dict, or None."""

    path = kwargs.get("path")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            header = handle.readline().rstrip("\n").split("\t")
            values = handle.readline().rstrip("\n").split("\t")
    except OSError:
        return None

    if not header or header[0] != "s" or len(header) < 2 or header[1] != "h:m:s":
        return None

    row = dict(zip(header, values))

    def number(name):
        try:
            return float(row.get(name, "")) if row.get(name, "") not in {"", "-", "NA"} else None
        except ValueError:
            return None

    return {"s": number("s"), "max_rss": number("max_rss"), "cpu_time": number("cpu_time")}


def benchmark_rule_name(**kwargs):
    """Rule name from a benchmark path: the first folder under the sample, else the file stem."""

    relative = kwargs.get("relative_path")
    parts = relative.replace("\\", "/").split("/")
    if len(parts) > 1:
        return parts[0]
    return os.path.splitext(parts[0])[0]


def load_benchmarks(**kwargs):
    """Aggregate Snakemake benchmarks per sample and rule."""

    organpipe_dir = kwargs.get("organpipe_dir")
    projects = set(kwargs.get("projects", []))
    benchmarks_dir = os.path.join(organpipe_dir, "benchmarks") if organpipe_dir else None

    if not benchmarks_dir or not os.path.isdir(benchmarks_dir):
        logging.warning("Snakemake benchmarks folder not found; benchmark table is empty")
        return pd.DataFrame(columns=BENCHMARK_COLUMNS)

    totals = collections.defaultdict(lambda: {"Runs": 0, "Wall time (s)": 0.0, "CPU time (s)": 0.0, "Max RSS (MB)": 0.0})
    for project in sorted(os.listdir(benchmarks_dir)):
        project_dir = os.path.join(benchmarks_dir, project)
        if not os.path.isdir(project_dir) or (projects and project not in projects):
            continue
        for root, _, files in os.walk(project_dir):
            for file_name in files:
                path = os.path.join(root, file_name)
                row = parse_benchmark_file(path=path)
                if row is None:
                    continue
                rule = benchmark_rule_name(relative_path=os.path.relpath(path, project_dir))
                entry = totals[(project, rule)]
                entry["Runs"] += 1
                entry["Wall time (s)"] += row["s"] or 0.0
                entry["CPU time (s)"] += row["cpu_time"] or 0.0
                entry["Max RSS (MB)"] = max(entry["Max RSS (MB)"], row["max_rss"] or 0.0)

    records = [{"Project name": project, "Rule": rule, **values} for (project, rule), values in sorted(totals.items())]
    return pd.DataFrame(records, columns=BENCHMARK_COLUMNS).round(2)


def environment_pins(**kwargs):
    """Dependencies pinned in environment.yml, as {name: version}."""

    path = kwargs.get("path") or os.path.join(repository_root(), "environment.yml")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        document = yaml.safe_load(handle) or {}
    pins = {}
    for dependency in document.get("dependencies", []):
        if isinstance(dependency, str):
            name, _, version = dependency.partition("=")
            pins[name.strip()] = version.strip("=") or "unpinned"
        elif isinstance(dependency, dict):
            for item in dependency.get("pip", []):
                name, _, version = item.partition("==")
                pins[f"pip:{name.strip()}"] = version.strip() or "unpinned"
    return pins


def git_commit():
    root = repository_root()
    if not os.path.isdir(os.path.join(root, ".git")):
        return "not a git checkout"
    try:
        output = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        commit = output.stdout.strip() or "unknown"
        dirty = subprocess.run(["git", "-C", root, "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, timeout=10)
        return f"{commit}{' (uncommitted changes)' if dirty.stdout.strip() else ''}"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def peak_memory_mb():
    """Peak resident memory of moCURA and its child processes (MAFFT, TRF), in MB."""

    self_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    children_kb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    divisor = 1024 * 1024 if sys.platform == "darwin" else 1024
    return round(self_kb / divisor, 1), round(children_kb / divisor, 1)


def flatten(**kwargs):
    value = kwargs.get("value")
    prefix = kwargs.get("prefix", "")
    if isinstance(value, dict):
        rows = []
        for key, item in value.items():
            if "api_key" in str(key):
                item = "(set)" if item else "(empty)"
            rows.extend(flatten(value=item, prefix=f"{prefix}.{key}" if prefix else str(key)))
        return rows
    return [(prefix, value if not isinstance(value, list) else ", ".join(map(str, value)))]


def build_provenance(**kwargs):
    """Return the provenance table as a dataframe."""

    config = kwargs.get("config", {})
    arguments = kwargs.get("arguments", {})
    organpipe_dir = kwargs.get("organpipe_dir")
    rows = []

    elapsed = time.time() - _START_TIME
    self_mb, children_mb = peak_memory_mb()
    rows += [
        ("Run", "Finished at", datetime.datetime.now().astimezone().isoformat(timespec="seconds")),
        ("Run", "Wall time (s)", round(elapsed, 1)),
        ("Run", "Peak memory, moCURA (MB)", self_mb),
        ("Run", "Peak memory, child processes (MB)", children_mb),
        ("Run", "moCURA commit", git_commit()),
        ("Run", "Python", platform.python_version()),
        ("Run", "Platform", platform.platform()),
        ("Run", "OrganPipe directory", organpipe_dir or "not found"),
    ]
    rows += [("Arguments", key, value) for key, value in arguments.items()]
    for name in RUNTIME_PACKAGES:
        try:
            rows.append(("Imported package", name, importlib.metadata.version(name)))
        except importlib.metadata.PackageNotFoundError:
            continue
    rows += [("environment.yml", name, version) for name, version in environment_pins().items()]
    rows += [("Effective configuration", key, value) for key, value in flatten(value=config)]

    return pd.DataFrame([{"Category": c, "Item": i, "Value": "" if v is None else str(v)} for c, i, v in rows], columns=PROVENANCE_COLUMNS)
