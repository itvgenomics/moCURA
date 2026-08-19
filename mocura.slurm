#!/usr/bin/env bash
#SBATCH --job-name=moCURA
#SBATCH --output=moCURA_%j.out
#SBATCH --error=moCURA_%j.err
#SBATCH --partition=op1_slurm
#SBATCH --nodes=1
#SBATCH --mem=8G
#SBATCH --cpus-per-task=12
#SBATCH --time=12:00:00
#SBATCH --mail-type=BEGIN,END,FAIL
#SBATCH --mail-user=<your-email@example.com>


SIF=/path/to/mocura.sif
RESULTS=/path/to/results
OUTPUT=/path/to/mocura_output
CONFIG=/path/to/config.yml
METADATA=/path/to/metadata.xlsx
THREADS=16

mkdir -p "${OUTPUT}"

singularity exec \
    --bind "${RESULTS}:/data/input" \
    --bind "${OUTPUT}:/data/output" \
    --bind "${CONFIG}:/config/config.yml" \
    --bind "${METADATA}:/config/metadata.xlsx" \
    "${SIF}" \
    python /opt/mocura/mocura.py \
    --results-dir /data/input \
    --output-dir /data/output \
    --config /config/config.yml \
    --metadata /config/metadata.xlsx \
    --threads "${THREADS}" \
    --only-circularized
