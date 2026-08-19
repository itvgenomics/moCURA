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

    # Remove any directory path and file extension, and remove leading numbers and punctuation
    filename = re.split(r"[\\/]", str(gene_name))[-1]
    filename = filename.rsplit(".", 1)[0]
    filename = re.sub(r"^\d+[-_. ]*", "", filename)

    # Remove any non-alphanumeric characters and convert to uppercase
    return re.sub(r"[^A-Za-z0-9]", "", filename).upper()

GENE_ALIASES = {
    # Create a mapping of normalized gene names to their standard names
    normalize_gene_name(gene_name=raw_name): standard_name
    for raw_name, standard_name in GENE_NAMES.items()
}

def standardized_gene_name(**kwargs):
    value = kwargs.get("value")

    # Normalize the gene name using the normalize_gene_name function
    normalized = normalize_gene_name(gene_name=value)

    # Check if the normalized gene name is in the GENE_ALIASES dictionary
    if normalized in GENE_ALIASES:
        return GENE_ALIASES[normalized]

    # If not found, check if the original gene name matches any of the raw names in GENE_NAMES
    for raw_name, standard_name in GENE_NAMES.items():
        if normalize_gene_name(gene_name=raw_name) in normalized:
            return standard_name

    # If no match is found, return the original value without any directory path
    return re.split(r"[\\/]", str(value))[-1]

