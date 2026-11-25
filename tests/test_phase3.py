"""Phase 3 analyses.

Real fixtures in ``tests/fixtures/phase3``:

* ``ITV38325_COIII_k20.rotated_excerpt.bam``: reads of the rotated BAM of
  CA_1_ITV38325_7-cytochrome_c_oxidase_subunit_III_20_1 overlapping 5300-5520
  and 15780-15960 (2,731 records, no base qualities, as OrganPipe writes them),
  with its rotated GenBank ``ITV38325_COIII_k20.rotated.gb``;
* ``table2asn_raw_mitos2.val`` / ``.dr``: table2asn 1.29.324 output for the raw
  MITOS2 GenBank of CA_1_ITV38302_12-NADH_dehydrogenase_subunit_6_20_1;
* ``bold_ITV38302_COI.ndjson``: BOLD v5 ID engine answer (public.tax-derep) for
  the COI of that assembly; ``blast_ITV38302_COI.json``: the first 15 hits of
  the NCBI megablast answer (core_nt, JSON2_S);
* ``taxonomy_1227502.xml``: NCBI taxonomy of Kinosternon scorpioides;
* ``NC_014577.gb``: RefSeq mitogenome of Kinosternon leucostomum.
"""

import asyncio
import json
import os
import shutil
import time

import pandas as pd
import pytest
from Bio import SeqIO

from moCURA.analysis.assembly_alerts import build_assembly_alerts
from moCURA.analysis.heteroplasmy import has_base_qualities, heteroplasmy_assembly_sync, repeat_intervals
from moCURA.analysis.ncbi_validation import feature_table, parse_discrepancies, parse_validation, run_ncbi_validation, select_jobs
from moCURA.analysis.reference_comparison import assembly_repeats, compare_project, genome_genes, range_status
from moCURA.analysis.run_organpipe_qc import declared_species, organelle_from_organpipe
from moCURA.analysis.species_identification import (
    blast_hits, bold_hits, identify_project, rank_species, representative_jobs, taxonomy_lineage, verdict,
)
from moCURA.utils.remote_service import RateLimiter, RemoteService, read_env_file

import pysam


ASSEMBLY = "CA_1_ITV38325_7-cytochrome_c_oxidase_subunit_III_20_1"


def coiii_job(fixture_path):
    return {
        "Project name": "ITV38325", "Seed order": 7, "Seed Input": "COIII", "K-mer": 20, "Assembly copy": 1, "Assembly": ASSEMBLY,
        "paths": {
            "rotated_bam": fixture_path("phase3", "ITV38325_COIII_k20.rotated_excerpt.bam"),
            "rotated_genbank": fixture_path("phase3", "ITV38325_COIII_k20.rotated.gb"),
        },
    }


def coi_job(fixture_path, tmp_path):
    """A job whose rotated GenBank holds the ITV38302 COI as a single CDS."""

    sequence = open(fixture_path("phase3", "ITV38302_COI.fasta")).read().split("\n", 1)[1].replace("\n", "")
    path = tmp_path / "coi.gb"
    path.write_text(
        "LOCUS       coi                     1549 bp    DNA     linear   UNK 01-JAN-1980\n"
        "FEATURES             Location/Qualifiers\n"
        "     CDS             1..1549\n"
        "                     /gene=\"cox1\"\n"
        "ORIGIN\n" + "\n".join(f"{i + 1:>9} {sequence[i:i + 60].lower()}" for i in range(0, len(sequence), 60)) + "\n//\n"
    )
    return {"Project name": "ITV38302", "Seed order": 12, "Seed Input": "ND6", "K-mer": 20, "Assembly copy": 1,
            "Assembly": "CA_1_ITV38302_12-NADH_dehydrogenase_subunit_6_20_1", "paths": {"rotated_genbank": str(path)}}


class FixtureService:
    """Stands in for RemoteService with the saved answers of BOLD, BLAST and NCBI taxonomy."""

    rate = 3

    def __init__(self, fixture_path):
        self.fixture_path = fixture_path
        self.blast_queries = []
        self.bold_batches = []

    async def bold(self, **kwargs):
        self.bold_batches.append(sorted(kwargs.get("sequences", {})))
        with open(self.fixture_path("phase3", "bold_ITV38302_COI.ndjson")) as handle:
            record = json.loads(handle.readline())
        return {identifier: record for identifier in kwargs.get("sequences", {})}

    async def blast(self, **kwargs):
        self.blast_queries.append(kwargs.get("entrez_query"))
        if kwargs.get("entrez_query"):
            return None
        with open(self.fixture_path("phase3", "blast_ITV38302_COI.json")) as handle:
            return json.load(handle)

    async def eutils(self, endpoint, params, **kwargs):
        if endpoint == "esearch":
            return {"esearchresult": {"idlist": ["1227502"] if "Kinosternon" in params["term"] else []}}
        with open(self.fixture_path("phase3", "taxonomy_1227502.xml")) as handle:
            return handle.read()


# ---------------- heteroplasmy ----------------

def test_heteroplasmy_finds_the_coi_site_and_flags_the_cluster(fixture_path, tmp_path):
    summary, sites = heteroplasmy_assembly_sync(job=coiii_job(fixture_path), settings={}, index_dir=str(tmp_path / "index"))
    by_position = {site["Position"]: site for site in sites}
    site = by_position[5407]
    assert (site["Region"], site["Major base"], site["Minor base"], site["Depth"]) == ("COI", "G", "A", 172)
    assert site["Minor frequency"] == pytest.approx(22 / 172, abs=1e-4)
    assert (site["Minor reads forward"], site["Minor reads reverse"], site["Confidence"]) == (13, 9, "high")
    cluster = [by_position[position] for position in (15873, 15875, 15877, 15879)]
    assert all(item["Confidence"] == "low" and "candidate sites within 20 bp" in item["Reason"] for item in cluster)
    assert summary["High-confidence sites"] == 1 and summary["Candidate sites"] == 5
    assert summary["Regions"] == "COI"
    assert summary["Base qualities"].startswith("absent")
    # the index is written to the output folder, never next to the input BAM
    assert os.path.isfile(tmp_path / "index" / "ITV38325_COIII_k20.rotated_excerpt.bam.bai")
    assert not os.path.isfile(fixture_path("phase3", "ITV38325_COIII_k20.rotated_excerpt.bam.bai"))


def test_heteroplasmy_thresholds_and_repeats_change_the_confidence(fixture_path, tmp_path):
    _, strict = heteroplasmy_assembly_sync(job=coiii_job(fixture_path), settings={"min_frequency": 0.2}, index_dir=str(tmp_path))
    assert {site["Position"] for site in strict} == {15873, 15877}
    repeats = repeat_intervals(dataframe=pd.DataFrame([{"Project name": "ITV38325", "Seed Input": "COIII", "K-mer": 20, "Assembly copy": 1, "Start": 5400, "End": 5410}]))
    summary, sites = heteroplasmy_assembly_sync(job=coiii_job(fixture_path), settings={}, index_dir=str(tmp_path),
                                                repeats=repeats[("ITV38325", "COIII", 20, 1)])
    assert summary["High-confidence sites"] == 0
    assert "inside a tandem repeat" in [site for site in sites if site["Position"] == 5407][0]["Reason"]


def test_heteroplasmy_without_bam_returns_none(fixture_path, tmp_path):
    job = coiii_job(fixture_path)
    job["paths"]["rotated_bam"] = None
    assert heteroplasmy_assembly_sync(job=job, settings={}, index_dir=str(tmp_path)) is None


def test_organpipe_bam_has_no_base_qualities(fixture_path):
    with pysam.AlignmentFile(fixture_path("phase3", "ITV38325_COIII_k20.rotated_excerpt.bam")) as handle:
        assert has_base_qualities(handle) is False


# ---------------- NCBI validation ----------------

def test_feature_table_uses_ncbi_products_and_completes_incomplete_stops(fixture_path):
    record = next(SeqIO.parse(fixture_path("ITV38325", "rotated.gb"), "genbank"))
    table, completed = feature_table(record=record, sequence_id="asm", genetic_code=2)
    lines = table.splitlines()
    assert lines[0] == ">Feature asm"
    assert "\t\t\tproduct\tcytochrome c oxidase subunit I" in lines
    assert "\t\t\tproduct\t12S ribosomal RNA" in lines
    assert "\t\t\tproduct\ttRNA-Leu" in lines and "\t\t\tgene\ttrnL1" in lines
    assert sum(1 for line in lines if line.endswith("\tCDS")) == 13
    assert sum(1 for line in lines if line.endswith("\tgene")) == 13 + 2 + 22
    assert completed == sum(1 for line in lines if line.startswith("\t\t\ttransl_except\t(pos:"))
    assert completed > 0
    assert all("aa:TERM)" in line for line in lines if "transl_except" in line)


def test_parse_table2asn_outputs_of_the_raw_mitos2_genbank(fixture_path):
    messages = parse_validation(path=fixture_path("phase3", "table2asn_raw_mitos2.val"))
    codes = pd.Series([message["Code"] for message in messages]).value_counts().to_dict()
    assert codes["SEQ_FEAT.MissingTrnaAA"] == 21
    assert codes["SEQ_FEAT.MissingProteinName"] == 13
    assert codes["SEQ_FEAT.NoStop"] == 5
    no_stop = [message for message in messages if message["Code"] == "SEQ_FEAT.NoStop"][0]
    assert no_stop["Severity"] == "error" and no_stop["Location"] == "c2318-1177"
    assert "BIOSEQ" not in no_stop["Message"]
    discrepancies = parse_discrepancies(path=fixture_path("phase3", "table2asn_raw_mitos2.dr"))
    assert [item["Code"] for item in discrepancies] == ["RNA_NO_PRODUCT"]


@pytest.mark.skipif(shutil.which("table2asn") is None, reason="table2asn not installed")
def test_table2asn_accepts_the_converted_annotation(fixture_path, tmp_path):
    job = {"Project name": "ITV38325", "Seed order": 1, "Seed Input": "ND1", "K-mer": 20, "Assembly copy": 1,
           "Assembly": "CA_1_ITV38325_1-NADH_dehydrogenase_subunit_1_20_1", "paths": {"rotated_genbank": fixture_path("ITV38325", "rotated.gb")}}
    summary, messages = asyncio.run(run_ncbi_validation(jobs=[job], settings={"assemblies": "all", "ignore_codes": ["SEQ_DESCR.NoTaxonID"]},
                                                        organisms={"ITV38325": "Kinosternon scorpioides"}, output_dir=str(tmp_path)))
    row = summary.iloc[0]
    assert (row["Rejects"], row["Errors"], row["Fatal discrepancies"]) == (0, 0, 0)
    folder = tmp_path / job["Assembly"]
    assert {path.suffix for path in folder.iterdir()} >= {".fsa", ".tbl", ".sqn", ".val", ".dr", ".gbf"}
    header = next(iter(open(next(folder.glob("*.fsa")))))
    assert "[organism=Kinosternon scorpioides]" in header and "[mgcode=2]" in header and "[location=mitochondrion]" in header


def test_validation_defaults_to_the_recommended_assemblies():
    jobs = [{"Assembly": "a"}, {"Assembly": "b"}]
    scores = pd.DataFrame({"Assembly": ["a", "b"], "Recommended": [False, True]})
    assert select_jobs(jobs=jobs, scores_dataframe=scores) == [{"Assembly": "b"}]
    assert select_jobs(jobs=jobs, scores_dataframe=scores, scope="all") == jobs
    assert select_jobs(jobs=jobs, scores_dataframe=pd.DataFrame()) == jobs


# ---------------- species identification ----------------

def read_bold(fixture_path):
    with open(fixture_path("phase3", "bold_ITV38302_COI.ndjson")) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def test_bold_species_are_ranked_by_identity_not_bit_score(fixture_path):
    rows = bold_hits(records=read_bold(fixture_path))
    # BOLD lists K. integrum first (longer overlap, higher bit score)
    assert rows[0]["Species"] == "Kinosternon integrum"
    ranked = rank_species(rows=rows, min_overlap=400)
    assert ranked[0]["Species"] == "Kinosternon scorpioides"
    assert ranked[0]["Identity (%)"] == pytest.approx(97.568)
    assert ranked[0]["BIN"] == "BOLD:AFG9442" and ranked[0]["Best record"] == "ECOHR040-23"
    assert ranked[1]["Species"] == "Kinosternon integrum"


def test_blast_hits_and_minimum_overlap(fixture_path):
    with open(fixture_path("phase3", "blast_ITV38302_COI.json")) as handle:
        rows = blast_hits(report=json.load(handle))
    assert len(rows) == 15
    ranked = rank_species(rows=rows, min_overlap=400)
    assert ranked[0]["Species"] == "Kinosternon leucostomum" and ranked[0]["Best record"] == "NC_014577"
    assert ranked[0]["Identity (%)"] == pytest.approx(100 * 1435 / 1549, abs=1e-3)
    assert rank_species(rows=rows, min_overlap=2000) == []


def test_verdicts():
    ranked = [{"Species": "Kinosternon scorpioides", "Identity (%)": 97.6}, {"Species": "Kinosternon integrum", "Identity (%)": 96.2}]
    assert verdict(declared=None, ranked=ranked) == "Not declared"
    assert verdict(declared="Kinosternon scorpioides", ranked=ranked, declared_identity=None) == "No reference"
    assert verdict(declared="Kinosternon scorpioides", ranked=ranked, declared_identity=97.6) == "Confirmed"
    assert verdict(declared="Kinosternon integrum", ranked=ranked, declared_identity=96.2) == "Not confirmed"
    assert verdict(declared="Kinosternon integrum", ranked=ranked, declared_identity=96.2, identity_threshold=96) == "Ambiguous"


def test_identify_project_confirms_the_declared_species(fixture_path, tmp_path):
    service = FixtureService(fixture_path)
    summary, hits = asyncio.run(identify_project(project="ITV38302", job=coi_job(fixture_path, tmp_path), service=service,
                                                 settings={}, organelle="mitochondrion", declared="Kinosternon scorpioides"))
    row = summary[0]
    assert (row["Marker"], row["Marker length"], row["Verdict"]) == ("COI", 1549, "Confirmed")
    assert row["Identity to declared species (%)"] == pytest.approx(97.568) and row["Declared species source"] == "BOLD"
    assert row["Best GenBank species"] == "Kinosternon leucostomum"
    assert row["Declared species identity in BOLD (%)"] == pytest.approx(97.568)
    assert row["Declared species identity in GenBank (%)"] is None
    assert row["Probable species"].split("; ")[0] == "Kinosternon scorpioides"
    assert (row["Genus"], row["Genus TaxID"], row["Family"], row["Family TaxID"]) == ("Kinosternon", 55538, "Kinosternidae", 34912)
    assert service.blast_queries == [None, "\"Kinosternon scorpioides\"[Organism]"]
    assert [hit["Database"] for hit in hits].count("BOLD") == 3 and [hit["Database"] for hit in hits].count("GenBank") == 3


def test_identify_project_without_metadata_lists_probable_species(fixture_path, tmp_path):
    service = FixtureService(fixture_path)
    summary, hits = asyncio.run(identify_project(project="ITV38302", job=coi_job(fixture_path, tmp_path), service=service,
                                                 settings={"top_species": 3}, organelle="mitochondrion", declared=None))
    row = summary[0]
    assert row["Verdict"] == "Not declared"
    assert row["Probable species"] == "Kinosternon scorpioides; Kinosternon integrum; Kinosternon hirtipes"
    assert row["Top BOLD species"].startswith("Kinosternon scorpioides (97.57%); Kinosternon integrum (96.")
    assert row["Top GenBank species"].split("; ")[0] == "Kinosternon leucostomum (92.64%)"
    assert len(row["Top GenBank species"].split("; ")) == 3
    assert row["Taxonomy species"] == "Kinosternon scorpioides"
    assert service.blast_queries == [None]


def test_marker_missing_and_representative_job(fixture_path, tmp_path):
    job = coi_job(fixture_path, tmp_path)
    summary, hits = asyncio.run(identify_project(project="ITV38302", job=job, service=FixtureService(fixture_path),
                                                 settings={"markers": ["rbcL"]}, organelle="chloroplast", declared=None))
    assert summary[0]["Verdict"] == "Marker not annotated" and hits == []
    other = {**job, "Assembly": "other"}
    scores = pd.DataFrame({"Project name": ["ITV38302"] * 2, "Assembly": ["other", job["Assembly"]], "Recommended": [False, True], "Rank in project": [2, 1]})
    assert representative_jobs(jobs=[other, job], scores_dataframe=scores)["ITV38302"]["Assembly"] == job["Assembly"]


def test_taxonomy_falls_back_to_the_genus(fixture_path):
    lineage = asyncio.run(taxonomy_lineage(service=FixtureService(fixture_path), name="Kinosternon sp. ABC"))
    assert lineage["Genus"] == "Kinosternon" and lineage["Order"] == "Testudines"
    empty = asyncio.run(taxonomy_lineage(service=FixtureService(fixture_path), name="Unknown thing"))
    assert empty["Genus"] is None


def test_bold_receives_every_project_in_one_submission(fixture_path, tmp_path):
    from moCURA.analysis.species_identification import run_species_identification
    first = coi_job(fixture_path, tmp_path)
    second = {**first, "Project name": "ITV99999", "Assembly": "other"}
    service = FixtureService(fixture_path)
    summary, hits = asyncio.run(run_species_identification(jobs=[first, second], service=service, settings={}, organelle="mitochondrion",
                                                           declared_species={"ITV38302": "Kinosternon scorpioides"}))
    assert service.bold_batches == [["q1", "q2"]]
    assert summary.set_index("Project name")["Verdict"].to_dict() == {"ITV38302": "Confirmed", "ITV99999": "Not declared"}


# ---------------- RefSeq comparison ----------------

def reference_item(fixture_path, repeats=(3, 120)):
    record = next(SeqIO.parse(fixture_path("phase3", "NC_014577.gb"), "genbank"))
    return {"Accession": record.id, "Organism": record.annotations["organism"], "Genome length": len(record.seq),
            "genes": genome_genes(record), "Tandem repeats": repeats[0], "Bases in repeats": repeats[1]}


def test_refseq_genes_use_the_same_names_as_the_assemblies(fixture_path):
    reference = reference_item(fixture_path)
    assembly = genome_genes(next(SeqIO.parse(fixture_path("ITV38325", "rotated.gb"), "genbank")))
    assert reference["Genome length"] == 16559
    assert len(reference["genes"]) == 37
    assert set(reference["genes"]) == set(assembly)


def test_compare_assembly_with_a_reference(fixture_path):
    job = {"Project name": "ITV38325", "Seed order": 1, "Seed Input": "ND1", "K-mer": 20, "Assembly copy": 1,
           "Assembly": "x", "paths": {"rotated_genbank": fixture_path("ITV38325", "rotated.gb")}}
    reference = reference_item(fixture_path)
    summaries, genes = compare_project(jobs=[job], references=[reference], level="genus", taxon="Kinosternon",
                                       assembly_repeats={("ITV38325", "ND1", 20, 1): (5, 300)})
    row = summaries[0]
    assert row["Genome length status"] == "Within" and row["Genes compared"] == 37
    assert row["Reference length min"] == row["Reference length max"] == 16559
    assert row["Repeat status"] == "More repeats"
    by_marker = {item["Marker"]: item for item in genes}
    assert by_marker["COI"]["Reference median"] == reference["genes"]["COI"]
    assert row["Genes outside the reference range"] == sum(1 for item in genes if item["Status"] != "Within")


def test_range_status_and_repeat_lookup():
    assert range_status(100, 100, 110, 5) == "Within"
    assert range_status(94, 100, 110, 5) == "Shorter"
    assert range_status(116, 100, 110, 5) == "Longer"
    assert range_status(None, 100, 110, 5) == "NA"
    summary = pd.DataFrame([{"Project name": "P", "Seed Input": "S", "K-mer": 20, "Assembly copy": 1},
                            {"Project name": "P", "Seed Input": "S", "K-mer": 30, "Assembly copy": 1}])
    repeats = pd.DataFrame([{"Project name": "P", "Seed Input": "S", "K-mer": 20, "Assembly copy": 1, "Start": 10, "End": 19},
                            {"Project name": "P", "Seed Input": "S", "K-mer": 20, "Assembly copy": 1, "Start": 15, "End": 24}])
    lookup = assembly_repeats(dataframe=repeats, summary_dataframe=summary)
    assert lookup[("P", "S", 20, 1)] == (2, 15)
    assert lookup[("P", "S", 30, 1)] == (0, 0)
    assert ("P", "S", 40, 1) not in lookup


# ---------------- alerts, remote access and configuration ----------------

def test_phase3_alerts(fixture_path):
    job = coiii_job(fixture_path)
    identity = {key: job[key] for key in ("Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly")}
    alerts = build_assembly_alerts(
        jobs=[job],
        heteroplasmy_dataframe=pd.DataFrame([{**identity, "High-confidence sites": 1, "Highest minor frequency": 0.128, "Regions": "COI"}]),
        species_dataframe=pd.DataFrame([{**identity, "Marker": "COI", "Verdict": "Ambiguous", "Declared species": "K. a",
                                         "Identity to declared species (%)": 97.1, "Probable species": "K. b; K. a"}]),
        reference_dataframe=pd.DataFrame([{**identity, "Genome length status": "Longer", "Genome length": 18000, "References": 2,
                                           "Reference level": "family", "Reference taxon": "Kinosternidae", "Reference length min": 16500,
                                           "Reference length max": 16600, "Genes outside the reference range": 1, "Genes outside (list)": "ND1 (900 bp)"}]),
        validation_dataframe=pd.DataFrame([{**identity, "Rejects": 0, "Errors": 2, "Fatal discrepancies": 0, "Main issues": "SEQ_FEAT.InternalStop ×2"}]),
    )
    assert alerts["Alert type"].tolist() == [
        "Possible heteroplasmy", "Species not confirmed", "Genome length outside references", "Gene lengths outside references", "NCBI validation errors",
    ]
    assert "13%" in alerts.iloc[0]["Detail"]


def test_env_file_and_rate(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# NCBI\nexport NCBI_API_KEY='abc123'\nNCBI_EMAIL = someone@example.org\nbroken line\n")
    env = read_env_file(path=str(path))
    assert env == {"NCBI_API_KEY": "abc123", "NCBI_EMAIL": "someone@example.org"}
    assert RemoteService(env=env).rate == 10
    assert RemoteService(env={}).rate == 3
    assert read_env_file(path=str(tmp_path / "missing.env")) == {}


def test_rate_limiter_spacing():
    async def run():
        limiter = RateLimiter(10)
        start = time.monotonic()
        await asyncio.gather(*[limiter.wait() for _ in range(5)])
        return time.monotonic() - start
    # five acquisitions at 10 per second: the last waits four intervals
    assert asyncio.run(run()) >= 0.39


def test_cache_round_trip(tmp_path):
    service = RemoteService(cache_dir=str(tmp_path))
    key = {"service": "eutils", "params": {"id": "1"}}
    assert service.cache_get(key) is None
    service.cache_put(key, {"answer": 1})
    assert service.cache_get(key) == {"answer": 1}
    assert RemoteService(cache_dir=str(tmp_path), refresh=True).cache_get(key) is None


def test_organelle_and_declared_species(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "config.yaml").write_text("assembly:\n  organelle: chloro\n")
    assert organelle_from_organpipe(organpipe_dir=str(tmp_path)) == "chloroplast"
    assert organelle_from_organpipe(configured="mitochondrion", organpipe_dir=str(tmp_path)) == "mitochondrion"
    assert organelle_from_organpipe(organpipe_dir=None) == "mitochondrion"
    metadata = tmp_path / "metadata.tsv"
    metadata.write_text("Project name\tSpecies\tLocation\nITV1\tKinosternon  scorpioides\tA\nITV2\t\tB\n")
    assert declared_species(metadata_path=str(metadata)) == {"ITV1": "Kinosternon scorpioides"}
    assert declared_species(metadata_path=None) == {}


def test_a_failing_phase3_analysis_does_not_stop_the_run():
    from moCURA.analysis.run_organpipe_qc import guarded

    async def broken():
        raise AttributeError("unexpected answer")
    first, second = asyncio.run(guarded("Species identification", broken(), 2))
    assert first.empty and second.empty


def test_old_bold_cache_entries_are_ignored(tmp_path):
    service = RemoteService(cache_dir=str(tmp_path))
    params = {"db": "public.tax-derep", "mi": "0.9", "mo": "100", "maxh": "100", "order": "3"}
    service.cache_put({"service": "bold", "params": params, "sequence": "ACGT"}, [{"seqid": "q1", "results": {}}])
    service.cache_put({"service": "bold", "format": 2, "params": params, "sequence": "ACGT"}, {"seqid": "q1", "results": {}})
    assert asyncio.run(service.bold(sequences={"q1": "ACGT"})) == {"q1": {"seqid": "q1", "results": {}}}
    assert service.requests == 0
