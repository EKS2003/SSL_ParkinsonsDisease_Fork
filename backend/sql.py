import sqlite3

conn = sqlite3.connect('ParkinsonsPatients.db')
cursor = conn.cursor()

#Lab Records not created yet
cursor.execute("CREATE TABLE patients(patient_id TEXT PRIMARY KEY, name TEXT, dob DATE, height INTEGER, weight INTEGER)")

cursor.execute("CREATE TABLE IF NOT EXISTS visits ( visit_id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES Patients(patient_id) ON DELETE CASCADE, visit_date DATETIME NOT NULL, progression_note TEXT, doctor_notes TEXT, vitals_json TEXT, status TEXT DEFAULT 'closed'")

cursor.execute("CREATE TABLE testresults(test_id INTEGER PRIMARY KEY, test_type TEXT, test_date DATE,keypoints text)")