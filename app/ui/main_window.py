from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QSortFilterProxyModel, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTabWidget,
    QTableView,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from app.config import BACKUP_DIR, DB_PATH, PAGE_SIZE
from app.services.backup_service import make_backup, restore_backup
from app.services.export_service import export_rows
from app.services.import_service import ImportService
from app.services.repository import Repository
from app.ui.table_models import DictTableModel


class ImportWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, fn: Callable[[str, Callable[[int, str], None]], dict], path: str):
        super().__init__()
        self.fn = fn
        self.path = path

    def run(self) -> None:
        try:
            result = self.fn(self.path, lambda p, t: self.progress.emit(p, t))
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, repo: Repository):
        super().__init__()
        self.repo = repo
        self.import_service = ImportService(repo)
        self._last_progress_value = -1
        self.setWindowTitle("Локальная база оборудования")
        self.resize(1600, 900)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.equipment_tab = self._build_equipment_tab()
        self.movements_tab = self._build_movements_tab()
        self.trips_tab = self._build_trips_tab()
        self.import_tab = self._build_import_tab()
        self.refs_tab = self._build_refs_tab()
        self.errors_tab = self._build_errors_tab()

        self.tabs.addTab(self.equipment_tab, "Оборудование")
        self.tabs.addTab(self.movements_tab, "Перемещения")
        self.tabs.addTab(self.trips_tab, "Рейсы")
        self.tabs.addTab(self.import_tab, "Импорт")
        self.tabs.addTab(self.refs_tab, "Справочники")
        self.tabs.addTab(self.errors_tab, "Журнал ошибок")

        self.refresh_all()

    def refresh_all(self) -> None:
        self.load_equipment()
        self.load_movements()
        self.load_trips()
        self.load_errors()
        self.load_statuses()
        self.load_locations_combo()

    def _base_table(self) -> tuple[QTableView, DictTableModel, QSortFilterProxyModel]:
        table = QTableView()
        model = DictTableModel([])
        proxy = QSortFilterProxyModel(self)
        proxy.setSourceModel(model)
        proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        table.setModel(proxy)
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableView.SelectRows)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        return table, model, proxy

    def _build_equipment_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        filters = QHBoxLayout()
        self.eq_search = QLineEdit()
        self.eq_search.setPlaceholderText("Поиск: serial / inventory / название / место")
        self.eq_search.textChanged.connect(self.load_equipment)
        self.eq_status = QComboBox()
        self.eq_status.addItem("Все статусы")
        self.eq_status.currentIndexChanged.connect(self.load_equipment)
        self.eq_location = QComboBox()
        self.eq_location.addItem("Все локации")
        self.eq_location.currentIndexChanged.connect(self.load_equipment)
        recalc_btn = QPushButton("Пересчитать текущее местоположение")
        recalc_btn.clicked.connect(self.recalc_locations)
        export_btn = QPushButton("Экспорт CSV/XLSX")
        export_btn.clicked.connect(lambda: self.export_table(self.eq_model))

        filters.addWidget(self.eq_search)
        filters.addWidget(self.eq_status)
        filters.addWidget(self.eq_location)
        filters.addWidget(recalc_btn)
        filters.addWidget(export_btn)

        self.eq_table, self.eq_model, _ = self._base_table()
        self.eq_table.doubleClicked.connect(self.show_equipment_card)
        self.eq_table.customContextMenuRequested.connect(self.eq_context_menu)
        self.eq_details = QTextEdit()
        self.eq_details.setReadOnly(True)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.eq_table)
        splitter.addWidget(self.eq_details)
        splitter.setSizes([700, 200])

        layout.addLayout(filters)
        layout.addWidget(splitter)
        return tab

    def _build_movements_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        top = QHBoxLayout()
        self.mv_search = QLineEdit()
        self.mv_search.setPlaceholderText("Поиск serial/from/to/comment")
        self.mv_search.textChanged.connect(self.load_movements)
        add_btn = QPushButton("Добавить перемещение")
        add_btn.clicked.connect(self.add_movement_dialog)
        export_btn = QPushButton("Экспорт CSV/XLSX")
        export_btn.clicked.connect(lambda: self.export_table(self.mv_model))
        top.addWidget(self.mv_search)
        top.addWidget(add_btn)
        top.addWidget(export_btn)
        self.mv_table, self.mv_model, _ = self._base_table()
        self.mv_table.customContextMenuRequested.connect(self.mv_context_menu)
        layout.addLayout(top)
        layout.addWidget(self.mv_table)
        return tab

    def _build_trips_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        top = QHBoxLayout()
        self.trip_search = QLineEdit()
        self.trip_search.setPlaceholderText("Поиск рейса или оборудования")
        self.trip_search.textChanged.connect(self.load_trips)
        export_btn = QPushButton("Экспорт CSV/XLSX")
        export_btn.clicked.connect(lambda: self.export_table(self.trip_model))
        top.addWidget(self.trip_search)
        top.addWidget(export_btn)
        self.trip_table, self.trip_model, _ = self._base_table()
        self.trip_table.doubleClicked.connect(self.show_trip_card)
        self.trip_details = QTextEdit()
        self.trip_details.setReadOnly(True)
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.trip_table)
        splitter.addWidget(self.trip_details)
        splitter.setSizes([700, 200])
        layout.addLayout(top)
        layout.addWidget(splitter)
        return tab

    def _build_import_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        btns = QHBoxLayout()
        eq_btn = QPushButton("Импорт оборудования")
        eq_btn.clicked.connect(lambda: self.run_import("equipment"))
        mv_btn = QPushButton("Импорт перемещений")
        mv_btn.clicked.connect(lambda: self.run_import("movements"))
        old_mv_btn = QPushButton("Импорт старого Excel перемещений")
        old_mv_btn.clicked.connect(lambda: self.run_import("movements"))
        trip_btn = QPushButton("Импорт рейсов")
        trip_btn.clicked.connect(lambda: self.run_import("trips"))
        backup_btn = QPushButton("Сделать backup БД")
        backup_btn.clicked.connect(self.create_backup)
        restore_btn = QPushButton("Восстановить из backup")
        restore_btn.clicked.connect(self.restore_backup_dialog)
        btns.addWidget(eq_btn)
        btns.addWidget(mv_btn)
        btns.addWidget(old_mv_btn)
        btns.addWidget(trip_btn)
        btns.addWidget(backup_btn)
        btns.addWidget(restore_btn)

        self.import_progress = QProgressBar()
        self.import_log = QTextEdit()
        self.import_log.setReadOnly(True)
        layout.addLayout(btns)
        layout.addWidget(self.import_progress)
        layout.addWidget(self.import_log)
        return tab

    def _build_refs_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        frm = QFormLayout()
        self.status_name = QLineEdit()
        self.status_color = QLineEdit("#1f6feb")
        add_btn = QPushButton("Добавить статус")
        add_btn.clicked.connect(self.add_status)
        self.statuses_view = QTextEdit()
        self.statuses_view.setReadOnly(True)
        frm.addRow("Новый статус", self.status_name)
        frm.addRow("Цвет HEX", self.status_color)
        layout.addLayout(frm)
        layout.addWidget(add_btn)
        layout.addWidget(self.statuses_view)
        return tab

    def _build_errors_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        export_btn = QPushButton("Экспорт журнала ошибок")
        export_btn.clicked.connect(lambda: self.export_table(self.err_model))
        self.err_table, self.err_model, _ = self._base_table()
        layout.addWidget(export_btn)
        layout.addWidget(self.err_table)
        return tab

    def load_equipment(self) -> None:
        search = self.eq_search.text().strip() if hasattr(self, "eq_search") else ""
        status_text = self.eq_status.currentText() if hasattr(self, "eq_status") else "Все статусы"
        location_text = self.eq_location.currentText() if hasattr(self, "eq_location") else "Все локации"

        sql = """
            SELECT e.serial_number, e.inventory_number, e.equipment_name, s.name AS status,
                   e.location_current, e.location_initial, e.operating_hours_total, e.updated_at
            FROM equipment e
            LEFT JOIN statuses s ON s.id = e.status_id
            WHERE 1 = 1
        """
        params: list[str] = []
        if search:
            sql += " AND (e.serial_number LIKE ? OR e.inventory_number LIKE ? OR e.equipment_name LIKE ? OR e.location_current LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        if status_text and status_text != "Все статусы":
            sql += " AND s.name = ?"
            params.append(status_text)
        if location_text and location_text != "Все локации":
            sql += " AND e.location_current = ?"
            params.append(location_text)
        sql += " ORDER BY e.updated_at DESC LIMIT ?"
        params.append(str(PAGE_SIZE * 20))
        rows = [dict(r) for r in self.repo.db.query_all(sql, tuple(params))]
        self.eq_model.set_rows(rows)

    def load_movements(self) -> None:
        search = self.mv_search.text().strip() if hasattr(self, "mv_search") else ""
        sql = """
            SELECT id, movement_date, serial_number, inventory_number, from_location, to_location, comment, source_file
            FROM movements
            WHERE 1 = 1
        """
        params: list[str] = []
        if search:
            sql += " AND (serial_number LIKE ? OR from_location LIKE ? OR to_location LIKE ? OR comment LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern, pattern])
        sql += " ORDER BY datetime(movement_date) DESC LIMIT ?"
        params.append(str(PAGE_SIZE * 20))
        rows = [dict(r) for r in self.repo.db.query_all(sql, tuple(params))]
        self.mv_model.set_rows(rows)

    def load_trips(self) -> None:
        search = self.trip_search.text().strip() if hasattr(self, "trip_search") else ""
        sql = """
            SELECT t.id, t.trip_name, t.date_start, t.date_end, t.status,
                   COUNT(te.id) AS equipment_count
            FROM trips t
            LEFT JOIN trip_equipment te ON te.trip_id = t.id
            WHERE 1 = 1
        """
        params: list[str] = []
        if search:
            sql += " AND (t.trip_name LIKE ? OR t.work_name LIKE ? OR EXISTS(SELECT 1 FROM trip_equipment x WHERE x.trip_id = t.id AND x.serial_number LIKE ?))"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        sql += " GROUP BY t.id ORDER BY datetime(t.date_start) DESC LIMIT ?"
        params.append(str(PAGE_SIZE * 20))
        rows = [dict(r) for r in self.repo.db.query_all(sql, tuple(params))]
        self.trip_model.set_rows(rows)

    def load_errors(self) -> None:
        rows = [
            dict(r)
            for r in self.repo.db.query_all(
                "SELECT id, created_at, source_file, source_row_id, error_type, error_message FROM import_errors ORDER BY id DESC LIMIT 5000"
            )
        ]
        self.err_model.set_rows(rows)

    def load_statuses(self) -> None:
        statuses = self.repo.list_statuses()
        self.statuses_view.setPlainText("\n".join([f"{s['name']} ({s['color_hex']})" for s in statuses]))
        current = self.eq_status.currentText() if hasattr(self, "eq_status") else "Все статусы"
        self.eq_status.blockSignals(True)
        self.eq_status.clear()
        self.eq_status.addItem("Все статусы")
        for st in statuses:
            self.eq_status.addItem(st["name"])
        idx = self.eq_status.findText(current)
        if idx >= 0:
            self.eq_status.setCurrentIndex(idx)
        self.eq_status.blockSignals(False)

    def load_locations_combo(self) -> None:
        locations = self.repo.list_locations()
        current = self.eq_location.currentText() if hasattr(self, "eq_location") else "Все локации"
        self.eq_location.blockSignals(True)
        self.eq_location.clear()
        self.eq_location.addItem("Все локации")
        self.eq_location.addItems(locations)
        idx = self.eq_location.findText(current)
        if idx >= 0:
            self.eq_location.setCurrentIndex(idx)
        self.eq_location.blockSignals(False)

    def run_import(self, import_type: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл",
            "",
            "Данные (*.csv *.xlsx *.xlsm *.xls)",
        )
        if not path:
            return

        self.import_log.append(f"Старт импорта {import_type}: {path}")
        fn_map = {
            "equipment": self.import_service.import_equipment,
            "movements": self.import_service.import_movements,
            "trips": self.import_service.import_trips,
        }
        fn = fn_map[import_type]
        self.thread = QThread(self)
        self.worker = ImportWorker(fn, path)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_import_progress)
        self.worker.finished.connect(self.on_import_finished)
        self.worker.error.connect(self.on_import_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_import_progress(self, value: int, text: str) -> None:
        self.import_progress.setValue(value)
        # Уменьшаем нагрузку на UI: не пишем в лог каждое событие прогресса.
        if value == 100 or value == 0 or value - self._last_progress_value >= 5:
            self.import_log.append(text)
            self._last_progress_value = value

    def on_import_finished(self, result: dict) -> None:
        self.import_progress.setValue(100)
        details = result.get("details", {})
        self.import_log.append(f"Готово: {result}")
        if details:
            self.import_log.append(f"Детали импорта: {details}")
        if result.get("added", 0) == 0 and result.get("updated", 0) == 0:
            QMessageBox.warning(
                self,
                "Импорт завершён без загрузки данных",
                "Импорт не добавил строк. Откроется вкладка 'Журнал ошибок' для проверки причин.",
            )
            self.tabs.setCurrentWidget(self.errors_tab)
        self._last_progress_value = -1
        self.refresh_all()

    def on_import_error(self, message: str) -> None:
        QMessageBox.critical(self, "Ошибка импорта", message)
        self.import_log.append(f"Ошибка: {message}")

    def add_movement_dialog(self) -> None:
        dialog = QWidget()
        dialog.setWindowTitle("Новое перемещение")
        form = QFormLayout(dialog)
        serial = QLineEdit()
        date = QLineEdit()
        date.setPlaceholderText("YYYY-MM-DD HH:MM:SS")
        from_loc = QLineEdit()
        to_loc = QLineEdit()
        comment = QLineEdit()
        save_btn = QPushButton("Сохранить")

        form.addRow("Serial", serial)
        form.addRow("Дата", date)
        form.addRow("Откуда", from_loc)
        form.addRow("Куда", to_loc)
        form.addRow("Комментарий", comment)
        form.addRow(save_btn)

        def save() -> None:
            if not serial.text().strip() or not date.text().strip():
                QMessageBox.warning(dialog, "Валидация", "Заполните serial и дату")
                return
            movement = {
                "movement_date": date.text().strip(),
                "serial_number": serial.text().strip(),
                "inventory_number": None,
                "from_location": from_loc.text().strip(),
                "to_location": to_loc.text().strip(),
                "comment": comment.text().strip(),
                "source_row_id": "manual",
            }
            with self.repo.db.transaction():
                res = self.repo.upsert_movement(movement, 0, "manual")
                if res == "skipped":
                    QMessageBox.information(dialog, "Дубликат", "Такое перемещение уже есть")
                    return
                self.repo.refresh_current_locations()
            dialog.close()
            self.refresh_all()

        save_btn.clicked.connect(save)
        dialog.setLayout(form)
        dialog.resize(420, 240)
        dialog.show()
        self._movement_dialog = dialog

    def eq_context_menu(self, pos) -> None:
        menu = QMenu(self)
        action_export = menu.addAction("Экспорт строки")
        action = menu.exec(self.eq_table.viewport().mapToGlobal(pos))
        if action == action_export:
            idx = self.eq_table.currentIndex()
            src_row = self.eq_model.get_row(idx.row())
            if src_row:
                self.export_rows([src_row])

    def mv_context_menu(self, pos) -> None:
        menu = QMenu(self)
        action_export = menu.addAction("Экспорт строки")
        action = menu.exec(self.mv_table.viewport().mapToGlobal(pos))
        if action == action_export:
            idx = self.mv_table.currentIndex()
            src_row = self.mv_model.get_row(idx.row())
            if src_row:
                self.export_rows([src_row])

    def show_equipment_card(self) -> None:
        idx = self.eq_table.currentIndex()
        row = self.eq_model.get_row(idx.row())
        if not row:
            return
        serial = row["serial_number"]
        movements = self.repo.db.query_all(
            "SELECT movement_date, from_location, to_location, comment FROM movements WHERE serial_number = ? ORDER BY datetime(movement_date) DESC LIMIT 20",
            (serial,),
        )
        trips = self.repo.db.query_all(
            "SELECT t.trip_name, t.date_start, t.status FROM trips t JOIN trip_equipment te ON te.trip_id = t.id WHERE te.serial_number = ? ORDER BY datetime(t.date_start) DESC LIMIT 20",
            (serial,),
        )
        txt = [f"Карточка: {serial}"]
        txt.append("\nИстория перемещений:")
        txt.extend([f"- {m['movement_date']}: {m['from_location']} -> {m['to_location']} ({m['comment'] or ''})" for m in movements])
        txt.append("\nСвязанные рейсы:")
        txt.extend([f"- {t['trip_name']} ({t['date_start'] or ''}) [{t['status'] or ''}]" for t in trips])
        self.eq_details.setPlainText("\n".join(txt))

    def show_trip_card(self) -> None:
        idx = self.trip_table.currentIndex()
        row = self.trip_model.get_row(idx.row())
        if not row:
            return
        trip_id = row["id"]
        equipment = self.repo.db.query_all(
            "SELECT serial_number, inventory_number, equipment_name FROM trip_equipment WHERE trip_id = ? ORDER BY serial_number",
            (trip_id,),
        )
        txt = [f"Рейс: {row['trip_name']}", "\nОборудование:"]
        txt.extend([f"- {e['serial_number']} / {e['inventory_number'] or ''} / {e['equipment_name'] or ''}" for e in equipment])
        self.trip_details.setPlainText("\n".join(txt))

    def recalc_locations(self) -> None:
        with self.repo.db.transaction():
            self.repo.refresh_current_locations()
        self.load_equipment()
        self.load_locations_combo()

    def add_status(self) -> None:
        name = self.status_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Валидация", "Название статуса обязательно")
            return
        color = self.status_color.text().strip() or "#1f6feb"
        with self.repo.db.transaction():
            self.repo.add_status(name, color)
        self.status_name.clear()
        self.load_statuses()

    def export_table(self, model: DictTableModel) -> None:
        rows = [model.get_row(i) for i in range(model.rowCount())]
        self.export_rows([r for r in rows if r is not None])

    def export_rows(self, rows: list[dict]) -> None:
        if not rows:
            QMessageBox.information(self, "Экспорт", "Нет данных для экспорта")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт", "", "CSV (*.csv);;Excel (*.xlsx)")
        if not path:
            return
        export_rows(rows, path)
        QMessageBox.information(self, "Экспорт", f"Сохранено: {path}")

    def create_backup(self) -> None:
        target = make_backup(DB_PATH, BACKUP_DIR)
        self.import_log.append(f"Backup создан: {target}")
        QMessageBox.information(self, "Backup", f"Создан файл: {target}")

    def restore_backup_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите backup", str(BACKUP_DIR), "SQLite DB (*.db)")
        if not path:
            return
        restore_backup(Path(path), DB_PATH)
        QMessageBox.information(self, "Восстановление", "База восстановлена. Перезапустите приложение.")
