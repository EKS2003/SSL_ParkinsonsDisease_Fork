// src/api/mappers/testMapper.ts
import { AVAILABLE_TESTS, Test, TestIndicator } from '@/types/patient';
import {IndicatorColor, BackendTestEntry , BackendTestIndicator, BackendPatientCreate, BackendPatient, BackendDoctorNoteEntry, BackendLabResultEntry} from '@/types/backend_types';

type TestType = Test['type'];
type TestStatus = Test['status'];

export const API_BASE_URL = 'http://localhost:8000'; //not using docker if you are swich back to 8000



const TEST_METADATA: Record<TestType, { name: string; description: string }> = AVAILABLE_TESTS.reduce(
  (acc, test) => {
    acc[test.id] = { name: test.name, description: test.description };
    return acc;
  },
  {
    'stand-and-sit': { name: 'Stand and Sit Test', description: 'Measures sit-to-stand motor function' },
    'finger-tapping': { name: 'Finger Tapping Test', description: 'Measures rapid finger dexterity' },
    'fist-open-close': { name: 'Fist Open and Close Test', description: 'Assesses hand opening and closing cycles' },
  } as Record<TestType, { name: string; description: string }>,
);



const resolveRecordingPaths = (recordingUrl?: string | null, recordingFile?: string | null) => {
  let absolute: string | undefined;
  let relative: string | undefined;

  if (recordingUrl) {
    if (recordingUrl.startsWith('http://') || recordingUrl.startsWith('https://')) {
      absolute = recordingUrl;
    } else {
      relative = recordingUrl.startsWith('/') ? recordingUrl : `/${recordingUrl}`;
      absolute = `${API_BASE_URL}${relative}`;
    }
  } else if (recordingFile) {
    const sanitized = recordingFile.replace(/^\/+/, '');
    relative = `/recordings/${sanitized}`;
    absolute = `${API_BASE_URL}${relative}`;
  }

  return { relative, absolute };
};

const STATUS_INDICATORS: Record<TestStatus, TestIndicator> = {
  completed: {
    color: 'success',
    label: 'Completed',
    description: 'Recording captured successfully.',
  },
  'in-progress': {
    color: 'warning',
    label: 'In Progress',
    description: 'Recording underway. Metrics may still be processing.',
  },
  pending: {
    color: 'muted',
    label: 'Pending',
    description: 'Test scheduled but no recording available yet.',
  },
};

const KNOWN_TEST_TYPES: readonly TestType[] = ['stand-and-sit', 'finger-tapping', 'fist-open-close'] as const;


const isIndicatorColor = (value: string): value is IndicatorColor => {
  return ['success', 'warning', 'destructive', 'muted'].includes(value);
};


const resolveTestStatus = (value?: string | null, hasRecording: boolean = false): TestStatus => {
  const normalized = (value || '').trim().toLowerCase();
  if (normalized === 'completed' || normalized === 'in-progress' || normalized === 'pending') {
    return normalized as TestStatus;
  }
  return hasRecording ? 'completed' : 'pending';
};

const normalizeIndicator = (status: TestStatus, indicator?: BackendTestIndicator | null): TestIndicator => {
  const base = { ...STATUS_INDICATORS[status] };
  if (!indicator) {
    return base;
  }
  if (indicator.color && typeof indicator.color === 'string' && isIndicatorColor(indicator.color)) {
    base.color = indicator.color;
  }
  if (indicator.label && typeof indicator.label === 'string') {
    base.label = indicator.label;
  }
  if (indicator.description && typeof indicator.description === 'string') {
    base.description = indicator.description;
  }
  return base;
};


const normalizeTestKey = (value?: string | null): string => {
  if (!value) return '';
  return value.trim().toLowerCase().replace(/[_\s]+/g, '-');
};


const resolveTestType = (value?: string | null): TestType => {
  const normalized = normalizeTestKey(value);
  if ((KNOWN_TEST_TYPES as readonly string[]).includes(normalized as TestType)) {
    return normalized as TestType;
  }
  if (normalized === 'finger-taping') {
    return 'finger-tapping';
  }
  return 'stand-and-sit';
};

const toDate = (value?: string | null): Date => {
  if (!value) return new Date();
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
};

const parseNumber = (value: number | string | null | undefined): number | null => {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

export function normalizeBirthDate(value: string): string {
  if (!value) return '';
  const trimmed = value.trim();
  if (!trimmed) return '';

  const isoMatch = trimmed.match(/^(\d{4})[\/-](\d{2})[\/-](\d{2})$/);
  if (isoMatch) {
    return `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return '';

  const year = parsed.getUTCFullYear();
  const month = String(parsed.getUTCMonth() + 1).padStart(2, '0');
  const day = String(parsed.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export const calculateAge = (birthDate: string): number => {
  const normalized = normalizeBirthDate(birthDate);
  if (!normalized) return 0;

  const [yearStr, monthStr, dayStr] = normalized.split('-');
  const year = Number(yearStr);
  const month = Number(monthStr);
  const day = Number(dayStr);

  if (!year || !month || !day) return 0;

  const today = new Date();
  let age = today.getFullYear() - year;
  const monthDiff = today.getMonth() + 1 - month;

  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < day)) {
    age--;
  }
  
  return Math.max(0, age);
};



export const convertBackendTestToFrontend = (patientId: string, entry: BackendTestEntry): Test => {
  const testType = resolveTestType(entry.test_name || entry.name || entry.display_name);
  const metadata = TEST_METADATA[testType];
  const recordingPaths = resolveRecordingPaths(entry.recording_url, entry.recording_file);
  const hasRecording = Boolean(recordingPaths.absolute);
  const status = resolveTestStatus(entry.status, hasRecording);
  const indicator = normalizeIndicator(status, entry.indicator);
  const testDate = toDate(entry.date);

  const dtwMetrics = entry.dtw || null;
  const similarity = dtwMetrics ? parseNumber(dtwMetrics.similarity) : null;
  const distance = dtwMetrics ? parseNumber(dtwMetrics.distance) : null;

  const rawId = entry.test_id || entry.id || entry.recording_file || `${testType}-${testDate.getTime()}`;
  const sanitizedId = String(rawId).replace(/\s+/g, '-');

  return {
    id: sanitizedId,
    patientId,
    name: entry.display_name || entry.name || metadata?.name || 'Motor Test',
    type: testType,
    date: testDate,
    status,
    videoUrl: recordingPaths.absolute,
    recordingUrl: recordingPaths.absolute ?? recordingPaths.relative,
    recordingFile: entry.recording_file || undefined,
    summaryAvailable: entry.summary_available ?? hasRecording,
    frameCount: parseNumber(entry.frame_count),
    fps: parseNumber(entry.fps),
    similarity,
    distance,
    dtwSessionId: dtwMetrics && typeof dtwMetrics.session_id === 'string' ? dtwMetrics.session_id : null,
    indicator,
    results: undefined,
  };
};

export const convertBackendToFrontend = (backendPatient: BackendPatient) => {
  // Handle undefined or null name
  const name = backendPatient.name || '';
  const nameParts = name.split(' ');
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ') || '';
  const normalizedBirthDate = normalizeBirthDate(backendPatient.birthDate);
  const doctorNotesHistoryRaw = backendPatient.doctors_notes_history || [];
  const labResultsHistoryRaw = backendPatient.lab_results_history || [];

  const doctorNotesHistory = doctorNotesHistoryRaw.map(entry => ({
    id: entry.id || `note_${Date.now()}`,
    date: new Date(entry.date),
    note: entry.note,
    addedBy: entry.added_by || 'Unknown',
  }));

  const labResultsHistory = labResultsHistoryRaw.map(entry => ({
    id: entry.id || `lab_${Date.now()}`,
    date: new Date(entry.date),
    results: entry.results,
    addedBy: entry.added_by || 'Unknown',
  }));

  const latestDoctorNoteBackend = backendPatient.latest_doctor_note || doctorNotesHistoryRaw
    .slice()
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0];

  const latestLabResultBackend = backendPatient.latest_lab_result || labResultsHistoryRaw
    .slice()
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())[0];

  const latestDoctorNote = latestDoctorNoteBackend
    ? {
        id: latestDoctorNoteBackend.id || `note_${Date.now()}`,
        date: new Date(latestDoctorNoteBackend.date),
        note: latestDoctorNoteBackend.note,
        addedBy: latestDoctorNoteBackend.added_by || 'Unknown',
      }
    : undefined;

  const latestLabResult = latestLabResultBackend
    ? {
        id: latestLabResultBackend.id || `lab_${Date.now()}`,
        date: new Date(latestLabResultBackend.date),
        results: latestLabResultBackend.results,
        addedBy: latestLabResultBackend.added_by || 'Unknown',
      }
    : undefined;

  const lastVisit = latestDoctorNote?.date ?? null;
  const primaryPhysician = latestDoctorNote?.addedBy?.trim() || null;

  return {
    id: backendPatient.patient_id || "",
    firstName,
    lastName,
    recordNumber: backendPatient.patient_id || '', // Using patient_id as record number
    birthDate: normalizedBirthDate || backendPatient.birthDate || '',
    height: `${backendPatient.height || 0} cm`,
    weight: `${backendPatient.weight || 0} kg`,
    labResults: latestLabResult?.results || '',
    doctorNotes: latestDoctorNote?.note || '',
    labResultsHistory,
    doctorNotesHistory,
    severity: mapSeverity(backendPatient.severity || 'low'),
    lastVisit,
    primaryPhysician,
    createdAt: lastVisit ?? new Date(), // Backend doesn't provide this, approximated from last visit
    updatedAt: lastVisit ?? new Date(), // Backend doesn't provide this, approximated from last visit
  };
};

export const convertFrontendToBackend = (frontendPatient: any): BackendPatientCreate => {
  const fullName = `${frontendPatient.firstName || ''} ${frontendPatient.lastName || ''}`.trim();
  
  const heightStr = (frontendPatient.height || '').replace(/[^\d.]/g, '');
  const weightStr = (frontendPatient.weight || '').replace(/[^\d.]/g, '');
  const normalizedBirthDate = normalizeBirthDate(frontendPatient.birthDate);
  
  const ensureISODate = (value: any): string => {
    if (value instanceof Date) return value.toISOString();
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? new Date().toISOString() : parsed.toISOString();
  };

  const labResultsHistory: BackendLabResultEntry[] = (frontendPatient.labResultsHistory || []).map((entry: any) => ({
    id: entry.id,
    date: ensureISODate(entry.date),
    results: entry.results,
    added_by: entry.addedBy,
  }));

  const doctorNotesHistory: BackendDoctorNoteEntry[] = (frontendPatient.doctorNotesHistory || []).map((entry: any) => ({
    id: entry.id,
    date: ensureISODate(entry.date),
    note: entry.note,
    added_by: entry.addedBy,
  }));

  const trimmedLabResults = (frontendPatient.labResults || '').trim();
  if (trimmedLabResults && labResultsHistory.length === 0) {
    labResultsHistory.push({
      id: `lab_${Date.now()}`,
      date: new Date().toISOString(),
      results: trimmedLabResults,
      added_by: frontendPatient.primaryPhysician || 'Unknown',
    });
  }

  const trimmedDoctorNotes = (frontendPatient.doctorNotes || '').trim();
  if (trimmedDoctorNotes && doctorNotesHistory.length === 0) {
    doctorNotesHistory.push({
      id: `note_${Date.now()}`,
      date: new Date().toISOString(),
      note: trimmedDoctorNotes,
      added_by: frontendPatient.primaryPhysician || 'Unknown',
    });
  }

  return {
    name: fullName,
    age: calculateAge(normalizedBirthDate || frontendPatient.birthDate), // Use your existing function
    birthDate: normalizedBirthDate || frontendPatient.birthDate,
    height: heightStr || '0',
    weight: weightStr || '0',
    severity: mapSeverityToBackend(frontendPatient.severity),
    lab_results_history: labResultsHistory,
    doctors_notes_history: doctorNotesHistory,
  };
};

export const mapSeverity = (backendSeverity: string): 'Stage 1' | 'Stage 2' | 'Stage 3' | 'Stage 4' | 'Stage 5' => {
  const normalized = (backendSeverity || '').trim().toLowerCase();
  const mapping: Record<string, 'Stage 1' | 'Stage 2' | 'Stage 3' | 'Stage 4' | 'Stage 5'> = {
    'stage 1': 'Stage 1',
    'stage 2': 'Stage 2',
    'stage 3': 'Stage 3',
    'stage 4': 'Stage 4',
    'stage 5': 'Stage 5',
    'low': 'Stage 1',
    'mild': 'Stage 2',
    'medium': 'Stage 3',
    'moderate': 'Stage 3',
    'high': 'Stage 4',
    'severe': 'Stage 5',
  };

  return mapping[normalized] ?? 'Stage 1';
};

const mapSeverityToBackend = (frontendSeverity: string): string => {
  const normalized = (frontendSeverity || '').trim().toLowerCase();
  const mapping: Record<string, string> = {
    'stage 1': 'Stage 1',
    'stage 2': 'Stage 2',
    'stage 3': 'Stage 3',
    'stage 4': 'Stage 4',
    'stage 5': 'Stage 5',
    'low': 'Stage 1',
    'mild': 'Stage 2',
    'medium': 'Stage 3',
    'moderate': 'Stage 3',
    'high': 'Stage 4',
    'severe': 'Stage 5',
  };

  return mapping[normalized] ?? 'Stage 1';
};

// Placeholder so you can later push backend test details into Test.results
export const formatTestResults = (_entry: BackendTestEntry): Partial<Test> => {
  return {};
};
