import { AVAILABLE_TESTS, Test, TestIndicator } from '@/types/patient';

export interface BackendLabResultEntry {
  id?: string;
  date: string;
  results: string;
  added_by?: string;
}

export interface BackendDoctorNoteEntry {
  id?: string;
  date: string;
  note: string;
  added_by?: string;
}

export interface BackendPatient {
  patient_id: string;
  name: string;
  birthDate: string;
  height: number;
  weight: number;
  severity: string;
  lab_results_history?: BackendLabResultEntry[];
  doctors_notes_history?: BackendDoctorNoteEntry[];
  latest_lab_result?: BackendLabResultEntry | null;
  latest_doctor_note?: BackendDoctorNoteEntry | null;
}

export type IndicatorColor = TestIndicator['color'];

export interface BackendTestIndicator {
  color?: string | null;
  label?: string | null;
  description?: string | null;
}

export interface BackendDtwMetrics {
  distance?: number | string | null;
  avg_step_cost?: number | string | null;
  similarity?: number | string | null;
  session_id?: string | null;
  artifacts_dir?: string | null;
  artifacts?: { dir?: string | null } | null;
}

export interface BackendTestEntry {
  id?: string | null;
  test_id?: string | null;
  test_name?: string | null;
  display_name?: string | null;
  name?: string | null;
  date?: string | null;
  status?: string | null;
  recording_file?: string | null;
  recording_url?: string | null;
  summary_available?: boolean | null;
  frame_count?: number | string | null;
  fps?: number | string | null;
  dtw?: BackendDtwMetrics | null;
  indicator?: BackendTestIndicator | null;
  patient_id?: string | null;
  model?: string | null;
}

export interface BackendPatientCreate {
  name: string;
  age: number;
  birthDate: string;
  height: string;
  weight: string;
  lab_results?: string;
  doctors_notes?: string;
  severity: string;
  lab_results_history?: BackendLabResultEntry[];
  doctors_notes_history?: BackendDoctorNoteEntry[];
}

export interface BackendPatientUpdate {
  name?: string;
  age?: number;
  birthDate?: string;
  height?: string;
  weight?: string;
  severity?: string;
  lab_results_history?: BackendLabResultEntry[];
  doctors_notes_history?: BackendDoctorNoteEntry[];
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}