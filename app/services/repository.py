from __future__ import annotations

import hashlib
from typing import Any

from app.db.database import Database
from app.utils.io_utils import json_dumps


class Repository:
    def __init__(self, db: Database):
        self.db = db

    def create_import_batch(self, import_type: str, source_file: str) -> int:
        cur = self.db.execute(
            "INSERT INTO import_batches(import_type, source_file) VALUES(?, ?)",
            (import_type, source_file),
        )
        return int(cur.lastrowid)

    def close_import_batch(self, batch_id: int, stats: dict[str, int], details: dict[str, Any]) -> None:
        self.db.execute(
            """
            UPDATE import_batches
            SET finished_at = CURRENT_TIMESTAMP,
                added_count = ?,
                updated_count = ?,
                skipped_count = ?,
                conflict_count = ?,
                details_json = ?
            WHERE id = ?
            """,
            (
                stats.get("added", 0),
                stats.get("updated", 0),
                stats.get("skipped", 0),
                stats.get("conflicts", 0),
                json_dumps(details),
                batch_id,
            ),
        )

    def log_import_error(
        self,
        batch_id: int | None,
        source_file: str,
        source_row_id: str,
        error_type: str,
        error_message: str,
        payload: dict[str, Any],
    ) -> None:
        self.db.execute(
            """
            INSERT INTO import_errors(import_batch_id, source_file, source_row_id, error_type, error_message, payload_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (batch_id, source_file, source_row_id, error_type, error_message, json_dumps(payload)),
        )

    def get_status_id(self, status_name: str | None) -> int | None:
        if not status_name:
            return None
        row = self.db.query_one("SELECT id FROM statuses WHERE name = ?", (status_name,))
        if row:
            return int(row["id"])
        cur = self.db.execute("INSERT INTO statuses(name) VALUES(?)", (status_name,))
        return int(cur.lastrowid)

    def upsert_equipment(self, item: dict[str, Any], batch_id: int, source_file: str) -> str:
        serial = item["serial_number"]
        existing = self.db.query_one(
            "SELECT serial_number, inventory_number FROM equipment WHERE serial_number = ?",
            (serial,),
        )
        if existing:
            if existing["inventory_number"] and item.get("inventory_number") and existing["inventory_number"] != item["inventory_number"]:
                return "conflict_inventory"
            self.db.execute(
                """
                UPDATE equipment
                SET equipment_name = ?, nomenclature_name = ?, status_id = ?, location_initial = ?,
                    operating_hours_after_service = ?, circulation_total_after_service_without_current = ?,
                    operating_hours_total = ?, extra_json = ?, source_file = ?, import_batch_id = ?
                WHERE serial_number = ?
                """,
                (
                    item.get("equipment_name"),
                    item.get("nomenclature_name"),
                    item.get("status_id"),
                    item.get("location_initial"),
                    item.get("operating_hours_after_service"),
                    item.get("circulation_total_after_service_without_current"),
                    item.get("operating_hours_total"),
                    item.get("extra_json"),
                    source_file,
                    batch_id,
                    serial,
                ),
            )
            return "updated"

        self.db.execute(
            """
            INSERT INTO equipment(
                serial_number, inventory_number, equipment_name, nomenclature_name, status_id,
                location_initial, location_current, operating_hours_after_service,
                circulation_total_after_service_without_current, operating_hours_total,
                extra_json, source_file, import_batch_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                serial,
                item.get("inventory_number"),
                item.get("equipment_name"),
                item.get("nomenclature_name"),
                item.get("status_id"),
                item.get("location_initial"),
                item.get("location_initial"),
                item.get("operating_hours_after_service"),
                item.get("circulation_total_after_service_without_current"),
                item.get("operating_hours_total"),
                item.get("extra_json"),
                source_file,
                batch_id,
            ),
        )
        return "added"

    @staticmethod
    def movement_fingerprint(data: dict[str, Any]) -> str:
        base = "|".join([
            data.get("movement_date") or "",
            data.get("serial_number") or "",
            data.get("from_location") or "",
            data.get("to_location") or "",
            (data.get("comment") or "").strip().lower(),
        ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest()

    def upsert_movement(self, movement: dict[str, Any], batch_id: int, source_file: str) -> str:
        fingerprint = self.movement_fingerprint(movement)
        movement["fingerprint"] = fingerprint
        exists = self.db.query_one("SELECT id FROM movements WHERE fingerprint = ?", (fingerprint,))
        if exists:
            return "skipped"

        equipment = self.db.query_one(
            "SELECT inventory_number FROM equipment WHERE serial_number = ?",
            (movement["serial_number"],),
        )
        inv = movement.get("inventory_number") or (equipment["inventory_number"] if equipment else None)
        self.db.execute(
            """
            INSERT INTO movements(
                movement_date, serial_number, inventory_number, from_location, to_location,
                comment, source_file, source_row_id, import_batch_id, fingerprint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                movement["movement_date"],
                movement["serial_number"],
                inv,
                movement.get("from_location"),
                movement.get("to_location"),
                movement.get("comment"),
                source_file,
                movement.get("source_row_id"),
                batch_id,
                fingerprint,
            ),
        )
        return "added"

    def refresh_current_locations(self) -> None:
        self.db.execute(
            """
            UPDATE equipment
            SET location_current = COALESCE(
                (
                    SELECT m.to_location
                    FROM movements m
                    WHERE m.serial_number = equipment.serial_number
                    ORDER BY datetime(m.movement_date) DESC, m.id DESC
                    LIMIT 1
                ),
                equipment.location_initial
            )
            """
        )

    def upsert_trip(self, trip: dict[str, Any], batch_id: int, source_file: str) -> tuple[str, int]:
        exists = self.db.query_one("SELECT id FROM trips WHERE trip_fingerprint = ?", (trip["trip_fingerprint"],))
        if exists:
            trip_id = int(exists["id"])
            self.db.execute(
                """
                UPDATE trips
                SET trip_name = ?, work_name = ?, date_start = ?, date_end = ?, status = ?,
                    extra_json = ?, source_file = ?, import_batch_id = ?
                WHERE id = ?
                """,
                (
                    trip.get("trip_name"),
                    trip.get("work_name"),
                    trip.get("date_start"),
                    trip.get("date_end"),
                    trip.get("status"),
                    trip.get("extra_json"),
                    source_file,
                    batch_id,
                    trip_id,
                ),
            )
            return "updated", trip_id

        cur = self.db.execute(
            """
            INSERT INTO trips(trip_name, work_name, date_start, date_end, status, extra_json, source_file, import_batch_id, trip_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip.get("trip_name"),
                trip.get("work_name"),
                trip.get("date_start"),
                trip.get("date_end"),
                trip.get("status"),
                trip.get("extra_json"),
                source_file,
                batch_id,
                trip["trip_fingerprint"],
            ),
        )
        return "added", int(cur.lastrowid)

    def add_trip_equipment(self, trip_id: int, serial_number: str) -> None:
        eq = self.db.query_one(
            "SELECT inventory_number, equipment_name FROM equipment WHERE serial_number = ?",
            (serial_number,),
        )
        self.db.execute(
            """
            INSERT OR IGNORE INTO trip_equipment(trip_id, serial_number, inventory_number, equipment_name)
            VALUES (?, ?, ?, ?)
            """,
            (
                trip_id,
                serial_number,
                eq["inventory_number"] if eq else None,
                eq["equipment_name"] if eq else None,
            ),
        )

    def list_statuses(self) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT id, name, color_hex FROM statuses ORDER BY name")
        return [dict(r) for r in rows]

    def add_status(self, name: str, color_hex: str = "#1f6feb") -> None:
        self.db.execute("INSERT OR IGNORE INTO statuses(name, color_hex) VALUES(?, ?)", (name, color_hex))

    def list_locations(self) -> list[str]:
        rows = self.db.query_all(
            "SELECT DISTINCT location_current FROM equipment WHERE location_current IS NOT NULL AND TRIM(location_current) <> '' ORDER BY location_current"
        )
        return [r["location_current"] for r in rows]
