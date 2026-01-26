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
    - remove apostrophes sometimes used for Excel text-protection
    """
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.replace(chr(39), "", regex=False)
    )


def _default_output_path(contacts_path: str) -> str:
    base, ext = os.path.splitext(contacts_path)
    if not ext:
        ext = ".csv"
    return f"{base}_with_description{ext}"


def main() -> int:
    default_contacts = r"data/contacts_2026-01-21T11_07_51 94.csv"
    default_source = r"single_output/input_augmented_5_30_STITCHED_filtered_deduped_with_pitch_text.csv"

    parser = argparse.ArgumentParser(
        description=(
            "One-off: add a lowercase 'description' column to a contacts CSV, "
            "pulling values from a source CSV by matching phone numbers."
        )
    )
    parser.add_argument("--contacts", default=default_contacts, help="Contacts CSV path to update.")
    parser.add_argument(
        "--source",
        default=default_source,
        help="Source CSV path containing the German 'description' column.",
    )
    parser.add_argument(
        "--contacts-phone-col",
        default="Telefonnummer",
        help="Phone column in contacts file.",
    )
    parser.add_argument(
        "--source-phone-col",
        default="found_number",
        help="Phone column in source file.",
    )
    parser.add_argument(
        "--source-description-col",
        default="description",
        help="Description column name in source file (lowercase).",
    )
    parser.add_argument(
        "--output-description-col",
        default="description",
        help="Column name to create in contacts file (default: description).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output path. If omitted, writes <contacts>_with_description.csv.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the contacts file in-place (creates a backup unless --no-backup).",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create a backup when overwriting in-place.",
    )

    args = parser.parse_args()

    contacts_path = args.contacts
    source_path = args.source
    output_path = contacts_path if args.overwrite else (args.output or _default_output_path(contacts_path))

    if not os.path.exists(contacts_path):
        print(f"Error: contacts file not found: {contacts_path}")
        return 1
    if not os.path.exists(source_path):
        print(f"Error: source file not found: {source_path}")
        return 1

    if args.overwrite and not args.no_backup:
        base, ext = os.path.splitext(contacts_path)
        backup_path = f"{base}_backup_before_description_merge{ext or '.csv'}"
        shutil.copy2(contacts_path, backup_path)
        print(f"Backup created: {backup_path}")

    df_contacts, sep_contacts = _load_csv(contacts_path)
    df_source, _sep_source = _load_csv(source_path)

    # Validate columns
    if args.contacts_phone_col not in df_contacts.columns:
        print(f"Error: contacts phone column '{args.contacts_phone_col}' not found.")
        print(f"Contacts columns: {df_contacts.columns.tolist()}")
        return 1
    if args.source_phone_col not in df_source.columns:
        print(f"Error: source phone column '{args.source_phone_col}' not found.")
        print(f"Source columns: {df_source.columns.tolist()}")
        return 1
    if args.source_description_col not in df_source.columns:
        print(f"Error: source description column '{args.source_description_col}' not found.")
        print(f"Source columns: {df_source.columns.tolist()}")
        return 1

    df_contacts = df_contacts.copy()
    df_source = df_source.copy()

    df_contacts["phone_norm"] = _normalize_phone(df_contacts[args.contacts_phone_col])
    df_source["phone_norm"] = _normalize_phone(df_source[args.source_phone_col])

    # Build mapping phone -> description (keep first if duplicates)
    mapping = (
        df_source[["phone_norm", args.source_description_col]]
        .drop_duplicates(subset=["phone_norm"], keep="first")
        .set_index("phone_norm")[args.source_description_col]
    )

    out_col = args.output_description_col
    before = df_contacts[out_col].copy() if out_col in df_contacts.columns else pd.Series([""] * len(df_contacts))

    df_contacts[out_col] = df_contacts["phone_norm"].map(mapping)

    matched = int(df_contacts["phone_norm"].isin(mapping.index).sum())
    filled = int(df_contacts[out_col].fillna("").astype(str).str.strip().ne("").sum())
    changed = int((before.fillna("").astype(str) != df_contacts[out_col].fillna("").astype(str)).sum())

    df_out = df_contacts.drop(columns=["phone_norm"])
    df_out.to_csv(
        output_path,
        index=False,
        sep=sep_contacts,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    print("\n--- Summary ---")
    print(f"Contacts rows: {len(df_out)}")
    print(f"Matched phones: {matched}")
    print(f"Non-empty '{out_col}' after: {filled}")
    print(f"Cells changed (vs previous '{out_col}' if existed): {changed}")
    print(f"Output written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

