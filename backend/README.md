Some helpfule things to note.
For the excel file upload it expects this type of file to be uploaded: 

A patients sheet with one row per patient and columns matching the Patient model:

patient_id  name  dob  height  weight

2. A visits sheet with one row per visit and a foreign key back to the patient

visit_id  patient_id  visit_date  progression_note  doctor_notes  vitals_json

3. A test results sheet with test-result entries and a foreign key to the patient

test_id  patiend_id  test_type  test_date  keypoints

Also follows the database structure


