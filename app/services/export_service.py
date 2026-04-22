from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_rows(rows: list[dict], file_path: str) -> None:
    path = Path(file_path)
    df = pd.DataFrame(rows)
    if path.suffix.lower() in [".xlsx", ".xls"]:
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
