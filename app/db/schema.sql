PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS statuses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color_hex TEXT DEFAULT '#1f6feb',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_type TEXT NOT NULL,
    source_file TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    added_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS import_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_batch_id INTEGER,
    source_file TEXT,
    source_row_id TEXT,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS equipment (
    serial_number TEXT PRIMARY KEY,
    inventory_number TEXT,
    equipment_name TEXT,
    nomenclature_name TEXT,
    status_id INTEGER,
    location_initial TEXT,
    location_current TEXT,
    operating_hours_after_service REAL,
    circulation_total_after_service_without_current REAL,
    operating_hours_total REAL,
    extra_json TEXT,
    source_file TEXT,
    import_batch_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(status_id) REFERENCES statuses(id) ON DELETE SET NULL,
    FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS movements (
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

CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name TEXT NOT NULL,
    work_name TEXT,
    date_start TEXT,
    date_end TEXT,
    status TEXT,
    extra_json TEXT,
    source_file TEXT,
    import_batch_id INTEGER,
    trip_fingerprint TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS trip_equipment (
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

CREATE INDEX IF NOT EXISTS idx_equipment_inventory ON equipment(inventory_number);
CREATE INDEX IF NOT EXISTS idx_equipment_location_current ON equipment(location_current);
CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment(status_id);
CREATE INDEX IF NOT EXISTS idx_movements_serial ON movements(serial_number);
CREATE INDEX IF NOT EXISTS idx_movements_date ON movements(movement_date);
CREATE INDEX IF NOT EXISTS idx_trips_name ON trips(trip_name);
CREATE INDEX IF NOT EXISTS idx_import_errors_batch ON import_errors(import_batch_id);

CREATE TRIGGER IF NOT EXISTS trg_equipment_updated_at
AFTER UPDATE ON equipment
BEGIN
    UPDATE equipment SET updated_at = CURRENT_TIMESTAMP WHERE serial_number = NEW.serial_number;
END;

CREATE TRIGGER IF NOT EXISTS trg_movements_updated_at
AFTER UPDATE ON movements
BEGIN
    UPDATE movements SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_trips_updated_at
AFTER UPDATE ON trips
BEGIN
    UPDATE trips SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
