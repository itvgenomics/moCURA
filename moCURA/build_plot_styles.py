import pandas as pd
import seaborn as sns

def build_plot_styles(**kwargs):
    dataframe = kwargs.get("dataframe", None)
    marker_cycle = kwargs.get(
        "marker_cycle",
        ["o", "s", "D", "^", "v", "P", "X", "<", ">", "h"],
    )

    seed_inputs = sorted(dataframe["Seed Input"].dropna().unique())

    seed_palette = dict(
        zip(seed_inputs, sns.color_palette("colorblind", len(seed_inputs)))
    )

    kmer_values = sorted(
        int(value) for value in dataframe["K-mer"].dropna().unique()
    )
    kmer_markers = {
        kmer: marker_cycle[index % len(marker_cycle)]
        for index, kmer in enumerate(kmer_values)
    }

    return seed_palette, kmer_markers