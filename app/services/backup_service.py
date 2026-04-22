from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def make_backup(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"airtable_local_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    target = backup_dir / backup_name
    shutil.copy2(db_path, target)
    return target


def restore_backup(backup_path: Path, db_path: Path) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(f"Файл резервной копии не найден: {backup_path}")
    shutil.copy2(backup_path, db_path)
