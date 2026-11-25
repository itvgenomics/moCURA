"""Comparison of each assembly with RefSeq organelle genomes of related species.

For every project, the taxonomy found by the species identification (the
declared species, or the best match when none is declared) gives the taxon to
search: RefSeq complete genomes of the same organelle in the genus, and in the
family when the genus has fewer than ``min_references`` (``levels`` in
``config.yml``; ``order`` can be added). RefSeq is used because its records are
curated. At most ``max_references`` genomes are downloaded per taxon.

Each assembly of the project is then compared with the references:

* genome length against the reference range, widened by ``length_tolerance_percent``;
* the length of every gene against the range of the same gene in the references,
  widened by ``gene_tolerance_percent``; genes present in most references but
  absent from the assembly are listed;
* tandem repeats: TRF (same parameters as the ``trf`` section) runs on every
  reference, and the number of repeats and bases in repeats of the assembly are
  compared with the reference range.

Gene names of the references go through the same standardization as the
assemblies (SynGenes aliases), so ``cox1``, ``COX1`` and ``COI`` are one gene.
"""

import asyncio
import io
import logging
import os
import re
import statistics

import pandas as pd
from Bio import SeqIO

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity
from ..standardization.standardized_marker_name import standardized_marker_name
from .run_trf_analysis import run_trf_job


REFERENCE_COLUMNS = [
    "Project name", "Reference level", "Reference taxon", "Accession", "Organism", "Genome length",
    "Genes", "Tandem repeats", "Bases in repeats",
]
SUMMARY_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Reference level", "Reference taxon", "References", "Genome length", "Reference length min",
    "Reference length median", "Reference length max", "Genome length status", "Genes compared",
    "Genes outside the reference range", "Genes outside (list)", "Genes absent but in references",
    "Tandem repeats", "Bases in repeats", "Reference repeats min", "Reference repeats max",
    "Reference bases in repeats min", "Reference bases in repeats max", "Repeat status",
]
GENE_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "Marker", "Length", "References with the gene", "Reference min", "Reference median", "Reference max",
    "Deviation from median (%)", "Status",
]


ONE_LETTER = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
}
# Anticodons of the two leucine and serine tRNAs (Leu1 reads CUN, Leu2 UUR, Ser1 AGN/AGY, Ser2 UCN).
ISOACCEPTORS = {("L", "TAG"): "L1", ("L", "TAA"): "L2", ("S", "GCT"): "S1", ("S", "TCT"): "S1", ("S", "TGA"): "S2"}


def trna_qualifiers(feature):
    """RefSeq tRNA names (``tRNA-Phe`` with an anticodon) rewritten as MITOS2 names (``trnF``).

    The marker standardization reads MITOS2-style names; RefSeq products such as
    ``tRNA-Phe`` would otherwise be resolved by the letter after ``trn``.
    """

    product = str((feature.qualifiers.get("product") or [""])[0])
    match = re.match(r"tRNA-([A-Za-z]{3})", product)
    if not match or match.group(1).capitalize() not in ONE_LETTER:
        return feature.qualifiers
    letter = ONE_LETTER[match.group(1).capitalize()]
    anticodon = re.search(r"seq:([acgtuACGTU]{3})", str((feature.qualifiers.get("anticodon") or [""])[0]))
    codon = anticodon.group(1).upper().replace("U", "T") if anticodon else ""
    name = ISOACCEPTORS.get((letter, codon), letter)
    return {"gene": [f"trn{name}"], "product": [f"trn{name}({codon.lower()})" if codon else f"trn{name}"]}


def genome_genes(record):
    """Length of every standardized gene of a GenBank record (longest copy)."""

    genes = {}
    for feature in record.features:
        if feature.type not in ("CDS", "rRNA", "tRNA"):
            continue
        qualifiers = trna_qualifiers(feature) if feature.type == "tRNA" else feature.qualifiers
        marker = standardized_marker_name(feature_type=feature.type, qualifiers=qualifiers)
        if not marker:
            continue
        genes[marker] = max(genes.get(marker, 0), len(feature.location))
    return genes


def organelle_filter(organelle):
    return "chloroplast[filter]" if organelle == "chloroplast" else "mitochondrion[filter]"


async def search_references(**kwargs):
    """GenBank records of the RefSeq genomes of one taxon (cached by the service)."""

    service = kwargs.get("service")
    taxid = kwargs.get("taxid")
    organelle = kwargs.get("organelle", "mitochondrion")
    maximum = int(kwargs.get("max_references", 50))
    term = f"txid{taxid}[Organism:exp] AND srcdb_refseq[PROP] AND {organelle_filter(organelle)} AND \"complete genome\"[Title]"
    search = await service.eutils("esearch", {"db": "nuccore", "term": term, "retmode": "json", "retmax": str(maximum), "sort": "accession"}, as_json=True)
    ids = ((search or {}).get("esearchresult") or {}).get("idlist") or []
    records = []
    for start in range(0, len(ids), 20):
        batch = ids[start:start + 20]
        text = await service.eutils("efetch", {"db": "nuccore", "id": ",".join(batch), "rettype": "gbwithparts", "retmode": "text"})
        if not text:
            continue
        try:
            records.extend(SeqIO.parse(io.StringIO(text), "genbank"))
        except ValueError as error:
            logging.warning("Could not parse RefSeq records for txid%s: %s", taxid, error)
    return records


async def reference_repeats(**kwargs):
    """(number of repeats, bases in repeats) of one reference genome with TRF."""

    record = kwargs.get("record")
    folder = kwargs.get("folder")
    trf_config = kwargs.get("trf_config", {}) or {}
    semaphore = kwargs.get("semaphore")
    accession = record.id.replace("/", "_")
    fasta_dir, raw_dir, logs_dir = (os.path.join(folder, name) for name in ("fasta", "trf_raw", "trf_logs"))
    for directory in (fasta_dir, raw_dir, logs_dir):
        os.makedirs(directory, exist_ok=True, mode=0o755)
    fasta_path = os.path.join(fasta_dir, f"{accession}.fasta")
    if not os.path.isfile(fasta_path):
        SeqIO.write([record], fasta_path, "fasta")
    metadata = {
        "Project name": "RefSeq", "Seed order": 0, "Seed Input": "", "K-mer": 0, "Assembly copy": 0, "GenBank file": accession,
        "Record ID": record.id, "Record length": len(record.seq), "Sequence ID": accession, "FASTA file": os.path.basename(fasta_path),
        "FASTA path": fasta_path,
    }
    try:
        result = await run_trf_job(metadata=metadata, raw_dir=raw_dir, logs_dir=logs_dir, binary=trf_config.get("binary", "trf"),
                                   config=trf_config, semaphore=semaphore, overwrite=False)
    except (OSError, RuntimeError, TimeoutError) as error:
        logging.warning("TRF failed for reference %s: %s", accession, error)
        return None, None
    repeats = result.get("repeats", [])
    covered = set()
    for repeat in repeats:
        covered.update(range(int(repeat["Start"]), int(repeat["End"]) + 1))
    return len(repeats), len(covered)


def assembly_genome(job):
    paths = job.get("paths", {})
    path = paths.get("rotated_genbank") or paths.get("genbank")
    if not path:
        return None
    return next(SeqIO.parse(path, "genbank"), None)


def assembly_repeats(**kwargs):
    """(number of repeats, bases in repeats) of each assembly from the moCURA TRF tables.

    Assemblies TRF processed without finding repeats get (0, 0); assemblies TRF
    did not process are left out (NA in the comparison).
    """

    dataframe = kwargs.get("dataframe")
    summary = kwargs.get("summary_dataframe")
    result = {}
    if summary is not None and not summary.empty:
        for _, row in summary.iterrows():
            try:
                result[(str(row["Project name"]), str(row["Seed Input"]), int(row["K-mer"]), int(row["Assembly copy"]))] = (0, 0)
            except (KeyError, TypeError, ValueError):
                continue
    if dataframe is None or dataframe.empty:
        return result
    for key, group in dataframe.groupby(["Project name", "Seed Input", "K-mer", "Assembly copy"]):
        covered = set()
        for _, row in group.iterrows():
            covered.update(range(int(row["Start"]), int(row["End"]) + 1))
        result[(str(key[0]), str(key[1]), int(key[2]), int(key[3]))] = (len(group), len(covered))
    return result


def range_status(value, low, high, tolerance):
    if value is None or low is None or high is None:
        return "NA"
    if value < low * (1 - tolerance / 100):
        return "Shorter"
    if value > high * (1 + tolerance / 100):
        return "Longer"
    return "Within"


def compare_project(**kwargs):
    """Summary and gene rows of every assembly of one project."""

    jobs = kwargs.get("jobs", [])
    references = kwargs.get("references", [])
    level, taxon = kwargs.get("level"), kwargs.get("taxon")
    length_tolerance = float(kwargs.get("length_tolerance_percent", 5))
    gene_tolerance = float(kwargs.get("gene_tolerance_percent", 10))
    repeats = kwargs.get("assembly_repeats", {})
    lengths = [item["Genome length"] for item in references]
    gene_lengths = {}
    for item in references:
        for marker, length in item["genes"].items():
            gene_lengths.setdefault(marker, []).append(length)
    repeat_counts = [item["Tandem repeats"] for item in references if item["Tandem repeats"] is not None]
    repeat_bases = [item["Bases in repeats"] for item in references if item["Bases in repeats"] is not None]
    summaries, genes = [], []

    for job in jobs:
        record = assembly_genome(job)
        if record is None:
            continue
        identity = assembly_identity(job=job)
        own = genome_genes(record)
        outside, absent = [], []
        for marker, values in sorted(gene_lengths.items()):
            low, high, middle = min(values), max(values), statistics.median(values)
            length = own.get(marker)
            if length is None:
                if len(values) > len(references) / 2:
                    absent.append(marker)
                    genes.append({**identity, "Marker": marker, "Length": None, "References with the gene": len(values), "Reference min": low,
                                  "Reference median": middle, "Reference max": high, "Deviation from median (%)": None, "Status": "Absent"})
                continue
            status = range_status(length, low, high, gene_tolerance)
            if status != "Within":
                outside.append(f"{marker} ({length} bp; references {low}-{high})")
            genes.append({**identity, "Marker": marker, "Length": length, "References with the gene": len(values), "Reference min": low,
                          "Reference median": middle, "Reference max": high,
                          "Deviation from median (%)": round(100 * (length - middle) / middle, 2) if middle else None, "Status": status})
        key = (str(job["Project name"]), str(job["Seed Input"]), int(job["K-mer"]), int(job["Assembly copy"]))
        count, bases = repeats.get(key, (None, None))
        repeat_status = "NA"
        if repeat_bases and bases is not None:
            repeat_status = "More repeats" if bases > max(repeat_bases) else ("Fewer repeats" if bases < min(repeat_bases) else "Within")
        summaries.append({
            **identity,
            "Reference level": level, "Reference taxon": taxon, "References": len(references),
            "Genome length": len(record.seq),
            "Reference length min": min(lengths) if lengths else None,
            "Reference length median": statistics.median(lengths) if lengths else None,
            "Reference length max": max(lengths) if lengths else None,
            "Genome length status": range_status(len(record.seq), min(lengths) if lengths else None, max(lengths) if lengths else None, length_tolerance),
            "Genes compared": sum(1 for marker in gene_lengths if marker in own),
            "Genes outside the reference range": len(outside),
            "Genes outside (list)": "; ".join(outside),
            "Genes absent but in references": ", ".join(absent),
            "Tandem repeats": count, "Bases in repeats": bases,
            "Reference repeats min": min(repeat_counts) if repeat_counts else None,
            "Reference repeats max": max(repeat_counts) if repeat_counts else None,
            "Reference bases in repeats min": min(repeat_bases) if repeat_bases else None,
            "Reference bases in repeats max": max(repeat_bases) if repeat_bases else None,
            "Repeat status": repeat_status,
        })
    return summaries, genes


async def run_reference_comparison(**kwargs):
    """Return (summary, genes, references) dataframes."""

    service = kwargs.get("service")
    settings = kwargs.get("settings", {}) or {}
    species = kwargs.get("species_dataframe")
    organelle = kwargs.get("organelle", "mitochondrion")
    output_dir = kwargs.get("output_dir")
    trf_config = kwargs.get("trf_config", {}) or {}
    jobs = kwargs.get("jobs", [])
    empty = (pd.DataFrame(columns=SUMMARY_COLUMNS), pd.DataFrame(columns=GENE_COLUMNS), pd.DataFrame(columns=REFERENCE_COLUMNS))
    if species is None or species.empty:
        logging.warning("RefSeq comparison skipped: no taxonomy from the species identification")
        return empty

    levels = [str(level).lower() for level in settings.get("levels", ["genus", "family"])]
    min_references = int(settings.get("min_references", 1))
    semaphore = asyncio.Semaphore(max(1, int(trf_config.get("concurrency", 4))))
    references_by_taxid = {}
    reference_dir = os.path.join(output_dir, "refseq")
    os.makedirs(reference_dir, exist_ok=True, mode=0o755)
    repeats = assembly_repeats(dataframe=kwargs.get("trf_repeats_dataframe"), summary_dataframe=kwargs.get("trf_summary_dataframe"))
    summaries, genes, reference_rows = [], [], []

    async def load_taxon(taxid):
        if taxid in references_by_taxid:
            return references_by_taxid[taxid]
        records = await search_references(service=service, taxid=taxid, organelle=organelle, max_references=settings.get("max_references", 50))
        items = []
        for record in records:
            path = os.path.join(reference_dir, f"{record.id}.gb")
            if not os.path.isfile(path):
                SeqIO.write([record], path, "genbank")
            count, bases = (await reference_repeats(record=record, folder=reference_dir, trf_config=trf_config, semaphore=semaphore)
                            if settings.get("compare_repeats", True) else (None, None))
            items.append({"Accession": record.id, "Organism": record.annotations.get("organism", ""), "Genome length": len(record.seq),
                          "genes": genome_genes(record), "Tandem repeats": count, "Bases in repeats": bases})
        references_by_taxid[taxid] = items
        return items

    projects = species.drop_duplicates("Project name")
    for _, row in projects.iterrows():
        project = str(row["Project name"])
        chosen = (None, None, [])
        for level in levels:
            column = level.capitalize()
            taxid = row.get(f"{column} TaxID")
            if taxid is None or pd.isna(taxid):
                continue
            items = await load_taxon(int(taxid))
            logging.info("RefSeq %s genomes for %s (%s %s): %d", organelle, project, level, row.get(column), len(items))
            if len(items) >= min_references:
                chosen = (level, row.get(column), items)
                break
        level, taxon, items = chosen
        if not items:
            logging.warning("No RefSeq %s genome found for %s at levels %s", organelle, project, ", ".join(levels))
            continue
        for item in items:
            reference_rows.append({"Project name": project, "Reference level": level, "Reference taxon": taxon,
                                   **{column: item[column] for column in ("Accession", "Organism", "Genome length", "Tandem repeats", "Bases in repeats")},
                                   "Genes": len(item["genes"])})
        project_jobs = [job for job in jobs if job["Project name"] == project]
        project_summaries, project_genes = compare_project(
            jobs=project_jobs, references=items, level=level, taxon=taxon, assembly_repeats=repeats,
            length_tolerance_percent=settings.get("length_tolerance_percent", 5), gene_tolerance_percent=settings.get("gene_tolerance_percent", 10),
        )
        summaries.extend(project_summaries)
        genes.extend(project_genes)

    logging.info("RefSeq comparison: %d assemblies compared with %d reference genomes", len(summaries), len({row["Accession"] for row in reference_rows}))
    return (pd.DataFrame(summaries, columns=SUMMARY_COLUMNS), pd.DataFrame(genes, columns=GENE_COLUMNS),
            pd.DataFrame(reference_rows, columns=REFERENCE_COLUMNS))
