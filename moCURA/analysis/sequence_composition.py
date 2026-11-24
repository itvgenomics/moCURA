"""Base composition and codon usage, ready for genome announcements.

* Whole genome: GC%, AT-skew = (A - T) / (A + T) and GC-skew = (G - C) / (G + C),
  on the strand written in the GenBank file.
* Protein-coding genes: the same indices on the concatenated coding sequences,
  separately for genes on the + and - strands (each read 5'->3' on its own
  coding strand), and for all of them together.
* RSCU of the protein-coding genes with the genetic code of the assembly:
  observed codon count / mean count of the synonymous codons of that amino
  acid. Incomplete codons and the terminal stop codon of each gene are left
  out.
"""

import asyncio
import logging
from collections import Counter

import pandas as pd
from Bio import SeqIO
from Bio.Data import CodonTable

from ..load.organpipe_layout import ASSEMBLY_ID_COLUMNS, assembly_identity

COMPOSITION_COLUMNS = ASSEMBLY_ID_COLUMNS + [
    "GenBank source", "Genome length", "GC %", "AT skew", "GC skew",
    "PCG + strand bp", "PCG + GC %", "PCG + AT skew", "PCG + GC skew",
    "PCG - strand bp", "PCG - GC %", "PCG - AT skew", "PCG - GC skew",
    "PCG bp", "PCG GC %", "PCG AT skew", "PCG GC skew", "Codons counted", "Genetic code",
]
RSCU_COLUMNS = ASSEMBLY_ID_COLUMNS + ["Codon", "Amino acid", "Count", "RSCU"]


def composition(**kwargs):
    """GC %, AT-skew and GC-skew of a DNA sequence (None when undefined)."""

    sequence = str(kwargs.get("sequence", "")).upper()
    counts = Counter(sequence)
    a, c, g, t = (counts.get(base, 0) for base in "ACGT")
    total = a + c + g + t
    return {
        "GC %": round(100 * (g + c) / total, 3) if total else None,
        "AT skew": round((a - t) / (a + t), 4) if a + t else None,
        "GC skew": round((g - c) / (g + c), 4) if g + c else None,
        "bp": len(sequence),
    }


def codon_counts(**kwargs):
    sequences = kwargs.get("sequences", [])
    table = CodonTable.unambiguous_dna_by_id[int(kwargs.get("table", 2))]
    counts = Counter()
    for sequence in sequences:
        sequence = str(sequence).upper()
        codons = [sequence[i:i + 3] for i in range(0, len(sequence) - len(sequence) % 3, 3)]
        if codons and codons[-1] in table.stop_codons:
            codons = codons[:-1]
        counts.update(codon for codon in codons if len(codon) == 3 and set(codon) <= set("ACGT"))
    return counts


def rscu(**kwargs):
    """RSCU rows for every sense codon of the genetic code."""

    counts = kwargs.get("counts", Counter())
    table = CodonTable.unambiguous_dna_by_id[int(kwargs.get("table", 2))]
    synonymous = {}
    for codon, amino_acid in table.forward_table.items():
        synonymous.setdefault(amino_acid, []).append(codon)
    rows = []
    for amino_acid in sorted(synonymous):
        codons = sorted(synonymous[amino_acid])
        total = sum(counts.get(codon, 0) for codon in codons)
        for codon in codons:
            value = counts.get(codon, 0)
            rows.append({
                "Codon": codon, "Amino acid": amino_acid, "Count": value,
                "RSCU": round(value * len(codons) / total, 4) if total else None,
            })
    return rows


def composition_assembly_sync(**kwargs):
    job = kwargs.get("job", {})
    genetic_code = int(kwargs.get("genetic_code", 2))
    paths = job.get("paths", {})
    path, source = paths.get("rotated_genbank"), "rotated"
    if not path:
        path, source = paths.get("genbank"), "unrotated"
    if not path:
        return None
    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return None

    plus, minus = [], []
    for feature in record.features:
        if feature.type != "CDS":
            continue
        coding = str(feature.extract(record.seq)).upper()
        (minus if feature.location.strand == -1 else plus).append(coding)

    identity = assembly_identity(job=job)
    genome = composition(sequence=record.seq)
    strand_plus = composition(sequence="".join(plus))
    strand_minus = composition(sequence="".join(minus))
    pcg = composition(sequence="".join(plus + minus))
    counts = codon_counts(sequences=plus + minus, table=genetic_code)
    row = {
        **identity, "GenBank source": source, "Genome length": len(record.seq),
        "GC %": genome["GC %"], "AT skew": genome["AT skew"], "GC skew": genome["GC skew"],
        "PCG + strand bp": strand_plus["bp"], "PCG + GC %": strand_plus["GC %"], "PCG + AT skew": strand_plus["AT skew"], "PCG + GC skew": strand_plus["GC skew"],
        "PCG - strand bp": strand_minus["bp"], "PCG - GC %": strand_minus["GC %"], "PCG - AT skew": strand_minus["AT skew"], "PCG - GC skew": strand_minus["GC skew"],
        "PCG bp": pcg["bp"], "PCG GC %": pcg["GC %"], "PCG AT skew": pcg["AT skew"], "PCG GC skew": pcg["GC skew"],
        "Codons counted": sum(counts.values()), "Genetic code": genetic_code,
    }
    usage = [{**identity, **item} for item in rscu(counts=counts, table=genetic_code)] if counts else []
    return {"composition": row, "rscu": usage}


async def composition_assembly(**kwargs):
    async with kwargs.get("semaphore"):
        return await asyncio.to_thread(composition_assembly_sync, job=kwargs.get("job"), genetic_code=kwargs.get("genetic_code"))


async def load_sequence_composition(**kwargs):
    """Return (composition dataframe, RSCU dataframe in long format)."""

    jobs = kwargs.get("jobs", [])
    genetic_code = int(kwargs.get("genetic_code", 2))
    semaphore = asyncio.Semaphore(max(1, int(kwargs.get("concurrency", 8))))
    results = await asyncio.gather(
        *[composition_assembly(job=job, genetic_code=genetic_code, semaphore=semaphore) for job in jobs], return_exceptions=True,
    )
    rows, usage = [], []
    for job, result in zip(jobs, results):
        if isinstance(result, Exception):
            logging.error("Sequence composition failed for %s: %s", job.get("Assembly"), result)
        elif result is not None:
            rows.append(result["composition"])
            usage.extend(result["rscu"])
    if len(rows) < len(jobs):
        logging.warning("GenBank missing for %d of %d assemblies; their composition is NA", len(jobs) - len(rows), len(jobs))
    logging.info("Sequence composition: %d assemblies", len(rows))
    return pd.DataFrame(rows, columns=COMPOSITION_COLUMNS), pd.DataFrame(usage, columns=RSCU_COLUMNS)
