import sqlite3

conn = sqlite3.connect("ParkinsonsPatients.db")
conn.execute("PRAGMA foreign_keys = ON")  # enable foreign key constraints
cursor = conn.cursor()

# Patients
cursor.execute("""
CREATE TABLE IF NOT EXISTS patients(
    patient_id TEXT PRIMARY KEY,
    name TEXT,
    dob DATE,
    height INTEGER,
    weight INTEGER
)
""")

# Visits
cursor.execute("""
CREATE TABLE IF NOT EXISTS visits(
    visit_id INTEGER PRIMARY KEY,
    patient_id TEXT NOT NULL,
    visit_date DATETIME NOT NULL,
    progression_note TEXT,
    doctor_notes TEXT,
    vitals_json TEXT,
    status TEXT DEFAULT 'closed',
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
)
""")

# Test Results
cursor.execute("""
CREATE TABLE IF NOT EXISTS testresults(
    test_id INTEGER PRIMARY KEY,
    patient_id TEXT NOT NULL,
    test_type TEXT,
    test_date DATE,
    keypoints TEXT,
    FOREIGN KEY(patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
)
""")

conn.commit()
conn.close()