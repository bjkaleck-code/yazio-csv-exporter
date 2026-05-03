CREATE TABLE IF NOT EXISTS daily_nutrition (
    date TEXT PRIMARY KEY,
    calories REAL,
    protein REAL,
    fat REAL,
    carbs REAL,
    energy_goal REAL
);

CREATE TABLE IF NOT EXISTS meal_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    meal TEXT,
    calories REAL
);

CREATE INDEX IF NOT EXISTS idx_meal_summary_date ON meal_summary (date);

CREATE TABLE IF NOT EXISTS nutrition_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    time TEXT,
    meal TEXT,
    type TEXT,
    product TEXT,
    source TEXT,
    amount REAL,
    unit TEXT,
    portions TEXT,
    calories_per_g REAL,
    calories_total REAL,
    protein_per_g REAL,
    fat_per_g REAL,
    carbs_per_g REAL,
    protein_total REAL,
    fat_total REAL,
    carbs_total REAL
);

CREATE INDEX IF NOT EXISTS idx_nutrition_entries_date ON nutrition_entries (date);

CREATE TABLE IF NOT EXISTS body_metrics (
    date TEXT PRIMARY KEY,
    weight REAL,
    steps INTEGER,
    training INTEGER,
    creatine INTEGER,
    coffee_oat_milk_ml REAL,
    comment TEXT
);

CREATE TABLE IF NOT EXISTS ai_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date TEXT,
    period_start TEXT,
    period_end TEXT,
    summary TEXT,
    recommendation TEXT,
    focus_today TEXT,
    risk_flags_json TEXT,
    confidence TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS health_daily (
    date TEXT PRIMARY KEY,
    steps INTEGER,
    distance_km REAL,
    active_kcal REAL,
    total_kcal REAL,
    workout_count INTEGER,
    workout_minutes REAL,
    weight_kg REAL,
    body_fat_percent REAL,
    sleep_hours REAL,
    basal_metabolic_rate_kcal REAL,
    basal_metabolic_rate_source TEXT,
    workout_estimated_active_kcal REAL,
    workout_estimated_active_kcal_source TEXT,
    effective_active_kcal REAL,
    effective_active_kcal_source TEXT,
    source TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS import_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source_path TEXT,
    source_modified_at TEXT,
    data_start_date TEXT,
    data_end_date TEXT,
    rows_read INTEGER,
    rows_written INTEGER,
    details_json TEXT,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_runs_source_finished
ON import_runs (source, finished_at);

CREATE TABLE IF NOT EXISTS body_composition_measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    measured_at TEXT,
    date TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seca',
    weight_kg REAL,
    body_fat_percent REAL,
    fat_mass_kg REAL,
    muscle_mass_kg REAL,
    skeletal_muscle_mass_kg REAL,
    skeletal_muscle_mass_percent REAL,
    body_water_percent REAL,
    body_water_l REAL,
    bmi REAL,
    visceral_fat REAL,
    visceral_fat_l REAL,
    basal_metabolic_rate_kcal REAL,
    waist_circumference_cm REAL,
    waist_hip_ratio REAL,
    muscle_right_arm_kg REAL,
    muscle_left_arm_kg REAL,
    muscle_torso_kg REAL,
    muscle_right_leg_kg REAL,
    muscle_left_leg_kg REAL,
    fat_right_arm_kg REAL,
    fat_left_arm_kg REAL,
    fat_torso_kg REAL,
    fat_right_leg_kg REAL,
    fat_left_leg_kg REAL,
    measurement_hash TEXT,
    original_file_sha256 TEXT,
    original_filename TEXT,
    raw_json TEXT,
    imported_at TEXT NOT NULL,
    UNIQUE(source, measured_at)
);

CREATE INDEX IF NOT EXISTS idx_body_composition_date
ON body_composition_measurements (date);

CREATE TABLE IF NOT EXISTS uploaded_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    original_filename TEXT,
    stored_filename TEXT,
    source_path TEXT,
    file_sha256 TEXT NOT NULL,
    file_size_bytes INTEGER,
    uploaded_at TEXT NOT NULL,
    imported_at TEXT,
    status TEXT NOT NULL,
    import_run_id INTEGER,
    details_json TEXT,
    UNIQUE(source, file_sha256)
);

CREATE INDEX IF NOT EXISTS idx_uploaded_files_source_uploaded
ON uploaded_files (source, uploaded_at);

CREATE TABLE IF NOT EXISTS workout_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL DEFAULT 'health_connect',
    external_id TEXT,
    date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_minutes REAL,
    exercise_type INTEGER,
    title TEXT,
    active_kcal REAL,
    distance_km REAL,
    app_source TEXT,
    estimated_active_kcal REAL,
    estimated_met REAL,
    estimated_kcal_source TEXT,
    raw_json TEXT,
    imported_at TEXT NOT NULL,
    UNIQUE(source, external_id)
);

CREATE INDEX IF NOT EXISTS idx_workout_sessions_date
ON workout_sessions (date);
