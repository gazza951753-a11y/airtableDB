import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from app.config import APP_NAME, APP_ORG, DB_PATH
from app.db.database import Database
from app.db.migrations import init_db
from app.services.repository import Repository
from app.ui.main_window import MainWindow


def apply_style(app: QApplication) -> None:
    app.setStyleSheet(
        """
        QWidget { font-size: 12px; }
        QTableView { gridline-color: #d0d7de; }
        QHeaderView::section { background-color: #f6f8fa; padding: 4px; border: 1px solid #d0d7de; }
        QPushButton { padding: 6px 10px; }
        QLineEdit, QComboBox { padding: 4px; }
        """
    )


def resolve_schema_path() -> Path:
    """Возвращает путь к schema.sql в обычном и PyInstaller-режиме."""
    if getattr(sys, "frozen", False):
        # В one-folder сборке PyInstaller данные попадают в папку приложения,
        # в one-file — во временную _MEIPASS директорию.
        base_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        schema_path = base_dir / "app" / "db" / "schema.sql"
        if schema_path.exists():
            return schema_path

    # Запуск из исходников
    return Path(__file__).resolve().parent / "db" / "schema.sql"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    apply_style(app)

    db = Database(DB_PATH)
    db.connect()

    schema_path = resolve_schema_path()
    if not schema_path.exists():
        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не найден файл схемы БД:\n{schema_path}\n\n"
            f"Переустановите приложение или пересоберите EXE.",
        )
        return 1

    init_db(db, schema_path)

    repo = Repository(db)
    window = MainWindow(repo)
    window.show()

    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
