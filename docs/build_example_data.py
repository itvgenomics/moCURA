#!/usr/bin/env python3
"""Build docs/assets/example_data.js from an OrganPipe results directory.

The interactive guide (docs/index.html) uses real values from the example
dataset: the genome map, the coverage track and the read-recruitment
histogram of every rotated assembly. This script reads them from the same
files moCURA reads and writes a small JavaScript file the page loads.

Usage (from the repository root, inside mocura_env or the container):

    python docs/build_example_data.py --results-dir data --output docs/assets/example_data.js
"""

import argparse
import json
import logging
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from Bio import SeqIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from moCURA.standardization.standardized_gene_name import standardized_gene_name  # noqa: E402

WINDOW = 50
ID_BINS = [90 + 0.5 * i for i in range(21)]
NAME_RE = re.compile(r"^(?P<prefix>[A-Za-z]+)_\d+_(?P<sample>[^_]+)_(?P<order>\d+)-(?P<seed>.+)_(?P<kmer>\d+)_(?P<copy>\d+)$")


def parse_name(**kwargs):
    match = NAME_RE.match(kwargs.get("name"))
    return match.groupdict() if match else None


def feature_type(**kwargs):
    return {"CDS": "p", "rRNA": "r", "tRNA": "t", "rep_origin": "o"}.get(kwargs.get("kind"))


def read_genes(**kwargs):
    record = next(SeqIO.parse(str(kwargs.get("path")), "genbank"))
    genes = []
    for feature in record.features:
        kind = feature_type(kind=feature.type)
        if not kind:
            continue
        qualifiers = feature.qualifiers
        name = (qualifiers.get("gene") or qualifiers.get("product") or ["?"])[0]
        name = re.sub(r"\(.*\)$", "", name)
        start, end = int(feature.location.start), int(feature.location.end) - 1
        genes.append([name, kind, start, end, 1 if (feature.location.strand or 1) > 0 else -1])
    return len(record.seq), genes


def read_coverage(**kwargs):
    path, length = kwargs.get("path"), kwargs.get("length")
    depth = [0] * length
    with open(path) as handle:
        for line in handle:
            parts = line.split("\t")
            if len(parts) >= 3:
                position = int(parts[1]) - 1
                if 0 <= position < length:
                    depth[position] = int(parts[2])
    windows = [round(sum(depth[i:i + WINDOW]) / len(depth[i:i + WINDOW])) for i in range(0, length, WINDOW)]
    stats = {
        "mean": round(sum(depth) / length, 1),
        "median": statistics.median(depth),
        "min": min(depth),
        "max": max(depth),
        "low10": sum(1 for d in depth if d < 10),
    }
    return windows, stats


def read_recruitment(**kwargs):
    path, length = kwargs.get("path"), kwargs.get("length")
    counts, covered, reads = [0] * len(ID_BINS), bytearray(length), 0
    with open(path) as handle:
        for line in handle:
            parts = line.split("\t")
            if len(parts) < 10:
                continue
            reads += 1
            identity = float(parts[2])
            index = 0 if identity < 90 else min(len(ID_BINS) - 1, int((identity - 90) * 2))
            counts[index] += 1
            a, b = sorted((int(parts[8]), int(parts[9])))
            covered[max(0, a - 1):min(length, b)] = b"\x01" * (min(length, b) - max(0, a - 1))
    return counts, reads, round(100 * sum(covered) / length, 2)


def read_novoplasty_contigs(**kwargs):
    sample_dir, seed, kmer = kwargs.get("sample_dir"), kwargs.get("seed"), kwargs.get("kmer")
    for log in (sample_dir / "novoplasty" / seed / f"kmer{kmer}").glob("log_*.txt"):
        match = re.search(r"Total contigs\s+:\s+(\d+)", log.read_text(errors="replace"))
        if match:
            return int(match.group(1))
    return None


def read_pilon(**kwargs):
    pilon_dir = kwargs.get("pilon_dir")
    log = pilon_dir / "pilon.log"
    if not log.exists():
        return None, []
    text = log.read_text(errors="replace")
    confirmed = re.search(r"Confirmed \d+ of \d+ bases \(([\d.]+)%\)", text)
    breaks = [(int(a), int(b)) for a, b in re.findall(r"fix break: \S+:(\d+)-(\d+) .*NoSolution", text)]
    return (float(confirmed.group(1)) if confirmed else None), breaks


def a_to_b_shift(**kwargs):
    """Cumulative indel offsets from a Pilon .changes file, as (A position, shift after it)."""
    path = kwargs.get("path")
    anchors = []
    if not path.exists():
        return anchors
    shift = 0
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        a_pos = int(re.findall(r":(\d+)", parts[0])[-1])
        ref, alt = parts[2], parts[3]
        ref_len = 0 if ref == "." else len(ref)
        alt_len = 0 if alt == "." else len(alt)
        shift += alt_len - ref_len
        anchors.append((a_pos, shift))
    return anchors


def rotation_offset(**kwargs):
    path = kwargs.get("path")
    if not path.exists():
        return None
    record = next(SeqIO.parse(str(path), "genbank"))
    for feature in record.features:
        if feature.type == "rRNA" and "rrnS" in str(feature.qualifiers.get("product", "")):
            return int(feature.location.start)
    return None


def build_one(**kwargs):
    rotated_gb = kwargs.get("rotated_gb")
    asm = rotated_gb.name[: -len(".rotated.gb")]
    meta = parse_name(name=asm)
    if not meta:
        return None
    sample_dir = rotated_gb.parents[1]
    seed_dir = f"{meta['order']}-{meta['seed']}"
    images = sample_dir / "images" / f"{seed_dir}_kmer{meta['kmer']}"
    depth_path = images / f"{asm}.rotated.depth"
    blast_path = images / f"{asm}.rotated.blastn.out"
    if not depth_path.exists() or not blast_path.exists():
        logging.warning("Skipping %s: missing depth or BLAST file", asm)
        return None
    length, genes = read_genes(path=rotated_gb)
    coverage, cov_stats = read_coverage(path=depth_path, length=length)
    hist, reads, target = read_recruitment(path=blast_path, length=length)
    pilon_dir = sample_dir / "pilon" / asm
    confirmed, breaks_a = read_pilon(pilon_dir=pilon_dir)
    anchors = a_to_b_shift(path=pilon_dir / f"{asm}.changes")
    offset = rotation_offset(path=sample_dir / "genbanks" / f"{asm}.gb")
    breaks_c = []
    if offset is not None:
        for a_start, a_end in breaks_a:
            coords = []
            for a in (a_start, a_end):
                shift = 0
                for a_pos, s in anchors:
                    if a_pos <= a:
                        shift = s
                coords.append(((a + shift - 1 - offset) % length) + 1)
            if coords[0] <= coords[1]:
                breaks_c.append(coords)
    return {
        "id": asm,
        "sample": meta["sample"],
        "seed": standardized_gene_name(value=meta["seed"]),
        "kmer": int(meta["kmer"]),
        "copy": int(meta["copy"]),
        "prefix": meta["prefix"],
        "length": length,
        "contigs": read_novoplasty_contigs(sample_dir=sample_dir, seed=seed_dir, kmer=meta["kmer"]),
        "pilon": confirmed,
        "genes": genes,
        "cov": coverage,
        "covStats": cov_stats,
        "breaks": breaks_c,
        "idHist": hist,
        "reads": reads,
        "target": target,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    rotated = sorted(p for p in args.results_dir.glob("*/genbanks/*.rotated.gb"))
    logging.info("Found %d rotated GenBank files", len(rotated))
    with ThreadPoolExecutor(max_workers=args.threads) as pool:
        records = [r for r in pool.map(lambda p: build_one(rotated_gb=p), rotated) if r]
    records.sort(key=lambda r: (r["sample"], r["seed"], r["kmer"], r["copy"]))

    payload = {"window": WINDOW, "idBins": ID_BINS, "assemblies": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("window.MOCURA_EXAMPLE = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    logging.info("Wrote %d assemblies to %s (%.0f kB)", len(records), args.output, args.output.stat().st_size / 1024)


if __name__ == "__main__":
    main()
