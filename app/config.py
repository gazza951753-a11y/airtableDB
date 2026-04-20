from pathlib import Path

APP_NAME = "Локальная база оборудования"
APP_ORG = "LocalOps"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "airtable_local.db"
BACKUP_DIR = DATA_DIR / "backups"

PAGE_SIZE = 500
DEFAULT_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%Y-%m-%d %H:%M:%S",
]

DEFAULT_STATUSES = [
    "В эксплуатации",
    "На дефектоскопию",
    "ТО",
    "ТО-1",
    "ТО-2",
    "ТО-3",
    "В ремонт",
    "На расследование",
    "На тестирование",
    "Ожидание ЗИП",
    "Ремонтируется",
    "Брак",
    "Оставлено в скважине",
    "Списан",
    "На калибровку",
    "На возврат",
    "На ревизии",
    "StubWelding",
    "Hardbanding",
    "Ожидание работ",
    "НА БУРОВОЙ",
    "На комразбор",
    "На консервации",
]
