import asyncio
import glob
import logging
import os
import shutil

import pandas as pd
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO

from ..export.export_rotated_genome_fastas import export_rotated_genome_fastas


TRF_REPEAT_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy",
    "GenBank file", "Record ID", "Record length", "Sequence ID", "FASTA file",
    "Repeat number", "Start", "End", "Repeat length", "Period Size", "Copy Number",
    "Consensus Size", "Percent Matches", "Percent Indels", "Score", "A", "C", "G", "T",
    "Entropy", "Consensus", "Repeat Sequence", "TRF data file",
]

TRF_SUMMARY_COLUMNS = [
    "Project name", "Seed order", "Seed Input", "K-mer", "Assembly copy",
    "GenBank file", "Record ID", "Record length", "Sequence ID", "FASTA file",
    "Repeats found", "TRF parameters", "TRF data file", "TRF log file",
]


def trf_parameter_values(**kwargs):
    config = kwargs.get("config", {})
    return [
        int(config.get("match", 2)),
        int(config.get("mismatch", 7)),
        int(config.get("delta", 7)),
        int(config.get("match_probability", 80)),
        int(config.get("indel_probability", 10)),
        int(config.get("min_score", 50)),
        int(config.get("max_period", 500)),
    ]


def build_trf_command(**kwargs):
    binary = kwargs.get("binary", "trf")
    fasta_path = kwargs.get("fasta_path")
    config = kwargs.get("config", {})
    command = [binary, os.path.abspath(fasta_path), *[str(value) for value in trf_parameter_values(config=config)]]

    if bool(config.get("flanking", False)):
        command.append("-f")
    if bool(config.get("masked", False)):
        command.append("-m")
    if bool(config.get("no_redundancy", False)):
        command.append("-r")

    if bool(config.get("suppress_html", True)):
        command.append("-h")
    else:
        command.append("-d")

    max_tr_length_millions = config.get("max_tr_length_millions")
    if max_tr_length_millions is not None:
        command.extend(["-l", str(int(max_tr_length_millions))])

    return command


def find_trf_data_file(**kwargs):
    fasta_path = kwargs.get("fasta_path")
    raw_dir = kwargs.get("raw_dir")
    config = kwargs.get("config", {})
    parameter_token = ".".join(str(value) for value in trf_parameter_values(config=config))
    exact_path = os.path.join(raw_dir, f"{os.path.basename(fasta_path)}.{parameter_token}.dat")

    if os.path.isfile(exact_path):
        return exact_path

    candidates = sorted(glob.glob(os.path.join(raw_dir, f"{os.path.basename(fasta_path)}.{parameter_token}*.dat")))
    return candidates[0] if candidates else None


def parse_trf_dat(**kwargs):
    dat_path = kwargs.get("dat_path")
    metadata = kwargs.get("metadata", {})
    records = []

    if not dat_path or not os.path.isfile(dat_path):
        return records

    with open(dat_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 15 or not parts[0].isdigit() or not parts[1].isdigit():
                continue

            try:
                start = int(parts[0])
                end = int(parts[1])
                record = {
                    "Project name": metadata["Project name"],
                    "Seed order": int(metadata["Seed order"]),
                    "Seed Input": metadata["Seed Input"],
                    "K-mer": int(metadata["K-mer"]),
                    "Assembly copy": int(metadata["Assembly copy"]),
                    "GenBank file": metadata["GenBank file"],
                    "Record ID": metadata["Record ID"],
                    "Record length": int(metadata["Record length"]),
                    "Sequence ID": metadata["Sequence ID"],
                    "FASTA file": metadata["FASTA file"],
                    "Start": start,
                    "End": end,
                    "Repeat length": end - start + 1,
                    "Period Size": int(float(parts[2])),
                    "Copy Number": float(parts[3]),
                    "Consensus Size": int(float(parts[4])),
                    "Percent Matches": float(parts[5]),
                    "Percent Indels": float(parts[6]),
                    "Score": float(parts[7]),
                    "A": float(parts[8]),
                    "C": float(parts[9]),
                    "G": float(parts[10]),
                    "T": float(parts[11]),
                    "Entropy": float(parts[12]),
                    "Consensus": parts[13],
                    "Repeat Sequence": "".join(parts[14:]),
                    "TRF data file": dat_path,
                }
            except (ValueError, IndexError, KeyError) as error:
                logging.warning("Could not parse TRF line in %s: %s", dat_path, error)
                continue

            records.append(record)

    for repeat_number, record in enumerate(records, start=1):
        record["Repeat number"] = repeat_number

    return records


async def run_trf_job(**kwargs):
    metadata = kwargs.get("metadata", {})
    raw_dir = kwargs.get("raw_dir")
    logs_dir = kwargs.get("logs_dir")
    binary = kwargs.get("binary", "trf")
    config = kwargs.get("config", {})
    semaphore = kwargs.get("semaphore") or asyncio.Semaphore(1)
    overwrite = bool(kwargs.get("overwrite", False))
    timeout = int(config.get("timeout", 3600))

    fasta_path = metadata["FASTA path"]
    sequence_id = metadata["Sequence ID"]
    log_path = os.path.join(logs_dir, f"{sequence_id}.log")
    existing_dat = find_trf_data_file(fasta_path=fasta_path, raw_dir=raw_dir, config=config)

    if not overwrite and existing_dat and os.path.getsize(existing_dat) > 0:
        repeats = parse_trf_dat(dat_path=existing_dat, metadata=metadata)
        return {"metadata": metadata, "dat_path": existing_dat, "log_path": log_path, "repeats": repeats, "status": "existing"}

    command = build_trf_command(binary=binary, fasta_path=fasta_path, config=config)

    async with semaphore:
        with open(log_path, "wb") as log_handle:
            process = await asyncio.create_subprocess_exec(*command, cwd=raw_dir, stdout=log_handle, stderr=log_handle)
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"TRF timed out for {sequence_id} after {timeout} seconds")

    dat_path = find_trf_data_file(fasta_path=fasta_path, raw_dir=raw_dir, config=config)

    if dat_path:
        repeats = parse_trf_dat(dat_path=dat_path, metadata=metadata)
        if process.returncode != 0:
            logging.debug("TRF returned legacy exit code %s for %s, but the .dat file was created successfully", process.returncode, sequence_id)
        return {"metadata": metadata, "dat_path": dat_path, "log_path": log_path, "repeats": repeats, "status": "completed"}

    with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
        log_text = handle.read()

    if "Done" in log_text:
        logging.info("TRF completed for %s without a .dat file; treating as zero repeats", sequence_id)
        return {"metadata": metadata, "dat_path": "", "log_path": log_path, "repeats": [], "status": "completed_no_repeats"}

    raise RuntimeError(f"TRF did not create a .dat file for {sequence_id} (exit code {process.returncode}). See {log_path}")


def write_consensus_fasta(**kwargs):
    repeats_dataframe = kwargs.get("repeats_dataframe")
    output_path = kwargs.get("output_path")

    if repeats_dataframe is None or repeats_dataframe.empty:
        return None

    records = []
    for _, row in repeats_dataframe.iterrows():
        consensus = str(row["Consensus"]).replace("-", "").strip()
        if not consensus:
            continue
        record_id = f"{row['Sequence ID']}__repeat_{int(row['Repeat number'])}"
        description = f"indices={int(row['Start'])}-{int(row['End'])} period={int(row['Period Size'])} copies={row['Copy Number']}"
        records.append(SeqRecord(Seq(consensus), id=record_id, description=description))

    if not records:
        return None

    SeqIO.write(records, output_path, "fasta")
    return output_path


async def run_trf_analysis(**kwargs):
    results_dir = kwargs.get("results_dir", ".")
    output_dir = kwargs.get("output_dir", "trf_analysis")
    genbank_files_dataframe = kwargs.get("genbank_files_dataframe")
    config = kwargs.get("config", {})
    overwrite = bool(config.get("overwrite", False))
    concurrency = max(1, int(config.get("concurrency", 4)))

    binary_name = str(config.get("binary", "trf"))
    binary = shutil.which(binary_name)
    if binary is None:
        raise FileNotFoundError(f"TRF executable not found in PATH: {binary_name}")

    os.makedirs(output_dir, exist_ok=True, mode=0o755)
    raw_dir = os.path.join(output_dir, "raw")
    logs_dir = os.path.join(output_dir, "logs")
    os.makedirs(raw_dir, exist_ok=True, mode=0o755)
    os.makedirs(logs_dir, exist_ok=True, mode=0o755)

    fasta_manifest = await export_rotated_genome_fastas(
        genbank_files_dataframe=genbank_files_dataframe,
        results_dir=results_dir,
        output_dir=output_dir,
        concurrency=concurrency,
        overwrite=overwrite,
    )

    if fasta_manifest.empty:
        return {
            "fasta_manifest": fasta_manifest,
            "summary_dataframe": pd.DataFrame(columns=TRF_SUMMARY_COLUMNS),
            "repeats_dataframe": pd.DataFrame(columns=TRF_REPEAT_COLUMNS),
            "summary_table": None,
            "repeats_table": None,
            "consensus_fasta": None,
        }

    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        run_trf_job(
            metadata=row.to_dict(), raw_dir=raw_dir, logs_dir=logs_dir, binary=binary,
            config=config, semaphore=semaphore, overwrite=overwrite,
        )
        for _, row in fasta_manifest.iterrows()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    summary_records = []
    repeat_records = []
    parameter_text = " ".join(str(value) for value in trf_parameter_values(config=config))

    for metadata, result in zip(fasta_manifest.to_dict("records"), results):
        if isinstance(result, Exception):
            logging.error("TRF failed for %s: %s", metadata["Sequence ID"], result)
            summary_records.append({
                **{key: metadata[key] for key in TRF_SUMMARY_COLUMNS if key in metadata},
                "Repeats found": pd.NA,
                "TRF parameters": parameter_text,
                "TRF data file": "",
                "TRF log file": os.path.join(logs_dir, f"{metadata['Sequence ID']}.log"),
            })
            continue

        repeats = result["repeats"]
        repeat_records.extend(repeats)
        summary_records.append({
            "Project name": metadata["Project name"],
            "Seed order": metadata["Seed order"],
            "Seed Input": metadata["Seed Input"],
            "K-mer": metadata["K-mer"],
            "Assembly copy": metadata["Assembly copy"],
            "GenBank file": metadata["GenBank file"],
            "Record ID": metadata["Record ID"],
            "Record length": metadata["Record length"],
            "Sequence ID": metadata["Sequence ID"],
            "FASTA file": metadata["FASTA file"],
            "Repeats found": len(repeats),
            "TRF parameters": parameter_text,
            "TRF data file": result["dat_path"],
            "TRF log file": result["log_path"],
        })

    summary_dataframe = pd.DataFrame(summary_records, columns=TRF_SUMMARY_COLUMNS)
    repeats_dataframe = pd.DataFrame(repeat_records, columns=TRF_REPEAT_COLUMNS)

    if not summary_dataframe.empty:
        summary_dataframe = summary_dataframe.sort_values(["Project name", "Seed order", "K-mer", "Assembly copy"]).reset_index(drop=True)
    if not repeats_dataframe.empty:
        repeats_dataframe = repeats_dataframe.sort_values(["Project name", "Seed order", "K-mer", "Assembly copy", "Repeat number"]).reset_index(drop=True)

    summary_table = os.path.join(output_dir, "trf_summary.tsv")
    repeats_table = os.path.join(output_dir, "trf_repeats.tsv")
    summary_dataframe.to_csv(summary_table, sep="\t", index=False)
    repeats_dataframe.to_csv(repeats_table, sep="\t", index=False)

    consensus_fasta = write_consensus_fasta(
        repeats_dataframe=repeats_dataframe,
        output_path=os.path.join(output_dir, "trf_consensus.fasta"),
    )

    logging.info("TRF analysis completed for %d assemblies, with %d repeats", len(summary_dataframe), len(repeats_dataframe))
    return {
        "fasta_manifest": fasta_manifest,
        "summary_dataframe": summary_dataframe,
        "repeats_dataframe": repeats_dataframe,
        "summary_table": summary_table,
        "repeats_table": repeats_table,
        "consensus_fasta": consensus_fasta,
    }
