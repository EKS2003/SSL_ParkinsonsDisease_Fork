import { calculateAge } from "@/lib/utils";

const API_BASE_URL = 'http://localhost:8000';

// Types for backend API
interface BackendPatient {
  patient_id: string;
  name: string;
  birthDate: string;
  age: number;
  height: number;
  weight: number;
  lab_results: Record<string, any>;
  doctors_notes: string;
  severity: string;
}

interface BackendPatientCreate {
  name: string;
  age: number;
  height: string;
  weight: string;
  lab_results?: Record<string, any>;
  doctors_notes?: string;
  severity: string;
}

interface BackendPatientUpdate {
  name?: string;
  birthDate?: string;
  age?: number;
  height?: string;
  weight?: string;
  lab_results?: Record<string, any>;
  doctors_notes?: string;
  severity?: string;
}

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Convert backend patient to frontend patient
const convertBackendToFrontend = (backendPatient: BackendPatient) => {
  // Handle undefined or null name
  const name = backendPatient.name || '';
  const nameParts = name.split(' ');
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ') || '';
  
  return {
    id: backendPatient.patient_id || '',
    firstName,
    lastName,
    recordNumber: backendPatient.patient_id || '', // Using patient_id as record number
    birthDate: backendPatient.birthDate || 0,
    height: `${backendPatient.height || 0} cm`,
    weight: `${backendPatient.weight || 0} kg`,
    labResults: JSON.stringify(backendPatient.lab_results || {}),
    doctorNotes: backendPatient.doctors_notes || '',
    severity: mapSeverity(backendPatient.severity || 'stage 1'),
    createdAt: new Date(), // Backend doesn't provide this, using current date
    updatedAt: new Date(), // Backend doesn't provide this, using current date
  };
};

// Convert frontend patient to backend format
const convertFrontendToBackend = (frontendPatient: any): BackendPatientCreate => {
  const fullName = `${frontendPatient.firstName || ''} ${frontendPatient.lastName || ''}`.trim();
  
  const heightStr = (frontendPatient.height || '').replace(/[^\d.]/g, '');
  const weightStr = (frontendPatient.weight || '').replace(/[^\d.]/g, '');
  
  // Calculate age from birthDate
  const age = frontendPatient.birthDate ? calculateAge(frontendPatient.birthDate) : 0;
  
  // Parse lab results safely
  let labResults = {};
  if (frontendPatient.labResults) {
    try {
      labResults = typeof frontendPatient.labResults === 'string' 
        ? JSON.parse(frontendPatient.labResults) 
        : frontendPatient.labResults;
    } catch (error) {
      console.error('Error parsing labResults:', error);
      labResults = { notes: frontendPatient.labResults };
    }
  }
  
  return {
    name: fullName,
    age: Math.max(0, age), // Ensure age is never negative
    height: heightStr || '0',
    weight: weightStr || '0',
    lab_results: labResults,
    doctors_notes: frontendPatient.doctorNotes || '',
    severity: mapSeverityToBackend(frontendPatient.severity) || 'Stage 1',
  };
};

const VALID_SEVERITY_LEVELS = ['Stage 1', 'Stage 2', 'Stage 3', 'Stage 4', 'Stage 5'] as const;
type SeverityLevel = typeof VALID_SEVERITY_LEVELS[number];

export const mapSeverity = (severity: string): SeverityLevel => {
  const normalized = severity.trim();
  return VALID_SEVERITY_LEVELS.includes(normalized as SeverityLevel) 
    ? normalized as SeverityLevel 
    : 'Stage 1';
};

const mapSeverityToBackend = mapSeverity;

// API service class
class ApiService {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const url = `${this.baseUrl}${endpoint}`;
      
      const response = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
        ...options,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error('API Error Response:', errorData);
        console.error('Error Response Type:', typeof errorData);
        console.error('Error Detail Type:', typeof errorData.detail);
        console.error('Full Error Object:', JSON.stringify(errorData, null, 2));
        
        let errorMessage = `HTTP error! status: ${response.status}`;
        
        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            // Handle validation error array
            errorMessage = errorData.detail.map((err: any) => {
              const field = err.loc?.join('.') || 'field';
              return `${field}: ${err.msg}`;
            }).join(', ');
          } else if (typeof errorData.detail === 'object') {
            // Handle nested error object
            errorMessage = JSON.stringify(errorData.detail);
          } else {
            errorMessage = errorData.detail;
          }
        } else if (errorData.message) {
          errorMessage = errorData.message;
        }
        
        throw new Error(errorMessage);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      console.error('API request failed:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  // Get all patients
  async getPatients(skip: number = 0, limit: number = 100): Promise<ApiResponse<any[]>> {
    const response = await this.request<{ patients: BackendPatient[]; total: number }>(
      `/patients/?skip=${skip}&limit=${limit}`
    );

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(convertBackendToFrontend);
      return { success: true, data: convertedPatients };
    }

    return { success: false, error: response.error };
  }

  // Get single patient
  async getPatient(patientId: string): Promise<ApiResponse<any>> {
    const response = await this.request<{ patient: BackendPatient } | BackendPatient>(`/patients/${patientId}`);

    if (response.success && response.data) {
      // Handle the nested patient structure from the backend
      const patientData = 'patient' in response.data ? response.data.patient : response.data;
      const convertedPatient = convertBackendToFrontend(patientData);
      return { success: true, data: convertedPatient };
    }

    return { success: false, error: response.error };
  }

  // Create new patient
  async createPatient(patientData: any): Promise<ApiResponse<any>> {
    const backendData = convertFrontendToBackend(patientData);
    
    const response = await this.request<BackendPatient>('/patients/', {
      method: 'POST',
      body: JSON.stringify(backendData),
    });

    if (response.success && response.data) {
      const convertedPatient = convertBackendToFrontend(response.data);
      return { success: true, data: convertedPatient };
    }

    return response;
  }

  // Update patient
  async updatePatient(patientId: string, updateData: any): Promise<ApiResponse<any>> {
    const backendData: BackendPatientUpdate = {};
    
    console.log('Update patient input data:', updateData);
    
    if (updateData.firstName || updateData.lastName) {
      const fullName = `${updateData.firstName || ''} ${updateData.lastName || ''}`.trim();
      backendData.name = fullName;
    }
    
    if (updateData.age !== undefined) backendData.birthDate = updateData.age;
    if (updateData.height) {
      const heightStr = updateData.height.replace(/[^\d.]/g, '');
      backendData.height = heightStr || '0';
    }
    if (updateData.weight) {
      const weightStr = updateData.weight.replace(/[^\d.]/g, '');
      backendData.weight = weightStr || '0';
    }
    if (updateData.labResults) {
      try {
        backendData.lab_results = JSON.parse(updateData.labResults);
      } catch (error) {
        console.error('Error parsing labResults:', error);
        backendData.lab_results = { notes: updateData.labResults };
      }
    }
    if (updateData.doctorNotes !== undefined) backendData.doctors_notes = updateData.doctorNotes;
    if (updateData.severity) {
      const mappedSeverity = mapSeverityToBackend(updateData.severity);
      console.log('Severity mapping:', updateData.severity, '->', mappedSeverity);
      backendData.severity = mappedSeverity;
    }

            console.log('Backend update data:', backendData);
        console.log('Data types:', {
          name: typeof backendData.name,
          age: typeof backendData.birthDate,
          height: typeof backendData.height,
          weight: typeof backendData.weight,
          severity: typeof backendData.severity
        });

    const response = await this.request<BackendPatient>(`/patients/${patientId}`, {
      method: 'PUT',
      body: JSON.stringify(backendData),
    });

    if (response.success && response.data) {
      const convertedPatient = convertBackendToFrontend(response.data);
      return { success: true, data: convertedPatient };
    }

    return response;
  }

  // Delete patient
  async deletePatient(patientId: string): Promise<ApiResponse<boolean>> {
    return await this.request<boolean>(`/patients/${patientId}`, {
      method: 'DELETE',
    });
  }

  // Search patients
  async searchPatients(query: string): Promise<ApiResponse<any[]>> {
    const response = await this.request<{ patients: BackendPatient[]; count: number }>(
      `/patients/search/${encodeURIComponent(query)}`
    );

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(convertBackendToFrontend);
      return { success: true, data: convertedPatients };
    }

    return { success: false, error: response.error };
  }

  // Filter patients
  async filterPatients(criteria: {
    minAge?: number;
    maxAge?: number;
    severity?: string;
  }): Promise<ApiResponse<any[]>> {
    const backendCriteria: any = {};
    
    if (criteria.minAge !== undefined) backendCriteria.min_age = criteria.minAge;
    if (criteria.maxAge !== undefined) backendCriteria.max_age = criteria.maxAge;
    if (criteria.severity) backendCriteria.severity = mapSeverityToBackend(criteria.severity);

    const response = await this.request<{ patients: BackendPatient[]; count: number }>(
      '/patients/filter/',
      {
        method: 'POST',
        body: JSON.stringify(backendCriteria),
      }
    );

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(convertBackendToFrontend);
      return { success: true, data: convertedPatients };
    }

    return { success: false, error: response.error };
  }

  // Get test history for a patient
  async getPatientTests(patientId: string): Promise<ApiResponse<any[]>> {
    const response = await this.request<{ tests: any[] }>(`/patients/${patientId}/tests`);
    if (response.success && response.data) {
      // Optionally, map/convert test data here
      return { success: true, data: response.data.tests };
    }
    return { success: false, error: response.error };
  }

  // Add a test result for a patient
  async addPatientTest(patientId: string, testData: any): Promise<ApiResponse<boolean>> {
    const response = await this.request<boolean>(`/patients/${patientId}/tests`, {
      method: 'POST',
      body: JSON.stringify(testData),
      headers: { 'Content-Type': 'application/json' },
    });
    return response;
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService; 