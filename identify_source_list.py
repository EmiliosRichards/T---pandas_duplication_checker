import argparse
import os
import re
import csv
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Set, Tuple

import pandas as pd


DEFAULT_PHONE_COLUMNS = [
    "Company Phone",
    "Telefonnummer",
    "Number",
    "$phone",
    "phone",
    "Phone",
    "found_number",
]


@dataclass(frozen=True)
class FilePhones:
    path: str
    phone_columns_used: Tuple[str, ...]
    phone_set: Set[str]  # digits only, no leading '+'


def read_table(path: str) -> pd.DataFrame:
    """
    Reads CSV/XLSX into a DataFrame, with best-effort delimiter detection for CSV.
    All columns are read as strings; blanks stay blank (not NaN) for easier cleaning.
    """
    _, ext = os.path.splitext(path.lower())
    if ext in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    if ext == ".csv":
        # Some vendor exports mix delimiters and/or have malformed quoting.
        # We do a light heuristic on the header line and then pick a safe parser mode.
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            header = f.readline()

        semi = header.count(";")
        comma = header.count(",")

        if semi > comma:
            # Semicolon exports in this repo have been observed with broken quotes.
            # QUOTE_NONE prevents parser errors and keeps quotes as literal characters.
            return pd.read_csv(
                path,
                dtype=str,
                sep=";",
                engine="python",
                keep_default_na=False,
                quoting=csv.QUOTE_NONE,
                on_bad_lines="skip",
            )

        # Comma-separated exports (e.g. Apollo) often contain quoted fields with commas.
        # Use the default quoting behavior.
        return pd.read_csv(
            path,
            dtype=str,
            sep=",",
            engine="python",
            keep_default_na=False,
        )
    raise ValueError(f"Unsupported file type: {path}")


_SPLIT_MULTI_PHONE_RE = re.compile(r"[;\|/]\s*")


def _coerce_scientific_or_float_str(s: str) -> str:
    # Handles e.g. "49123456789.0" or "4.9123456789E+10"
    s = s.strip()
    if not s:
        return s
    if s.endswith(".0"):
        return s[:-2]
    if "e" in s.lower():
        try:
            return f"{int(float(s))}"
        except Exception:
            return s
    return s


def normalize_phone_to_digits(phone_value: object) -> List[str]:
    """
    Normalizes a phone cell to digits-only strings:
    - Keeps country code if present (e.g. +49..., 0049..., 49...)
    - If local leading 0, assumes Germany (+49)
    Returns 0..n phone numbers (some cells contain multiple numbers).
    """
    if phone_value is None:
        return []

    raw = str(phone_value).strip()
    if not raw or raw.lower() in {"nan", "none", "<na>"}:
        return []

    raw = _coerce_scientific_or_float_str(raw)

    # Common “extension” markers can pollute parsing; normalize them to separators.
    # Examples: " +49 ... ext 123", "Durchwahl: 12", "x123"
    raw_for_scan = re.sub(r"(?i)\b(ext|extension|durchwahl|dw)\b[:\.\s-]*\d+\b", " ", raw)
    raw_for_scan = re.sub(r"(?i)\bx\s*\d+\b", " ", raw_for_scan)

    # Instead of splitting on specific delimiters, extract phone-ish substrings robustly.
    # This handles cases where multiple numbers are comma-separated inside a cell.
    # We intentionally keep '+' / '00' / leading '0' patterns in the match.
    candidates = re.findall(r"(?:\+|00)?\d[\d\s\-\(\)\/\.\,]{6,}\d", raw_for_scan)
    if not candidates:
        candidates = [raw_for_scan]

    out: List[str] = []
    seen: Set[str] = set()
    for cand in candidates:
        s = _coerce_scientific_or_float_str(cand).strip()
        if not s:
            continue

        # Keep leading '+' then digits; drop all other characters.
        s_cleaned = re.sub(r"[^\d\+]", "", s)
        if not s_cleaned:
            continue

        if s_cleaned.startswith("00"):
            s_cleaned = "+" + s_cleaned[2:]
        elif s_cleaned.startswith("0") and not s_cleaned.startswith("00"):
            # Assume German local format
            s_cleaned = "+49" + s_cleaned[1:]
        elif not s_cleaned.startswith("+"):
            # Only accept “explicit” country code numbers here; otherwise keep best-effort.
            if re.match(r"^(49|41|43)\d{7,}$", s_cleaned):
                s_cleaned = "+" + s_cleaned
            else:
                s_cleaned = "+" + s_cleaned

        digits_only = re.sub(r"\D", "", s_cleaned)
        if len(digits_only) < 9:
            continue

        if digits_only not in seen:
            seen.add(digits_only)
            out.append(digits_only)

    return out


def detect_phone_columns(df: pd.DataFrame, preferred: Iterable[str]) -> List[str]:
    cols = [c for c in preferred if c in df.columns]
    if cols:
        return cols

    # Fallback: any column that contains 'phone' (case-insensitive)
    phone_like = [c for c in df.columns if isinstance(c, str) and "phone" in c.lower()]
    return phone_like


def extract_phones(path: str, phone_columns: Optional[List[str]]) -> FilePhones:
    df = read_table(path)
    cols = phone_columns or detect_phone_columns(df, DEFAULT_PHONE_COLUMNS)
    cols = [c for c in cols if c in df.columns]
    if not cols:
        raise ValueError(
            f"No phone columns found in {path}. "
            f"Provide --phone-cols or check headers. Columns: {df.columns.tolist()}"
        )

    phone_set: Set[str] = set()
    for col in cols:
        for v in df[col].tolist():
            for p in normalize_phone_to_digits(v):
                phone_set.add(p)

    return FilePhones(path=path, phone_columns_used=tuple(cols), phone_set=phone_set)


def overlap_stats(a: Set[str], b: Set[str]) -> Tuple[int, float, float]:
    """
    Returns (intersection_count, coverage_of_a, jaccard).
    """
    if not a:
        return 0, 0.0, 0.0
    inter = a & b
    union = a | b
    coverage = len(inter) / len(a) if a else 0.0
    jaccard = (len(inter) / len(union)) if union else 0.0
    return len(inter), coverage, jaccard


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare phone-number overlap between one target list and candidate lists, "
            "or produce a pairwise overlap matrix if no target is provided."
        )
    )
    parser.add_argument("--target", help="Path to the actual calling list (optional).")
    parser.add_argument(
        "--candidates",
        nargs="+",
        required=True,
        help="Paths to candidate source lists (one or more).",
    )
    parser.add_argument(
        "--phone-cols",
        nargs="*",
        default=None,
        help="Optional explicit phone column names to use (must exist in each file).",
    )
    parser.add_argument(
        "--output-dir",
        default="comparison_output",
        help="Directory for the overlap report (default: comparison_output).",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(args.output_dir, f"phone_overlap_report_{timestamp}.xlsx")

    files: List[str] = []
    if args.target:
        files.append(args.target)
    files.extend(args.candidates)

    extracted: List[FilePhones] = []
    for p in files:
        extracted.append(extract_phones(p, args.phone_cols))

    # Summary rows
    summary_rows = []
    for fp in extracted:
        summary_rows.append(
            {
                "file": fp.path,
                "phone_columns_used": ", ".join(fp.phone_columns_used),
                "unique_phone_count": len(fp.phone_set),
            }
        )
    df_summary = pd.DataFrame(summary_rows)

    if args.target:
        target_fp = extracted[0]
        candidates_fp = extracted[1:]

        compare_rows = []
        for cand in candidates_fp:
            inter_count, coverage, jaccard = overlap_stats(target_fp.phone_set, cand.phone_set)
            compare_rows.append(
                {
                    "target": target_fp.path,
                    "candidate": cand.path,
                    "target_unique_phones": len(target_fp.phone_set),
                    "candidate_unique_phones": len(cand.phone_set),
                    "intersection_count": inter_count,
                    "coverage_of_target": coverage,
                    "jaccard_similarity": jaccard,
                }
            )
        df_compare = pd.DataFrame(compare_rows).sort_values(
            by=["coverage_of_target", "intersection_count"], ascending=False
        )

        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, index=False, sheet_name="summary")
            df_compare.to_excel(writer, index=False, sheet_name="target_vs_candidates")

        print(f"Wrote overlap report: {out_path}")
        print(df_compare.to_string(index=False))
        return 0

    # Pairwise matrix mode
    names = [fp.path for fp in extracted]
    matrix = pd.DataFrame(index=names, columns=names, dtype=float)
    counts = pd.DataFrame(index=names, columns=names, dtype=int)

    for i, a in enumerate(extracted):
        for j, b in enumerate(extracted):
            inter_count, coverage, jaccard = overlap_stats(a.phone_set, b.phone_set)
            # diagonal will be 1.0 jaccard and full coverage
            matrix.iloc[i, j] = jaccard
            counts.iloc[i, j] = inter_count

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, index=False, sheet_name="summary")
        matrix.to_excel(writer, sheet_name="pairwise_jaccard")
        counts.to_excel(writer, sheet_name="pairwise_intersection_count")

    print(f"Wrote pairwise overlap report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

