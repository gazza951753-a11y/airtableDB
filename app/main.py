import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    apply_style(app)

    db = Database(DB_PATH)
    db.connect()
    schema_path = Path(__file__).resolve().parent / "db" / "schema.sql"
    init_db(db, schema_path)

    repo = Repository(db)
    window = MainWindow(repo)
    window.show()

    code = app.exec()
    db.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
