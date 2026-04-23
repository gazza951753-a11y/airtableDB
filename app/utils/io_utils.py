import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import chardet
import pandas as pd
from dateutil import parser


def detect_encoding(file_path: Path) -> str:
    raw = file_path.read_bytes()[:100_000]
    detected = chardet.detect(raw)
    return detected.get("encoding") or "utf-8"


def detect_separator(file_path: Path, encoding: str) -> str:
    sample = file_path.read_text(encoding=encoding, errors="replace")[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
        return dialect.delimiter
    except Exception:
        return ";" if sample.count(";") > sample.count(",") else ","


def read_tabular_file(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in [".xlsx", ".xlsm", ".xls"]:
        return pd.read_excel(path, engine="openpyxl")

    if suffix == ".csv":
        encoding = detect_encoding(path)
        sep = detect_separator(path, encoding)
        return pd.read_csv(path, encoding=encoding, sep=sep)

    raise ValueError(f"Неподдерживаемый формат файла: {suffix}")


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def split_multi_value(value: Any) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    parts = re.split(r"[;,\n|]+", text)
    return [p.strip() for p in parts if p.strip()]


def parse_date(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        dt = parser.parse(text, dayfirst=True)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def to_float(value: Any) -> float | None:
    text = normalize_text(value).replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
