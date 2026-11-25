"""Species identification of each sample against BOLD and GenBank.

For every project, the barcode markers of one assembly (the recommended one,
else the best ranked, else the first with the marker) are searched:

* mitochondrion: COI (``markers`` in ``config.yml``) against the BOLD v5 ID
  engine (``public.tax-derep``) and NCBI megablast against ``core_nt``;
* chloroplast: rbcL and matK against BOLD ``public.plants`` and ``core_nt``.

Hits shorter than ``min_overlap`` are ignored and species are ranked by their
best identity (not by bit score, which favours long partial genomes over
658 bp barcodes). The ``top_species`` best species of each database are kept,
because the first one is not necessarily right.

When the metadata gives a species for the project, it is also searched in
GenBank on its own (``ENTREZ_QUERY``) and a verdict is given:

* ``Confirmed``: identity to the declared species >= ``identity_threshold`` and
  no other species more than ``tie_margin`` points closer;
* ``Ambiguous``: identity >= threshold, but another species is closer;
* ``Not confirmed``: identity below the threshold;
* ``No reference``: neither database has a sequence of the declared species.

Without metadata the verdict is ``Not declared`` and the probable species are
listed: ``Top BOLD species`` and ``Top GenBank species`` give the best
``top_species`` of each database with their identity, and ``Probable species``
merges both by identity. The NCBI taxonomy (genus, family, order, class) of the declared species,
or of the best match when none is declared, is returned for the RefSeq
comparison.
"""

import asyncio
import logging
import xml.etree.ElementTree as ElementTree

import pandas as pd
from Bio import SeqIO

from ..standardization.standardized_marker_name import standardized_marker_name


RANKS = ("genus", "family", "order", "class")
SUMMARY_COLUMNS = [
    "Project name", "Assembly", "Organelle", "Marker", "Marker length", "Declared species", "Verdict",
    "Identity to declared species (%)", "Declared species source",
    "Declared species identity in BOLD (%)", "Declared species identity in GenBank (%)", "Declared species GenBank record", "Best BOLD species", "Best BOLD identity (%)",
    "Best GenBank species", "Best GenBank identity (%)", "Top BOLD species", "Top GenBank species", "Probable species", "BOLD status", "GenBank status",
    "Taxonomy species", "TaxID", "Genus", "Genus TaxID", "Family", "Family TaxID", "Order", "Order TaxID", "Class", "Class TaxID",
]
HIT_COLUMNS = [
    "Project name", "Assembly", "Marker", "Database", "Rank", "Species", "Identity (%)", "Overlap (bp)",
    "Records", "Best record", "BIN", "Title",
]
DEFAULT_MARKERS = {"mitochondrion": ["COI"], "chloroplast": ["rbcL", "matK"]}
DEFAULT_BOLD = {"mitochondrion": "public.tax-derep", "chloroplast": "public.plants"}


def marker_matches(feature, marker):
    target = marker.lower()
    standard = standardized_marker_name(feature_type=feature.type, qualifiers=feature.qualifiers) or ""
    if standard.lower() == target:
        return True
    names = [str(value).lower() for key in ("gene", "product") for value in feature.qualifiers.get(key, [])]
    return any(name == target or name.split("(")[0] == target for name in names)


def marker_sequence(**kwargs):
    """Sequence of ``marker`` (first CDS/gene match) in the GenBank of a job."""

    job = kwargs.get("job", {})
    marker = kwargs.get("marker")
    paths = job.get("paths", {})
    path = paths.get("rotated_genbank") or paths.get("genbank")
    if not path:
        return None
    record = next(SeqIO.parse(path, "genbank"), None)
    if record is None:
        return None
    for kind in ("CDS", "gene"):
        for feature in record.features:
            if feature.type == kind and marker_matches(feature, marker):
                return str(feature.extract(record.seq)).upper()
    return None


def representative_jobs(**kwargs):
    """One job per project: recommended, else best ranked, else the first."""

    jobs = kwargs.get("jobs", [])
    scores = kwargs.get("scores_dataframe")
    by_name = {job["Assembly"]: job for job in jobs}
    chosen = {}
    if scores is not None and not scores.empty:
        ordered = scores.sort_values(["Project name", "Recommended", "Rank in project"], ascending=[True, False, True])
        for _, row in ordered.iterrows():
            project = str(row["Project name"])
            if project not in chosen and str(row["Assembly"]) in by_name:
                chosen[project] = by_name[str(row["Assembly"])]
    for job in jobs:
        if job["Project name"] not in chosen and (job["paths"].get("rotated_genbank") or job["paths"].get("genbank")):
            chosen[job["Project name"]] = job
    return chosen


def bold_hits(**kwargs):
    """Rows (species, identity, overlap, record, BIN) from BOLD ID engine records."""

    rows = []
    for result in kwargs.get("records") or []:
        if not isinstance(result, dict):
            continue
        for key, data in (result.get("results") or {}).items():
            parts = key.split("|")
            taxonomy = data.get("taxonomy") or {}
            species = str(taxonomy.get("species") or "").strip()
            if not species:
                genus = str(taxonomy.get("genus") or "").strip()
                species = f"{genus} sp." if genus else ""
            if not species:
                continue
            identity = data.get("pident")
            if identity is None and data.get("pdist") is not None:
                identity = 100 - float(data["pdist"])
            rows.append({
                "Species": species, "Identity (%)": round(float(identity), 3), "Overlap (bp)": int(data.get("overlap") or data.get("length") or 0),
                "Best record": parts[0] if parts else "", "BIN": parts[2] if len(parts) > 2 else "", "Title": " / ".join(
                    str(taxonomy.get(rank) or "") for rank in ("order", "family", "genus") if taxonomy.get(rank)),
                "taxonomy": taxonomy,
            })
    return rows


def blast_hits(**kwargs):
    """Rows (species, identity, overlap, accession) from a BLAST JSON2_S report."""

    report = kwargs.get("report") or {}
    rows = []
    try:
        search = report["BlastOutput2"][0]["report"]["results"]["search"]
    except (KeyError, IndexError, TypeError):
        return rows
    for hit in search.get("hits", []):
        description = (hit.get("description") or [{}])[0]
        hsps = hit.get("hsps") or []
        if not hsps:
            continue
        best = max(hsps, key=lambda hsp: hsp.get("bit_score", 0))
        length = int(best.get("align_len") or 0)
        if not length:
            continue
        species = str(description.get("sciname") or "").strip()
        if not species:
            continue
        rows.append({
            "Species": species, "Identity (%)": round(100.0 * int(best.get("identity", 0)) / length, 3), "Overlap (bp)": length,
            "Best record": description.get("accession", ""), "BIN": "", "Title": description.get("title", ""),
            "taxid": description.get("taxid"),
        })
    return rows


def rank_species(**kwargs):
    """Best hit of each species among hits >= ``min_overlap``, ordered by identity."""

    rows = [row for row in kwargs.get("rows", []) if row["Overlap (bp)"] >= int(kwargs.get("min_overlap", 400))]
    best = {}
    counts = {}
    for row in rows:
        species = row["Species"]
        counts[species] = counts.get(species, 0) + 1
        current = best.get(species)
        if current is None or (row["Identity (%)"], row["Overlap (bp)"]) > (current["Identity (%)"], current["Overlap (bp)"]):
            best[species] = row
    ranked = sorted(best.values(), key=lambda row: (-row["Identity (%)"], -row["Overlap (bp)"], row["Species"]))
    return [{**row, "Records": counts[row["Species"]]} for row in ranked]


def same_species(left, right):
    normalize = lambda name: " ".join(str(name or "").replace("_", " ").split()[:2]).lower()
    return bool(left) and bool(right) and normalize(left) == normalize(right)


def verdict(**kwargs):
    declared = kwargs.get("declared")
    ranked = kwargs.get("ranked", [])
    declared_identity = kwargs.get("declared_identity")
    threshold = float(kwargs.get("identity_threshold", 97))
    margin = float(kwargs.get("tie_margin", 0.5))
    if not declared:
        return "Not declared"
    if declared_identity is None:
        return "No reference"
    if declared_identity < threshold:
        return "Not confirmed"
    closer = [row for row in ranked if not same_species(row["Species"], declared) and row["Identity (%)"] > declared_identity + margin]
    return "Ambiguous" if closer else "Confirmed"


async def taxonomy_lineage(**kwargs):
    """NCBI taxonomy of a species name (falls back to its genus)."""

    service = kwargs.get("service")
    name = str(kwargs.get("name") or "").strip()
    empty = {"Taxonomy species": name or None, "TaxID": None, **{rank.capitalize(): None for rank in RANKS}, **{f"{rank.capitalize()} TaxID": None for rank in RANKS}}
    if not name or service is None:
        return empty
    candidates = [name]
    if " " in name:
        candidates.append(name.split()[0])
    for candidate in candidates:
        search = await service.eutils("esearch", {"db": "taxonomy", "term": f"\"{candidate}\"[Scientific Name]", "retmode": "json"}, as_json=True)
        ids = ((search or {}).get("esearchresult") or {}).get("idlist") or []
        if not ids:
            continue
        text = await service.eutils("efetch", {"db": "taxonomy", "id": ids[0], "retmode": "xml"})
        if not text:
            continue
        try:
            taxon = ElementTree.fromstring(text).find("Taxon")
        except ElementTree.ParseError:
            continue
        if taxon is None:
            continue
        lineage = {"Taxonomy species": name, "TaxID": int(ids[0])}
        nodes = [(item.findtext("Rank"), item.findtext("ScientificName"), item.findtext("TaxId")) for item in (taxon.find("LineageEx") if taxon.find("LineageEx") is not None else [])]
        nodes.append((taxon.findtext("Rank"), taxon.findtext("ScientificName"), taxon.findtext("TaxId")))
        for rank in RANKS:
            match = next((node for node in nodes if node[0] == rank), None)
            lineage[rank.capitalize()] = match[1] if match else None
            lineage[f"{rank.capitalize()} TaxID"] = int(match[2]) if match else None
        return lineage
    return empty


async def bold_search(**kwargs):
    """BOLD search of {project: sequence}; FASTA identifiers are q1, q2... so any project name is safe."""

    settings = kwargs.get("settings", {}) or {}
    sequences = kwargs.get("sequences") or {}
    names = {f"q{index}": project for index, project in enumerate(sequences, start=1)}
    answers = await kwargs.get("service").bold(
        sequences={identifier: sequences[project] for identifier, project in names.items()}, database=kwargs.get("database"),
        min_identity=settings.get("bold_min_identity", 0.9), max_hits=settings.get("bold_max_hits", 100), batch_size=settings.get("bold_batch_size", 20),
    )
    return {names[identifier]: record for identifier, record in (answers or {}).items() if identifier in names}


async def single_result(task, identifier):
    return ((await task) or {}).get(identifier)


async def identify_project(**kwargs):
    project = kwargs.get("project")
    job = kwargs.get("job")
    service = kwargs.get("service")
    settings = kwargs.get("settings", {}) or {}
    organelle = kwargs.get("organelle", "mitochondrion")
    declared = kwargs.get("declared")
    markers = settings.get("markers") or DEFAULT_MARKERS.get(organelle, ["COI"])
    bold_database = settings.get("bold_database") or DEFAULT_BOLD.get(organelle, "public.tax-derep")
    min_overlap = int(settings.get("min_overlap", 400))
    top = int(settings.get("top_species", 3))
    summaries, hit_rows = [], []

    bold_results = kwargs.get("bold_results")
    for marker in markers:
        sequence = marker_sequence(job=job, marker=marker)
        base = {"Project name": project, "Assembly": job["Assembly"], "Organelle": organelle, "Marker": marker,
                "Marker length": len(sequence) if sequence else None, "Declared species": declared or None}
        if not sequence:
            summaries.append({**base, "Verdict": "Marker not annotated", "BOLD status": "not queried", "GenBank status": "not queried"})
            continue

        if bold_results is not None:
            bold_task = asyncio.sleep(0, result=bold_results.get((project, marker)))
        else:
            bold_task = bold_search(service=service, sequences={project: sequence}, database=bold_database, settings=settings)
            bold_task = single_result(bold_task, project)
        blast_task = service.blast(sequence=sequence, database=settings.get("blast_database", "core_nt"), hitlist_size=settings.get("blast_hitlist_size", 250))
        declared_task = (service.blast(sequence=sequence, database=settings.get("blast_database", "core_nt"), hitlist_size=20,
                                       entrez_query=f"\"{declared}\"[Organism]") if declared else asyncio.sleep(0, result=None))
        bold_records, blast_report, declared_report = await asyncio.gather(bold_task, blast_task, declared_task)

        bold_ranked = rank_species(rows=bold_hits(records=[bold_records] if bold_records else []), min_overlap=min_overlap)
        blast_ranked = rank_species(rows=blast_hits(report=blast_report), min_overlap=min_overlap)
        declared_rows = rank_species(rows=blast_hits(report=declared_report), min_overlap=min_overlap)
        for database, ranked in (("BOLD", bold_ranked), ("GenBank", blast_ranked)):
            for rank, row in enumerate(ranked[:top], start=1):
                hit_rows.append({"Project name": project, "Assembly": job["Assembly"], "Marker": marker, "Database": database, "Rank": rank,
                                 **{column: row.get(column) for column in ("Species", "Identity (%)", "Overlap (bp)", "Records", "Best record", "BIN", "Title")}})

        declared_identity, declared_source = None, None
        bold_declared = max((row["Identity (%)"] for row in bold_ranked if same_species(row["Species"], declared)), default=None) if declared else None
        genbank_declared_rows = [row for row in blast_ranked + declared_rows if declared and same_species(row["Species"], declared)]
        genbank_declared = max(genbank_declared_rows, key=lambda row: row["Identity (%)"], default=None)
        if declared:
            options = [(row["Identity (%)"], "BOLD") for row in bold_ranked if same_species(row["Species"], declared)]
            options += [(row["Identity (%)"], "GenBank") for row in blast_ranked + declared_rows if same_species(row["Species"], declared)]
            if options:
                declared_identity, declared_source = max(options)
        combined = sorted(bold_ranked + blast_ranked, key=lambda row: -row["Identity (%)"])
        probable = []
        for row in combined:
            if not any(same_species(row["Species"], name) for name in probable):
                probable.append(row["Species"])
        summaries.append({
            **base,
            "Verdict": verdict(declared=declared, ranked=combined, declared_identity=declared_identity,
                               identity_threshold=settings.get("identity_threshold", 97), tie_margin=settings.get("tie_margin", 0.5)),
            "Identity to declared species (%)": declared_identity,
            "Declared species source": declared_source,
            "Declared species identity in BOLD (%)": bold_declared,
            "Declared species identity in GenBank (%)": genbank_declared["Identity (%)"] if genbank_declared else None,
            "Declared species GenBank record": genbank_declared["Best record"] if genbank_declared else None,
            "Best BOLD species": bold_ranked[0]["Species"] if bold_ranked else None,
            "Best BOLD identity (%)": bold_ranked[0]["Identity (%)"] if bold_ranked else None,
            "Best GenBank species": blast_ranked[0]["Species"] if blast_ranked else None,
            "Best GenBank identity (%)": blast_ranked[0]["Identity (%)"] if blast_ranked else None,
            "Top BOLD species": "; ".join(f"{row['Species']} ({row['Identity (%)']:.2f}%)" for row in bold_ranked[:top]),
            "Top GenBank species": "; ".join(f"{row['Species']} ({row['Identity (%)']:.2f}%)" for row in blast_ranked[:top]),
            "Probable species": "; ".join(probable[:top]),
            "BOLD status": "failed" if bold_records is None else f"{len(bold_ranked)} species",
            "GenBank status": "failed" if blast_report is None else f"{len(blast_ranked)} species",
        })

    first = next((row for row in summaries if row.get("Probable species") is not None), summaries[0] if summaries else {})
    name = declared or (str(first.get("Probable species") or "").split(";")[0].strip() or None)
    lineage = await taxonomy_lineage(service=service, name=name)
    return [{**row, **lineage} for row in summaries], hit_rows


async def run_species_identification(**kwargs):
    """Return (summary dataframe, hits dataframe)."""

    service = kwargs.get("service")
    settings = kwargs.get("settings", {}) or {}
    organelle = kwargs.get("organelle", "mitochondrion")
    declared = kwargs.get("declared_species", {}) or {}
    chosen = representative_jobs(jobs=kwargs.get("jobs", []), scores_dataframe=kwargs.get("scores_dataframe"))
    logging.info("Species identification: %d projects, %s, %d requests per second to NCBI and BOLD",
                 len(chosen), "declared species from the metadata" if declared else "no metadata (probable species only)", service.rate)

    # BOLD limits concurrent submissions: every sequence of a marker goes in one request.
    markers = settings.get("markers") or DEFAULT_MARKERS.get(organelle, ["COI"])
    bold_database = settings.get("bold_database") or DEFAULT_BOLD.get(organelle, "public.tax-derep")
    bold_results = {}
    for marker in markers:
        sequences = {}
        for project, job in sorted(chosen.items()):
            sequence = marker_sequence(job=job, marker=marker)
            if sequence:
                sequences[project] = sequence
        if sequences:
            answers = await bold_search(service=service, sequences=sequences, database=bold_database, settings=settings)
            bold_results.update({(project, marker): record for project, record in (answers or {}).items()})

    results = await asyncio.gather(*[
        identify_project(project=project, job=job, service=service, settings=settings, organelle=organelle, declared=declared.get(project),
                         bold_results=bold_results)
        for project, job in sorted(chosen.items())
    ])
    summaries = [row for result in results for row in result[0]]
    hits = [row for result in results for row in result[1]]
    summary = pd.DataFrame(summaries, columns=SUMMARY_COLUMNS)
    if not summary.empty:
        logging.info("Species identification verdicts: %s", summary["Verdict"].value_counts().to_dict())
    return summary, pd.DataFrame(hits, columns=HIT_COLUMNS)
