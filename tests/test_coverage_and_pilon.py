from moCURA.load.load_coverage_data import (
    a_to_b,
    b_to_c,
    coverage_metrics,
    parse_changes,
    parse_fix_breaks,
    read_depth,
)


def test_read_depth_fills_missing_positions_with_zero(fixture_path):
    depth = read_depth(path=fixture_path("ITV38325", "rotated.depth.excerpt"), length=40)
    assert len(depth) == 40
    assert depth[:4] == [94, 96, 96, 96]
    assert depth[4] == 0 and depth[5] == 0
    assert depth[39] > 0


def test_coverage_metrics_windows_and_threshold():
    depth = [100] * 100 + [0] * 50 + [20] * 50
    metrics, windows = coverage_metrics(depth=depth, window=50, threshold=10)
    assert windows == [100.0, 100.0, 0.0, 20.0]
    assert metrics["Positions below threshold"] == 50
    assert metrics["Percent below threshold"] == 25.0
    assert metrics["Lowest window start"] == 101
    assert metrics["Lowest window end"] == 150
    assert metrics["Median depth"] == 60.0


def test_parse_real_pilon_insertion(fixture_text):
    changes = parse_changes(text=fixture_text("ITV38324_ND4_k45.changes"))
    assert changes == [{
        "Position before Pilon": 13726,
        "Position after Pilon": 13726,
        "Change type": "Insertion",
        "Reference": ".",
        "Replacement": "CATGC",
        "Length change": 5,
    }]


def test_coordinate_conversion_matches_rotated_genbank(fixture_text):
    # ITV38324 ND4 k45: rrnS starts at 13,832 in the .gb (offset 13,831); B has 16,532 bp.
    changes = parse_changes(text=fixture_text("ITV38324_ND4_k45.changes"))
    assert a_to_b(position=13725, changes=changes) == 13725
    assert a_to_b(position=13740, changes=changes) == 13745
    assert b_to_c(position=13832, offset=13831, length=16532) == 1
    assert b_to_c(position=13726, offset=13831, length=16532) == 16427
    assert b_to_c(position=1, offset=13831, length=16532) == 2702
    assert b_to_c(position=1, offset=None, length=16532) is None


def test_parse_unresolved_pilon_break(fixture_text):
    breaks = parse_fix_breaks(text=fixture_text("ITV38325", "pilon.log"))
    assert breaks == [{"start": 15731, "end": 16023, "message": "0 -0 +0 NoSolution TandemRepeat 2"}]
