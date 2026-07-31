import re

GENE_NAMES = {
    "ATP6": "ATP6",
    "ATP_synthase_F0_subunit_6": "ATP6",
    "ATP8": "ATP8",
    "ATP_synthase_F0_subunit_8": "ATP8",
    "ND1": "ND1",
    "NADH_dehydrogenase_subunit_1": "ND1",
    "ND2": "ND2",
    "NADH_dehydrogenase_subunit_2": "ND2",
    "ND3": "ND3",
    "NADH_dehydrogenase_subunit_3": "ND3",
    "ND4": "ND4",
    "NADH_dehydrogenase_subunit_4": "ND4",
    "ND4L": "ND4L",
    "NADH_dehydrogenase_subunit_4L": "ND4L",
    "ND5": "ND5",
    "NADH_dehydrogenase_subunit_5": "ND5",
    "ND6": "ND6",
    "NADH_dehydrogenase_subunit_6": "ND6",
    "CYTB": "CYTB",
    "cytochrome_b": "CYTB",
    "COB": "CYTB",
    "COI": "COI",
    "CO1": "COI",
    "COX1": "COI",
    "cytochrome_c_oxidase_subunit_I": "COI",
    "COII": "COII",
    "CO2": "COII",
    "COX2": "COII",
    "cytochrome_c_oxidase_subunit_II": "COII",
    "COIII": "COIII",
    "CO3": "COIII",
    "COX3": "COIII",
    "cytochrome_c_oxidase_subunit_III": "COIII",
}

def normalize_gene_name(**kwargs):
    gene_name = kwargs.get("gene_name", None)
    
    filename = re.split(r"[\\/]", str(gene_name))[-1]
    filename = filename.rsplit(".", 1)[0]
    filename = re.sub(r"^\d+[-_. ]*", "", filename)

    return re.sub(r"[^A-Za-z0-9]", "", filename).upper()

GENE_ALIASES = {
    normalize_gene_name(
        gene_name=raw_name
    ): standard_name
    for raw_name, standard_name in GENE_NAMES.items()
}

def standardized_gene_name(**kwargs):
    value = kwargs.get("value")

    normalized = normalize_gene_name(gene_name=value)

    if normalized in GENE_ALIASES:
        return GENE_ALIASES[normalized]

    for raw_name, standard_name in GENE_NAMES.items():
        if normalize_gene_name(
            gene_name=raw_name
        ) in normalized:
            return standard_name

    return re.split(r"[\\/]", str(value))[-1]

