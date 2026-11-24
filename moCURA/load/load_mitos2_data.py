"""Read MITOS2 outputs: gene completeness, gene order and genes that cross the origin.

Files read per assembly (``mitos2/{seed}_kmer{k}/{asm}/``):

* ``result.mitos``: kept annotations, 0-based inclusive start/stop.
* ``ignored.mitos``: hits rejected by MITOS2. A hit whose start is greater than
  its stop wraps around the contig origin; it is the evidence used to recover
  the full length of a gene that MITOS2 kept only as a fragment.
* ``result.geneorder``: gene order, with ``-`` for the minus strand.

Coordinates are in the post-Pilon system (B). Nothing here changes the existing
``Marker Lengths`` sheet.
"""

import asyncio
import collections
import logging
import os

import pandas as pd

from ..standardization.standardized_marker_name import standardized_marker_name
from ..utils.gather_records import gather_records
from ..utils.read_text_async import read_text_file
from .organpipe_layout import assembly_identity


MITOS_TYPES = {"gene": "CDS", "rRNA": "rRNA", "tRNA": "tRNA"}

MITOS_CANONICAL_GENES = [
    ("gene", "cox1"), ("gene", "cox2"), ("gene", "cox3"), ("gene", "atp6"), ("gene", "atp8"),
    ("gene", "nad1"), ("gene", "nad2"), ("gene", "nad3"), ("gene", "nad4"), ("gene", "nad4l"),
    ("gene", "nad5"), ("gene", "nad6"), ("gene", "cob"),
    ("rRNA", "rrnS"), ("rRNA", "rrnL"),
    ("tRNA", "trnA"), ("tRNA", "trnR"), ("tRNA", "trnN"), ("tRNA", "trnD"), ("tRNA", "trnC"),
    ("tRNA", "trnQ"), ("tRNA", "trnE"), ("tRNA", "trnG"), ("tRNA", "trnH"), ("tRNA", "trnI"),
    ("tRNA", "trnL1"), ("tRNA", "trnL2"), ("tRNA", "trnK"), ("tRNA", "trnM"), ("tRNA", "trnF"),
    ("tRNA", "trnP"), ("tRNA", "trnS1"), ("tRNA", "trnS2"), ("tRNA", "trnT"), ("tRNA", "trnW"),
    ("tRNA", "trnY"), ("tRNA", "trnV"),
]

COMPLETENESS_STATUS = ("Present", "Absent", "Duplicated", "Partial at origin")

ORIGIN_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy", "Assembly",
    "Marker", "Raw marker", "Annotated start", "Annotated end", "Annotated length",
    "Contig length", "Crosses origin", "Origin-corrected length", "Origin evidence",
]


def standard_mitos_name(**kwargs):
    """Standardize a MITOS2 gene name with the moCURA (SynGenes) marker rules."""

    mitos_type = str(kwargs.get("mitos_type", ""))
    name = str(kwargs.get("name", "")).split("(")[0].strip()
    feature_type = MITOS_TYPES.get(mitos_type)

    if feature_type is None:
        return None

    return standardized_marker_name(feature_type=feature_type, qualifiers={"gene": [name]})


EXPECTED_MARKERS = [standard_mitos_name(mitos_type=t, name=n) for t, n in MITOS_CANONICAL_GENES]


def parse_mitos_table(**kwargs):
    """Parse ``result.mitos`` or ``ignored.mitos`` text into feature dictionaries."""

    text = kwargs.get("text", "") or ""
    features = []

    for line in text.splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 7 or parts[0].startswith("#"):
            continue
        try:
            start, stop = int(parts[4]), int(parts[5])
        except ValueError:
            continue
        features.append(
            {
                "type": parts[1],
                "name": parts[2],
                "method": parts[3],
                "start": start,
                "stop": stop,
                "strand": "-" if parts[6].strip() == "-1" else "+",
                "score": parts[8] if len(parts) > 8 else None,
                "marker": standard_mitos_name(mitos_type=parts[1], name=parts[2]),
            }
        )

    return features


def parse_gene_order(**kwargs):
    """Parse ``result.geneorder`` into a list of tokens such as ``-trnQ``."""

    text = kwargs.get("text", "") or ""
    tokens = []

    for line in text.splitlines():
        if line.startswith(">"):
            continue
        tokens.extend(line.split())

    return tokens


def canonical_gene_order(**kwargs):
    """Rotate a circular gene order so it starts at 12S (rrnS), keeping strands.

    Origin markers (OL, OH) are dropped because MITOS2 reports them
    inconsistently between runs.
    """

    tokens = [token for token in kwargs.get("tokens", []) if not token.lstrip("-").startswith(("OL", "OH"))]

    # An assembly built on the opposite strand lists the same order reversed with
    # every strand flipped; normalize it so that rrnS is on the plus strand.
    if "-rrnS" in tokens:
        tokens = [token[1:] if token.startswith("-") else f"-{token}" for token in reversed(tokens)]

    names = [token.lstrip("-") for token in tokens]
    if "rrnS" in names:
        start = names.index("rrnS")
        tokens = tokens[start:] + tokens[:start]

    return " ".join(tokens)


def feature_length(**kwargs):
    feature = kwargs.get("feature")
    length = kwargs.get("length")
    if feature["start"] <= feature["stop"]:
        return feature["stop"] - feature["start"] + 1
    if length:
        return (length - feature["start"]) + feature["stop"] + 1
    return None


def contained_in_wrapped(**kwargs):
    """Return True when ``kept`` lies inside the circular interval of ``wrapped``."""

    kept = kwargs.get("kept")
    wrapped = kwargs.get("wrapped")
    in_tail = kept["start"] >= wrapped["start"] and kept["stop"] >= wrapped["start"]
    in_head = kept["start"] <= wrapped["stop"] and kept["stop"] <= wrapped["stop"]
    return in_tail or in_head


def origin_checks(**kwargs):
    """Detect kept features that are fragments of an origin-crossing hit."""

    kept = kwargs.get("kept", [])
    ignored = kwargs.get("ignored", [])
    length = kwargs.get("length")
    records = []

    wrapped_hits = [hit for hit in ignored if hit["start"] > hit["stop"] and hit["marker"]]

    for hit in wrapped_hits:
        fragments = [f for f in kept if f["marker"] == hit["marker"] and contained_in_wrapped(kept=f, wrapped=hit)]
        if not fragments:
            continue
        fragment = max(fragments, key=lambda f: f["stop"] - f["start"])
        records.append(
            {
                "Marker": hit["marker"],
                "Raw marker": hit["name"],
                "Annotated start": fragment["start"] + 1,
                "Annotated end": fragment["stop"] + 1,
                "Annotated length": fragment["stop"] - fragment["start"] + 1,
                "Contig length": length,
                "Crosses origin": True,
                "Origin-corrected length": feature_length(feature=hit, length=length),
                "Origin evidence": f"ignored.mitos {hit['name']} {hit['start']}-{hit['stop']} score {hit['score']}",
            }
        )

    return records


def contig_length(**kwargs):
    """Length of the sequence MITOS2 annotated (``mitos2.fasta``), or None."""

    path = os.path.join(kwargs.get("mitos2_dir"), "mitos2.fasta")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as handle:
        return sum(len(line.strip()) for line in handle if not line.startswith(">"))


def parse_mitos2_assembly_sync(**kwargs):
    """Parse the MITOS2 folder of one assembly."""

    job = kwargs.get("job", {})
    mitos2_dir = job.get("paths", {}).get("mitos2_dir")
    identity = assembly_identity(job=job)

    if not mitos2_dir:
        logging.debug("MITOS2 folder not found for %s", job.get("Assembly"))
        return None

    result_path = os.path.join(mitos2_dir, "result.mitos")
    if not os.path.isfile(result_path):
        logging.debug("MITOS2 result.mitos not found: %s", mitos2_dir)
        return None

    kept = parse_mitos_table(text=read_text_file(file_path=result_path))
    ignored_path = os.path.join(mitos2_dir, "ignored.mitos")
    ignored = parse_mitos_table(text=read_text_file(file_path=ignored_path)) if os.path.isfile(ignored_path) else []
    order_path = os.path.join(mitos2_dir, "result.geneorder")
    tokens = parse_gene_order(text=read_text_file(file_path=order_path)) if os.path.isfile(order_path) else []
    if not tokens:
        tokens = [("-" if f["strand"] == "-" else "") + f["name"].split("(")[0] for f in sorted(kept, key=lambda f: f["start"])]

    length = contig_length(mitos2_dir=mitos2_dir)
    origin_records = [{**identity, **record} for record in origin_checks(kept=kept, ignored=ignored, length=length)]
    partial_markers = {record["Marker"] for record in origin_records}

    counts = collections.Counter(f["marker"] for f in kept if f["marker"])
    status = {}
    for marker in EXPECTED_MARKERS:
        if marker in partial_markers:
            status[marker] = "Partial at origin"
        elif counts[marker] == 0:
            status[marker] = "Absent"
        elif counts[marker] > 1:
            status[marker] = "Duplicated"
        else:
            status[marker] = "Present"

    completeness = {
        **identity,
        "Genes present": sum(1 for value in status.values() if value != "Absent"),
        "Genes absent": sum(1 for value in status.values() if value == "Absent"),
        "Genes duplicated": sum(1 for value in status.values() if value == "Duplicated"),
        "Genes partial at origin": sum(1 for value in status.values() if value == "Partial at origin"),
        "Missing genes": ", ".join(marker for marker, value in status.items() if value == "Absent"),
        "Gene order": canonical_gene_order(tokens=tokens),
        **{marker: status[marker] for marker in EXPECTED_MARKERS},
    }

    return {"completeness": completeness, "origin": origin_records}


async def parse_mitos2_assembly(**kwargs):
    semaphore = kwargs.get("semaphore")
    async with semaphore:
        return await asyncio.to_thread(parse_mitos2_assembly_sync, job=kwargs.get("job"))


def order_consistent(**kwargs):
    """True when the genes of ``order`` appear in the same circular order and strand as in ``modal``.

    Partial assemblies (missing genes) are compared on the genes they have, so
    only real rearrangements or strand changes count as differences.
    """

    tokens = str(kwargs.get("order", "")).split()
    modal = str(kwargs.get("modal", "")).split()
    if not tokens or not modal:
        return None
    present = set(tokens)
    restricted = [token for token in modal if token in present]
    if len(restricted) != len(tokens) or len(set(tokens)) != len(tokens):
        return False
    start = restricted.index(tokens[0])
    return restricted[start:] + restricted[:start] == tokens


def compare_gene_orders(**kwargs):
    """Add the project modal gene order and whether each assembly matches it."""

    dataframe = kwargs.get("dataframe")
    if dataframe is None or dataframe.empty:
        return dataframe

    modal_orders = {}
    for project, group in dataframe.groupby("Project name"):
        orders = group.loc[group["Genes absent"] == 0, "Gene order"]
        if orders.empty:
            orders = group["Gene order"]
        modal_orders[project] = orders.mode().iloc[0] if not orders.mode().empty else ""

    dataframe = dataframe.copy()
    dataframe["Modal gene order"] = dataframe["Project name"].map(modal_orders)
    dataframe["Gene order matches modal"] = [
        order_consistent(order=order, modal=modal) for order, modal in zip(dataframe["Gene order"], dataframe["Modal gene order"])
    ]
    return dataframe


async def load_mitos2_data(**kwargs):
    """Return (completeness dataframe, origin-check dataframe) for all assemblies."""

    jobs = kwargs.get("jobs", [])
    concurrency = max(1, int(kwargs.get("concurrency", 8)))
    semaphore = asyncio.Semaphore(concurrency)

    results = await gather_records(
        tasks=[parse_mitos2_assembly(job=job, semaphore=semaphore) for job in jobs],
        source_name="MITOS2 folder",
    )

    if len(results) < len(jobs):
        logging.warning("MITOS2 results missing for %d of %d assemblies; their completeness is NA", len(jobs) - len(results), len(jobs))

    completeness = pd.DataFrame([r["completeness"] for r in results])
    origin = pd.DataFrame([row for r in results for row in r["origin"]], columns=ORIGIN_COLUMNS)

    if not completeness.empty:
        completeness = compare_gene_orders(dataframe=completeness)
        lead = [c for c in completeness.columns if c not in EXPECTED_MARKERS]
        completeness = completeness[lead + EXPECTED_MARKERS]

    logging.info("MITOS2 folders parsed: %d (%d genes crossing the origin)", len(completeness), len(origin))
    return completeness, origin
