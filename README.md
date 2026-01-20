# pandas_duplication_checker

Small utility repo for filtering, deduping, and post-processing lead lists (CSV or Excel) using pandas.

## Setup

```bash
pip install -r requirements.txt
```

## Scripts

### `filter_phone_numbers.py`

Filters rows to **DACH phone numbers only**:
- **Keeps** rows where the formatted primary phone starts with **`+49` (DE), `+41` (CH), or `+43` (AT)**.
- If you provide a **secondary** phone column, rows can be “rescued” if the primary is non‑DACH but the secondary is DACH (the primary column is replaced by the secondary).
- Writes **two outputs**:
  - **kept rows** → your `--output`
  - **removed rows** → same path with `"_removed"` appended before the extension
- **CSV in → CSV out**, **Excel in → Excel out**.
- Before writing, the kept phone values in the primary phone column are **prefixed with a leading apostrophe** (`'`) to help Excel/Sheets treat them as text.

Usage:

```bash
python filter_phone_numbers.py --input "data/input_augmented_5_30_STITCHED.csv" --primary-col "found_number"
```

Optional output + secondary column:

```bash
python filter_phone_numbers.py --input "data/input_augmented_5_30_STITCHED.csv" --output "data/input_augmented_5_30_STITCHED_filtered.csv" --primary-col "found_number" --secondary-col "Secondary_Number_1"
```

### `single_dedupe.py`

Deduplicates a file by **one column**, keeping the first occurrence:
- Writes a **deduped output** file and a **removed duplicates log** file.
- Supports **CSV and Excel**.

Usage (example: dedupe on URL):

```bash
python single_dedupe.py --input "data/input_augmented_5_30_STITCHED_filtered.csv" --dedupe-column "CanonicalEntryURL"
```

If you want explicit output paths:

```bash
python single_dedupe.py --input "data/input_augmented_5_30_STITCHED_filtered.csv" --dedupe-column "CanonicalEntryURL" --output "data/input_augmented_5_30_STITCHED_filtered_deduped.csv" --removed-log "data/input_augmented_5_30_STITCHED_filtered_deduped_removed_log.csv"
```

### `extract_pitch_text.py`

Adds two columns derived from a “sales pitch” column:
- `dynamic_pitch_text`: text between the phrases
  - start: `Ich rufe Sie an, weil wir bereits sehr erfolgreich ein ähnliches Projekt umgesetzt haben`
  - end: `Für dieses`
- `lead_count`: first integer matched by `(\d+)\s+Leads`

Supports **CSV and Excel**. If you don’t provide `--pitch-column`, it will try to auto-detect (e.g. `sales_pitch`).

Usage:

```bash
python extract_pitch_text.py --input "data/input_augmented_5_30_STITCHED_filtered_deduped.csv" --pitch-column "sales_pitch"
```

## End-to-end pipeline (recommended)

From your raw stitched file → filtered to DACH phone numbers → deduped on URL → pitch text extracted:

```bash
# 1) Filter to DACH phones (creates *_filtered.csv and *_filtered_removed.csv)
python filter_phone_numbers.py --input "data/input_augmented_5_30_STITCHED.csv" --primary-col "found_number"

# 2) Dedupe the filtered file (creates *_deduped.csv and *_deduped_removed_log.csv)
python single_dedupe.py --input "data/input_augmented_5_30_STITCHED_filtered.csv" --dedupe-column "CanonicalEntryURL"

# 3) Extract pitch text + lead count (creates *_with_pitch_text.csv)
python extract_pitch_text.py --input "single_output/input_augmented_5_30_STITCHED_filtered_deduped.csv" --pitch-column "sales_pitch"
```

