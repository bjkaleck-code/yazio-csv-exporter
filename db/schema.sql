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
    source TEXT,
    updated_at TEXT
);
