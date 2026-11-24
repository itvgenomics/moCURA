from moCURA.generate.prepare_html_report_data import alignment_sequence_spans


def test_alignment_spans_mark_terminal_gaps(tmp_path):
    alignment = tmp_path / "marker.aligned.fasta"
    alignment.write_text(
        ">complete\nACGTACGTAC\n"
        ">truncated\n---TACG---\n"
        ">internal_gap\nACG--CGTAC\n"
    )
    spans, length = alignment_sequence_spans(path=str(alignment))
    assert length == 10
    assert spans["complete"] == {"ungapped_length": 10, "first_column": 1, "last_column": 10}
    assert spans["truncated"] == {"ungapped_length": 4, "first_column": 4, "last_column": 7}
    # Internal gaps are deletions, not missing data: the span still covers the whole marker.
    assert spans["internal_gap"]["first_column"] == 1 and spans["internal_gap"]["last_column"] == 10


def test_missing_alignment_gives_no_spans(tmp_path):
    assert alignment_sequence_spans(path=str(tmp_path / "absent.fasta")) == ({}, None)
