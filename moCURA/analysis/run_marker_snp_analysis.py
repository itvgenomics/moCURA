import asyncio
import csv
import logging
import os
import shlex
import shutil

from ..export.export_marker_fastas import export_marker_fastas
from ..plots.plot_marker_snp_matrix import plot_marker_snp_matrix


def command_to_text(**kwargs):
    """Return a shell-readable external command."""

    command = kwargs.get(
        "command",
        [],
    )

    return " ".join(
        shlex.quote(
            str(argument)
        )
        for argument in command
    )


def require_executable(**kwargs):
    """Resolve a required executable."""

    executable = str(
        kwargs.get(
            "executable",
            "",
        )
    )

    resolved = shutil.which(
        executable
    )

    if resolved is None:
        raise FileNotFoundError(
            "Required executable was not found in PATH: "
            f"{executable}"
        )

    return resolved


def read_log_tail(**kwargs):
    """Read the final lines of an external command log."""

    log_path = kwargs.get(
        "log_path"
    )

    number_of_lines = max(
        1,
        int(
            kwargs.get(
                "number_of_lines",
                40,
            )
        ),
    )

    if (
        not log_path
        or not os.path.isfile(
            log_path
        )
    ):
        return ""

    with open(
        log_path,
        "r",
        encoding="utf-8",
        errors="replace",
    ) as input_handle:
        lines = input_handle.readlines()

    return "".join(
        lines[
            -number_of_lines:
        ]
    ).strip()


async def run_subprocess(**kwargs):
    """Run one external command asynchronously."""

    command = kwargs.get(
        "command",
        [],
    )

    stdout_path = kwargs.get(
        "stdout_path"
    )

    stderr_path = kwargs.get(
        "stderr_path"
    )

    semaphore = kwargs.get(
        "semaphore"
    )

    if semaphore is None:
        semaphore = asyncio.Semaphore(
            1
        )

    async with semaphore:
        stderr_directory = os.path.dirname(
            stderr_path
        )

        if stderr_directory:
            os.makedirs(
                stderr_directory,
                exist_ok=True,
            )

        stdout_handle = (
            open(
                stdout_path,
                "wb",
            )
            if stdout_path
            else asyncio.subprocess.DEVNULL
        )

        try:
            with open(
                stderr_path,
                "wb",
            ) as stderr_handle:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                )

                return_code = await process.wait()

        finally:
            if hasattr(
                stdout_handle,
                "close",
            ):
                stdout_handle.close()

        if return_code != 0:
            log_tail = read_log_tail(
                log_path=stderr_path,
                number_of_lines=40,
            )

            details = (
                f"\nLast log lines:\n{log_tail}"
                if log_tail
                else ""
            )

            raise RuntimeError(
                "Command failed with exit code "
                f"{return_code}: "
                + command_to_text(
                    command=command
                )
                + f". See log: {stderr_path}"
                + details
            )

        return {
            "command": command,
            "return_code": return_code,
            "stdout_path": stdout_path,
            "stderr_path": stderr_path,
        }


def build_mafft_mode_args(**kwargs):
    """Translate readable MAFFT modes into valid arguments."""

    mode = str(
        kwargs.get(
            "mode",
            "auto",
        )
    ).lower()

    modes = {
        "auto": [
            "--auto",
        ],
        "linsi": [
            "--localpair",
            "--maxiterate",
            "1000",
        ],
        "ginsi": [
            "--globalpair",
            "--maxiterate",
            "1000",
        ],
        "einsi": [
            "--genafpair",
            "--maxiterate",
            "1000",
        ],
        "fftns1": [
            "--retree",
            "1",
        ],
        "fftns2": [
            "--retree",
            "2",
        ],
        "none": [],
        "": [],
    }

    if mode not in modes:
        raise ValueError(
            "Unsupported MAFFT mode: "
            f"{mode}. Supported values: "
            + ", ".join(
                sorted(
                    key
                    for key in modes
                    if key
                )
            )
        )

    return modes[
        mode
    ]


async def run_mafft_job(**kwargs):
    """Align one all-K-mer marker FASTA."""

    job = kwargs.get(
        "job",
        {},
    )

    mafft_binary = kwargs.get(
        "mafft_binary",
        "mafft",
    )

    mafft_config = kwargs.get(
        "mafft_config",
        {},
    )

    output_root = kwargs.get(
        "output_root",
        "marker_snp_analysis",
    )

    semaphore = kwargs.get(
        "semaphore"
    )

    overwrite = bool(
        kwargs.get(
            "overwrite",
            False,
        )
    )

    marker_slug = job[
        "marker_slug"
    ]

    alignment_directory = os.path.join(
        output_root,
        "alignments",
        marker_slug,
    )

    log_directory = os.path.join(
        output_root,
        "logs",
        "mafft",
    )

    os.makedirs(
        alignment_directory,
        exist_ok=True,
    )

    os.makedirs(
        log_directory,
        exist_ok=True,
    )

    alignment_path = os.path.join(
        alignment_directory,
        (
            f"{marker_slug}_"
            "all_kmers.aligned.fasta"
        ),
    )

    log_path = os.path.join(
        log_directory,
        (
            f"{marker_slug}_"
            "all_kmers.log"
        ),
    )

    if (
        not overwrite
        and os.path.isfile(
            alignment_path
        )
        and os.path.getsize(
            alignment_path
        )
        > 0
    ):
        return {
            **job,
            "alignment_path": alignment_path,
            "mafft_status": "existing",
            "mafft_log": log_path,
        }

    command = [
        mafft_binary,
        *build_mafft_mode_args(
            mode=mafft_config.get(
                "mode",
                "auto",
            )
        ),
        "--thread",
        str(
            max(
                1,
                int(
                    mafft_config.get(
                        "threads_per_job",
                        2,
                    )
                ),
            )
        ),
        *[
            str(argument)
            for argument in mafft_config.get(
                "extra_args",
                [],
            )
        ],
        job[
            "fasta_path"
        ],
    ]

    await run_subprocess(
        command=command,
        stdout_path=alignment_path,
        stderr_path=log_path,
        semaphore=semaphore,
    )

    return {
        **job,
        "alignment_path": alignment_path,
        "mafft_status": "completed",
        "mafft_log": log_path,
    }


async def plot_snp_matrix_job(**kwargs):
    """Generate one SNP matrix without blocking the event loop."""

    job = kwargs.get(
        "job",
        {},
    )

    output_directory = kwargs.get(
        "output_directory"
    )

    matrix_config = kwargs.get(
        "matrix_config",
        {},
    )

    semaphore = kwargs.get(
        "semaphore"
    )

    if semaphore is None:
        semaphore = asyncio.Semaphore(
            1
        )

    async with semaphore:
        return await asyncio.to_thread(
            plot_marker_snp_matrix,
            alignment_path=job[
                "alignment_path"
            ],
            output_dir=output_directory,
            marker=job[
                "marker"
            ],
            sequence_metadata=job.get(
                "sequence_metadata",
                [],
            ),
            labels_path=job.get(
                "labels_path"
            ),
            config=matrix_config,
        )


def write_analysis_manifest(**kwargs):
    """Write results for generated and skipped marker plots."""

    aligned_jobs = kwargs.get(
        "aligned_jobs",
        [],
    )

    matrix_results = kwargs.get(
        "matrix_results",
        [],
    )

    output_root = kwargs.get(
        "output_root",
        "marker_snp_analysis",
    )

    matrix_by_marker = {
        result.get(
            "marker"
        ): result
        for result in matrix_results
        if isinstance(
            result,
            dict,
        )
    }

    manifest_directory = os.path.join(
        output_root,
        "manifests",
    )

    os.makedirs(
        manifest_directory,
        exist_ok=True,
    )

    manifest_path = os.path.join(
        manifest_directory,
        "marker_snp_matrix.tsv",
    )

    fieldnames = [
        "marker",
        "sequence_count",
        "project_count",
        "kmer_values",
        "alignment_path",
        "mafft_status",
        "snp_count",
        "plot_status",
        "reason",
        "image_path",
        "table_path",
        "reference_sequence_id",
    ]

    with open(
        manifest_path,
        "w",
        encoding="utf-8",
        newline="",
    ) as output_handle:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=fieldnames,
            delimiter="\t",
        )

        writer.writeheader()

        for job in aligned_jobs:
            matrix_result = matrix_by_marker.get(
                job[
                    "marker"
                ],
                {},
            )

            writer.writerow(
                {
                    "marker": job.get(
                        "marker",
                        "",
                    ),
                    "sequence_count": job.get(
                        "sequence_count",
                        "",
                    ),
                    "project_count": job.get(
                        "project_count",
                        "",
                    ),
                    "kmer_values": ",".join(
                        str(value)
                        for value in job.get(
                            "kmer_values",
                            [],
                        )
                    ),
                    "alignment_path": job.get(
                        "alignment_path",
                        "",
                    ),
                    "mafft_status": job.get(
                        "mafft_status",
                        "",
                    ),
                    "snp_count": matrix_result.get(
                        "snp_count",
                        0,
                    ),
                    "plot_status": (
                        "generated"
                        if matrix_result.get(
                            "generated",
                            False,
                        )
                        else "skipped"
                    ),
                    "reason": matrix_result.get(
                        "reason",
                        "",
                    ),
                    "image_path": matrix_result.get(
                        "image_path",
                        "",
                    )
                    or "",
                    "table_path": matrix_result.get(
                        "table_path",
                        "",
                    )
                    or "",
                    "reference_sequence_id": (
                        matrix_result.get(
                            "reference_sequence_id",
                            "",
                        )
                    ),
                }
            )

    return manifest_path


async def run_marker_snp_analysis(**kwargs):
    """
    Export markers, align all K-mers with MAFFT, and plot true SNP matrices.

    Images are generated only for markers containing at least one true SNP.
    All marker images are written directly into the same output folder.
    """

    results_dir = kwargs.get(
        "results_dir",
        ".",
    )

    output_dir = kwargs.get(
        "output_dir",
        "marker_snp_analysis",
    )

    genbank_files_dataframe = kwargs.get(
        "genbank_files_dataframe"
    )

    marker_dataframe = kwargs.get(
        "marker_dataframe"
    )

    config = kwargs.get(
        "config",
        {},
    )

    overwrite = bool(
        config.get(
            "overwrite",
            False,
        )
    )

    minimum_sequences = max(
        2,
        int(
            config.get(
                "minimum_sequences",
                2,
            )
        ),
    )

    minimum_projects = max(
        1,
        int(
            config.get(
                "minimum_projects",
                2,
            )
        ),
    )

    extraction_config = config.get(
        "extraction",
        {},
    )

    mafft_config = config.get(
        "mafft",
        {},
    )

    matrix_config = config.get(
        "snp_matrix",
        {},
    )

    export_result = await export_marker_fastas(
        results_dir=results_dir,
        output_dir=output_dir,
        genbank_files_dataframe=genbank_files_dataframe,
        marker_dataframe=marker_dataframe,
        concurrency=int(
            extraction_config.get(
                "concurrency",
                4,
            )
        ),
        feature_types=extraction_config.get(
            "feature_types",
            [
                "CDS",
                "rRNA",
                "tRNA",
                "misc_feature",
                "regulatory",
            ],
        ),
        infer_control_region=bool(
            extraction_config.get(
                "infer_control_region",
                True,
            )
        ),
        representative_strategy=extraction_config.get(
            "representative_strategy",
            "matching_seed_then_modal",
        ),
        preferred_seed_inputs=extraction_config.get(
            "preferred_seed_inputs",
            [],
        ),
        sequence_id_order=extraction_config.get(
            "sequence_id_order",
            "project_then_kmer",
        ),
        project_labels=matrix_config.get(
            "project_labels",
            {},
        ),
        label_template=matrix_config.get(
            "label_template",
            "{project_label} | K-mer {kmer}",
        ),
        minimum_sequences=minimum_sequences,
        minimum_projects=minimum_projects,
    )

    fasta_jobs = [
        job
        for job in export_result[
            "jobs"
        ]
        if job[
            "ready"
        ]
    ]

    if not fasta_jobs:
        logging.warning(
            "No marker FASTAs contained enough projects and sequences"
        )

        return {
            **export_result,
            "alignments": [],
            "matrix_results": [],
            "images": [],
            "analysis_manifest": None,
        }

    mafft_binary = require_executable(
        executable=mafft_config.get(
            "binary",
            "mafft",
        )
    )

    mafft_semaphore = asyncio.Semaphore(
        max(
            1,
            int(
                mafft_config.get(
                    "concurrency",
                    4,
                )
            ),
        )
    )

    mafft_results = await asyncio.gather(
        *[
            run_mafft_job(
                job=job,
                mafft_binary=mafft_binary,
                mafft_config=mafft_config,
                output_root=output_dir,
                semaphore=mafft_semaphore,
                overwrite=overwrite,
            )
            for job in fasta_jobs
        ],
        return_exceptions=True,
    )

    aligned_jobs = []

    for job, result in zip(
        fasta_jobs,
        mafft_results,
    ):
        if isinstance(
            result,
            Exception,
        ):
            logging.error(
                "MAFFT failed for %s: %s",
                job[
                    "marker"
                ],
                result,
            )

            continue

        aligned_jobs.append(
            result
        )

    matrix_output_directory = os.path.join(
        output_dir,
        str(
            matrix_config.get(
                "output_folder",
                "snp_matrices",
            )
        ),
    )

    os.makedirs(
        matrix_output_directory,
        exist_ok=True,
    )

    matrix_semaphore = asyncio.Semaphore(
        max(
            1,
            int(
                matrix_config.get(
                    "concurrency",
                    2,
                )
            ),
        )
    )

    matrix_results_raw = await asyncio.gather(
        *[
            plot_snp_matrix_job(
                job=job,
                output_directory=matrix_output_directory,
                matrix_config=matrix_config,
                semaphore=matrix_semaphore,
            )
            for job in aligned_jobs
        ],
        return_exceptions=True,
    )

    matrix_results = []

    for job, result in zip(
        aligned_jobs,
        matrix_results_raw,
    ):
        if isinstance(
            result,
            Exception,
        ):
            logging.error(
                "SNP matrix failed for %s: %s",
                job[
                    "marker"
                ],
                result,
            )

            matrix_results.append(
                {
                    "marker": job[
                        "marker"
                    ],
                    "generated": False,
                    "reason": str(
                        result
                    ),
                    "snp_count": 0,
                    "image_path": None,
                    "table_path": None,
                }
            )

            continue

        # The HTML report reads the alignment to flag incomplete marker sequences.
        matrix_results.append(
            {
                **result,
                "alignment_path": job.get(
                    "alignment_path"
                ),
            }
        )

    generated_images = [
        result[
            "image_path"
        ]
        for result in matrix_results
        if (
            result.get(
                "generated",
                False,
            )
            and result.get(
                "image_path"
            )
        )
    ]

    analysis_manifest = write_analysis_manifest(
        aligned_jobs=aligned_jobs,
        matrix_results=matrix_results,
        output_root=output_dir,
    )

    logging.info(
        (
            "Marker SNP analysis completed: "
            "%d alignments, %d static SNP images, "
            "%d markers without true SNPs"
        ),
        len(
            aligned_jobs
        ),
        len(
            generated_images
        ),
        sum(
            1
            for result in matrix_results
            if result.get(
                "reason"
            )
            == "no_true_snp"
        ),
    )

    return {
        **export_result,
        "alignments": aligned_jobs,
        "matrix_results": matrix_results,
        "images": generated_images,
        "analysis_manifest": analysis_manifest,
        "image_directory": matrix_output_directory,
    }
