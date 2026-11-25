import re

from .plastid_marker_name import plastid_marker_name
from .standardized_gene_name import GENE_ALIASES, normalize_gene_name


AMINO_ACID_CODES = {
    "A": "Ala",
    "ALA": "Ala",
    "ALANINE": "Ala",
    "R": "Arg",
    "ARG": "Arg",
    "ARGININE": "Arg",
    "N": "Asn",
    "ASN": "Asn",
    "ASPARAGINE": "Asn",
    "D": "Asp",
    "ASP": "Asp",
    "ASPARTATE": "Asp",
    "ASPARTICACID": "Asp",
    "C": "Cys",
    "CYS": "Cys",
    "CYSTEINE": "Cys",
    "Q": "Gln",
    "GLN": "Gln",
    "GLUTAMINE": "Gln",
    "E": "Glu",
    "GLU": "Glu",
    "GLUTAMATE": "Glu",
    "GLUTAMICACID": "Glu",
    "G": "Gly",
    "GLY": "Gly",
    "GLYCINE": "Gly",
    "H": "His",
    "HIS": "His",
    "HISTIDINE": "His",
    "I": "Ile",
    "ILE": "Ile",
    "ISOLEUCINE": "Ile",
    "L": "Leu",
    "LEU": "Leu",
    "LEUCINE": "Leu",
    "K": "Lys",
    "LYS": "Lys",
    "LYSINE": "Lys",
    "M": "Met",
    "MET": "Met",
    "METHIONINE": "Met",
    "F": "Phe",
    "PHE": "Phe",
    "PHENYLALANINE": "Phe",
    "P": "Pro",
    "PRO": "Pro",
    "PROLINE": "Pro",
    "S": "Ser",
    "SER": "Ser",
    "SERINE": "Ser",
    "T": "Thr",
    "THR": "Thr",
    "THREONINE": "Thr",
    "W": "Trp",
    "TRP": "Trp",
    "TRYPTOPHAN": "Trp",
    "Y": "Tyr",
    "TYR": "Tyr",
    "TYROSINE": "Tyr",
    "V": "Val",
    "VAL": "Val",
    "VALINE": "Val",
}


def first_qualifier_value(**kwargs):
    """Return the first non-empty value from a GenBank qualifier."""

    qualifiers = kwargs.get("qualifiers", {})
    qualifier_name = kwargs.get("qualifier_name")
    values = qualifiers.get(qualifier_name, [])

    if isinstance(values, str):
        values = [values]

    for value in values:
        value = str(value).strip()
        if value:
            return value

    return ""


def normalize_marker_text(**kwargs):
    """Normalize marker text for tolerant alias comparisons."""

    value = kwargs.get("value", "")

    # Remove any directory path and file extension, and remove leading numbers and punctuation
    return re.sub(r"[^A-Za-z0-9]", "", str(value)).upper()


def standardize_protein_coding_marker(**kwargs):
    """Resolve common mitochondrial protein-coding gene aliases."""

    value = kwargs.get("value", "")
    normalized = normalize_gene_name(gene_name=value)
    compact_value = normalize_marker_text(value=value)

    if normalized in GENE_ALIASES:
        return GENE_ALIASES[normalized]

    if compact_value in {"NAD1", "NADH1"}:
        return "ND1"

    if compact_value in {"NAD2", "NADH2"}:
        return "ND2"

    if compact_value in {"NAD3", "NADH3"}:
        return "ND3"

    if compact_value in {"NAD4", "NADH4"}:
        return "ND4"

    if compact_value in {"NAD4L", "NADH4L"}:
        return "ND4L"

    if compact_value in {"NAD5", "NADH5"}:
        return "ND5"

    if compact_value in {"NAD6", "NADH6"}:
        return "ND6"

    nadh_match = re.search(
        r"(?:NADH|NAD)(?:DEHYDROGENASE)?(?:SUBUNIT)?(4L|[1-6])",
        compact_value,
    )

    if nadh_match:
        return f"ND{nadh_match.group(1)}".upper()

    for alias, standard_name in GENE_ALIASES.items():
        if alias and alias in normalized:
            return standard_name

    return None


def standardize_rrna_marker(**kwargs):
    """Resolve mitochondrial small and large ribosomal RNA names."""

    value = kwargs.get("value", "")
    normalized = normalize_marker_text(value=value)

    small_subunit_patterns = (
        "12S",
        "RRNS",
        "SRRNA",
        "SMALLSUBUNITRIBOSOMALRNA",
        "SMALLRIBOSOMALRNA",
    )
    large_subunit_patterns = (
        "16S",
        "RRNL",
        "LRRNA",
        "LARGESUBUNITRIBOSOMALRNA",
        "LARGERIBOSOMALRNA",
    )

    if any(pattern in normalized for pattern in small_subunit_patterns):
        return "12S"

    if any(pattern in normalized for pattern in large_subunit_patterns):
        return "16S"

    return None


def extract_trna_amino_acid(**kwargs):
    """Extract the amino-acid name from a tRNA annotation."""

    value = str(kwargs.get("value", ""))
    upper_value = value.upper()

    gene_match = re.search(r"\bTRN([ARNDCQEGHILKMFPSTWYV])(?:1|2)?\b", upper_value)
    if gene_match:
        return AMINO_ACID_CODES.get(gene_match.group(1))

    descriptor_match = re.search(
        r"(?:T[ -]?RNA|TRANSFER[ -]?RNA)[\s_:\-]*("
        r"ALA|ARG|ASN|ASP|CYS|GLN|GLU|GLY|HIS|ILE|LEU|LYS|"
        r"MET|PHE|PRO|SER|THR|TRP|TYR|VAL|"
        r"ALANINE|ARGININE|ASPARAGINE|ASPARTATE|ASPARTIC ACID|"
        r"CYSTEINE|GLUTAMINE|GLUTAMATE|GLUTAMIC ACID|GLYCINE|"
        r"HISTIDINE|ISOLEUCINE|LEUCINE|LYSINE|METHIONINE|"
        r"PHENYLALANINE|PROLINE|SERINE|THREONINE|TRYPTOPHAN|"
        r"TYROSINE|VALINE)",
        upper_value,
    )

    if descriptor_match:
        descriptor = normalize_marker_text(value=descriptor_match.group(1))
        return AMINO_ACID_CODES.get(descriptor)

    for amino_acid_code, amino_acid_name in sorted(AMINO_ACID_CODES.items(), key=lambda item: len(item[0]), reverse=True):
        if len(amino_acid_code) < 3:
            continue

        pattern = rf"\b{re.escape(amino_acid_code)}\b"
        if re.search(pattern, upper_value):
            return amino_acid_name

    return None


def standardize_trna_marker(**kwargs):
    """Resolve mitochondrial tRNA names, including Leu and Ser isoacceptors."""

    value = kwargs.get("value", "")
    qualifiers = kwargs.get("qualifiers", {})

    combined_text = " ".join(
        part
        for part in (
            str(value),
            first_qualifier_value(qualifiers=qualifiers, qualifier_name="gene"),
            first_qualifier_value(qualifiers=qualifiers, qualifier_name="product"),
            first_qualifier_value(qualifiers=qualifiers, qualifier_name="label"),
            first_qualifier_value(qualifiers=qualifiers, qualifier_name="note"),
            first_qualifier_value(qualifiers=qualifiers, qualifier_name="anticodon"),
        )
        if str(part).strip()
    )

    normalized = normalize_marker_text(value=combined_text)
    amino_acid = extract_trna_amino_acid(value=combined_text)

    if amino_acid is None:
        return None

    if amino_acid == "Leu":
        if any(
            pattern in normalized
            for pattern in ("TRNL1", "LEU1", "CUN", "CUU", "CUC", "CUA", "CUG", "UAG")
        ):
            return "tRNA-Leu-1"

        if any(
            pattern in normalized
            for pattern in ("TRNL2", "LEU2", "UUR", "UUA", "UUG", "UAA")
        ):
            return "tRNA-Leu-2"

    if amino_acid == "Ser":
        if any(
            pattern in normalized
            for pattern in ("TRNS1", "SER1", "AGN", "AGA", "AGG", "AGU", "AGC")
        ):
            return "tRNA-Ser-1"

        if any(
            pattern in normalized
            for pattern in ("TRNS2", "SER2", "UCN", "UCU", "UCC", "UCA", "UCG")
        ):
            return "tRNA-Ser-2"

    return f"tRNA-{amino_acid}"


def standardized_marker_name(**kwargs):
    """Return a standardized marker name from GenBank feature qualifiers."""

    feature_type = str(kwargs.get("feature_type", "")).strip()
    qualifiers = kwargs.get("qualifiers", {})

    # Plastid gene symbols (psbA, trnH-GUG, rrn16) are kept as written; see plastid_marker_name.
    plastid_name = plastid_marker_name(feature_type=feature_type, qualifiers=qualifiers)
    if plastid_name:
        return plastid_name

    candidate_values = [
        first_qualifier_value(qualifiers=qualifiers, qualifier_name="gene"),
        first_qualifier_value(qualifiers=qualifiers, qualifier_name="product"),
        first_qualifier_value(qualifiers=qualifiers, qualifier_name="label"),
        first_qualifier_value(qualifiers=qualifiers, qualifier_name="note"),
    ]

    candidate_values = [value for value in candidate_values if value]

    combined_value = " | ".join(candidate_values)

    if feature_type.lower() == "trna":
        marker_name = standardize_trna_marker(value=combined_value, qualifiers=qualifiers)
        if marker_name:
            return marker_name

    if feature_type.lower() == "rrna":
        marker_name = standardize_rrna_marker(value=combined_value)
        if marker_name:
            return marker_name

    for candidate_value in candidate_values:
        marker_name = standardize_protein_coding_marker(value=candidate_value)
        if marker_name:
            return marker_name

    marker_name = standardize_rrna_marker(value=combined_value)
    if marker_name:
        return marker_name

    marker_name = standardize_trna_marker(value=combined_value, qualifiers=qualifiers)
    if marker_name:
        return marker_name

    return None
