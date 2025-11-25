import { Test } from "@/types/patient";
import { API_BASE_URL } from "./mappers/testMapper";
import {
  ApiResponse,
  BackendPatient,
  BackendPatientUpdate,
  BackendTestEntry,
} from "@/types/backend_types";
import {
  normalizeBirthDate,
  calculateAge,
  convertBackendTestToFrontend,
  convertBackendToFrontend,
  convertFrontendToBackend,
} from "./mappers/testMapper";

import type {
  AxisAggResponse,
  CanonicalTest,
  DtwSessionMeta,
  DtwSeriesMetrics,
  BackendDtwSessionRow,
  BackendLookupSession,
} from "@/types/dtw";
// API service class

class ApiService {
  private baseUrl: string;

  private tokenKey = "auth_token";
  private accessToken: string | null;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;

    //Basically checks if window is fine. Tries to also check if there is a token
    if (typeof window !== "undefined") {
      this.accessToken = window.localStorage.getItem(this.tokenKey);
    } else {
      this.accessToken = null;
    }
  }

  private setToken(token: string | null) {
    this.accessToken = token;
    if (typeof window !== "undefined") {
      if (token) {
        window.localStorage.setItem(this.tokenKey, token);
      } else {
        window.localStorage.removeItem(this.tokenKey);
      }
    }
  }

  public getToken(): string | null {
    return this.accessToken ?? null;
  }

  public isAuthenticated(): boolean {
    return !!this.accessToken;
  }

  public logout() {
    this.setToken(null);
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    try {
      const url = `${this.baseUrl}${endpoint}`;

      // NEW: build headers, add JSON Content-Type & Authorization
      const headers: HeadersInit = {
        ...(options.headers || {}),
      };

      // Only force JSON if body is not FormData and user didn't set content-type
      const hasContentType = Object.keys(headers).some(
        (k) => k.toLowerCase() === "content-type"
      );
      if (
        options.body &&
        !(options.body instanceof FormData) &&
        !hasContentType
      ) {
        headers["Content-Type"] = "application/json";
      }

      if (this.accessToken) {
        headers["Authorization"] = `Bearer ${this.accessToken}`;
      }

      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        this.logout(); // clears token + localStorage
        window.location.href = "/login"; // hard redirect to login
        return { success: false, error: "Unauthorized" };
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        console.error("API Error Response:", errorData);
        console.error("Error Response Type:", typeof errorData);
        console.error("Error Detail Type:", typeof errorData.detail);
        console.error("Full Error Object:", JSON.stringify(errorData, null, 2));

        let errorMessage = `HTTP error! status: ${response.status}`;

        if (errorData.detail) {
          if (Array.isArray(errorData.detail)) {
            // Handle validation error array
            errorMessage = errorData.detail
              .map((err: any) => {
                const field = err.loc?.join(".") || "field";
                return `${field}: ${err.msg}`;
              })
              .join(", ");
          } else if (typeof errorData.detail === "object") {
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
      console.error("API request failed:", error);
      return {
        success: false,
        error:
          error instanceof Error ? error.message : "Unknown error occurred",
      };
    }
  }

  async login(username: string, password: string): Promise<boolean> {
    const body = new URLSearchParams();
    body.append("username", username);
    body.append("password", password);

    const res = await this.request<{ access_token: string }>("/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });

    if (res.success && res.data?.access_token) {
      this.setToken(res.data.access_token);
      return true;
    }

    return false;
  }

  async registerUser(payload: {
    username: string;
    first_name: string;
    last_name: string;
    email: string;
    password: string;
    location?: string;
    title?: string;
    department?: string;
    speciality?: string;
  }): Promise<ApiResponse<any>> {
    return this.request<any>("/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // Get all patients
  async getPatients(
    skip: number = 0,
    limit: number = 100
  ): Promise<ApiResponse<any[]>> {
    const response = await this.request<{
      patients: BackendPatient[];
      total: number;
    }>(`/patients/?skip=${skip}&limit=${limit}`);

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(
        convertBackendToFrontend
      );
      return { success: true, data: convertedPatients };
    }

    return { success: false, error: response.error };
  }

  // Get single patient
  async getPatient(patientId: string): Promise<ApiResponse<any>> {
    const response = await this.request<
      { patient: BackendPatient } | BackendPatient
    >(`/patients/${patientId}`);

    if (response.success && response.data) {
      // Handle the nested patient structure from the backend
      const patientData =
        "patient" in response.data ? response.data.patient : response.data;
      const convertedPatient = convertBackendToFrontend(patientData);
      return { success: true, data: convertedPatient };
    }

    return { success: false, error: response.error };
  }

  // Create new patient
  async createPatient(patientData: any): Promise<ApiResponse<any>> {
    const backendData = convertFrontendToBackend(patientData);

    const response = await this.request<BackendPatient>("/patients/", {
      method: "POST",
      body: JSON.stringify(backendData),
    });

    if (response.success && response.data) {
      const convertedPatient = convertBackendToFrontend(response.data);
      return { success: true, data: convertedPatient };
    }

    return response;
  }

  // Update patient
  async updatePatient(
    patientId: string,
    updateData: any
  ): Promise<ApiResponse<any>> {
    const backendData: BackendPatientUpdate = {};

    console.log("Update patient input data:", updateData);

    if (updateData.firstName || updateData.lastName) {
      const fullName = `${updateData.firstName || ""} ${
        updateData.lastName || ""
      }`.trim();
      backendData.name = fullName;
    }

    if (updateData.birthDate !== undefined) {
      const normalized = normalizeBirthDate(updateData.birthDate);
      backendData.birthDate = normalized || updateData.birthDate;
      backendData.age = calculateAge(normalized || updateData.birthDate); // Use your existing function
    }

    if (updateData.height) {
      const heightStr = updateData.height.replace(/[^\d.]/g, "");
      backendData.height = heightStr || "0";
    }
    if (updateData.weight) {
      const weightStr = updateData.weight.replace(/[^\d.]/g, "");
      backendData.weight = weightStr || "0";
    }
    const ensureISODate = (value: any): string => {
      if (value instanceof Date) return value.toISOString();
      const parsed = new Date(value);
      return Number.isNaN(parsed.getTime())
        ? new Date().toISOString()
        : parsed.toISOString();
    };

    if (updateData.labResultsHistory) {
      backendData.lab_results_history = updateData.labResultsHistory.map(
        (entry: any) => ({
          id: entry.id,
          date: ensureISODate(entry.date),
          results: entry.results,
          added_by: entry.addedBy,
        })
      );
    } else if (
      typeof updateData.labResults === "string" &&
      updateData.labResults.trim()
    ) {
      backendData.lab_results_history = [
        {
          id: `lab_${Date.now()}`,
          date: new Date().toISOString(),
          results: updateData.labResults.trim(),
          added_by: updateData.primaryPhysician || "Unknown",
        },
      ];
    }

    if (updateData.doctorNotesHistory) {
      backendData.doctors_notes_history = updateData.doctorNotesHistory.map(
        (entry: any) => ({
          id: entry.id,
          date: ensureISODate(entry.date),
          note: entry.note,
          added_by: entry.addedBy,
        })
      );
    } else if (
      typeof updateData.doctorNotes === "string" &&
      updateData.doctorNotes.trim()
    ) {
      backendData.doctors_notes_history = [
        {
          id: `note_${Date.now()}`,
          date: new Date().toISOString(),
          note: updateData.doctorNotes.trim(),
          added_by: updateData.primaryPhysician || "Unknown",
        },
      ];
    }
    if (updateData.severity) {
      const mappedSeverity = updateData.severity;
      console.log(
        "Severity mapping:",
        updateData.severity,
        "->",
        mappedSeverity
      );
      backendData.severity = mappedSeverity;
    }

    console.log("Backend update data:", backendData);
    console.log("Data types:", {
      name: typeof backendData.name,
      birthDate: typeof backendData.birthDate,
      height: typeof backendData.height,
      weight: typeof backendData.weight,
      severity: typeof backendData.severity,
    });

    const response = await this.request<BackendPatient>(
      `/patients/${patientId}`,
      {
        method: "PUT",
        body: JSON.stringify(backendData),
      }
    );

    if (response.success && response.data) {
      const convertedPatient = convertBackendToFrontend(response.data);
      return { success: true, data: convertedPatient };
    }

    return response;
  }

  // Delete patient
  async deletePatient(patientId: string): Promise<ApiResponse<boolean>> {
    return await this.request<boolean>(`/patients/${patientId}`, {
      method: "DELETE",
    });
  }

  // Search patients
  async searchPatients(query: string): Promise<ApiResponse<any[]>> {
    const response = await this.request<{
      patients: BackendPatient[];
      count: number;
    }>(`/patients/search/${encodeURIComponent(query)}`);

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(
        convertBackendToFrontend
      );
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

    if (criteria.minAge !== undefined)
      backendCriteria.min_age = criteria.minAge;
    if (criteria.maxAge !== undefined)
      backendCriteria.max_age = criteria.maxAge;
    if (criteria.severity) backendCriteria.severity = criteria.severity;

    const response = await this.request<{
      patients: BackendPatient[];
      count: number;
    }>("/patients/filter/", {
      method: "POST",
      body: JSON.stringify(backendCriteria),
    });

    if (response.success && response.data) {
      const convertedPatients = response.data.patients.map(
        convertBackendToFrontend
      );
      return { success: true, data: convertedPatients };
    }

    return { success: false, error: response.error };
  }

  async addLabResult(
    patientId: string,
    lab: {
      id: string;
      date: string; // ISO string, e.g. toLocalISO()
      added_by: string | null;
      results: string;
    }
  ): Promise<ApiResponse<any>> {
    return this.request<any>(`/patients/${patientId}`, {
      method: "PUT",
      body: JSON.stringify({
        lab_results: lab,
      }),
    });
  }

  async addDoctorNote(
    patientId: string,
    note: {
      id: string;
      date: string; // ISO string, e.g. toLocalISO()
      note: string;
      added_by: string | null;
    }
  ): Promise<ApiResponse<any>> {
    return this.request<any>(`/patients/${patientId}`, {
      method: "PUT",
      body: JSON.stringify({
        doctors_notes: note,
      }),
    });
  }

  // Get test history for a patient
  async getPatientTests(patientId: string): Promise<ApiResponse<Test[]>> {
    const response = await this.request<
      { tests: BackendTestEntry[] } | BackendTestEntry[]
    >(`/patients/${patientId}/tests`);

    if (response.success && response.data) {
      const payload = response.data;
      const testsRaw = Array.isArray(payload) ? payload : payload.tests ?? [];
      const converted = testsRaw
        .filter(Boolean)
        .map((entry) =>
          convertBackendTestToFrontend(patientId, entry as BackendTestEntry)
        );
      converted.sort((a, b) => b.date.getTime() - a.date.getTime());
      return { success: true, data: converted };
    }

    return { success: false, error: response.error };
  }

  // Add a test result for a patient
  async addPatientTest(
    patientId: string,
    testData: any
  ): Promise<ApiResponse<boolean>> {
    const response = await this.request<boolean>(
      `/patients/${patientId}/tests`,
      {
        method: "POST",
        body: JSON.stringify(testData),
        headers: { "Content-Type": "application/json" },
      }
    );
    return response;
  }

  async resolveDtwRoute(
    idOrSession: string,
    signal?: AbortSignal
  ): Promise<{ testName: string; sessionId: string }> {
    const res = await this.request<BackendLookupSession>(
      `/dtw/sessions/lookup/${encodeURIComponent(idOrSession)}`,
      { signal }
    );
    if (!res.success || !res.data) {
      throw new Error(res.error || "Failed to resolve DTW route");
    }

    // Map backend → frontend shape
    return {
      testName: res.data.test_name,
      sessionId: res.data.session_id,
    };
  }

  async listDtwSessions(
    testKey: CanonicalTest,
    signal?: AbortSignal
  ): Promise<DtwSessionMeta[]> {
    const res = await this.request<BackendDtwSessionRow[]>(
      `/dtw/sessions/${encodeURIComponent(testKey)}`,
      { signal }
    );
    if (!res.success || !res.data) {
      throw new Error(res.error || "Failed to list DTW sessions");
    }

    // Adapt SQL-backed rows to the older DtwSessionMeta shape
    const mapped: DtwSessionMeta[] = res.data.map((row) => ({
      session_id: row.session_id,
      created_utc: row.test_date ?? "",
      // we don't have model/live_len/ref_len in SQL schema, leave undefined
      distance: row.distance_pos ?? undefined,
      similarity: row.similarity_overall ?? undefined,
    }));

    return mapped;
  }

  async getDtwSeriesMetrics(
    testKey: CanonicalTest,
    sessionId: string,
    maxPoints = 200,
    signal?: AbortSignal
  ): Promise<DtwSeriesMetrics> {
    const res = await this.request<DtwSeriesMetrics>(
      `/dtw/sessions/${encodeURIComponent(testKey)}/${encodeURIComponent(
        sessionId
      )}/series?max_points=${maxPoints}`,
      { signal }
    );
    if (!res.success || !res.data) {
      throw new Error(res.error || "Failed to fetch DTW series metrics");
    }
    return res.data;
  }

  async getAxisAggregate(
    params: {
      testKey: CanonicalTest;
      sessionId: string;
      axis?: "x" | "y" | "z";
      reduce?: "mean" | "median" | "pca1";
      landmarks?: string;
      maxPoints?: number;
    },
    signal?: AbortSignal
  ): Promise<AxisAggResponse> {
    const {
      testKey,
      sessionId,
      axis = "x",
      reduce = "mean",
      landmarks = "all",
      maxPoints = 600,
    } = params;

    const query =
      `?axis=${axis}` +
      `&reduce=${reduce}` +
      `&landmarks=${encodeURIComponent(landmarks)}` +
      `&max_points=${maxPoints}`;

    const res = await this.request<AxisAggResponse>(
      `/dtw/sessions/${encodeURIComponent(testKey)}/${encodeURIComponent(
        sessionId
      )}/axis_agg${query}`,
      { signal }
    );
    if (!res.success || !res.data) {
      throw new Error(res.error || "Failed to fetch DTW axis aggregate");
    }
    return res.data;
  }

 async listTestVideos(
    patientId: string,
    testKey: CanonicalTest,
    signal?: AbortSignal
  ): Promise<{ success: boolean; videos: string[] }> {
    const res = await this.request<{ success: boolean; videos: string[] }>(
      `/videos/${encodeURIComponent(patientId)}/${encodeURIComponent(testKey)}`,
      { signal }
    );
    if (!res.success || !res.data) {
      throw new Error(res.error || "Failed to list DTW videos");
    }
    return res.data;
  }

  // SIMPLE: build a public URL to a recording
  public buildVideoUrl(filename: string): string {
    return `${this.baseUrl}/recordings/${encodeURIComponent(filename)}`;
  }

  async downloadDtwPayload(
    testKey: CanonicalTest,
    sessionId: string,
    signal?: AbortSignal
  ): Promise<Blob> {
    const url = `${this.baseUrl}/dtw/sessions/${encodeURIComponent(
      testKey
    )}/${encodeURIComponent(sessionId)}/download`;

    const headers: HeadersInit = {};
    if (this.accessToken) {
      headers["Authorization"] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(url, { headers, signal });
    if (!response.ok) {
      throw new Error(
        `Failed to download DTW recording (status ${response.status})`
      );
    }
    return await response.blob();
  }
}

// Export singleton instance
export const apiService = new ApiService();
export default apiService;
