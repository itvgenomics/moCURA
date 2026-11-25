"""Names of plastid (chloroplast) genes.

Plastid annotators (CPGAVAS2, Chloë, GeSeq) and RefSeq plastomes use gene
symbols such as ``psbA``, ``rbcL``, ``rps12``, ``trnH-GUG`` and ``rrn16``.
The mitochondrial standardization cannot keep them apart: plastomes carry
several tRNAs for the same amino acid (``trnI-CAU`` and ``trnI-GAU``,
``trnR-ACG`` and ``trnR-UCU``), and their rRNAs are 4.5S, 5S, 16S and 23S.

``plastid_marker_name`` returns the canonical symbol of a plastid gene, or None
for anything else, so mitochondrial names (``COI``, ``trnF(gaa)``, ``TRNF``,
``rrnS``) are left to the mitochondrial rules. MITOS2 writes tRNAs as
``trnF(gaa)``; plastid annotators as ``trnF-GAA``, the only form read here.
"""

import re


PROTEIN_CODING = re.compile(
    r"^(psa[a-jm]|psb[a-z]|pet[a-nlg]|atp[a-i]|ndh[a-k]|rbcl|rpo[abc]\d?|rps\d{1,2}|rpl\d{1,2}|clpp\d?|ycf\d{1,2}|"
    r"accd|ccsa|cema|infa|matk|lhba|pafi{1,2}|pbf1|chl[bln]|ftsh|ycf\d{1,2}a?)$",
    re.IGNORECASE,
)
TRNA = re.compile(r"^trn(f?M|[A-Z])[-_]([ACGTU]{3})$", re.IGNORECASE)
RRNA = re.compile(r"^(?:rrn)?(4\.5|5|16|23)S?$", re.IGNORECASE)
PLASTID_RRNA_PRODUCT = re.compile(r"^(4\.5|5|23)S ribosomal RNA$", re.IGNORECASE)


def first_value(qualifiers, name):
    values = qualifiers.get(name) or []
    if isinstance(values, str):
        values = [values]
    for value in values:
        value = str(value).strip()
        if value:
            return value
    return ""


def canonical_protein_coding(symbol):
    """``PSBA`` -> ``psbA``, ``rps12`` -> ``rps12``, ``ycf1`` -> ``ycf1``, ``clpP1`` -> ``clpP1``."""

    head, tail = symbol[:3].lower(), symbol[3:]
    if tail[:1].isalpha():
        tail = tail[:1].upper() + tail[1:].lower()
    return head + tail


def plastid_marker_name(**kwargs):
    """Canonical plastid gene symbol of a GenBank feature, or None."""

    feature_type = str(kwargs.get("feature_type", "")).strip().lower()
    qualifiers = kwargs.get("qualifiers", {}) or {}
    gene = first_value(qualifiers, "gene")

    if feature_type == "trna":
        match = TRNA.match(gene)
        if match:
            amino_acid = match.group(1)
            amino_acid = "fM" if amino_acid.lower() == "fm" else amino_acid.upper()
            return f"trn{amino_acid}-{match.group(2).upper().replace('T', 'U')}"
        return None

    if feature_type == "rrna":
        compact = gene.replace(" ", "")
        if compact.lower().startswith("rrn"):
            match = RRNA.match(compact)
            if match:
                return f"rrn{match.group(1)}"
            return None
        # Without a gene symbol, only the plastid-specific rRNAs are told by their product:
        # a bare "16S ribosomal RNA" is also the large mitochondrial rRNA, so it stays 16S.
        match = PLASTID_RRNA_PRODUCT.match(first_value(qualifiers, "product")) if not gene else None
        return f"rrn{match.group(1)}" if match else None

    if feature_type in ("cds", "gene") and PROTEIN_CODING.match(gene):
        return canonical_protein_coding(gene)
    return None
