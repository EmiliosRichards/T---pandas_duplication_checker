import argparse
import ast
import csv
import json
import os
import re
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd


###############################################################################
# Constants / small utilities
###############################################################################

START_PHRASE = "Ich rufe Sie an, weil wir bereits sehr erfolgreich ein ähnliches Projekt umgesetzt haben"
END_PHRASE = "Für dieses"


def _sniff_csv_separator(input_file_path: str, default: str = ",") -> str:
    """
    Best-effort delimiter detection.

    - Newer stitched outputs in this repo can be comma-delimited.
    - Older stitched outputs can be semicolon-delimited.
    """
    try:
        with open(input_file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            header = f.readline()
        if header.count(",") >= header.count(";") and header.count(",") > 0:
            return ","
        if header.count(";") > 0:
            return ";"
    except Exception:
        pass
    return default


def _load_csv(path: str) -> Tuple[pd.DataFrame, str]:
    sep = _sniff_csv_separator(path)
    # engine='python' is slower but safer with messy quoting/newlines
    df = pd.read_csv(path, sep=sep, dtype=str, encoding="utf-8-sig", engine="python")
    return df, sep


def _write_csv(df: pd.DataFrame, path: str, sep: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    df.to_csv(
        path,
        index=False,
        sep=sep,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )


def _stem(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _strip_suffix(text: str, suffix: str) -> str:
    return text[: -len(suffix)] if text.endswith(suffix) else text


def _join_out(out_dir: str, filename: str) -> str:
    return os.path.join(out_dir, filename) if out_dir else filename


def _default_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _make_unique_run_dir(out_root: str, run_id: str) -> str:
    """
    Create a unique run folder under out_root.
    If the target exists, append _01, _02, ... (to avoid overwriting previous runs).
    """
    base = os.path.join(out_root, run_id) if out_root else run_id
    if not os.path.exists(base):
        return base

    for i in range(1, 1000):
        candidate = f"{base}_{i:02d}"
        if not os.path.exists(candidate):
            return candidate

    # Extremely unlikely fallback
    return f"{base}_{datetime.now().strftime('%f')}"


def _normalize_phone(s: str) -> str:
    """
    Normalize phone-ish strings to something close to E.164.
    (Upstream outputs are usually already +49/+41/+43, but we keep this defensive.)
    """
    if s is None or (isinstance(s, float) and pd.isna(s)) or pd.isna(s):
        return ""
    raw = str(s).strip()
    if raw == "":
        return ""
    # Remove Excel text prefix if present
    if raw.startswith("'"):
        raw = raw[1:].strip()

    # Handle scientific notation / floats
    if "E+" in raw.upper() or "E-" in raw.upper():
        try:
            raw = f"{int(float(raw))}"
        except Exception:
            pass
    if raw.endswith(".0"):
        raw = raw[:-2]

    # Remove separators except leading '+'
    cleaned = re.sub(r"[^\d\+]", "", raw)
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    elif cleaned.startswith("0") and not cleaned.startswith("00"):
        # Assume German local by default
        cleaned = "+49" + cleaned[1:]
    if not cleaned.startswith("+") and cleaned.isdigit():
        cleaned = "+" + cleaned
    return cleaned


def _is_dach(phone: str) -> bool:
    if not phone or not phone.startswith("+"):
        return False
    return phone.startswith("+49") or phone.startswith("+41") or phone.startswith("+43")


def _text_protect(value: str) -> str:
    """
    Prefix with a leading apostrophe so Excel treats it as text.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return ""
    s = str(value).strip()
    if s == "":
        return ""
    if s.startswith("'"):
        return s
    return f"'{s}"


def _normalize_url(url: str) -> str:
    if url is None or (isinstance(url, float) and pd.isna(url)) or pd.isna(url):
        return ""
    s = str(url).strip().lower()
    if s == "":
        return ""
    # remove protocol
    for p in ("https://", "http://"):
        if s.startswith(p):
            s = s[len(p) :]
            break
    # drop common prefix
    if s.startswith("www."):
        s = s[4:]
    # strip trailing slashes
    s = s.rstrip("/")
    return s


def _normalize_company(name: str) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)) or pd.isna(name):
        return ""
    return str(name).strip().lower()


def _parse_json_list_maybe(value) -> List[str]:
    """
    Parse a column that is often a JSON-stringified list. If parsing fails, return [].
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return []
    s = str(value).strip()
    if s == "" or s == "[]":
        return []
    if not (s.startswith("[") and s.endswith("]")):
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        return []
    return []


def _parse_listish(value) -> Optional[list]:
    """
    Try to parse JSON list OR python-repr list (single quotes) into a Python list.
    Returns None if it can't be parsed.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return None
    s = str(value).strip()
    if s == "" or s == "[]":
        return []
    if not (s.startswith("[") and s.endswith("]")):
        return None

    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass

    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        return None

    return None


def _parse_number_list_any(value) -> List[str]:
    """
    Parse "list of numbers" columns that can appear as:
    - JSON list: [\"+49...\", \"+41...\"]
    - Python repr list: ['+49...', '+41...']
    - string with separators: +49...; +41...

    Returns normalized phone strings.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return []
    s = str(value).strip()
    if s == "" or s == "[]":
        return []

    parsed_list = _parse_listish(s)
    if isinstance(parsed_list, list):
        out: List[str] = []
        for x in parsed_list:
            num = _normalize_phone(x)
            if num:
                out.append(num)
        return out

    # Fall back: split by common separators
    parts = [p.strip() for p in re.split(r"[;,]", s) if p.strip()]
    out: List[str] = []
    for p in parts:
        num = _normalize_phone(p)
        if num:
            out.append(num)
    return out


def extract_dynamic_pitch_text(pitch: str) -> str:
    if not isinstance(pitch, str):
        return ""
    if START_PHRASE not in pitch or END_PHRASE not in pitch:
        return ""
    # non-greedy extract between phrases
    try:
        m = re.search(
            f"{re.escape(START_PHRASE)}(.*?){re.escape(END_PHRASE)}",
            pitch,
            flags=re.DOTALL,
        )
        return (m.group(1).strip() if m else "")
    except Exception:
        return ""


def extract_lead_count_from_pitch(pitch: str) -> str:
    """
    Extract the first numeric lead count appearing as "<number> Leads" (case-insensitive).

    Supports integers and simple decimals:
      "8 Leads" -> "8"
      "8.3 Leads" -> "8,3" (German-Excel-safe)
      "8,3 Leads" -> "8,3"
    """
    if not isinstance(pitch, str):
        return ""
    try:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s+Leads\b", pitch, flags=re.IGNORECASE)
        if not m:
            return ""
        return _normalize_decimal_for_german_excel(m.group(1))
    except Exception:
        return ""


###############################################################################
# Decimal normalization for German Excel safety
###############################################################################


def _normalize_decimal_for_german_excel(value) -> str:
    """
    Normalize a numeric-ish value to a German-Excel-safe string:
    - remove trailing .0
    - use comma as decimal separator

    Examples:
      "8.0" -> "8"
      "8.3" -> "8,3"
      "8,50" -> "8,5"

    NOTE: Output is meant for Excel import. If you write comma-delimited CSV,
    values containing a comma will be quoted automatically by pandas.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return ""
    s = str(value).strip()
    if s == "":
        return ""

    # remove spaces
    s = s.replace("\u00A0", "").replace(" ", "")

    # Fast path for plain ints
    if re.fullmatch(r"\d+", s):
        return s

    # If it looks like a decimal with comma: keep, but trim trailing zeros
    if re.fullmatch(r"\d+,\d+", s):
        int_part, frac = s.split(",", 1)
        frac = frac.rstrip("0")
        return int_part if frac == "" else f"{int_part},{frac}"

    # Dot decimal: convert to comma, trim trailing zeros
    if re.fullmatch(r"\d+\.\d+", s):
        int_part, frac = s.split(".", 1)
        frac = frac.rstrip("0")
        return int_part if frac == "" else f"{int_part},{frac}"

    # Otherwise: try numeric parsing and reformat
    try:
        # Handle "1.234,5" and "1,234.5" best-effort by picking the last separator as decimal
        if "," in s and "." in s:
            last_comma = s.rfind(",")
            last_dot = s.rfind(".")
            if last_comma > last_dot:
                # decimal comma, '.' thousands
                s2 = s.replace(".", "").replace(",", ".")
            else:
                # decimal dot, ',' thousands
                s2 = s.replace(",", "")
        else:
            s2 = s.replace(",", ".")

        num = pd.to_numeric(pd.Series([s2]), errors="coerce").iloc[0]
        if pd.isna(num):
            return s
        # general format to remove trailing .0, then convert '.' to ','
        out = format(float(num), "g")
        if "." in out:
            out = out.replace(".", ",")
        return out
    except Exception:
        return s


###############################################################################
# Phone selection
###############################################################################


@dataclass
class SelectedNumber:
    number: str
    source: str  # which source slot (e.g., "Top_1", "Top_2", "MainOffice")
    type_value: str
    source_url: str
    person_name: str = ""
    person_role: str = ""
    person_department: str = ""


def _is_fax_type(type_value: str) -> bool:
    if not type_value:
        return False
    t = str(type_value).strip().lower()
    return ("fax" in t) or ("telefax" in t)


def _parse_json_list_of_dicts_maybe(value) -> List[dict]:
    """
    Parse a column that is often a JSON-stringified list of dicts.
    Returns [] if parsing fails.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return []
    s = str(value).strip()
    if s == "" or s == "[]":
        return []
    if not (s.startswith("[") and s.endswith("]")):
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
    except Exception:
        return []
    return []


def _build_number_metadata_lookup(row: pd.Series) -> Dict[str, dict]:
    """
    Build lookup from normalized number -> metadata.

    Sources:
    - LLMExtractedNumbers (often contains associated_person_* and source_url/type)
    - PersonContacts (best-effort JSON list of people with numbers)
    - BestPersonContact* (single best contact)
    """
    lookup: Dict[str, dict] = {}

    # 1) LLMExtractedNumbers
    for item in _parse_json_list_of_dicts_maybe(row.get("LLMExtractedNumbers")):
        num = _normalize_phone(item.get("number", ""))
        if not num:
            continue
        lookup.setdefault(num, {})
        # keep first non-empty values
        for k in [
            "type",
            "source_url",
            "associated_person_name",
            "associated_person_role",
            "associated_person_department",
        ]:
            v = item.get(k)
            if v is None:
                continue
            v = str(v).strip()
            if v and not lookup[num].get(k):
                lookup[num][k] = v

    # 2) PersonContacts (varies by upstream; try common keys)
    for item in _parse_json_list_of_dicts_maybe(row.get("PersonContacts")):
        num = _normalize_phone(item.get("number") or item.get("phone") or item.get("phone_number") or "")
        if not num:
            continue
        lookup.setdefault(num, {})
        name = str(item.get("name") or item.get("full_name") or "").strip()
        role = str(item.get("role") or item.get("title") or "").strip()
        dept = str(item.get("department") or "").strip()
        if name and not lookup[num].get("associated_person_name"):
            lookup[num]["associated_person_name"] = name
        if role and not lookup[num].get("associated_person_role"):
            lookup[num]["associated_person_role"] = role
        if dept and not lookup[num].get("associated_person_department"):
            lookup[num]["associated_person_department"] = dept

    # 3) BestPersonContact*
    best_num = _normalize_phone(row.get("BestPersonContactNumber", ""))
    if best_num:
        lookup.setdefault(best_num, {})
        name = str(row.get("BestPersonContactName", "") or "").strip()
        role = str(row.get("BestPersonContactRole", "") or "").strip()
        dept = str(row.get("BestPersonContactDepartment", "") or "").strip()
        if name and not lookup[best_num].get("associated_person_name"):
            lookup[best_num]["associated_person_name"] = name
        if role and not lookup[best_num].get("associated_person_role"):
            lookup[best_num]["associated_person_role"] = role
        if dept and not lookup[best_num].get("associated_person_department"):
            lookup[best_num]["associated_person_department"] = dept

    return lookup


def select_first_call_and_mainline(row: pd.Series) -> Tuple[Optional[SelectedNumber], Optional[SelectedNumber], Optional[SelectedNumber]]:
    """
    User requirement:
    - prioritize Top_Number_1..3 for first_call; if Top_1 isn't DACH, try Top_2 then Top_3
    - main line backup is ONLY MainOffice_Number (not "Top" even if Top is a main line)
    - if no DACH in Top_1..3, then try MainOffice_Number (DACH only)
    - if still none, try OtherRelevantNumbers (pick best DACH; attach person metadata if available)
    - if still none, try Company Phone (best-effort); type should be marked as an input fallback
    - never select anything in SuspectedOtherOrgNumbers
    - never select fax-type numbers
    """
    # SuspectedOtherOrgNumbers can be JSON list, python-list string, or ';'-separated
    suspected = set(_parse_number_list_any(row.get("SuspectedOtherOrgNumbers")))
    meta = _build_number_metadata_lookup(row)

    def ok(phone: str, type_value: str, require_dach: bool = True) -> bool:
        if not phone:
            return False
        if _is_fax_type(type_value):
            return False
        if phone in suspected:
            return False
        return (_is_dach(phone) if require_dach else True)

    def with_person_fields(sel: SelectedNumber) -> SelectedNumber:
        info = meta.get(sel.number, {})
        name = str(info.get("associated_person_name", "") or "").strip()
        role = str(info.get("associated_person_role", "") or "").strip()
        dept = str(info.get("associated_person_department", "") or "").strip()
        sel.person_name = name
        sel.person_role = role
        sel.person_department = dept
        return sel

    # Top list (first call)
    top_slots: List[Tuple[str, str, str, str]] = [
        ("Top_1", row.get("Top_Number_1", ""), row.get("Top_Type_1", ""), row.get("Top_SourceURL_1", "")),
        ("Top_2", row.get("Top_Number_2", ""), row.get("Top_Type_2", ""), row.get("Top_SourceURL_2", "")),
        ("Top_3", row.get("Top_Number_3", ""), row.get("Top_Type_3", ""), row.get("Top_SourceURL_3", "")),
    ]

    first_call: Optional[SelectedNumber] = None
    for slot, num_raw, type_val, src_url in top_slots:
        num = _normalize_phone(num_raw)
        if ok(num, type_val, require_dach=True):
            first_call = with_person_fields(
                SelectedNumber(number=num, source=slot, type_value=str(type_val or ""), source_url=str(src_url or ""))
            )
            break

    # Main line backup (strictly from MainOffice)
    main_office: Optional[SelectedNumber] = None
    mo_num = _normalize_phone(row.get("MainOffice_Number", ""))
    mo_type = str(row.get("MainOffice_Type", "") or "")
    mo_url = str(row.get("MainOffice_SourceURL", "") or "")
    if ok(mo_num, mo_type, require_dach=True):
        main_office = with_person_fields(
            SelectedNumber(number=mo_num, source="MainOffice", type_value=mo_type, source_url=mo_url)
        )

    # If there is no Top_* DACH number, try main office as first call
    if first_call is None and main_office is not None:
        first_call = main_office

    # If still none: try OtherRelevantNumbers (DACH only)
    if first_call is None and "OtherRelevantNumbers" in row.index:
        candidates = _parse_number_list_any(row.get("OtherRelevantNumbers"))

        # Prefer person-associated DACH numbers if present
        def candidate_score(num: str) -> int:
            info = meta.get(num, {})
            has_person = bool(str(info.get("associated_person_name", "") or "").strip())
            return 10 if has_person else 0

        candidates_sorted = sorted(candidates, key=candidate_score, reverse=True)
        for num in candidates_sorted:
            if not num:
                continue
            # type/source url from metadata when possible; otherwise label as "Other Relevant"
            info = meta.get(num, {})
            t = str(info.get("type", "") or "Other Relevant").strip() or "Other Relevant"
            u = str(info.get("source_url", "") or "").strip()
            if ok(num, t, require_dach=True):
                first_call = with_person_fields(
                    SelectedNumber(number=num, source="OtherRelevant", type_value=t, source_url=u)
                )
                break

    # If still none: try Company Phone (prefer DACH if possible; final fallback even if non-DACH)
    if first_call is None:
        raw = row.get("Company Phone", "")
        num = _normalize_phone(raw)
        if num and ok(num, "Input Backup", require_dach=True):
            first_call = with_person_fields(
                SelectedNumber(number=num, source="CompanyPhone", type_value="Input Backup", source_url="")
            )
        elif num and ok(num, "Input Backup", require_dach=False):
            # no DACH anywhere; keep row but clearly label this as an input fallback
            first_call = with_person_fields(
                SelectedNumber(number=num, source="CompanyPhone", type_value="Input Backup", source_url="")
            )

    # Final fallback: PhoneNumber (some files have this populated even when Company Phone is blank)
    if first_call is None:
        raw = row.get("PhoneNumber", "")
        num = _normalize_phone(raw)
        if num and ok(num, "Input Backup", require_dach=True):
            first_call = with_person_fields(
                SelectedNumber(number=num, source="PhoneNumber", type_value="Input Backup", source_url="")
            )
        elif num and ok(num, "Input Backup", require_dach=False):
            first_call = with_person_fields(
                SelectedNumber(number=num, source="PhoneNumber", type_value="Input Backup", source_url="")
            )

    # Backup number only needed when mainline == Top_1 specifically (your preference)
    backup: Optional[SelectedNumber] = None
    if (
        first_call
        and main_office
        and first_call.source == "Top_1"
        and first_call.number == main_office.number
    ):
        # backup should be Top_2, then Top_3, not equal to first_call
        for slot, num_raw, type_val, src_url in top_slots[1:]:
            num = _normalize_phone(num_raw)
            if num and num != first_call.number and ok(num, type_val, require_dach=True):
                backup = with_person_fields(
                    SelectedNumber(number=num, source=slot, type_value=str(type_val or ""), source_url=str(src_url or ""))
                )
                break

    return first_call, main_office, backup


###############################################################################
# Dedupe scoring and review mechanics
###############################################################################


def build_dedupe_key(df: pd.DataFrame) -> pd.Series:
    company = df.get("CompanyName", pd.Series([""] * len(df))).apply(_normalize_company)
    url = df.get("CanonicalEntryURL", pd.Series([""] * len(df))).fillna("").astype(str)
    given = df.get("GivenURL", pd.Series([""] * len(df))).fillna("").astype(str)
    use_url = url.where(url.str.strip().ne(""), given)
    url_norm = use_url.apply(_normalize_url)
    return company + "||" + url_norm


def score_row(row: pd.Series) -> int:
    """
    Higher is better:
    - having a valid DACH first-call number is most important
    - having a valid DACH main line is next
    - having a sales pitch is a mild tie-breaker (doesn't filter)
    """
    first_call, main_line, _backup = select_first_call_and_mainline(row)
    s = 0
    if first_call:
        s += 100
    if main_line:
        s += 50
    if str(row.get("sales_pitch", "") or "").strip():
        s += 10
    return s


def apply_recommendations(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["dedupe_key"] = build_dedupe_key(df)
    df["dedupe_group_size"] = df.groupby("dedupe_key")["dedupe_key"].transform("size")
    df["review_needed"] = df["dedupe_group_size"] > 1

    # Recommended keep = max score within group (first occurrence if tie)
    scores = df.apply(score_row, axis=1)
    df["_dedupe_score"] = scores
    df["recommended_keep"] = False

    for key, idxs in df.groupby("dedupe_key").groups.items():
        idx_list = list(idxs)
        if len(idx_list) == 1:
            df.loc[idx_list[0], "recommended_keep"] = True
            continue
        best_idx = df.loc[idx_list, "_dedupe_score"].astype(int).idxmax()
        df.loc[best_idx, "recommended_keep"] = True

    # Manual review columns (user fills in Excel)
    if "review_keep" not in df.columns:
        df["review_keep"] = ""
    if "review_drop" not in df.columns:
        df["review_drop"] = ""
    if "review_notes" not in df.columns:
        df["review_notes"] = ""

    return df


def _truthy_cell(v) -> bool:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return False
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y", "x", "keep", "k")


def resolve_keep_mask(df: pd.DataFrame) -> pd.Series:
    """
    Resolve the final keep mask from manual review fields:
    - If any row in a dedupe group has review_keep truthy: keep those, drop others.
    - Else: keep the recommended_keep row.
    - review_drop truthy always forces drop.
    """
    df = df.copy()
    keep = pd.Series([False] * len(df), index=df.index)

    for key, idxs in df.groupby("dedupe_key").groups.items():
        idxs = list(idxs)
        group = df.loc[idxs]
        any_manual_keep = group["review_keep"].apply(_truthy_cell).any()
        if any_manual_keep:
            keep.loc[idxs] = group["review_keep"].apply(_truthy_cell).values
        else:
            keep.loc[idxs] = group["recommended_keep"].astype(bool).values

        # Force drops
        forced_drop = group["review_drop"].apply(_truthy_cell)
        if forced_drop.any():
            keep.loc[idxs] = keep.loc[idxs] & (~forced_drop.values)

    return keep


###############################################################################
# Main pipeline behaviors
###############################################################################


def add_operational_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    first_calls: List[str] = []
    first_types: List[str] = []
    first_urls: List[str] = []
    main_lines: List[str] = []
    main_types: List[str] = []
    main_urls: List[str] = []
    backup_nums: List[str] = []
    backup_types: List[str] = []
    backup_urls: List[str] = []
    first_person_names: List[str] = []
    first_person_roles: List[str] = []
    first_person_departments: List[str] = []

    for _, row in df.iterrows():
        first_call, main_line, backup = select_first_call_and_mainline(row)

        def tp(x: Optional[SelectedNumber]) -> Tuple[str, str, str]:
            if not x:
                return "", "", ""
            return _text_protect(x.number), str(x.type_value or ""), str(x.source_url or "")

        fc_num, fc_type, fc_url = tp(first_call)
        ml_num, ml_type, ml_url = tp(main_line)
        bk_num, bk_type, bk_url = tp(backup)

        first_calls.append(fc_num)
        first_types.append(fc_type)
        first_urls.append(fc_url)
        first_person_names.append(first_call.person_name if first_call else "")
        first_person_roles.append(first_call.person_role if first_call else "")
        first_person_departments.append(first_call.person_department if first_call else "")
        main_lines.append(ml_num)
        main_types.append(ml_type)
        main_urls.append(ml_url)
        backup_nums.append(bk_num)
        backup_types.append(bk_type)
        backup_urls.append(bk_url)

    df["first_call_number"] = first_calls
    df["first_call_type"] = first_types
    df["first_call_source_url"] = first_urls
    df["first_call_person_name"] = first_person_names
    df["first_call_person_role"] = first_person_roles
    df["first_call_person_department"] = first_person_departments

    df["main_line_backup_number"] = main_lines
    df["main_line_backup_type"] = main_types
    df["main_line_backup_source_url"] = main_urls

    # only populated when mainline == first_call_number (per your preference)
    df["backup_number_if_mainline_top1"] = backup_nums
    df["backup_number_type"] = backup_types
    df["backup_number_source_url"] = backup_urls

    # Sales pitch excerpt: dynamic part between standard phrases
    df["sales_pitch_excerpt"] = df.get("sales_pitch", pd.Series([""] * len(df))).apply(
        lambda x: extract_dynamic_pitch_text(x if isinstance(x, str) else "")
    )
    # Lead count extracted from the pitch text (placed next to excerpt)
    df["sales_pitch_lead_count"] = df.get("sales_pitch", pd.Series([""] * len(df))).apply(
        lambda x: extract_lead_count_from_pitch(x if isinstance(x, str) else "")
    )

    # Normalize common numeric columns to German-Excel-safe format (no dot decimals)
    # This prevents dot-decimals like "8.2" being interpreted as "82" in some Excel locales.
    decimal_columns = [
        "Avg Leads Per Day",
        "lead_count",
        "model_score",
        "cost_usd",
        "token_cost_usd",
        "sales_pitch_lead_count",
    ]
    for col in decimal_columns:
        if col in df.columns:
            df[col] = df[col].apply(_normalize_decimal_for_german_excel)

    return df


def filter_no_usable_phone(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Drop rows with no usable phone at all (Top_1..3, MainOffice, OtherRelevantNumbers, Company Phone).

    Note: We no longer drop purely because no DACH exists; if no DACH exists anywhere,
    we still keep a row if Company Phone exists (labeled as "Input Backup").
    """
    keep_mask = []
    for _, row in df.iterrows():
        first_call, main_line, _backup = select_first_call_and_mainline(row)
        keep_mask.append(bool(first_call or main_line))
    keep_mask = pd.Series(keep_mask, index=df.index)
    return df[keep_mask].copy(), df[~keep_mask].copy()


def generate_review(input_path: str, out_review_path: str, out_suggested_path: Optional[str] = None) -> Dict[str, int]:
    df, in_sep = _load_csv(input_path)

    # Always output comma-delimited per your preference
    out_sep = ","

    df = apply_recommendations(df)
    df = add_operational_columns(df)

    _write_csv(df, out_review_path, out_sep)

    summary = {
        "input_rows": int(len(df)),
        "dedupe_groups": int(df["dedupe_key"].nunique()),
        "rows_with_review_needed": int(df["review_needed"].sum()) if "review_needed" in df.columns else 0,
    }

    if out_suggested_path:
        keep = resolve_keep_mask(df)
        df_kept = df[keep].copy()
        df_kept, df_no_phone = filter_no_usable_phone(df_kept)
        # Suggested output should be "ops ready" (drop review/helper columns)
        drop_cols = [
            "dedupe_key",
            "dedupe_group_size",
            "review_needed",
            "_dedupe_score",
            "recommended_keep",
            "review_keep",
            "review_drop",
            "review_notes",
        ]
        df_kept = df_kept.drop(columns=[c for c in drop_cols if c in df_kept.columns])
        df_no_phone = df_no_phone.drop(columns=[c for c in drop_cols if c in df_no_phone.columns])

        _write_csv(df_kept, out_suggested_path, out_sep)
        if len(df_no_phone) > 0:
            base, ext = os.path.splitext(out_suggested_path)
            _write_csv(df_no_phone, f"{base}_dropped_no_usable_phone{ext or '.csv'}", out_sep)
        summary["suggested_rows_kept"] = int(len(df_kept))
        summary["suggested_rows_dropped_no_usable_phone"] = int(len(df_no_phone))
        summary["suggested_rows_dropped_no_dach"] = int(len(df_no_phone))  # backwards-compatible key

    return summary


def apply_review(review_path: str, out_final_path: str) -> Dict[str, int]:
    df, _sep_in = _load_csv(review_path)
    out_sep = ","

    # Ensure required columns exist; if user edited file externally, recompute what we need.
    df = apply_recommendations(df)
    df = add_operational_columns(df)

    keep = resolve_keep_mask(df)
    df_kept = df[keep].copy()
    df_kept, df_no_phone = filter_no_usable_phone(df_kept)

    # Final output should be "ops ready" (drop review/helper columns)
    drop_cols = [
        "dedupe_key",
        "dedupe_group_size",
        "review_needed",
        "_dedupe_score",
        "recommended_keep",
        "review_keep",
        "review_drop",
        "review_notes",
    ]
    df_kept = df_kept.drop(columns=[c for c in drop_cols if c in df_kept.columns])
    df_no_phone = df_no_phone.drop(columns=[c for c in drop_cols if c in df_no_phone.columns])

    _write_csv(df_kept, out_final_path, out_sep)
    if len(df_no_phone) > 0:
        base, ext = os.path.splitext(out_final_path)
        _write_csv(df_no_phone, f"{base}_dropped_no_usable_phone{ext or '.csv'}", out_sep)

    return {
        "review_rows": int(len(df)),
        "kept_after_dedupe": int(len(df_kept) + len(df_no_phone)),
        "dropped_no_usable_phone": int(len(df_no_phone)),
        "dropped_no_dach": int(len(df_no_phone)),  # backwards-compatible key
        "final_rows": int(len(df_kept)),
    }


###############################################################################
# CLI
###############################################################################


def main() -> int:
    parser = argparse.ArgumentParser(description="Ops prep pipeline: review + apply.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate-review", help="Generate a manual review CSV (with recommendations).")
    gen.add_argument("-i", "--input", required=True, help="Input stitched CSV path.")
    gen.add_argument(
        "--out-dir",
        default="ops_output",
        help="Ops output ROOT folder. Each run gets its own subfolder (default: ops_output).",
    )
    gen.add_argument(
        "--run-id",
        default=None,
        help="Optional run id for the run folder (default: timestamp).",
    )
    gen.add_argument(
        "--review-out",
        default=None,
        help="Review CSV output path. Default: <input>_ops_review.csv",
    )
    gen.add_argument(
        "--suggested-out",
        default=None,
        help="Optional: also write an auto-suggested final output using recommendations.",
    )

    app = sub.add_parser("apply-review", help="Apply a reviewed CSV and write final output.")
    app.add_argument("--review", required=True, help="Reviewed CSV path (generated by generate-review).")
    app.add_argument(
        "--out-dir",
        default="ops_output",
        help="Ops output ROOT folder (used only if --run-id is provided). Default: ops_output.",
    )
    app.add_argument(
        "--run-id",
        default=None,
        help=(
            "Optional run id to force outputs into ops_output/<run-id>/ even if the review file "
            "is elsewhere. If omitted, outputs go next to the review file."
        ),
    )
    app.add_argument(
        "--final-out",
        default=None,
        help="Final output path. Default: <review>_ops_final.csv",
    )

    args = parser.parse_args()

    if args.cmd == "generate-review":
        out_root = args.out_dir or ""
        if out_root:
            os.makedirs(out_root, exist_ok=True)

        run_id = (args.run_id or "").strip() or _default_run_id()
        run_dir = _make_unique_run_dir(out_root, run_id)
        os.makedirs(run_dir, exist_ok=True)

        review_out = args.review_out
        if not review_out:
            review_out = _join_out(run_dir, f"{_stem(args.input)}_ops_review.csv")

        suggested_out = args.suggested_out
        if suggested_out is not None and suggested_out.strip() == "":
            suggested_out = None
        if suggested_out is None:
            # Default suggested location if user didn't provide one
            suggested_out = _join_out(run_dir, f"{_stem(args.input)}_ops_suggested.csv")

        summary = generate_review(args.input, review_out, suggested_out)
        summary_path = os.path.splitext(review_out)[0] + "_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        run_info = {
            "run_id": os.path.basename(run_dir),
            "run_dir": os.path.abspath(run_dir),
            "input": os.path.abspath(args.input),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "review_csv": os.path.abspath(review_out),
            "suggested_csv": os.path.abspath(suggested_out) if suggested_out else None,
        }
        run_info_path = os.path.join(run_dir, "RUN_INFO.json")
        with open(run_info_path, "w", encoding="utf-8") as f:
            json.dump(run_info, f, indent=2)

        print(f"Run folder: {run_dir}")
        print(f"Wrote review: {review_out}")
        print(f"Wrote summary: {summary_path}")
        if suggested_out:
            print(f"Wrote suggested: {suggested_out}")
        print(f"Wrote run info: {run_info_path}")
        return 0

    if args.cmd == "apply-review":
        # Default: write final outputs next to the review file (same run folder).
        # If --run-id is provided, force outputs into <out-dir>/<run-id>/.
        if args.run_id and str(args.run_id).strip():
            out_root = args.out_dir or ""
            if out_root:
                os.makedirs(out_root, exist_ok=True)
            run_dir = os.path.join(out_root, str(args.run_id).strip())
            os.makedirs(run_dir, exist_ok=True)
        else:
            run_dir = os.path.dirname(args.review) or "."

        final_out = args.final_out
        if not final_out:
            base = _stem(args.review)
            base = _strip_suffix(base, "_ops_review")
            final_out = _join_out(run_dir, f"{base}_ops_final.csv")
        summary = apply_review(args.review, final_out)
        summary_path = os.path.splitext(final_out)[0] + "_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Update / write run info next to outputs (best-effort)
        run_info_path = os.path.join(run_dir, "RUN_INFO.json")
        run_info = {
            "run_id": os.path.basename(run_dir),
            "run_dir": os.path.abspath(run_dir),
            "review_csv": os.path.abspath(args.review),
            "final_csv": os.path.abspath(final_out),
            "applied_at": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            with open(run_info_path, "w", encoding="utf-8") as f:
                json.dump(run_info, f, indent=2)
        except Exception:
            pass

        print(f"Run folder: {run_dir}")
        print(f"Wrote final: {final_out}")
        print(f"Wrote summary: {summary_path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

