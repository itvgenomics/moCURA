import asyncio
import logging
import os
import re

import pandas as pd
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord


FASTA_MANIFEST_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy",
    "GenBank file", "Relative path", "Record ID", "Record length",
    "Sequence ID", "FASTA file", "FASTA path",
]


def sanitize_file_token(**kwargs):
    value = str(kwargs.get("value", "")).strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return value or "unknown"


def build_sequence_id(**kwargs):
    row = kwargs.get("row", {})
    project = sanitize_file_token(value=row["Project name"])
    seed = sanitize_file_token(value=row["Seed Input"])
    record_id = sanitize_file_token(value=row["Record ID"])
    return f"{project}__seed_{int(row['Seed order'])}-{seed}__kmer_{int(row['K-mer'])}__copy_{int(row['Assembly copy'])}__{record_id}"


def export_genbank_record_sync(**kwargs):
    row = kwargs.get("row", {})
    results_dir = kwargs.get("results_dir", ".")
    fasta_dir = kwargs.get("fasta_dir", "fastas")
    overwrite = bool(kwargs.get("overwrite", False))

    genbank_path = os.path.join(results_dir, str(row["Relative path"]))
    if not os.path.isfile(genbank_path):
        raise FileNotFoundError(f"Rotated GenBank file not found: {genbank_path}")

    sequence_id = build_sequence_id(row=row)
    fasta_file = f"{sequence_id}.fasta"
    fasta_path = os.path.join(fasta_dir, fasta_file)

    if not overwrite and os.path.isfile(fasta_path) and os.path.getsize(fasta_path) > 0:
        return {**row, "Sequence ID": sequence_id, "FASTA file": fasta_file, "FASTA path": fasta_path}

    selected_record = None
    for record in SeqIO.parse(genbank_path, "genbank"):
        if str(record.id) == str(row["Record ID"]):
            selected_record = record
            break

    if selected_record is None:
        raise ValueError(f"Record {row['Record ID']} was not found in {genbank_path}")

    description = (
        f"project={row['Project name']} seed={row['Seed Input']} kmer={int(row['K-mer'])} "
        f"copy={int(row['Assembly copy'])} record={row['Record ID']} source={row['GenBank file']}"
    )
    fasta_record = SeqRecord(selected_record.seq, id=sequence_id, description=description)
    SeqIO.write([fasta_record], fasta_path, "fasta")

    return {**row, "Sequence ID": sequence_id, "FASTA file": fasta_file, "FASTA path": fasta_path}


async def export_rotated_genome_fastas(**kwargs):
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe")
    results_dir = kwargs.get("results_dir", ".")
    output_dir = kwargs.get("output_dir", "trf_analysis")
    concurrency = max(1, int(kwargs.get("concurrency", 4)))
    overwrite = bool(kwargs.get("overwrite", False))

    if genbank_files_dataframe is None or genbank_files_dataframe.empty:
        return pd.DataFrame(columns=FASTA_MANIFEST_COLUMNS)

    fasta_dir = os.path.join(output_dir, "fastas")
    os.makedirs(fasta_dir, exist_ok=True, mode=0o755)
    semaphore = asyncio.Semaphore(concurrency)

    async def export_row(row):
        async with semaphore:
            return await asyncio.to_thread(
                export_genbank_record_sync,
                row=row,
                results_dir=results_dir,
                fasta_dir=fasta_dir,
                overwrite=overwrite,
            )

    tasks = [export_row(row.to_dict()) for _, row in genbank_files_dataframe.iterrows()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    records = []

    for result in results:
        if isinstance(result, Exception):
            logging.error("Could not export rotated GenBank sequence to FASTA: %s", result)
            continue
        records.append(result)

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=FASTA_MANIFEST_COLUMNS)

    dataframe = dataframe[FASTA_MANIFEST_COLUMNS].sort_values(
        ["Project name", "Seed order", "K-mer", "Assembly copy", "Record ID"]
    ).reset_index(drop=True)

    manifest_path = os.path.join(output_dir, "fasta_manifest.tsv")
    dataframe.to_csv(manifest_path, sep="\t", index=False)
    logging.info("Exported %d rotated GenBank sequences to FASTA", len(dataframe))
    return dataframe
