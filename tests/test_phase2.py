"""Phase 2 analyses.

Real fixtures from ITV38325, assembly CA_1_ITV38325_1-NADH_dehydrogenase_subunit_1_20_1:

* ``rotated.gb``: its rotated GenBank (MITOS2 annotation);
* ``rotated_origin.bam``: the reads of its rotated BAM within 1 kb of either end
  (3,327 records, primary and supplementary). NOVOPlasty already wrote this
  genome starting at rrnS, so the circularization junction is on the origin.
"""

from Bio import SeqIO
from Bio.Seq import Seq

from moCURA.analysis.annotation_integrity import check_cds, integrity_assembly_sync, length_deviation_issues
from moCURA.analysis.assembly_concordance import concordance_groups, pairwise_identity
from moCURA.analysis.assembly_score import build_assembly_score, weighted_score
from moCURA.analysis.junction_support import classify_junction, count_junction_support, junction_position
from moCURA.analysis.sequence_composition import codon_counts, composition, composition_assembly_sync, rscu


def rotated_sequence(fixture_path):
    return str(next(SeqIO.parse(fixture_path("ITV38325", "rotated.gb"), "genbank")).seq).upper()


def job_for(fixture_path):
    return {
        "Project name": "ITV38325", "Seed order": 1, "Seed Input": "ND1", "K-mer": 20, "Assembly copy": 1,
        "Assembly": "CA_1_ITV38325_1-NADH_dehydrogenase_subunit_1_20_1",
        "paths": {"rotated_genbank": fixture_path("ITV38325", "rotated.gb")},
    }


# ---------------- junction ----------------

def test_junction_position_forward_and_reverse(fixture_path):
    rotated = rotated_sequence(fixture_path)
    original = rotated[5000:] + rotated[:5000]
    assert junction_position(original=original, rotated=rotated) == {"position": 5000, "orientation": "+"}
    reverse = str(Seq(original).reverse_complement())
    assert junction_position(original=reverse, rotated=rotated) == {"position": 5000, "orientation": "-"}
    assert junction_position(original=rotated, rotated=rotated)["position"] == 0


def test_origin_junction_counts_split_reads_and_wrap_pairs(fixture_path):
    counts = count_junction_support(bam_path=fixture_path("ITV38325", "rotated_origin.bam"), junction=0)
    # Same numbers as the complete BAM: 76 reads split across the ends, 37 pairs wrapping around.
    assert counts["Spanning reads"] == 76
    assert counts["Flanking pairs"] == 37
    assert classify_junction(spanning=counts["Spanning reads"], pairs=counts["Flanking pairs"]) == "Supported"


def test_internal_junction_without_reads_is_unsupported(fixture_path):
    counts = count_junction_support(bam_path=fixture_path("ITV38325", "rotated_origin.bam"), junction=8000)
    assert counts["Spanning reads"] == 0 and counts["Reads at junction"] == 0
    assert classify_junction(spanning=0, pairs=0) == "Unsupported"
    assert classify_junction(spanning=4, pairs=0) == "Weak"
    assert classify_junction(spanning=None, pairs=None) == "NA"


# ---------------- annotation integrity ----------------

def test_check_cds_vertebrate_mitochondrial_code():
    assert check_cds(sequence="ATGAAATAA", table=2) == []
    assert check_cds(sequence="ATGAAAT", table=2)[0][:2] == ("Incomplete stop codon", "info")
    assert check_cds(sequence="ATGAAATA", table=2)[0][:2] == ("Incomplete stop codon", "info")
    checks = {check for check, _, _ in check_cds(sequence="ATGTAAAAATAA", table=2)}
    assert "Internal stop codon" in checks
    # AGA is a stop codon in the vertebrate mitochondrial code but not in the standard code.
    assert {check for check, _, _ in check_cds(sequence="ATGAGAAAATAA", table=2)} == {"Internal stop codon"}
    assert check_cds(sequence="ATGAGAAAATAA", table=1) == []
    assert check_cds(sequence="CCCAAATAA", table=2)[0][0] == "Non-standard start codon"
    assert check_cds(sequence="ATGAAAGG", table=2)[0][:2] == ("Length not a multiple of 3", "error")


def test_integrity_of_real_genbank(fixture_path):
    result = integrity_assembly_sync(job=job_for(fixture_path), genetic_code=2)
    assert result["length"] == 16544
    assert len({feature["Marker"] for feature in result["features"]}) == 37
    severities = {issue["Severity"] for issue in result["issues"]}
    assert severities == {"info"}
    assert sum(issue["Check"] == "Incomplete stop codon" for issue in result["issues"]) == 5


def test_length_deviation_against_project_mode():
    base = {"Project name": "P", "Marker": "ND1", "Feature type": "CDS"}
    features = [{**base, "Assembly": name, "Length": length} for name, length in (("a", 960), ("b", 960), ("c", 700))]
    issues = length_deviation_issues(features=features, length_deviation_percent=10)
    assert [issue["Assembly"] for issue in issues] == ["c"]


# ---------------- concordance ----------------

def test_pairwise_identity_excludes_gaps_and_counts_indel_events():
    result = pairwise_identity(first="ACGT--ACGTAC", second="ACGTTTACGAAC")
    assert result["Compared columns"] == 10
    assert result["Identity %"] == 90.0
    assert result["Indels"] == 1
    partial = pairwise_identity(first="ACGTACGTAC", second="----ACGT--")
    assert partial["Identity %"] == 100.0 and partial["Coverage %"] == 40.0


def test_concordance_groups_need_identity_and_coverage():
    pairs = [
        {"Assembly A": "a", "Assembly B": "b", "Identity %": 100.0, "Coverage %": 100.0},
        {"Assembly A": "a", "Assembly B": "c", "Identity %": 100.0, "Coverage %": 40.0},
        {"Assembly A": "b", "Assembly B": "c", "Identity %": 99.0, "Coverage %": 100.0},
    ]
    groups = concordance_groups(names=["a", "b", "c"], pairs=pairs, identity_threshold=99.5, min_coverage=95)
    assert groups == {"a": 1, "b": 1, "c": 2}


# ---------------- composition ----------------

def test_composition_and_rscu():
    assert composition(sequence="AAAT") == {"GC %": 0.0, "AT skew": 0.5, "GC skew": None, "bp": 4}
    counts = codon_counts(sequences=["ATGCTACTGTAA"], table=2)
    assert counts == {"ATG": 1, "CTA": 1, "CTG": 1}
    rows = {row["Codon"]: row for row in rscu(counts=counts, table=2)}
    # Leucine has six codons in code 2; two observed once each give RSCU 3.
    assert rows["CTA"]["RSCU"] == 3.0 and rows["CTC"]["RSCU"] == 0.0
    assert rows["ATG"]["Amino acid"] == "M"


def test_composition_of_real_genbank(fixture_path):
    result = composition_assembly_sync(job=job_for(fixture_path), genetic_code=2)
    row = result["composition"]
    assert row["Genome length"] == 16544
    assert 30 < row["GC %"] < 45
    assert row["PCG - strand bp"] > 0 and row["PCG + strand bp"] > row["PCG - strand bp"]
    # Vertebrate mitochondrial code: 64 codons minus the 4 stop codons (TAA, TAG, AGA, AGG).
    assert len(result["rscu"]) == 60


# ---------------- score ----------------

def test_weighted_score_counts_na_as_neutral():
    weights = {"completeness": 1, "junction": 1}
    assert weighted_score(components={"completeness": 1.0, "junction": None}, weights=weights)[0] == 75.0
    assert weighted_score(components={"completeness": 1.0, "junction": None}, weights=weights, na_value=None)[0] == 100.0


def test_ranking_never_recommends_open_assemblies():
    import pandas as pd

    jobs = [
        {"Project name": "P", "Seed order": 1, "Seed Input": "S", "K-mer": 20, "Assembly copy": 1, "Assembly": "closed"},
        {"Project name": "P", "Seed order": 1, "Seed Input": "S", "K-mer": 45, "Assembly copy": 1, "Assembly": "open"},
    ]
    completeness = pd.DataFrame({"Assembly": ["closed", "open"], "Genes present": [30, 37]})
    table = build_assembly_score(
        jobs=jobs, completeness_dataframe=completeness,
        circular_lookup={("P", "S", 20): True, ("P", "S", 45): False},
    )
    ranked = table.set_index("Assembly")
    assert ranked.loc["closed", "Recommended"] and not ranked.loc["open", "Recommended"]
    assert ranked.loc["open", "Score"] > ranked.loc["closed", "Score"]
    assert ranked.loc["open", "Rank in project"] == 2


def test_ranking_lists_the_files_of_each_assembly(fixture_path):
    import os
    import pandas as pd

    job = {**job_for(fixture_path), "paths": {"rotated_genbank": fixture_path("ITV38325", "rotated.gb"), "genbank": None, "pilon_dir": None}}
    table = build_assembly_score(jobs=[job], completeness_dataframe=pd.DataFrame({"Assembly": [job["Assembly"]], "Genes present": [37]}))
    row = table.iloc[0]
    assert row["Rotated GenBank"] == os.path.abspath(fixture_path("ITV38325", "rotated.gb"))
    assert row["GenBank"] is None and row["Pilon FASTA"] is None
