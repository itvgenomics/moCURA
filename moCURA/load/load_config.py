import copy
import logging
import os

import yaml


DEFAULT_CONFIG = {
    "pipeline": {
        "threads": 20,
        "only_circularized": True,
    },
    "figures": {
        "format": "png",
        "dpi": 300,
        "style": {
            "annotate": True,
            "bar_linewidth": 10,
            "x_tick_pad": 7.5,
            "x_label_pad": 15,
            "plot_height_scale": 1.50,
            "panel_title_fontsize": 24,
            "panel_letter_fontsize": 17,
            "legend_fontsize": 13,
            "legend_title_fontsize": 15,
            "colorbar_label_fontsize": 11,
            "colorbar_tick_fontsize": 10,
            "project_label_fontsize": 9,
            "axis_label_fontsize": 11,
        },
    },
    "plots": {
        "novoplasty_summary": {"enabled": True},
        "genome_size_heatmap": {
            "enabled": True,
            "cmap": "viridis",
            "mismatch_alpha": 0.25,
        },
        "pilon_heatmap": {
            "enabled": True,
            "mismatch_alpha": 0.25,
            "metrics_per_row": 2,
            "gene_rows_per_metric": 2,
        },
        "pilon_before_after_heatmap": {
            "enabled": True,
            "mismatch_alpha": 0.25,
            "metrics_per_row": 2,
            "gene_rows_per_metric": 2,
            "stage_bar_offset": 0.030,
        },
        "marker_length_heatmaps": {
            "enabled": True,
            "plots_per_row": 4,
            "cmap": "viridis",
            "title_fontsize": 24,
            "panel_letter_fontsize": 18,
            "legend_fontsize": 14,
            "legend_title_fontsize": 16,
            "x_tick_size": 9,
            "y_tick_size": 10,
            "annotation_fontsize": 8,
            "colorbar_tick_fontsize": 10,
        },
    },
    "genbank": {
        "enabled": True,
        "folder_name": "genbanks",
        "suffix": ".rotated.gb",
        "feature_types": [
            "CDS",
            "rRNA",
            "tRNA",
            "D-loop",
            "misc_feature",
            "regulatory",
        ],
        "include_unknown_markers": False,
        "marker_order": [],
    },
    "trf": {
        "enabled": True,
        "output_folder": "trf_analysis",
        "binary": "trf",
        "overwrite": False,
        "concurrency": 4,
        "timeout": 3600,
        "match": 2,
        "mismatch": 7,
        "delta": 7,
        "match_probability": 80,
        "indel_probability": 10,
        "min_score": 50,
        "max_period": 500,
        "suppress_html": True,
        "flanking": False,
        "masked": False,
        "no_redundancy": False,
        "max_tr_length_millions": None,
    },
    "organpipe": {
        "organpipe_dir": None,
    },
    "mitos2_completeness": {
        "enabled": True,
        "output_folder": "mitos2_completeness",
    },
    "coverage_profile": {
        "enabled": True,
        "window_size": 50,
        "low_depth_threshold": 10,
        "low_coverage_alert_percent": 5,
        "output_folder": "coverage_profile",
    },
    "pilon_changes": {
        "enabled": True,
        "output_folder": "pilon_changes",
    },
    "read_recruitment": {
        "enabled": True,
        "identity_threshold": 98,
        "output_folder": "read_recruitment",
    },
    "nhmmer_alerts": {
        "enabled": True,
        "max_evalue": 0.001,
        "output_folder": "nhmmer_alerts",
    },
    "read_qc": {
        "enabled": True,
        "output_folder": "read_qc",
    },
    "provenance": {
        "enabled": True,
        "output_folder": "provenance",
    },
    "assembly_alerts": {
        "enabled": True,
        "output_folder": "assembly_alerts",
    },
    "junction_validation": {
        "enabled": True,
        "output_folder": "junction_validation",
        "min_flank": 20,
        "min_mapping_quality": 20,
        "supported_min_spanning_reads": 10,
        "weak_min_spanning_reads": 3,
        "weak_min_flanking_pairs": 3,
        "max_insert_size": 1000,
        "bam_template": None,
    },
    "annotation_integrity": {
        "enabled": True,
        "output_folder": "annotation_integrity",
        "genetic_code": None,
        "length_deviation_percent": 10,
    },
    "assembly_concordance": {
        "enabled": True,
        "output_folder": "assembly_concordance",
        "group_identity_threshold": 99.5,
        "group_min_coverage": 95,
        "max_sequences": 150,
        "overwrite": False,
        "mafft": {},
    },
    "sequence_composition": {
        "enabled": True,
        "output_folder": "sequence_composition",
    },
    "assembly_score": {
        "enabled": True,
        "output_folder": "assembly_score",
        "length_tolerance_percent": 5,
        "na_value": 0.5,
        "weights": {
            "completeness": 3,
            "integrity": 2,
            "junction": 2,
            "coverage": 1,
            "pilon": 1,
            "concordance": 2,
            "length": 1,
        },
    },
}


def deep_merge(**kwargs):
    """Recursively merge a user dictionary into a base dictionary."""

    base = copy.deepcopy(kwargs.get("base", {}))
    updates = kwargs.get("updates", {})

    if not isinstance(updates, dict):
        return copy.deepcopy(updates)

    for key, value in updates.items():
        if (key in base and isinstance(base[key], dict) and isinstance(value, dict)):
            base[key] = deep_merge(base=base[key], updates=value)
        else:
            base[key] = copy.deepcopy(value)

    return base

def load_config(**kwargs):
    config_file = kwargs.get("config_file")
    config = copy.deepcopy(DEFAULT_CONFIG)

    if config_file is None:
        return config

    config_file = os.path.abspath(os.path.expanduser(str(config_file)))

    if not os.path.isfile(config_file):
        logging.warning(f"Configuration file not found, using defaults: {config_file}")
        return config

    with open(config_file, "r", encoding="utf-8") as config_handle:
        loaded_config = yaml.safe_load(config_handle) or {}

    if not isinstance(loaded_config, dict):
        raise ValueError("The YAML configuration root must be a dictionary")

    config = deep_merge(base=config,    updates=loaded_config)
    logging.info(f"Configuration loaded: {config_file}")

    return config

def config_section(**kwargs):
    """Return a nested configuration dictionary without mutating it."""

    config = kwargs.get("config", {})
    keys = kwargs.get("keys", [])
    default = kwargs.get("default", {})

    current = config

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return copy.deepcopy(default)
        current = current[key]

    return copy.deepcopy(current)
