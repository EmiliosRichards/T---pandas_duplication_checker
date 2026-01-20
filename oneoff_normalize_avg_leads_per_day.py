import argparse
import csv
import os
import re
import shutil
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

import pandas as pd


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


_RE_ONLY_DIGITS = re.compile(r"^\d+$")
_RE_DOT_DECIMAL = re.compile(r"^\d+\.\d+$")
_RE_COMMA_DECIMAL = re.compile(r"^\d+,\d+$")
_RE_DOT_THOUSANDS_COMMA_DECIMAL = re.compile(r"^\d{1,3}(\.\d{3})+(,\d+)?$")
_RE_COMMA_THOUSANDS_DOT_DECIMAL = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")


def _parse_number_best_effort(raw: str) -> Optional[Decimal]:
    """
    Parse a numeric string that may be in:
    - "8.0" (dot decimal)
    - "8,5" (comma decimal)
    - "1.234,5" (de thousands + de decimal)
    - "1,234.5" (us thousands + dot decimal)
    Returns Decimal or None if not parseable.
    """
    s = raw.strip()
    if s == "":
        return None

    # Normalize spaces
    s = s.replace("\u00A0", "").replace(" ", "")

    if _RE_ONLY_DIGITS.match(s):
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    # "8,5"
    if _RE_COMMA_DECIMAL.match(s):
        try:
            return Decimal(s.replace(",", "."))
        except InvalidOperation:
            return None

    # "8.5"
    if _RE_DOT_DECIMAL.match(s):
        try:
            return Decimal(s)
        except InvalidOperation:
            return None

    # "1.234,5" -> remove '.' thousands, comma -> dot
    if _RE_DOT_THOUSANDS_COMMA_DECIMAL.match(s):
        try:
            s2 = s.replace(".", "").replace(",", ".")
            return Decimal(s2)
        except InvalidOperation:
            return None

    # "1,234.5" -> remove ',' thousands
    if _RE_COMMA_THOUSANDS_DOT_DECIMAL.match(s):
        try:
            s2 = s.replace(",", "")
            return Decimal(s2)
        except InvalidOperation:
            return None

    # Last attempt: if both separators exist, guess right-most is decimal
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        try:
            if last_comma > last_dot:
                # decimal is comma, '.' are thousands
                s2 = s.replace(".", "").replace(",", ".")
            else:
                # decimal is dot, ',' are thousands
                s2 = s.replace(",", "")
            return Decimal(s2)
        except InvalidOperation:
            return None

    # Unknown format
    return None


def _format_decimal_for_de_excel(value: Decimal) -> str:
    """
    Format as a German-Excel-friendly numeric string:
    - no trailing .0
    - comma as decimal separator
    - no thousands separators
    """
    # Normalize removes exponent and trims trailing zeros
    normalized = value.normalize()

    # Decimal('8.0').normalize() can become Decimal('8') which is fine
    s = format(normalized, "f")

    if "." in s:
        int_part, frac_part = s.split(".", 1)
        frac_part = frac_part.rstrip("0")
        if frac_part == "":
            return int_part
        return f"{int_part},{frac_part}"
    return s


def normalize_avg_leads_value(raw_value) -> Optional[str]:
    """
    Normalize raw Avg Leads Per Day value to avoid German-Excel parsing issues:
    - "8.0" -> "8"
    - "5.0" -> "5"
    - "8,5" stays "8,5"
    - "8.5" -> "8,5"
    """
    if raw_value is None or pd.isna(raw_value):
        return None
    s = str(raw_value).strip()
    if s == "":
        return ""

    num = _parse_number_best_effort(s)
    if num is None:
        # Leave unparseable values as-is
        return s
    return _format_decimal_for_de_excel(num)


def main() -> int:
    default_input = "single_output/input_augmented_5_30_STITCHED_filtered_deduped_with_pitch_text.csv"

    parser = argparse.ArgumentParser(
        description=(
            "One-off: normalize 'Avg Leads Per Day' for German-locale Excel CSV import. "
            "Examples: 8.0->8, 8.5->8,5, 8,50->8,5. Creates a backup when overwriting."
        )
    )
    parser.add_argument("-i", "--input", default=default_input, help="Input CSV path.")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path. If omitted, overwrites the input in-place.",
    )
    parser.add_argument(
        "--column",
        default="Avg Leads Per Day",
        help="Column name to normalize.",
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

    if os.path.abspath(output_path) == os.path.abspath(input_path) and not args.no_backup:
        base, ext = os.path.splitext(input_path)
        backup_path = f"{base}_backup_before_avg_leads_normalize{ext or '.csv'}"
        shutil.copy2(input_path, backup_path)
        print(f"Backup created: {backup_path}")

    df, sep = _load_csv(input_path)

    col = args.column
    if col not in df.columns:
        print(f"Error: column not found: '{col}'")
        print(f"Available columns: {df.columns.tolist()}")
        return 1

    before = df[col].copy()
    df[col] = df[col].apply(normalize_avg_leads_value)

    changed = int((before.fillna("") != df[col].fillna("")).sum())

    df.to_csv(
        output_path,
        index=False,
        sep=sep,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    # Quick stats
    remaining_dot_decimal = int(
        df[col].fillna("").astype(str).str.contains(r"\d+\.\d+", regex=True).sum()
    )
    remaining_trailing_dot_zero = int(
        df[col].fillna("").astype(str).str.contains(r"\.0+$", regex=True).sum()
    )

    print("\n--- Summary ---")
    print(f"Rows: {len(df)}")
    print(f"Column normalized: {col}")
    print(f"Cells changed: {changed}")
    print(f"Remaining dot-decimal patterns in column: {remaining_dot_decimal}")
    print(f"Remaining trailing '.0' patterns in column: {remaining_trailing_dot_zero}")
    print(f"Output written: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

