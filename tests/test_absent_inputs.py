"""Parsers for OrganPipe files that the example dataset does not contain.

The example dataset has no nhmmer tables, fastp reports or Snakemake
benchmarks. These fixtures follow the documented formats (HMMER --tblout,
fastp JSON, Snakemake benchmark TSV); replace them with real excerpts when a
current OrganPipe run is available.
"""

import json
import os

import pandas as pd

from moCURA.analysis.provenance import environment_pins, load_benchmarks, parse_benchmark_file
from moCURA.generate.generate_excel import append_excel_sheets, generate_excel
from moCURA.load.load_fastp_data import fastp_candidates, parse_fastp_json
from moCURA.load.load_nhmmer_data import overlaps, parse_tblout


def test_parse_tblout_and_intergenic_check(fixture_text):
    hits = parse_tblout(text=fixture_text("format_examples", "intergenes_filter.tblout.out"))
    assert len(hits) == 2
    assert hits[0]["Query model"] == "trnF"
    assert (hits[0]["Alignment start"], hits[0]["Alignment end"]) == (15962, 16030)
    features = [{"start": 15961, "stop": 16029}]
    assert overlaps(start=15962, end=16030, features=features) is True
    assert overlaps(start=hits[1]["Alignment start"], end=hits[1]["Alignment end"], features=features) is False


def test_parse_fastp_json(fixture_text):
    record = parse_fastp_json(document=json.loads(fixture_text("format_examples", "fastp.json")))
    assert record["Reads before filtering"] == 16631016
    assert record["Reads after filtering"] == 16210450
    assert record["Q30 rate after"] == 0.941
    assert record["Duplication rate"] == 0.0312


def test_fastp_candidate_paths():
    paths = fastp_candidates(project="ITV38325", results_dir="/run/results", organpipe_dir="/run")
    assert paths[0] == os.path.join("/run", "resources", "ITV38325", "rawreads", "fastp.json")


def test_benchmarks_are_aggregated_per_rule(tmp_path, fixture_text):
    sample = tmp_path / "benchmarks" / "ITV38325"
    for rule, name in (("pilon", "a.benchmark"), ("pilon", "b.benchmark"), ("mitos2", "c.benchmark")):
        (sample / rule).mkdir(parents=True, exist_ok=True)
        (sample / rule / name).write_text(fixture_text("format_examples", "snakemake.benchmark"))
    (sample / "notes.txt").write_text("not a benchmark\n")
    assert parse_benchmark_file(path=str(sample / "notes.txt")) is None

    table = load_benchmarks(organpipe_dir=str(tmp_path), projects=["ITV38325"])
    pilon = table[table["Rule"] == "pilon"].iloc[0]
    assert pilon["Runs"] == 2
    assert pilon["Wall time (s)"] == 2 * 12.5
    assert pilon["Max RSS (MB)"] == 812.3
    assert set(table["Rule"]) == {"pilon", "mitos2"}


def test_missing_benchmarks_give_empty_table(tmp_path):
    assert load_benchmarks(organpipe_dir=str(tmp_path), projects=[]).empty


def test_environment_pins_from_repository():
    pins = environment_pins()
    assert pins["python"] == "3.14"
    assert "biopython" in pins


def test_extra_sheets_and_appended_provenance(tmp_path):
    output = tmp_path / "moCURA_summary.xlsx"
    summary = pd.DataFrame({"Project name": ["P"], "K-mer": [20], "Seed Input": ["ND1"]})
    generate_excel(
        dataframe=summary, genbank_files_dataframe=pd.DataFrame(), marker_dataframe=pd.DataFrame(),
        trf_summary_dataframe=pd.DataFrame(), trf_repeats_dataframe=pd.DataFrame(),
        output_file=str(output), separate_groups=False,
        extra_sheets=[("Coverage", pd.DataFrame({"Mean depth": [1.0]})), ("Empty", pd.DataFrame())],
    )
    append_excel_sheets(output_file=str(output), sheets=[("Provenance", pd.DataFrame({"Item": ["x"], "Value": ["y"]}))])
    assert list(pd.read_excel(output, sheet_name=None)) == ["Summary", "Coverage", "Provenance"]
