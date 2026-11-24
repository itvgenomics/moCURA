from moCURA.load.load_recruitment_data import IDENTITY_BINS, identity_bin, summarize_blast_table


def test_identity_bins():
    assert IDENTITY_BINS[0] == 90 and IDENTITY_BINS[-1] == 100
    assert identity_bin(identity=85.0) == 0
    assert identity_bin(identity=97.656) == IDENTITY_BINS.index(97.5)
    assert identity_bin(identity=100.0) == len(IDENTITY_BINS) - 1


def test_summarize_real_blast_excerpt(fixture_path):
    summary, histogram = summarize_blast_table(
        path=fixture_path("ITV38325", "rotated.blastn.excerpt"), threshold=98, target_length=16544,
    )
    assert summary["Recruited reads"] == 8
    assert summary["Reads below threshold"] == 2
    assert summary["Percent below threshold"] == 25.0
    assert sum(histogram) == 8
    # Reverse-strand hits (start > end) are counted with their true span.
    assert summary["Target bases covered"] > 0
    assert summary["Target coverage %"] < 10
