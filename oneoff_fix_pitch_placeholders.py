import argparse
import csv
import os
import shutil
from typing import Optional, Tuple

import pandas as pd


PLACEHOLDER = "{programmatic placeholder}"


def _sniff_csv_separator(input_file_path: str, default: str = ";") -> str:
    """
    Best-effort delimiter detection (prefers ';' for EU-style CSVs).
    """
    try:
        with open(input_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            header = f.readline()
        if header.count(";") >= header.count(",") and header.count(";") > 0:
            return ";"
        if header.count(",") > 0:
            return ","
    except Exception:
        pass
    return default


def _load_csv(input_file_path: str) -> Tuple[pd.DataFrame, str]:
    sep = _sniff_csv_separator(input_file_path)
    df = pd.read_csv(input_file_path, sep=sep, dtype=str, encoding="utf-8-sig")
    return df, sep


def _format_leads_value(value) -> Optional[str]:
    """
    Convert "Avg Leads Per Day" values like "8.0" -> "8".
    Keeps non-numeric values as stripped strings.
    """
    if value is None or pd.isna(value):
        return None
    s = str(value).strip()
    if s == "":
        return None
    num = pd.to_numeric(pd.Series([s]), errors="coerce").iloc[0]
    if pd.isna(num):
        return s
    # use general format to drop trailing .0 for int-like floats
    return format(float(num), "g")


def main() -> int:
    default_input = (
        "single_output/input_augmented_5_30_STITCHED_filtered_deduped_with_pitch_text.csv"
    )

    parser = argparse.ArgumentParser(
        description=(
            "One-off fix: replace '{programmatic placeholder}' in sales_pitch with the row's "
            "'Avg Leads Per Day' value, and fill missing lead_count with the same value. "
            "Creates a backup before overwriting (unless disabled)."
        )
    )
    parser.add_argument(
        "-i",
        "--input",
        default=default_input,
        help="Input CSV path (semicolon-delimited supported).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path. If omitted, overwrites the input file in-place.",
    )
    parser.add_argument(
        "--pitch-column",
        default="sales_pitch",
        help="Pitch column that contains the placeholder text.",
    )
    parser.add_argument(
        "--avg-leads-column",
        default="Avg Leads Per Day",
        help="Column holding the value that should replace the placeholder.",
    )
    parser.add_argument(
        "--lead-count-column",
        default="lead_count",
        help="Column to fill when missing (will be filled from Avg Leads Per Day).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup file when overwriting in-place.",
    )

    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or input_path

    if not os.path.exists(input_path):
        print(f"Error: input file not found: {input_path}")
        return 1

    # Backup if overwriting
    if os.path.abspath(output_path) == os.path.abspath(input_path) and not args.no_backup:
        base, ext = os.path.splitext(input_path)
        backup_path = f"{base}_backup_before_placeholder_fix{ext or '.csv'}"
        shutil.copy2(input_path, backup_path)
        print(f"Backup created: {backup_path}")

    df, sep = _load_csv(input_path)

    pitch_col = args.pitch_column
    avg_col = args.avg_leads_column
    lead_count_col = args.lead_count_column

    missing_cols = [c for c in [pitch_col, avg_col, lead_count_col] if c not in df.columns]
    if missing_cols:
        print(f"Error: missing required columns: {missing_cols}")
        print(f"Available columns: {df.columns.tolist()}")
        return 1

    # Prepare formatted lead values (as strings)
    formatted_avg = df[avg_col].apply(_format_leads_value)

    # 1) Replace placeholder in pitch
    pitch_series = df[pitch_col].fillna("")
    mask_placeholder = pitch_series.str.contains(r"\{programmatic placeholder\}", regex=True, na=False)
    mask_can_replace = mask_placeholder & formatted_avg.notna()

    replaced_count = 0
    if mask_can_replace.any():
        idxs = df.index[mask_can_replace]
        for i in idxs:
            old_pitch = df.at[i, pitch_col]
            if pd.isna(old_pitch):
                old_pitch = ""
            new_pitch = str(old_pitch).replace(PLACEHOLDER, str(formatted_avg.at[i]))
            if new_pitch != old_pitch:
                df.at[i, pitch_col] = new_pitch
                replaced_count += 1

    # 2) Fill missing lead_count from avg leads
    lead_count_series = df[lead_count_col]
    mask_missing_lead = lead_count_series.isna() | (lead_count_series.astype(str).str.strip() == "")
    mask_fill_lead = mask_missing_lead & formatted_avg.notna()
    filled_lead_count = 0
    if mask_fill_lead.any():
        df.loc[mask_fill_lead, lead_count_col] = formatted_avg.loc[mask_fill_lead]
        filled_lead_count = int(mask_fill_lead.sum())

    # Write output
    df.to_csv(
        output_path,
        index=False,
        sep=sep,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    # Summary
    remaining_placeholders = int(
        df[pitch_col].fillna("").str.contains(r"\{programmatic placeholder\}", regex=True).sum()
    )
    remaining_missing_lead = int(
        (df[lead_count_col].isna() | (df[lead_count_col].astype(str).str.strip() == "")).sum()
    )

    print("\n--- Summary ---")
    print(f"Rows: {len(df)}")
    print(f"Pitch placeholder rows replaced: {replaced_count}")
    print(f"lead_count filled from '{avg_col}': {filled_lead_count}")
    print(f"Remaining placeholder occurrences: {remaining_placeholders}")
    print(f"Remaining missing lead_count rows: {remaining_missing_lead}")
    print(f"Output written: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

