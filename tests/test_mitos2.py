from moCURA.load.load_mitos2_data import (
    EXPECTED_MARKERS,
    canonical_gene_order,
    order_consistent,
    origin_checks,
    parse_gene_order,
    parse_mitos_table,
)


def test_expected_markers_are_37_unique_standard_names():
    assert len(EXPECTED_MARKERS) == 37
    assert len(set(EXPECTED_MARKERS)) == 37
    assert {"ND1", "CYTB", "12S", "16S", "tRNA-Leu-1", "tRNA-Leu-2", "tRNA-Ser-1", "tRNA-Ser-2"} <= set(EXPECTED_MARKERS)


def test_parse_result_mitos(fixture_text):
    features = parse_mitos_table(text=fixture_text("ITV38325", "result.mitos"))
    first = features[0]
    assert (first["name"], first["start"], first["stop"], first["strand"], first["marker"]) == ("rrnS", 0, 447, "+", "12S")
    nad6 = next(f for f in features if f["name"] == "nad6")
    assert nad6["strand"] == "-" and nad6["marker"] == "ND6"
    markers = {f["marker"] for f in features if f["marker"]}
    assert markers == set(EXPECTED_MARKERS)


def test_origin_crossing_12s_recovers_962_bp(fixture_text):
    kept = parse_mitos_table(text=fixture_text("ITV38325", "result.mitos"))
    ignored = parse_mitos_table(text=fixture_text("ITV38325", "ignored.mitos"))
    records = origin_checks(kept=kept, ignored=ignored, length=16544)
    assert len(records) == 1
    record = records[0]
    assert record["Marker"] == "12S"
    assert record["Annotated length"] == 448
    assert record["Origin-corrected length"] == 962
    assert record["Crosses origin"] is True


def test_no_origin_record_without_wrapped_hit(fixture_text):
    kept = parse_mitos_table(text=fixture_text("ITV38325", "result.mitos"))
    assert origin_checks(kept=kept, ignored=[], length=16544) == []


def test_gene_order_is_rotated_and_strand_normalized(fixture_text):
    tokens = parse_gene_order(text=fixture_text("ITV38325", "result.geneorder"))
    order = canonical_gene_order(tokens=tokens)
    assert order.startswith("rrnS trnV rrnL")
    assert "OL" not in order.split() and "OH" not in order.split()
    reverse = [token[1:] if token.startswith("-") else f"-{token}" for token in reversed(tokens)]
    assert canonical_gene_order(tokens=reverse) == order


def test_order_consistent_on_partial_assemblies():
    modal = "rrnS trnV rrnL trnL2 nad1 trnI -trnQ trnM"
    assert order_consistent(order=modal, modal=modal) is True
    assert order_consistent(order="trnL2 nad1 -trnQ", modal=modal) is True
    assert order_consistent(order="nad1 trnL2 -trnQ", modal=modal) is False
    assert order_consistent(order="trnL2 nad1 trnQ", modal=modal) is False
