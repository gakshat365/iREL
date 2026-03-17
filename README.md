# iREL — Pedagogical Flow Extraction from Hinglish Lectures

> **COMPLEX** — **C**ode-Mixed **O**nline **M**ultilingual **P**edagogical **L**earning **EX**traction

A 9-step NLP pipeline that processes Hinglish (Hindi-English code-mixed) YouTube lectures and produces an interactive **pedagogical knowledge graph** showing concept prerequisites and teaching flow.

**Domain:** Theory of Computation (Gate Smashers, 5 lectures)  
**Output:** JSON-LD knowledge graph + interactive `vis.js` HTML dashboard  

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.10 |
| ffmpeg | any recent (must be on PATH) |
| Git | any |
| Kaggle account | for Step 2 (GPU transcription only) |

Install ffmpeg on Windows:
```powershell
winget install ffmpeg
```

---

## Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd iREL

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux / macOS

# 3. Install dependencies
pip install -r complex/requirements.txt

# 4. Download NLTK data (one-time)
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt')"

# 5. (Optional) Download spaCy model for entity linking in Step 9
python -m spacy download en_core_web_sm
```

> All scripts must be run from the **`complex/`** directory unless noted otherwise.

```bash
cd complex
```

---

## Pipeline

### Step 1 — Fetch video metadata  *(local)*

Reads `video_links.txt`, calls `yt-dlp` to extract titles and metadata, and writes `data/raw/metadata.json`.

```bash
python src/audio_processing/step1_source.py
```

**Output:** `data/raw/metadata.json`

---

### Step 2 — Transcribe audio  *(Kaggle GPU — T4 x2)*

Whisper large-v3 requires a GPU. Run this step on Kaggle:

1. Upload `data/raw/metadata.json` as a Kaggle dataset.
2. Open `notebooks/01_transcription_parallel.ipynb` on Kaggle (accelerator: **GPU T4 x2**).
3. Run all cells — the notebook downloads audio via `yt-dlp`, converts to 16 kHz WAV with `ffmpeg`, and transcribes with Whisper (`language="hi"`, `task="transcribe"`).
4. Download the output files and place them in `data/interim/`:
   - `v1_raw_transcript_lec_1_*.json`
   - `v1_raw_transcript_lec_2_*.json`
   - … (one file per video)

> The sequential variant `notebooks/01_transcription.ipynb` also works but is slower.

---

### Step 3 — Transliterate  *(local)*

Converts Devanagari script segments to Roman ITRANS using `indic-transliteration`, then applies schwa-deletion corrections from `assets/schwa_corrections.json`.

```bash
python src/normalization/step3_transliterate.py
```

**Input:** `data/interim/v1_raw_transcript_*.json`  
**Output:** `data/interim/v2_hinglish_roman_*.txt`

---

### Step 4 — Clean sentences  *(local)*

Strips URLs, hashtags, non-ASCII noise, and disfluencies (`uh`, `um`, etc.). Segments into sentences with `pysbd` and Purn Viram (`।`) splitting.

```bash
python src/normalization/step4_clean.py
```

**Input:** `data/interim/v2_hinglish_roman_*.txt`  
**Output:** `data/interim/v3_cleaned_sentences_*.txt`

---

### Step 5 — Enhance terms  *(local)*

4-stage term recovery:
1. Unicode normalization
2. SymSpell spelling correction (domain vocab, edit distance ≤ 2)
3. Soundex phonetic fallback
4. Domain lexicon phrase replacement (`assets/domain_lexicon.json`)

```bash
python src/normalization/step5_enhance.py
```

**Input:** `data/interim/v3_cleaned_sentences_*.txt`  
**Output:** `data/interim/v4_standardized_terms_*.txt`

---

### Step 6 — Canonicalize  *(local)*

Collapses orthographic variants using:
- Hinglish filler whitelist guard (`assets/hinglish_fillers.json`)
- Dialect map (`assets/dialect_map.json`)
- Contractions (`assets/contractions.json`)
- Damerau-Levenshtein fallback (jellyfish)

```bash
python src/normalization/step6_canonicalize.py
```

**Input:** `data/interim/v4_standardized_terms_*.txt`  
**Output:** `data/interim/v5_ready_data_*.txt`

---

### Step 7 — Extract concepts  *(local, CPU-heavy)*

Extracts concepts from all lectures jointly using:
- TF-IDF + YAKE keyword scoring
- Double Metaphone phonetic deduplication
- Semantic cosine similarity clustering (`sentence-transformers`)
- Stack Overflow tags (`assets/so_tags.txt`) as anchors

```bash
python src/extraction/step7_extract.py
```

**Input:** `data/interim/v5_ready_data_*.txt`  
**Output:** `data/interim/concepts.json`

---

### Step 8 — Map prerequisite edges  *(local)*

Computes **Reference Distance (RefD)** between concept pairs across lectures to infer prerequisite ordering, then emits directed edges.

```bash
python src/relational_logic/step8_map.py
```

**Input:** `data/interim/concepts.json`  
**Output:** `data/interim/flow_edges.csv`

---

### Step 9 — Serialize outputs  *(local)*

Produces the final deliverables:
- JSON-LD knowledge graph (`pedagogical_flow.jsonld`)
- Interactive `vis.js` HTML dashboard with `tom-select` concept search
- Optional: spaCy `en_core_web_sm` entity linking for `sameAs` enrichment

```bash
python src/output_utils/step9_serialize.py
```

**Input:** `data/interim/concepts.json` + `data/interim/flow_edges.csv`  
**Output:**
- `data/processed/pedagogical_flow.jsonld`
- `data/processed/pedagogical_flow.html`
- `data/processed/pedagogical_flow_lec_N_*.html` (one per lecture)

Open any `.html` file in a browser to explore the interactive graph.

---

## Running Tests

```bash
cd complex
pytest tests/
```

---

## Project Structure

```
complex/
├── assets/          Hand-engineered NLP dictionaries and vocabulary files
├── data/
│   ├── raw/         yt-dlp metadata (Step 1 output)
│   ├── interim/     Versioned intermediate files (Steps 2–8)
│   └── processed/   Final outputs: JSON-LD + HTML (Step 9)
├── lib/             Vendored frontend JS/CSS (vis.js, tom-select)
├── notebooks/       Kaggle GPU transcription notebooks (Step 2)
├── src/
│   ├── audio_processing/   step1_source.py
│   ├── normalization/      step3–6
│   ├── extraction/         step7_extract.py
│   ├── relational_logic/   step8_map.py
│   └── output_utils/       step9_serialize.py
└── requirements.txt
```
