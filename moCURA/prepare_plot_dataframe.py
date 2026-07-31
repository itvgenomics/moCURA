import logging
import re

def parse_genome_range(value):
    match = re.search(r"(\d[\d,.]*)\s*[-–]\s*(\d[\d,.]*)", str(value))

    if not match:
        return None, None

    start, end = (
        int(part.replace(",", "").replace(".", ""))
        for part in match.groups()
    )

    return start, end

def prepare_plot_dataframe(**kwargs):
    dataframe = kwargs.get("dataframe", None)
    only_circularized = bool(kwargs.get("only_circularized", True))

    plot_df = dataframe.dropna(subset=["Total contigs"]).copy()

    if only_circularized:
        plot_df = plot_df[plot_df["Circularized"]].copy()

    limits = plot_df["Genome range"].apply(parse_genome_range)
    plot_df["Genome range start"] = [start for start, _ in limits]
    plot_df["Genome range end"] = [end for _, end in limits]

    logging.info(
        f"Rows available for plots: {len(plot_df)}, circularized filter: {only_circularized}",
    )

    return plot_df