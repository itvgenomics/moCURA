"""RefSeq composition, plastid names, the default .env, shared BLAST searches and the Excel order.

Real fixtures:

* ``phase3/NC_014577.gb``: RefSeq mitogenome of Kinosternon leucostomum;
* ``phase3/LC729555_rbcL_region.gb``: 4,931 bp of the plastome of Ipomoea
  pes-caprae (GenBank LC729555) with trnM-CAU, atpE, atpB and rbcL;
* ``phase3/blast_ITV38302_COI.json``: NCBI megablast answer for a COI.
"""

import asyncio
import json
import os
import urllib.error

import pandas as pd
from Bio import SeqIO

from moCURA.analysis.ncbi_validation import feature_table
from moCURA.analysis.reference_comparison import genome_genes, reference_composition, run_reference_comparison
from moCURA.analysis.run_organpipe_qc import organelle_from_novoplasty, organelle_from_organpipe
from moCURA.analysis.sequence_composition import composition
from moCURA.generate.generate_excel import generate_excel
from moCURA.generate.prepare_html_report_data import compact_reference_rscu, compact_rscu
from moCURA.standardization.plastid_marker_name import plastid_marker_name
from moCURA.standardization.standardized_gene_name import standardized_gene_name
from moCURA.standardization.standardized_marker_name import standardized_marker_name
from moCURA.utils.remote_service import DEFAULT_ENV_FILE, RemoteService, read_env_file, resolve_env_file


def plastome_excerpt(fixture_path):
    return next(SeqIO.parse(fixture_path("phase3", "LC729555_rbcL_region.gb"), "genbank"))


# ---------------- RefSeq composition ----------------

def test_reference_composition_matches_the_assembly_formulas(fixture_path):
    record = next(SeqIO.parse(fixture_path("phase3", "NC_014577.gb"), "genbank"))
    row, usage = reference_composition(record, 2)
    assert row["Accession"] == "NC_014577.1" and row["Genome length"] == 16559
    assert row["GC %"] == composition(sequence=record.seq)["GC %"]
    # 13 protein-coding genes; ND6 is the only one on the minus strand.
    assert row["PCG - strand bp"] == len(next(f for f in record.features if f.type == "CDS" and f.location.strand == -1))
    assert row["Codons counted"] > 3500
    assert len(usage) == 60  # sense codons of the vertebrate mitochondrial code (4 stops)
    assert all(item["Accession"] == "NC_014577.1" for item in usage)


def test_reference_rscu_follows_the_codon_order_of_the_assemblies(fixture_path):
    record = next(SeqIO.parse(fixture_path("phase3", "NC_014577.gb"), "genbank"))
    _, usage = reference_composition(record, 2)
    reference = pd.DataFrame(usage)
    assemblies = compact_rscu(dataframe=reference.rename(columns={"Accession": "Assembly"}).assign(**{
        "Project name": "P", "Seed order": 1, "Seed Input": "COI", "K-mer": 20, "Assembly copy": 1}))
    compact = compact_reference_rscu(dataframe=reference, codons=assemblies["codons"])
    assert compact[0]["Accession"] == "NC_014577.1"
    assert compact[0]["RSCU"] == assemblies["assemblies"][0]["RSCU"]


class ReferenceService:
    """RefSeq search answering with the saved NC_014577 record."""

    rate = 3

    def __init__(self, fixture_path):
        self.text = open(fixture_path("phase3", "NC_014577.gb")).read()

    async def eutils(self, endpoint, params, **kwargs):
        if endpoint == "esearch":
            return {"esearchresult": {"idlist": ["308745804"]}}
        return self.text


def test_reference_comparison_returns_genes_composition_and_rscu(fixture_path, tmp_path):
    species = pd.DataFrame([{"Project name": "ITV38325", "Genus": "Kinosternon", "Genus TaxID": 55538, "Family": "Kinosternidae", "Family TaxID": 34912}])
    job = {"Project name": "ITV38325", "Seed order": 1, "Seed Input": "ND1", "K-mer": 20, "Assembly copy": 1, "Assembly": "x",
           "paths": {"rotated_genbank": fixture_path("ITV38325", "rotated.gb")}}
    result = asyncio.run(run_reference_comparison(
        jobs=[job], service=ReferenceService(fixture_path), species_dataframe=species, output_dir=str(tmp_path),
        settings={"compare_repeats": False}, genetic_code=2,
    ))
    summary, genes, genomes, gene_lengths, reference_comp, reference_rscu = result
    assert len(summary) == 1 and summary.iloc[0]["Reference taxon"] == "Kinosternon"
    assert set(gene_lengths["Marker"]) == set(genes["Marker"]) and len(gene_lengths) == 37
    assert gene_lengths.set_index("Marker").loc["COI", "Length"] == genes.set_index("Marker").loc["COI", "Reference median"]
    assert reference_comp.iloc[0]["Accession"] == "NC_014577.1" and reference_comp.iloc[0]["Genetic code"] == 2
    assert len(reference_rscu) == 60


# ---------------- plastid names ----------------

def test_plastid_gene_symbols_are_kept():
    cases = [
        ("tRNA", {"gene": ["trnK-UUU"], "product": ["tRNA-Lys"]}, "trnK-UUU"),
        ("tRNA", {"gene": ["trnfM-CAU"]}, "trnfM-CAU"),
        ("tRNA", {"gene": ["trnH_GTG"]}, "trnH-GUG"),
        ("CDS", {"gene": ["MATK"]}, "matK"),
        ("CDS", {"gene": ["rbcL"]}, "rbcL"),
        ("CDS", {"gene": ["rps12"]}, "rps12"),
        ("CDS", {"gene": ["ycf1"]}, "ycf1"),
        ("rRNA", {"gene": ["rrn4.5"]}, "rrn4.5"),
        ("rRNA", {"gene": ["rrn16"], "product": ["16S ribosomal RNA"]}, "rrn16"),
        ("rRNA", {"product": ["23S ribosomal RNA"]}, "rrn23"),
        ("rRNA", {"product": ["4.5S ribosomal RNA"]}, "rrn4.5"),
    ]
    for feature_type, qualifiers, expected in cases:
        assert standardized_marker_name(feature_type=feature_type, qualifiers=qualifiers) == expected


def test_mitochondrial_names_are_unchanged():
    cases = [
        ("tRNA", {"gene": ["trnF(gaa)"], "product": ["trnF(gaa)"]}, "tRNA-Phe"),
        ("tRNA", {"gene": ["trnL2(taa)"], "product": ["trnL2(taa)"]}, "tRNA-Leu-2"),
        ("rRNA", {"gene": ["rrnS"]}, "12S"),
        ("rRNA", {"gene": ["rrnL"]}, "16S"),
        ("rRNA", {"product": ["16S ribosomal RNA"]}, "16S"),  # also the large mitochondrial rRNA
        ("CDS", {"gene": ["cox1"]}, "COI"),
        ("CDS", {"gene": ["ATP8"]}, "ATP8"),
        ("CDS", {"gene": ["nad4L"]}, "ND4L"),
    ]
    for feature_type, qualifiers, expected in cases:
        assert plastid_marker_name(feature_type=feature_type, qualifiers=qualifiers) is None
        assert standardized_marker_name(feature_type=feature_type, qualifiers=qualifiers) == expected


def test_plastome_excerpt_genes_and_seed_names(fixture_path):
    genes = genome_genes(plastome_excerpt(fixture_path))
    assert genes == {"trnM-CAU": 73, "atpE": 402, "atpB": 1473, "rbcL": 1431}
    # NOVOPlasty writes the seed file; the assembly files carry the gene name.
    assert standardized_gene_name(value="resources/IPO001/seeds/1-rbcL.fasta") == "rbcL"
    assert standardized_gene_name(value="12-NADH_dehydrogenase_subunit_6.fasta") == "ND6"


def test_plastid_feature_table_keeps_ncbi_trna_products(fixture_path):
    text, _ = feature_table(record=plastome_excerpt(fixture_path), sequence_id="cp1", genetic_code=11)
    assert "\t\t\tproduct\ttRNA-Met" in text
    assert "\t\t\tgene\trbcL" in text
    assert "ribulose" in text.lower()


def test_organelle_from_the_novoplasty_log(tmp_path):
    log = tmp_path / "IPO001" / "novoplasty" / "1-rbcL" / "kmer33" / "log_IPO001.txt"
    log.parent.mkdir(parents=True)
    log.write_text("Project:\n----\nProject name          = IPO001\nType                  = chloro\nGenome range          = 120000-200000\n")
    assert organelle_from_novoplasty(results_dir=str(tmp_path)) == "chloroplast"
    assert organelle_from_organpipe(configured=None, organpipe_dir=None, results_dir=str(tmp_path)) == "chloroplast"
    assert organelle_from_organpipe(configured="mitochondrion", results_dir=str(tmp_path)) == "mitochondrion"
    log.write_text("Type                  = mito\n")
    assert organelle_from_organpipe(results_dir=str(tmp_path)) == "mitochondrion"


# ---------------- .env ----------------

def test_default_env_file_is_at_the_moCURA_root(tmp_path, caplog):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert DEFAULT_ENV_FILE == os.path.join(root, ".env")
    assert resolve_env_file(path=None) == (DEFAULT_ENV_FILE, False)
    assert resolve_env_file(path="other.env") == ("other.env", True)
    caplog.clear()
    assert read_env_file(path=str(tmp_path / ".env"), explicit=False) == {}
    assert "not found" not in caplog.text
    assert read_env_file(path=str(tmp_path / ".env"), explicit=True) == {}
    assert "not found" in caplog.text
    empty = tmp_path / "empty.env"
    empty.write_text("NCBI_API_KEY=\n")
    assert RemoteService(env=read_env_file(path=str(empty))).rate == 3


def test_an_invalid_key_falls_back_to_three_requests_per_second(monkeypatch):
    service = RemoteService(env={"NCBI_API_KEY": "not-a-key"})
    assert service.rate == 10
    calls = []

    def fake_request(url, data=None, headers=None):
        calls.append(url)
        if "api_key=" in url:
            raise urllib.error.HTTPError(url, 400, "API key invalid", None, None)
        return 200, "{}"

    monkeypatch.setattr(service, "_request_sync", fake_request)
    assert asyncio.run(service.available()) is True
    assert service.api_key is None and service.rate == 3
    assert "api_key=" in calls[0] and "api_key=" not in calls[1]


# ---------------- BLAST ----------------

def test_identical_blast_searches_share_one_submission(fixture_path, tmp_path):
    report = json.load(open(fixture_path("phase3", "blast_ITV38302_COI.json")))
    service = RemoteService(cache_dir=str(tmp_path))
    submissions = []

    async def fake_once(**kwargs):
        submissions.append(kwargs["sequence"])
        await asyncio.sleep(0.05)
        return report

    service.blast_once = fake_once

    async def seven_samples():
        return await asyncio.gather(*[service.blast(sequence="ACGT" * 200) for _ in range(7)])

    results = asyncio.run(seven_samples())
    assert len(submissions) == 1
    assert all(result == report for result in results)
    # The second run reads the cache.
    assert asyncio.run(service.blast(sequence="ACGT" * 200)) == report and len(submissions) == 1


def test_a_dropped_blast_search_is_submitted_again(fixture_path, tmp_path):
    report = json.load(open(fixture_path("phase3", "blast_ITV38302_COI.json")))
    service = RemoteService(cache_dir=str(tmp_path))
    answers = [None, report]

    async def fake_once(**kwargs):
        return answers.pop(0)

    service.blast_once = fake_once
    assert asyncio.run(service.blast(sequence="TTTT")) == report
    assert service.failures == 0

    service.blast_once = lambda **kwargs: asyncio.sleep(0, result=None)
    assert asyncio.run(service.blast(sequence="GGGG")) is None
    assert service.failures == 1


# ---------------- Excel ----------------

def test_recommendation_is_the_first_sheet(tmp_path):
    import openpyxl

    path = str(tmp_path / "summary.xlsx")
    summary = pd.DataFrame([{"Project name": "P", "K-mer": 20, "Circularized": True}])
    generate_excel(dataframe=summary, output_file=path, extra_sheets=[
        ("Coverage", pd.DataFrame([{"a": 1}])), ("Recommendation", pd.DataFrame([{"b": 2}])),
    ])
    assert openpyxl.load_workbook(path, read_only=True).sheetnames == ["Recommendation", "Summary", "Coverage"]


def test_plastid_exceptions_for_trans_splicing_and_edited_starts():
    from Bio.Seq import Seq
    from Bio.SeqFeature import CompoundLocation, FeatureLocation, SeqFeature
    from Bio.SeqRecord import SeqRecord

    # psbL-like CDS starting with ACG (edited to AUG) and an rps12-like CDS with exons on both strands.
    sequence = "ACG" + "GCT" * 10 + "TAA" + "A" * 30 + "ATG" + "AAA" * 5 + "TTT" + "C" * 20 + "TTACCC" + "G" * 10
    record = SeqRecord(Seq(sequence), id="cp")
    edited = SeqFeature(FeatureLocation(0, 36, 1), type="CDS", qualifiers={"gene": ["psbL"], "product": ["photosystem II protein L"]})
    split = SeqFeature(CompoundLocation([FeatureLocation(66, 84, 1), FeatureLocation(107, 113, -1)]), type="CDS",
                       qualifiers={"gene": ["rps12"], "product": ["ribosomal protein S12"]})
    record.features = [edited, split]
    text, _ = feature_table(record=record, sequence_id="cp", genetic_code=11)
    assert "\t\t\ttransl_except\t(pos:1..3,aa:Met)\n\t\t\texception\tRNA editing" in text
    assert text.count("\t\t\texception\ttrans-splicing") == 2  # gene and CDS
    # The same ACG start in a mitochondrial code is left alone.
    text, _ = feature_table(record=record, sequence_id="cp", genetic_code=2)
    assert "RNA editing" not in text


def test_submission_id_keeps_the_copy_number():
    from moCURA.analysis.ncbi_validation import submission_id

    first = submission_id("CA_1_ITV38292_2-NADH_dehydrogenase_subunit_2_45_1")
    second = submission_id("CA_1_ITV38292_2-NADH_dehydrogenase_subunit_2_45_2")
    assert len(first) <= 48 and first.endswith("_45_1")
    assert first != second
    assert submission_id("CA_1_IPO001_1-rbcL_33_1") == "CA_1_IPO001_1-rbcL_33_1"
