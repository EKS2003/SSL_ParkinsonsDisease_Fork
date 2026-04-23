# Frontend Cleanup & Backend Integration Design

**Date:** 2026-04-23  
**Branch:** ml-demo-refactor  

---

## Goals

1. Fix broken backend integration in `PatientDetails.tsx` (hardcoded URLs, edits not saving)
2. Add shared `AuthContext` so `getMe()` is called once and current user is available everywhere
3. Strip dead code and debug noise from `api.ts`, `PatientList.tsx`, `VideoSummary.tsx`
4. Fix DTW session 404s caused by missing `dtw_artifacts.npz` and empty templates directory

---

## Section 1: AuthContext

**New file:** `frontend/src/contexts/AuthContext.tsx`

- Exports `AuthProvider` and `useAuth()`
- Shape: `{ fullName: string; email: string } | null`
- Calls `apiService.getMe()` once on mount; skips fetch if no token present
- Provider wraps the route tree in `App.tsx` (inside `QueryClientProvider`)

**Consumers that replace their own `getMe()` calls:**
- `PatientList.tsx` — remove `useEffect` + `getMe()` for avatar initials; use `useAuth()`
- `Profile.tsx` — remove `useEffect` + `getMe()` for initial form values; use `useAuth()`
- `PatientDetails.tsx` — use `useAuth()` for `addedBy` in lab result and doctor note handlers

---

## Section 2: PatientDetails backend integration fixes

### 2a. Patient fetch
- **Before:** raw `fetch('http://localhost:8000/patients/${id}')` with inline conversion logic (line 252)
- **After:** `apiService.getPatient(id)` — uses auth token, Vite proxy, and existing conversion

### 2b. Edit patient submit
- **Before:** `handleEditSubmit` only calls `setPatient(updated)` — changes are never persisted
- **After:** calls `apiService.updatePatient(patient.id, editData)`, uses returned patient to update state, shows toast on success/failure

### 2c. Add lab result
- **Before:** raw `fetch('http://localhost:8000/patients/${patient.id}', { method: 'PUT', ... })` (line 168) with no auth header; `addedBy` hardcoded to `"Current User"`
- **After:** `apiService.updatePatient(patient.id, { lab_results: { ... } })`; `addedBy` = `useAuth()?.fullName ?? 'Unknown'`

### 2d. Add doctor note
- **Before:** same raw fetch pattern (line 221); `addedBy` hardcoded to `"Current User"`
- **After:** `apiService.updatePatient(patient.id, { doctors_notes: { ... } })`; `addedBy` = `useAuth()?.fullName ?? 'Unknown'`

---

## Section 3: api.ts dead code cleanup

| Item | Location | Action |
|---|---|---|
| `calculateAge` function | `api.ts:60` | Remove; import `calculateAge` from `@/lib/utils` instead |
| Duplicate `ensureISODate` helper | defined inside both `convertFrontendToBackend` and `updatePatient` | Extract to one module-level function |
| Debug `console.log` / `console.error` | ~10 calls in `request`, `updatePatient`, `getPatients` | Remove all |
| `//remove later` comment | `api.ts:59` | Remove with the function |
| Debug logs in `PatientList.tsx` | lines 135–138 | Remove |
| Debug logs in `VideoSummary.tsx` | lines 601–604, 659 | Remove |

---

## Section 4: DTW session 404 fix

### Root cause chain
1. `*.npz` is gitignored globally — template NPZ files were never committed
2. `backend/routes/templates/` is empty on this checkout
3. `EndOnlyDTW.__init__` catches the `FileNotFoundError` and sets `init_error`
4. `finalize_and_save` returns `{ok: False}` early — `save_dtw_npz` is never called — no `dtw_artifacts.npz` is written
5. Old `meta.json` files (from a prior machine where templates existed) are committed to git — they appear as selectable sessions but 404 on `/series` and `/axis_agg`

### Fixes

**Backend:**
- Add `!backend/routes/templates/**/*.npz` to `.gitignore` so template files can be committed
- User must run `create_template.py` to generate templates (one-time setup per test type)
- `list_sessions` in `dtw_rest.py`: skip session dirs that have no `dtw_artifacts.npz` so broken orphaned sessions don't appear in the UI
- Remove all 6 orphaned `meta.json`-only session directories under `backend/routes/dtw_runs/finger-tapping/` from the repo (`git rm -r`)

**Frontend (VideoSummary.tsx):**
- When `/series` returns 404 (artifacts missing), show a clear "No analysis data available for this session. Run a new test to generate results." state instead of a raw error string
- The existing graceful error handling wiring (`metricsErr`) is already in place; just improve the message when the status is 404

---

## Files to create/modify

| File | Change |
|---|---|
| `frontend/src/contexts/AuthContext.tsx` | Create |
| `frontend/src/App.tsx` | Wrap routes with `AuthProvider` |
| `frontend/src/pages/PatientList.tsx` | Use `useAuth()`, remove debug logs |
| `frontend/src/pages/Profile.tsx` | Use `useAuth()` |
| `frontend/src/pages/PatientDetails.tsx` | Use `apiService` for all fetches, use `useAuth()` for `addedBy` |
| `frontend/src/services/api.ts` | Remove dead code and debug logs |
| `frontend/src/pages/VideoSummary.tsx` | Improve 404 error messaging |
| `backend/routes/dtw_rest.py` | Filter sessions without NPZ in `list_sessions` |
| `.gitignore` | Add exception for template NPZ files |
| `backend/routes/dtw_runs/finger-tapping/` | Delete orphaned `meta.json`-only session dirs |
