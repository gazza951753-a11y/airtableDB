from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from app.services.repository import Repository
from app.utils.io_utils import json_dumps, normalize_text, parse_date, read_tabular_file, split_multi_value, to_float

ProgressCb = Callable[[int, str], None]


class ImportService:
    def __init__(self, repo: Repository):
        self.repo = repo

    @staticmethod
    def _normalize_col_name(name: str) -> str:
        text = str(name).strip().lower().replace("ё", "е")
        # Оставляем только буквы/цифры для устойчивого сопоставления.
        return re.sub(r"[^a-zа-я0-9]+", "", text)

    @classmethod
    def _find_column(cls, columns: list[str], aliases: list[str]) -> str | None:
        """
        Ищет колонку сначала точным совпадением нормализованных имён,
        затем по вхождению alias в имя колонки.
        """
        normalized_to_original = {cls._normalize_col_name(c): c for c in columns}
        normalized_columns = list(normalized_to_original.keys())

        for alias in aliases:
            key = cls._normalize_col_name(alias)
            if key in normalized_to_original:
                return normalized_to_original[key]

        for alias in aliases:
            key = cls._normalize_col_name(alias)
            for col_norm in normalized_columns:
                if key and key in col_norm:
                    return normalized_to_original[col_norm]

        return None

    @staticmethod
    def _column_or_empty(row: pd.Series, col: str | None) -> Any:
        return row[col] if col and col in row else None

    @staticmethod
    def _report_progress(progress: ProgressCb | None, idx: int, total: int, title: str) -> None:
        if not progress:
            return
        if idx == 0 or idx == total - 1 or (idx + 1) % 200 == 0:
            progress(int((idx + 1) / max(total, 1) * 100), f"{title}: {idx + 1}/{total}")

    def import_equipment(self, file_path: str, progress: ProgressCb | None = None) -> dict[str, Any]:
        df = read_tabular_file(file_path).fillna("")
        columns = list(df.columns)

        serial_col = self._find_column(columns, ["serial_number", "serial number", "serial", "серийный номер", "заводской номер"])
        inv_col = self._find_column(columns, ["inventory_number", "inventory number", "инвентарный номер", "inventory"])
        status_col = self._find_column(columns, ["status", "статус"])
        name_col = self._find_column(columns, ["equipment_name", "equipment name", "наименование", "nomenclature_name"])
        location_col = self._find_column(columns, ["location", "location_current", "местоположение", "местонахождение"])

        batch_id = self.repo.create_import_batch("equipment", Path(file_path).name)
        stats = {"added": 0, "updated": 0, "skipped": 0, "conflicts": 0}

        if not serial_col:
            with self.repo.db.transaction():
                self.repo.log_import_error(
                    batch_id,
                    file_path,
                    "header",
                    "missing_serial_column",
                    "Не найдена колонка serial_number в файле оборудования",
                    {"columns": [str(c) for c in columns]},
                )
                self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "columns": [str(c) for c in columns]})
            return {"batch_id": batch_id, **stats}

        with self.repo.db.transaction():
            for idx, row in df.iterrows():
                self._report_progress(progress, idx, len(df), "Импорт оборудования")

                serial_number = normalize_text(self._column_or_empty(row, serial_col))
                if not serial_number:
                    stats["conflicts"] += 1
                    self.repo.log_import_error(batch_id, file_path, str(idx + 2), "missing_serial", "Пустой serial_number", row.to_dict())
                    continue

                status_name = normalize_text(self._column_or_empty(row, status_col))
                status_id = self.repo.get_status_id(status_name) if status_name else None

                item = {
                    "serial_number": serial_number,
                    "inventory_number": normalize_text(self._column_or_empty(row, inv_col)),
                    "equipment_name": normalize_text(self._column_or_empty(row, name_col)),
                    "nomenclature_name": normalize_text(self._column_or_empty(row, name_col)),
                    "status_id": status_id,
                    "location_initial": normalize_text(self._column_or_empty(row, location_col)),
                    "operating_hours_after_service": to_float(row.get("operating_hours_after_service")),
                    "circulation_total_after_service_without_current": to_float(row.get("circulation_total_after_service_without_current")),
                    "operating_hours_total": to_float(row.get("operating_hours_total")),
                    "extra_json": json_dumps(row.to_dict()),
                }

                result = self.repo.upsert_equipment(item, batch_id, Path(file_path).name)
                if result == "conflict_inventory":
                    stats["conflicts"] += 1
                    self.repo.log_import_error(
                        batch_id,
                        file_path,
                        str(idx + 2),
                        "inventory_conflict",
                        "Конфликт serial_number -> inventory_number",
                        row.to_dict(),
                    )
                else:
                    stats[result] += 1

            self.repo.refresh_current_locations()
            self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "serial_column": serial_col})
        return {"batch_id": batch_id, **stats}

    def import_movements(self, file_path: str, progress: ProgressCb | None = None) -> dict[str, Any]:
        df = read_tabular_file(file_path).fillna("")
        columns = list(df.columns)

        date_col = self._find_column(columns, ["movement_date", "date", "дата", "дата перемещения"])
        serial_col = self._find_column(columns, ["serial_number", "serial", "серийный номер", "приборы", "оборудование"])
        inv_col = self._find_column(columns, ["inventory_number", "инвентарный номер"])
        from_col = self._find_column(columns, ["from_location", "откуда", "from"])
        to_col = self._find_column(columns, ["to_location", "куда", "to"])
        comment_col = self._find_column(columns, ["comment", "примечание", "комментарий"])

        batch_id = self.repo.create_import_batch("movements", Path(file_path).name)
        stats = {"added": 0, "updated": 0, "skipped": 0, "conflicts": 0}

        if not serial_col or not date_col:
            with self.repo.db.transaction():
                self.repo.log_import_error(
                    batch_id,
                    file_path,
                    "header",
                    "missing_required_column",
                    "Не найдены обязательные колонки для импорта перемещений (date/serial)",
                    {"columns": [str(c) for c in columns]},
                )
                self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "columns": [str(c) for c in columns]})
            return {"batch_id": batch_id, **stats}

        with self.repo.db.transaction():
            for idx, row in df.iterrows():
                self._report_progress(progress, idx, len(df), "Импорт перемещений")

                movement_date = parse_date(self._column_or_empty(row, date_col))
                if not movement_date:
                    stats["conflicts"] += 1
                    self.repo.log_import_error(batch_id, file_path, str(idx + 2), "bad_date", "Некорректная дата", row.to_dict())
                    continue

                serial_values = split_multi_value(self._column_or_empty(row, serial_col))
                if not serial_values:
                    stats["conflicts"] += 1
                    self.repo.log_import_error(batch_id, file_path, str(idx + 2), "missing_serial", "Не найден serial_number", row.to_dict())
                    continue

                for serial in serial_values:
                    movement = {
                        "movement_date": movement_date,
                        "serial_number": normalize_text(serial),
                        "inventory_number": normalize_text(self._column_or_empty(row, inv_col)),
                        "from_location": normalize_text(self._column_or_empty(row, from_col)),
                        "to_location": normalize_text(self._column_or_empty(row, to_col)),
                        "comment": normalize_text(self._column_or_empty(row, comment_col)),
                        "source_row_id": str(idx + 2),
                    }
                    if not movement["serial_number"]:
                        stats["conflicts"] += 1
                        self.repo.log_import_error(batch_id, file_path, str(idx + 2), "missing_serial", "Пустой serial после разбиения", row.to_dict())
                        continue

                    result = self.repo.upsert_movement(movement, batch_id, Path(file_path).name)
                    stats[result] += 1

            self.repo.refresh_current_locations()
            self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "serial_column": serial_col, "date_column": date_col})

        return {"batch_id": batch_id, **stats}

    def import_trips(self, file_path: str, progress: ProgressCb | None = None) -> dict[str, Any]:
        df = read_tabular_file(file_path).fillna("")
        columns = list(df.columns)
        trip_name_col = self._find_column(columns, ["trip_name", "рейс", "наименование работ", "work_name"])
        start_col = self._find_column(columns, ["date_start", "start", "дата начала"])
        end_col = self._find_column(columns, ["date_end", "end", "дата окончания"])
        status_col = self._find_column(columns, ["status", "статус"])
        equipment_col = self._find_column(columns, ["serial_number", "приборы", "equipment", "equipment_list"])

        batch_id = self.repo.create_import_batch("trips", Path(file_path).name)
        stats = {"added": 0, "updated": 0, "skipped": 0, "conflicts": 0}

        if not trip_name_col:
            with self.repo.db.transaction():
                self.repo.log_import_error(
                    batch_id,
                    file_path,
                    "header",
                    "missing_trip_name_column",
                    "Не найдена обязательная колонка trip_name",
                    {"columns": [str(c) for c in columns]},
                )
                self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "columns": [str(c) for c in columns]})
            return {"batch_id": batch_id, **stats}

        with self.repo.db.transaction():
            for idx, row in df.iterrows():
                self._report_progress(progress, idx, len(df), "Импорт рейсов")

                trip_name = normalize_text(self._column_or_empty(row, trip_name_col))
                if not trip_name:
                    stats["conflicts"] += 1
                    self.repo.log_import_error(batch_id, file_path, str(idx + 2), "missing_trip_name", "Пустое название рейса", row.to_dict())
                    continue

                date_start = parse_date(self._column_or_empty(row, start_col))
                date_end = parse_date(self._column_or_empty(row, end_col))
                serials = split_multi_value(self._column_or_empty(row, equipment_col))

                finger_source = f"{trip_name}|{date_start or ''}|{date_end or ''}|{normalize_text(self._column_or_empty(row, status_col))}"
                trip = {
                    "trip_name": trip_name,
                    "work_name": trip_name,
                    "date_start": date_start,
                    "date_end": date_end,
                    "status": normalize_text(self._column_or_empty(row, status_col)),
                    "extra_json": json_dumps(row.to_dict()),
                    "trip_fingerprint": hashlib.sha1(finger_source.encode("utf-8")).hexdigest(),
                }
                res, trip_id = self.repo.upsert_trip(trip, batch_id, Path(file_path).name)
                stats[res] += 1

                for serial in serials:
                    clean_serial = normalize_text(serial)
                    if clean_serial:
                        self.repo.add_trip_equipment(trip_id, clean_serial)

            self.repo.close_import_batch(batch_id, stats, {"rows": len(df), "trip_name_column": trip_name_col})

        return {"batch_id": batch_id, **stats}
