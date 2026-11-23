# OrganPipe inputs available to moCURA

Phase 0 reconnaissance. Nothing in production code was changed for this document.

- **Dataset inspected:** `/mnt/c/dev/results` (the `--results-dir` used to build `example_output/`)
- **Projects:** 7 (`ITV38290`, `ITV38292`, `ITV38302`, `ITV38307`, `ITV38323`, `ITV38324`, `ITV38325`)
- **Assembler / organelle:** NOVOPlasty, mitochondrion
- **K-mers:** 20, 45, 65, 85, 100
- **Seeds:** 13 PCG seeds per sample
- **Reference:** OrganPipe `main` branch (`workflow/rules/*.smk`, `workflow/scripts/rotate_genbank.py`, `workflow/scripts/mito_gff2genbank.py`), read on 2026-11-23

The example dataset was produced by an **older OrganPipe layout**. It has no assembler level (`novoplasty/`) under `results/{sample}/{step}/`, and it contains only the `results/` tree. There is no `workflow/reports/`, `benchmarks/`, `resources/` or `config/`.

## 1. Real file map

Placeholders:

- `{sample}`: project, e.g. `ITV38290`.
- `{seed}`: `{order}-{seed_name}`, e.g. `6-ATP_synthase_F0_subunit_6`.
- `{kmer}`: e.g. `20`.
- `{asm}`: assembly header, `{PREFIX}_{n}_{sample}_{seed}_{kmer}_{copy}`, e.g. `CA_1_ITV38290_6-ATP_synthase_F0_subunit_6_20_1`.

| Item | Example dataset (`results/`) | OrganPipe `main` | Present in example? |
| --- | --- | --- | --- |
| NOVOPlasty log | `{sample}/novoplasty/{seed}/kmer{kmer}/log_{sample}.txt` | same, with `novoplasty/` already the step dir | yes, 455 logs (65 per sample) |
| NOVOPlasty assembly | `{sample}/novoplasty/{seed}/kmer{kmer}/{Circularized_assembly,Contigs,Option}_1_{sample}.fasta` | same | yes |
| Assembled reads | `{sample}/novoplasty/{seed}/kmer{kmer}/Assembled_reads_{sample}_R{1,2}.fasta` | same | yes, sometimes only R1 or R2 is kept |
| Split assemblies | `{sample}/assemblies/{seed}_kmer{kmer}/{asm}.fasta` (+ bwa index) | `assemblies/novoplasty/{seed}_kmer{kmer}/` | yes |
| Pilon log | `{sample}/pilon/{asm}/pilon.log` | `pilon/novoplasty/{asm}/` | yes, 393 dirs |
| Pilon FASTA | `{sample}/pilon/{asm}/{asm}.fasta` | `pilon/novoplasty/{asm}/` | yes |
| Pilon changes | `{sample}/pilon/{asm}/{asm}.changes` | `pilon/novoplasty/{asm}/` | yes, 391 files (169 non-empty) |
| BAM, original contig | `{sample}/pilon/{asm}/{asm}_mapping.bam` (+ `.bai`) | `pilon/novoplasty/{asm}/` | yes, 391 files |
| MITOS2 raw | `{sample}/mitos2/{seed}_kmer{kmer}/{asm}/result.{bed,gff,mitos,geneorder,faa,fas,seq}`, `ignored.mitos`, `mitos2.fasta` | `mitos2/novoplasty/{seed}_kmer{kmer}/{asm}/` | yes, 391 runs |
| MITOS2 summary | — | `workflow/reports/{sample}/mitos2.csv` | **no** |
| GenBank | `{sample}/genbanks/{asm}.gb` | `genbanks/novoplasty/{asm}.gb` | yes, 687 files |
| Rotated GenBank | `{sample}/genbanks/{asm}.rotated.gb` | `genbanks/novoplasty/{asm}.rotated.gb` | yes, 296 files |
| Images FASTA | `{sample}/images/{seed}_kmer{kmer}/{asm}.fasta` and `{asm}.rotated.fasta` | `images/novoplasty/{seed}_kmer{kmer}/` | yes |
| Depth, original | `{sample}/images/{seed}_kmer{kmer}/{asm}.depth` | `images/novoplasty/...` | yes, 391 files |
| Depth, rotated | `{sample}/images/{seed}_kmer{kmer}/{asm}.rotated.depth` | `images/novoplasty/...` | yes, 296 files (one per rotated GenBank) |
| BAM, rotated | `{sample}/images/{seed}_kmer{kmer}/{asm}.rotated_mapping.bam` | `images/novoplasty/...` | yes, 296 files, **without `.bai`** |
| Read recruitment | `{sample}/images/{seed}_kmer{kmer}/{asm}.blastn.out` and `{asm}.rotated.blastn.out` | `images/novoplasty/...` | yes, 391 + 296 files |
| nhmmer (intergenic) | — | `nhmmer/novoplasty/{seed}_kmer{kmer}/{asm}/intergenes_filter.tblout.out` | **no** |
| fastp report | — | `resources/{sample}/rawreads/fastp.json` | **no** (only FastQC zips in `results/fastqc_cesar/`, outside the OrganPipe tree) |
| Snakemake benchmarks | — | `benchmarks/{sample}/**/*.benchmark` | **no** (`/mnt/c/dev/benchmarks` belongs to a nuclear-genome pipeline, not to OrganPipe) |
| OrganPipe config | — | `config/config.yaml`, `config/snakemake_config.yaml` | **no** (NOVOPlasty `config.txt` per run is available) |
| Step check files | `*.check` next to every output | same | yes |

Extra items in `results/` that are not part of OrganPipe:

- `results/genbanks/{sample}/*.rotated.gb` holds copies of the rotated GenBanks for 34 samples, 27 of them without the other results.
- `results/genbanksSynGenes.log`.
- `{sample}/hashtable/kmer{kmer}/` holds NOVOPlasty reads.

## 2. Naming patterns

- **Assembly prefix:** `CA` (Circularized_assembly), `CTG` (Contigs), `OPT` (Option) and `INVALIDSEED` (OrganPipe placeholder when the seed failed).
  - Counts in `genbanks/`: 478 `CA_1`, 204 `CTG_1`, 5 `OPT_1`.
- **Copy suffix `_{copy}`:** one per FASTA record. A NOVOPlasty file with two contigs yields `_1` and `_2`, and each one is mapped, polished and annotated independently.
- **Seed directory:** `{order}-{seed_name}_kmer{kmer}`. Seed names are long product names (`ATP_synthase_F0_subunit_6`) that `standardized_gene_name()` already converts (e.g. `ATP6`).
- **Parsers to reuse:**
  - `parse_rotated_genbank_filename()` (`load_genbank_marker_data.py`): `^.+?_{project}_{order}-{seed}_{kmer}_{copy}`.
  - `parse_pilon_dir_name()` (`load_pilon_data.py`): `^[A-Za-z]+_\d+_{project}_{seed}_{kmer}_\d+$`.

  Both accept `CA`/`CTG`/`OPT`. A `{seed}_kmer{kmer}` directory parser does not exist yet. It is trivial (`^(?P<order>\d+)-(?P<seed>.+)_kmer(?P<kmer>\d+)$`).
- **Rotated files:** the `.rotated` suffix is placed before the extension (`.rotated.gb`, `.rotated.depth`, `.rotated.fasta`, `.rotated.blastn.out`). For the BAM it comes before `_mapping` (`.rotated_mapping.bam`).
- **Header inside files:**
  - `.depth`, `.blastn.out` and `.bam` use `{asm}` or `{asm}.rotated` as the reference name.
  - MITOS2 files use `temp_header`.
  - `.changes` uses `{asm}` and `{asm}_pilon`.

## 3. Coordinate systems

Three coordinate systems coexist. Every positional input must be converted before it is drawn on the rotated genome track.

| System | Sequence | Files that use it |
| --- | --- | --- |
| **A. pre-Pilon** | `assemblies/.../{asm}.fasta` (NOVOPlasty record) | `pilon/{asm}/{asm}_mapping.bam`, `{asm}.depth` (produced from that BAM), left side of `.changes` |
| **B. post-Pilon** | `pilon/{asm}/{asm}.fasta` = `genbanks/{asm}.gb` = `images/.../{asm}.fasta` | `{asm}.gb`, MITOS2 outputs, `{asm}.blastn.out`, right side of `.changes` |
| **C. rotated** | `genbanks/{asm}.rotated.gb` = `images/.../{asm}.rotated.fasta` | `.rotated.gb`, `.rotated.depth`, `.rotated_mapping.bam`, `.rotated.blastn.out` |

- **A → B:** apply the `.changes` indels cumulatively. Example: `ITV38324 ND4 k45 _1` has a 5 bp Pilon insertion. `.depth` reaches 16,527 (A) while `.blastn.out` reaches 16,532 (B).
- **B → C:** circular shift by the rotation offset, `rotated = (pos_B − offset) mod length`. The offset is `start` of the first `rRNA` with `product = rrnS` in `{asm}.gb`. It can also be recovered by locating `rotated[:k]` in `gb + gb`, which is reliable because the sequences are identical. Of the 296 rotated files, 239 have a non-zero offset.
- `.rotated.depth` and `.rotated_mapping.bam` are already in C. Use them directly for the coverage track and the junction analysis, and use `{asm}.depth` only as a fallback.
- **Original junction position in C:** `(length − offset) mod length`.

## 4. File formats (as observed)

- **`.depth`:** `samtools depth` without `-a`, three columns: `ref`, `pos` (1-based), `depth`. Zero-depth positions are missing. For example, `ITV38290 ATP6 k20 _1` has 15,438 lines for 15,553 bp.
- **`.blastn.out`:** BLAST outfmt 6 (12 standard columns).
  - `qseqid` = `{read}/{1|2}`.
  - `-max_target_seqs 1 -evalue 1e-5 -task blastn`.
  - Query = `Assembled_reads` R1+R2 of the same NOVOPlasty run.
- **`.changes`:** `{asm}:{pos} {asm}_pilon:{pos[-pos]} {ref|.} {alt|.}`, one line per correction. 222 of the 391 files are empty.
- **`pilon.log`:** already parsed. It also contains `# fix break: {asm}:{a}-{b} ... NoSolution TandemRepeat` lines (74 in the dataset), which are unresolved local breaks and worth surfacing.
- **MITOS2:**
  - `result.bed`: 0-based half-open, with the e-value in the score column.
  - `result.mitos` and `ignored.mitos`: 0-based inclusive start/stop, columns `seqid type name method start stop strand evalue score anticodon ...`.
  - `ignored.mitos` holds hits that MITOS2 rejected. It is essential for the 12S diagnosis.
  - `result.geneorder`: one FASTA-like record, with `-` prefixes for minus-strand genes.
  - `result.gff`: declares `Is_circular=True`.
- **NOVOPlasty log:**
  - `Total contigs`.
  - `Contig N : size`.
  - The line `(Check manually if the two contigs overlap to merge them together!)` appears when a "circularized" assembly has 2 contigs.
  - `config.txt` stores `Genome Range`, `Type`, `Seed Input` and `Reference sequence` (empty here).

## 5. Differences from the table in the task

1. The example has no `{assembler}/` level (`pilon/{asm}`, not `pilon/novoplasty/{asm}`; the same applies to `mitos2/`, `images/`, `genbanks/` and `assemblies/`). The current moCURA loaders only work with this old layout:
   - the Pilon loader looks for `{project}/pilon/{run}`;
   - the GenBank loader looks for `{project}/genbanks/`.

   **A dataset from current OrganPipe would not load Pilon or GenBank data.** Phase 1 should make the finders accept both layouts. The NOVOPlasty loader already does, because it walks the tree.
2. `mitos2.csv`, nhmmer outputs, `fastp.json`, Snakemake benchmarks and OrganPipe `config/` are absent. Their parsers can be written and unit-tested against fixtures, but they cannot be exercised end-to-end on this dataset. A small real sample from a current OrganPipe run is needed (see §8).
3. The rotated BAM exists but has **no `.bai`**. Junction counting in Phase 2 must either index it into `--output-dir` or stream the whole (small) BAM.
4. There are two `.blastn.out` files per assembly (original and rotated), not one.
5. `.depth` (original) is in pre-Pilon coordinates, not in the rotated genome's coordinates.
6. The genetic code is not available from files in the example. It must come from `config.yml` (default 2, vertebrate mitochondrial).

## 6. Diagnosis of the 12S length problem

### Symptom

In `Marker Lengths`, every 12S feature starts at position 1 (`[0:N]`). Its length varies between 30 and 962 bp within the same individual.

Of 296 rotated assemblies, **88 (29.7%) have a 12S shorter than 900 bp**. The modal length is 962 bp.

### The hypothesis in the task is not what happens here

The hypothesis was that `rotate_genbank.py` uses `feature.location.start` of a `CompoundLocation` and splits the gene.

- There are **zero `CompoundLocation`s** in all 687 `.gb` and 296 `.rotated.gb` files.
- MITOS2 never emitted a wrapped (`start > end`) `rrnS` in `result.gff`/`result.bed`. Had it done so, `mito_gff2genbank.py` would have built a `CompoundLocation`.
- The rotation code is not the origin of the truncation. The truncated feature already exists in the MITOS2 output.

### The moCURA loader is not at fault

`parse_genbank_file_sync()` uses `len(feature.location)`, which sums all parts of a `CompoundLocation` (checked: a `join(16031..16544,1..448)` gives 962).

Its `Start`/`End` columns are `min`/`max`, so an origin-crossing feature would show as `1..length`. That is misleading, but harmless for length.

### Actual causes: three mechanisms

**A. The gene crosses the contig origin, MITOS2 keeps only the 3′ fragment, and the rotation does nothing (40 assemblies).**

- The NOVOPlasty contig origin falls inside the 12S.
- MITOS2 finds the complete wrapped hit but writes it to `ignored.mitos` and keeps only the fragment after the origin.
- Example: `ITV38325 ND1 k20 _1`.
  - `ignored.mitos`: `rrnS 16030 → 447`, score 664.
  - `result.bed`: `rrnS 0–448`.
  - The full gene is 514 + 448 = **962 bp**.
- `rotate_genbank.py` then rotates to `start = 0`, so nothing changes. The 5′ 514 bp stay unannotated at the end of the "rotated" genome, after `trnF`.

**C. The gene crosses the origin, MITOS2 keeps only the 5′ fragment, and the rotation is correct but the feature stays truncated (9 assemblies).**

- Example: `ITV38292 ND5 k20 _1`.
  - Original `rrnS` is `[15954:16525]` (571 bp, at the end of the contig).
  - The 3′ 391 bp sit unannotated at `[0:391]`, before `trnV`.
- The rotation moves position 15954 to 0, which is the true 12S start, so the genome is correctly oriented (`trnF` ends at the last base and `trnV` starts at 962).
- The feature still says `[0:571]`, while the gene is 571 + 391 = 962 bp.
- `ignored.mitos` again contains the wrapped hit.

In all 49 assemblies of A + C, the wrapped `rrnS` hit in `ignored.mitos` has length **962** (one has 845). That is exactly the modal length.

**B. The assembly genuinely lacks the region (39 assemblies).**

- NOVOPlasty reports "The genome has been circularized", but with **2 contigs** and the warning "Check manually if the two contigs overlap to merge them together!".
- Example: `ITV38290 ATP8 k20`. Contig 1 is 15,553 bp and Contig 2 is 989 bp.
- OrganPipe splits the file into `_1` and `_2` and annotates them separately. In this dataset, Contig 2 is always the ~1 kb segment that holds the 5′ part of 12S, `trnF` and part of the control region.
- The `_1` genome (~15.5 kb versus ~16.5 kb) therefore has only the last 30–99 bp of 12S. No wrapped hit exists, and the gene cannot be recovered from `_1` alone.
- k-mer mapping of a complete ITV38290 genome confirmed that its 100–1100 region is absent from Contig 1 and present in Contig 2.

### Related findings that matter for curation

- **70 of the 216 NOVOPlasty runs flagged "circularized" (32%) have 2 contigs.** moCURA currently reports them as `Circularized = True` without qualification. `Total contigs` is already a column, so this check is cheap.
- **95 `.gb` files have no `.rotated.gb`.** In all of them, MITOS2 annotated no `rrnS`, `rotate_genbank.py` raised `ValueError`, and the `except: pass` hid it.
  - 70 are small `_2` contigs.
  - **19 are circularized `_1` assemblies of 15 kb or more** (e.g. ITV38290 ND1 k45, 15,452 bp). They disappear silently from every GenBank-based moCURA analysis.
- `rotate_genbank.py` has a latent bug. When a feature crosses the *new* origin, it builds `FeatureLocation(start, end + length)`, which runs past the sequence end, instead of a `CompoundLocation`. This does not trigger here, because the rotation point is always the start of a feature.

### Proposed correction in moCURA (Phase 1, pending confirmation)

1. **Read MITOS2 `ignored.mitos`** next to `result.bed`.
   - When a kept feature is a strict sub-interval of a wrapped hit with the same name (`start > stop`), mark it `Crosses origin = True` and report `Origin-corrected length` = `(length − start) + stop + 1`.
   - Map the wrapped hit to rotated coordinates with the rotation offset (§3).
   - This recovers 962 bp for all 49 A + C cases.
2. **For a `CompoundLocation` in any GenBank** (future OrganPipe versions or other annotators):
   - keep the summed length (already correct);
   - set `Crosses origin = True` when its parts touch both sequence ends;
   - report the true start/end, i.e. the first part in strand order.
3. **Fallback without MITOS2 files:** flag a feature that starts at 1 or ends at the last base and is more than X% shorter than the project modal as `Possibly truncated at origin`. Do not infer a length.
4. **New alerts at the assembly level:**
   - `Circularized with N contigs (manual merge required)`;
   - `Annotated, but not rotated (no rrnS)` for `.gb` files without a `.rotated.gb`.

   These assemblies should appear in the report instead of vanishing.
5. **Existing outputs stay unchanged.** `Marker length`, `Start` and `End` keep their current meaning (the raw annotation). The new information goes into **new columns** (`Crosses origin`, `Origin-corrected length`, `Origin evidence`) and into the integrity analysis.

   **Decision needed:** should the marker FASTA extraction for the SNP analysis use the corrected 12S? Doing so changes the current 12S alignments.

### Recommendations for OrganPipe (not changed here)

- Annotate a pre-rotated FASTA. For example, shift each circular contig so that the origin falls in the middle of the largest intergenic region, run MITOS2, then rotate to `rrnS`. Alternatively, promote wrapped hits from `ignored.mitos` when they supersede a kept fragment.
- Replace `except: pass` in `rotate_genbank.py` with logging, and emit a `CompoundLocation` for features crossing the new origin.
- Do not treat a 2-contig "Circularized_assembly" as a single complete genome. Try to merge the contigs, or flag them.

## 7. What each Phase 1 item can use in this dataset

| Phase 1 item | Source in example | End-to-end testable here? |
| --- | --- | --- |
| 1. Completeness / gene order | `mitos2/.../result.{geneorder,mitos,bed}` (no `mitos2.csv`) | yes, via the fallback path |
| 2. Coverage profile | `.rotated.depth` (296 files) | yes |
| 3. Pilon change positions | `.changes` (169 non-empty) + rotation offset | yes |
| 4. Read recruitment | `.rotated.blastn.out` / `.blastn.out` | yes |
| 5. Missed annotations (nhmmer) | absent | fixture only |
| 6. Read QC (fastp) | absent | fixture only |
| 7. Benchmarks / provenance | benchmarks absent; moCURA self-timing, environment and git hash are available | partial |

## 8. Open questions for the user

1. Can you provide a small directory from a **current** OrganPipe run (one sample, one seed) with `workflow/reports/`, `benchmarks/`, `resources/{sample}/rawreads/fastp.json`, `nhmmer/` and `config/`? It would be used to build test fixtures and to check the layout with the `novoplasty/` level.
2. 12S correction: keep the existing `Marker length` unchanged and add the corrected value as a new column (proposed)? Should the SNP marker extraction also use the corrected sequence?
3. Should the 19 large assemblies without `rrnS` (no `.rotated.gb`) be loaded from their unrotated `.gb` in the new analyses, flagged as "not rotated"?
