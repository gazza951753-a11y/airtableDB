from pathlib import Path

from app.config import DEFAULT_STATUSES
from app.db.database import Database


def init_db(db: Database, schema_path: Path) -> None:
    """Инициализирует схему и базовые справочники при первом запуске."""
    schema_sql = schema_path.read_text(encoding="utf-8")
    with db.transaction():
        db.conn.executescript(schema_sql)
        for status in DEFAULT_STATUSES:
            db.execute(
                "INSERT OR IGNORE INTO statuses(name) VALUES(?)",
                (status,),
            )
