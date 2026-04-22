from pathlib import Path

from app.config import DEFAULT_STATUSES
from app.db.database import Database
<<<<<<< HEAD
=======
from app.db.schema_fallback import DEFAULT_SCHEMA_SQL
>>>>>>> origin/codex/develop-desktop-application-for-windows-lp0n7x


def _table_has_fk_to_equipment(db: Database, table_name: str) -> bool:
    rows = db.query_all(f"PRAGMA foreign_key_list({table_name})")
    return any((row["table"] == "equipment") for row in rows)


def _migrate_remove_equipment_fk_from_movements(db: Database) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS movements_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_date TEXT NOT NULL,
            serial_number TEXT NOT NULL,
            inventory_number TEXT,
            from_location TEXT,
            to_location TEXT,
            comment TEXT,
            source_file TEXT,
            source_row_id TEXT,
            import_batch_id INTEGER,
            fingerprint TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL
        );

        INSERT OR IGNORE INTO movements_new(
            id, movement_date, serial_number, inventory_number, from_location, to_location,
            comment, source_file, source_row_id, import_batch_id, fingerprint, created_at, updated_at
        )
        SELECT
            id, movement_date, serial_number, inventory_number, from_location, to_location,
            comment, source_file, source_row_id, import_batch_id, fingerprint, created_at, updated_at
        FROM movements;

        DROP TABLE movements;
        ALTER TABLE movements_new RENAME TO movements;

        CREATE INDEX IF NOT EXISTS idx_movements_serial ON movements(serial_number);
        CREATE INDEX IF NOT EXISTS idx_movements_date ON movements(movement_date);

        CREATE TRIGGER IF NOT EXISTS trg_movements_updated_at
        AFTER UPDATE ON movements
        BEGIN
            UPDATE movements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END;
        """
    )


def _migrate_remove_equipment_fk_from_trip_equipment(db: Database) -> None:
    db.conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS trip_equipment_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trip_id INTEGER NOT NULL,
            serial_number TEXT,
            inventory_number TEXT,
            equipment_name TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trip_id, serial_number),
            FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE CASCADE
        );

        INSERT OR IGNORE INTO trip_equipment_new(
            id, trip_id, serial_number, inventory_number, equipment_name, created_at, updated_at
        )
        SELECT
            id, trip_id, serial_number, inventory_number, equipment_name, created_at, updated_at
        FROM trip_equipment;

        DROP TABLE trip_equipment;
        ALTER TABLE trip_equipment_new RENAME TO trip_equipment;
        """
    )


<<<<<<< HEAD
def init_db(db: Database, schema_path: Path) -> None:
    """Инициализирует схему и базовые справочники при первом запуске."""
    schema_sql = schema_path.read_text(encoding="utf-8")
    with db.transaction():
        db.conn.executescript(schema_sql)

        # Миграция старой схемы: удаляем FK на equipment в movements/trip_equipment,
        # чтобы можно было хранить перемещения/связи рейсов для серийников,
        # которых ещё нет в таблице equipment.
=======
def init_db(db: Database, schema_path: Path | None) -> None:
    """Инициализирует схему и базовые справочники при первом запуске."""
    schema_sql = DEFAULT_SCHEMA_SQL
    if schema_path and schema_path.exists():
        schema_sql = schema_path.read_text(encoding="utf-8")

    with db.transaction():
        db.conn.executescript(schema_sql)

>>>>>>> origin/codex/develop-desktop-application-for-windows-lp0n7x
        if _table_has_fk_to_equipment(db, "movements"):
            _migrate_remove_equipment_fk_from_movements(db)

        if _table_has_fk_to_equipment(db, "trip_equipment"):
            _migrate_remove_equipment_fk_from_trip_equipment(db)

        for status in DEFAULT_STATUSES:
            db.execute(
                "INSERT OR IGNORE INTO statuses(name) VALUES(?)",
                (status,),
            )
