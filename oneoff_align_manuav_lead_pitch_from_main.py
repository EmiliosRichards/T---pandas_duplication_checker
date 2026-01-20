import argparse
import csv
import os
import shutil
from typing import Tuple

import pandas as pd


def _sniff_csv_separator(input_file_path: str, default: str = ";") -> str:
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


def _load_csv(path: str) -> Tuple[pd.DataFrame, str]:
    sep = _sniff_csv_separator(path)
    return pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig"), sep


def _normalize_phone(series: pd.Series) -> pd.Series:
    """
    Normalize phone numbers for joining:
    - strip whitespace
    - remove leading apostrophes sometimes used for Excel text-protection
    """
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(chr(39), "", regex=False)
    )


def main() -> int:
    default_main = "single_output/input_augmented_5_30_STITCHED_filtered_deduped_with_pitch_text.csv"
    default_manu = "data/manuav_008_500_spgpece_apolsc.csv"

    parser = argparse.ArgumentParser(
        description=(
            "One-off: align a manuav export by replacing its Lead_Pitch column with values "
            "from the main output file (joined by phone number). Creates a backup when overwriting."
        )
    )
    parser.add_argument("--main", default=default_main, help="Main (source) CSV path.")
    parser.add_argument("--manuav", default=default_manu, help="Manuav (target) CSV path.")
    parser.add_argument(
        "--main-phone-col",
        default="found_number",
        help="Phone column in the main file.",
    )
    parser.add_argument(
        "--manuav-phone-col",
        default="Telefonnummer",
        help="Phone column in the manuav file.",
    )
    parser.add_argument(
        "--main-value-col",
        default="Avg Leads Per Day",
        help="Value column in the main file to copy from.",
    )
    parser.add_argument(
        "--manuav-target-col",
        default="Lead_Pitch",
        help="Target column in the manuav file to overwrite.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path. If omitted, overwrites the manuav file in-place.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup when overwriting in-place.",
    )

    args = parser.parse_args()

    main_path = args.main
    manuav_path = args.manuav
    output_path = args.output or manuav_path

    if not os.path.exists(main_path):
        print(f"Error: main file not found: {main_path}")
        return 1
    if not os.path.exists(manuav_path):
        print(f"Error: manuav file not found: {manuav_path}")
        return 1

    if os.path.abspath(output_path) == os.path.abspath(manuav_path) and not args.no_backup:
        base, ext = os.path.splitext(manuav_path)
        backup_path = f"{base}_backup_before_align{ext or '.csv'}"
        shutil.copy2(manuav_path, backup_path)
        print(f"Backup created: {backup_path}")

    df_main, _sep_main = _load_csv(main_path)
    df_manu, sep_manu = _load_csv(manuav_path)

    # Validate columns
    for c in [args.main_phone_col, args.main_value_col]:
        if c not in df_main.columns:
            print(f"Error: column '{c}' not found in main file.")
            print(f"Main columns: {df_main.columns.tolist()}")
            return 1
    for c in [args.manuav_phone_col, args.manuav_target_col]:
        if c not in df_manu.columns:
            print(f"Error: column '{c}' not found in manuav file.")
            print(f"Manuav columns: {df_manu.columns.tolist()}")
            return 1

    df_main = df_main.copy()
    df_manu = df_manu.copy()

    df_main["phone_norm"] = _normalize_phone(df_main[args.main_phone_col])
    df_manu["phone_norm"] = _normalize_phone(df_manu[args.manuav_phone_col])

    # Build mapping phone -> value (keep first if duplicates)
    mapping = (
        df_main[["phone_norm", args.main_value_col]]
        .drop_duplicates(subset=["phone_norm"], keep="first")
        .set_index("phone_norm")[args.main_value_col]
    )

    before = df_manu[args.manuav_target_col].copy()
    df_manu[args.manuav_target_col] = df_manu["phone_norm"].map(mapping)

    changed = int((before.fillna("") != df_manu[args.manuav_target_col].fillna("")).sum())
    matched = int(df_manu["phone_norm"].isin(mapping.index).sum())
    nonempty_after = int(
        df_manu[args.manuav_target_col].fillna("").astype(str).str.strip().ne("").sum()
    )

    df_out = df_manu.drop(columns=["phone_norm"])
    df_out.to_csv(
        output_path,
        index=False,
        sep=sep_manu,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    print("\n--- Summary ---")
    print(f"Rows: {len(df_out)}")
    print(f"Matched rows by phone: {matched}")
    print(f"Target column overwritten: {args.manuav_target_col}")
    print(f"Cells changed: {changed}")
    print(f"Non-empty '{args.manuav_target_col}' after: {nonempty_after}")
    print(f"Output written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

