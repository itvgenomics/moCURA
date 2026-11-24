import os

from moCURA.load.load_genbank_marker_data import find_rotated_genbank_jobs
from moCURA.load.load_pilon_data import find_pilon_jobs
from moCURA.load.organpipe_layout import (
    directory_listing,
    find_organpipe_assemblies,
    infer_organpipe_dir,
    parse_assembly_name,
)

ASM = "CA_1_ITV38325_1-NADH_dehydrogenase_subunit_1_20_1"


def touch(path, text=""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def build_tree(root, assembler_level):
    level = ["novoplasty"] if assembler_level else []
    project = os.path.join(root, "ITV38325")
    seed_dir = "1-NADH_dehydrogenase_subunit_1_kmer20"
    touch(os.path.join(project, "pilon", *level, ASM, "pilon.log"), "Input genome size: 16544\n")
    touch(os.path.join(project, "pilon", *level, "INVALIDSEED_1", "pilon.log"))
    touch(os.path.join(project, "mitos2", *level, seed_dir, ASM, "result.mitos"))
    touch(os.path.join(project, "genbanks", *level, f"{ASM}.gb"))
    touch(os.path.join(project, "genbanks", *level, f"{ASM}.rotated.gb"))
    touch(os.path.join(project, "images", *level, seed_dir, f"{ASM}.rotated.depth"))
    touch(os.path.join(project, "images", *level, seed_dir, f"{ASM}.rotated.blastn.out"))
    directory_listing.cache_clear()
    return project


def test_parse_assembly_name():
    meta = parse_assembly_name(name=ASM, project_name="ITV38325")
    assert meta["Seed Input"] == "ND1"
    assert meta["Seed order"] == 1
    assert meta["K-mer"] == 20
    assert meta["Assembly copy"] == 1
    assert meta["Assembly prefix"] == "CA"
    assert meta["seed_directory"] == "1-NADH_dehydrogenase_subunit_1_kmer20"
    assert parse_assembly_name(name="INVALIDSEED_1", project_name="ITV38325") is None


def test_find_assemblies_in_both_layouts(tmp_path):
    for assembler_level in (False, True):
        root = tmp_path / ("current" if assembler_level else "old")
        build_tree(str(root), assembler_level)
        jobs = find_organpipe_assemblies(results_dir=str(root))
        assert [job["Assembly"] for job in jobs] == [ASM]
        paths = jobs[0]["paths"]
        assert paths["mitos2_dir"].endswith(ASM)
        assert paths["rotated_depth"].endswith(".rotated.depth")
        assert paths["rotated_blastn"].endswith(".rotated.blastn.out")
        assert paths["depth"] is None
        assert ("novoplasty" in paths["genbank"]) == assembler_level


def test_existing_finders_accept_assembler_level(tmp_path):
    build_tree(str(tmp_path), assembler_level=True)
    pilon_jobs = find_pilon_jobs(results_dir=str(tmp_path))
    assert [(job["seed_input"], job["kmer"]) for job in pilon_jobs] == [("ND1", 20)]
    genbank_jobs = find_rotated_genbank_jobs(results_dir=str(tmp_path))
    assert len(genbank_jobs) == 1
    assert genbank_jobs[0]["relative_path"].replace("\\", "/") == f"ITV38325/genbanks/novoplasty/{ASM}.rotated.gb"


def test_infer_organpipe_dir(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    assert infer_organpipe_dir(results_dir=str(results)) is None
    (tmp_path / "workflow" / "reports").mkdir(parents=True)
    (tmp_path / "benchmarks").mkdir()
    assert infer_organpipe_dir(results_dir=str(results)) == str(tmp_path)
