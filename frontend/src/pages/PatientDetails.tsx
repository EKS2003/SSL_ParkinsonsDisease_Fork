import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Plus,
  Calendar,
  FileText,
  Activity,
  Edit,
  Play,
  User,
  Stethoscope,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Patient,
  Test,
  LabResultEntry,
  DoctorNoteEntry,
} from "@/types/patient";
import { getSeverityColor, calculateAge } from "@/lib/utils";
import { mapSeverity } from "@/services/api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";

// ---------- Date helpers ----------
const isValidDate = (d: unknown): d is Date =>
  d instanceof Date && !Number.isNaN(d.getTime());
const asDate = (v: unknown): Date => {
  const d = v instanceof Date ? v : new Date(v as any);
  return isValidDate(d) ? d : new Date(); // or choose to return new Date(0) / null
};
const toISO = (v: unknown): string => {
  const d = v instanceof Date ? v : new Date(v as any);
  return isValidDate(d) ? d.toISOString() : new Date().toISOString();
};

const PatientDetails = () => {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tests, setTests] = useState<Test[]>([]); // Placeholder – replace with real API if available
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editData, setEditData] = useState<Partial<Patient>>({});
  const [isLabResultModalOpen, setIsLabResultModalOpen] = useState(false);
  const [isDoctorNoteModalOpen, setIsDoctorNoteModalOpen] = useState(false);
  const [newLabResult, setNewLabResult] = useState("");
  const [newDoctorNote, setNewDoctorNote] = useState("");
  const { toast } = useToast();

  const openForEdit = useCallback(() => {
    if (!patient) return;
    setEditData({
      firstName: patient.firstName ?? "",
      lastName: patient.lastName ?? "",
      birthDate: patient.birthDate ?? "",
      height: patient.height ?? "",
      weight: patient.weight ?? "",
      labResults: patient.labResults ?? "",
      doctorNotes: patient.doctorNotes ?? "",
      severity: (patient.severity as Patient["severity"]) ?? "Stage 1",
    });
    setIsEditOpen(true);
  }, [patient]);

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!patient) return;
    const updated: Patient = { ...patient, ...editData } as Patient;
    setPatient(updated);
    setIsEditOpen(false);
  };

  // --- Send ONE lab result per submit (optimistic UI + rollback) ---
  const handleAddLabResult = async () => {
    if (!patient || !newLabResult.trim()) return;

    const newEntry: LabResultEntry = {
      id: `lab_${Date.now()}`,
      date: new Date(),
      results: newLabResult.trim(),
      addedBy: "Current User", // In a real app, this would come from auth context
    };

    const prev = patient;
    const updated = {
      ...patient,
      labResultsHistory: [...(patient.labResultsHistory ?? []), newEntry],
    };

    // optimistic UI
    setPatient(updated);
    setNewLabResult("");
    setIsLabResultModalOpen(false);

    try {
      const res = await fetch(`http://localhost:8000/patients/${patient.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lab_results: { value: newLabResult.trim() } }), // <-- not lab_results_history
      });
      const text = await res.text();
      if (!res.ok) throw new Error(`Save failed ${res.status}: ${text}`);
      toast({
        title: "Lab Result Added",
        description: "Recorded successfully.",
      });
    } catch (e) {
      console.error("Error saving lab result:", e);
      // rollback
      setPatient(prev);
      toast({
        title: "Error",
        description: "Failed to save lab result.",
        variant: "destructive",
      });
    }
  };

  // --- OPTIONAL: Send ONE doctor note per submit (same pattern) ---
  const handleAddDoctorNote = async () => {
    if (!patient || !newDoctorNote.trim()) return;

    const newEntry: DoctorNoteEntry = {
      id: `note_${Date.now()}`,
      date: new Date(),
      note: newDoctorNote.trim(),
      addedBy: "Current User",
    };

    const prev = patient;
    const updated = {
      ...patient,
      doctorNotesHistory: [...(patient.doctorNotesHistory ?? []), newEntry],
    };

    // optimistic UI
    setPatient(updated);
    setNewDoctorNote("");
    setIsDoctorNoteModalOpen(false);

    try {
      const res = await fetch(`http://localhost:8000/patients/${patient.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctors_notes: [
            {
              id: newEntry.id,
              date: toISO(newEntry.date),
              note: newEntry.note,
              added_by: newEntry.addedBy ?? null,
            },
          ],
        }),
      });
      const text = await res.text();
      if (!res.ok) throw new Error(`Save failed ${res.status}: ${text}`);
      toast({ title: "Note Added", description: "Recorded successfully." });
    } catch (e) {
      console.error("Error saving doctor note:", e);
      // rollback
      setPatient(prev);
      toast({
        title: "Error",
        description: "Couldn't save doctor's note.",
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    const fetchPatient = async () => {
      try {
        const response = await fetch(`http://localhost:8000/patients/${id}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "Failed to fetch patient");
        }

        const notesHist = data.doctors_notes_history || [];
        const labsHist = (data.lab_results_history || []).map(
          (e: any, i: number) => ({
            id: e.id ?? `lab_${i}`,
            date: asDate(e.date),
            results: e.results ?? "",
            addedBy: e.added_by ?? undefined,
          })
        );
        // Debug logging
        console.log("API Response:", data);
        console.log("Patient data:", data);
        console.log("Lab results history:", data?.lab_results_history);
        console.log("Doctor notes history:", data?.doctors_notes_history);

        const [firstName, lastName] = (data.name ?? "").split(" ");

        setPatient({
          id: data.patient_id,
          firstName: (data.name ?? "").split(" ")[0] ?? "",
          lastName: (data.name ?? "").split(" ").slice(1).join(" ") ?? "",
          recordNumber: data.patient_id,
          birthDate: data.birthDate,
          height: `${data.height}`,
          weight: `${data.weight}`,
          labResults: data.lab_results?.value ?? "", // <-- was .notes
          doctorNotes: data.doctors_notes || "",
          labResultsHistory: labsHist,
          doctorNotesHistory: notesHist.map((e: any) => ({
            id: e.visit_id,
            date: asDate(e.visit_date),
            note: e.note,
            addedBy: e.added_by,
          })),
          severity: mapSeverity(data.severity),
          createdAt: new Date(),
          updatedAt: new Date(),
        });

        setTests([]);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPatient();
  }, [id]);

  const getStatusColor = (status: Test["status"]) => {
    switch (status) {
      case "completed":
        return "bg-success text-success-foreground";
      case "in-progress":
        return "bg-warning text-warning-foreground";
      case "pending":
        return "bg-muted text-muted-foreground";
      default:
        return "bg-muted text-muted-foreground";
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-muted-foreground">Loading patient data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-destructive">{error}</p>
      </div>
    );
  }

  if (!patient) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card shadow-card">
        <div className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link to="/">
                <Button variant="outline" size="sm">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Back to Patients
                </Button>
              </Link>
              <div>
                <h1 className="text-3xl font-bold text-foreground">
                  {patient.firstName} {patient.lastName}
                </h1>
                <p className="text-muted-foreground mt-1">
                  Record: {patient.recordNumber || "N/A"}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Button variant="outline" onClick={openForEdit}>
                <Edit className="mr-2 h-4 w-4" />
                Edit Patient
              </Button>
              <Link to={`/patient/${id}/test-selection`}>
                <Button className="bg-primary hover:bg-primary-hover">
                  <Plus className="mr-2 h-4 w-4" />
                  New Test
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Patient Information */}
      <div className="container mx-auto px-6 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  Patient Information
                  <Badge className={getSeverityColor(patient.severity)}>
                    {patient.severity}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Date of Birth
                    </p>
                    <p className="text-lg font-semibold">
                      {patient.birthDate || "N/A"}
                      {patient.birthDate && (
                        <span className="text-sm text-muted-foreground ml-2">
                          (Age: {calculateAge(patient.birthDate)} years)
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground/70">
                      YYYY-MM-DD format
                    </p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Height
                    </p>
                    <p className="text-lg font-semibold">{patient.height}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Weight
                    </p>
                    <p className="text-lg font-semibold">{patient.weight}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      Severity
                    </p>
                    <p className="text-lg font-semibold">{patient.severity}</p>
                  </div>
                </div>

                <Separator />

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-sm font-medium text-muted-foreground">
                      Lab Results History
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setIsLabResultModalOpen(true)}
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Add Lab Result
                    </Button>
                  </div>
                  <div className="space-y-3">
                    {patient.labResultsHistory &&
                    patient.labResultsHistory.length > 0 ? (
                      patient.labResultsHistory
                        .sort((a, b) => a.date.getTime() - b.date.getTime())
                        .map((entry) => (
                          <div
                            key={entry.id}
                            className="border rounded-lg p-4 bg-card"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center text-sm text-muted-foreground">
                                <Stethoscope className="mr-2 h-4 w-4" />
                                <span>{entry.date.toLocaleDateString()}</span>
                                {entry.addedBy && (
                                  <>
                                    <span className="mx-2">•</span>
                                    <span>by {entry.addedBy}</span>
                                  </>
                                )}
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {entry.date.toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-sm">{entry.results}</p>
                          </div>
                        ))
                    ) : (
                      <p className="text-sm text-muted-foreground italic">
                        No lab results recorded
                      </p>
                    )}
                  </div>
                </div>

                <Separator />

                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-sm font-medium text-muted-foreground">
                      Doctor's Notes History
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setIsDoctorNoteModalOpen(true)}
                    >
                      <Plus className="mr-2 h-4 w-4" />
                      Add Note
                    </Button>
                  </div>
                  <div className="space-y-3">
                    {patient.doctorNotesHistory &&
                    patient.doctorNotesHistory.length > 0 ? (
                      patient.doctorNotesHistory
                        .sort((a, b) => a.date.getTime() - b.date.getTime())
                        .map((entry) => (
                          <div
                            key={entry.id}
                            className="border rounded-lg p-4 bg-muted/50"
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center text-sm text-muted-foreground">
                                <User className="mr-2 h-4 w-4" />
                                <span>{entry.date.toLocaleDateString()}</span>
                                {entry.addedBy && (
                                  <>
                                    <span className="mx-2">•</span>
                                    <span>by {entry.addedBy}</span>
                                  </>
                                )}
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {entry.date.toLocaleTimeString()}
                              </span>
                            </div>
                            <p className="text-sm">{entry.note}</p>
                          </div>
                        ))
                    ) : (
                      <p className="text-sm text-muted-foreground italic">
                        No doctor's notes recorded
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Test History (placeholder for now) */}
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center">
                  <Activity className="mr-2 h-5 w-5" />
                  Test History
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {tests.length > 0 ? (
                    tests.map((test) => (
                      <div key={test.id} className="border rounded-lg p-4">
                        <div className="flex items-start justify-between mb-2">
                          <div>
                            <h4 className="font-medium text-sm">{test.name}</h4>
                            <div className="text-xs text-muted-foreground mt-1">
                              <Calendar className="inline-block mr-1 h-3 w-3" />
                              {test.date.toLocaleDateString()}
                            </div>
                          </div>
                          <Badge
                            className={getStatusColor(test.status)}
                            variant="secondary"
                          >
                            {test.status}
                          </Badge>
                        </div>
                        {test.status === "completed" && (
                          <Link to={`/patient/${id}/video-summary/${test.id}`}>
                            <Button
                              size="sm"
                              variant="outline"
                              className="w-full mt-2"
                            >
                              <Play className="mr-2 h-3 w-3" />
                              View Results
                            </Button>
                          </Link>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <FileText className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                      <p className="text-sm text-muted-foreground">
                        No tests recorded yet
                      </p>
                      <Link to={`/patient/${id}/test-selection`}>
                        <Button size="sm" className="mt-3">
                          <Plus className="mr-2 h-3 w-3" />
                          Create First Test
                        </Button>
                      </Link>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Edit Patient pop up*/}
      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent aria-describedby={undefined}>
          <DialogHeader>
            <DialogTitle className="mb-4 text-lg font-semibold">
              Edit Patient Details
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="firstName">First Name</Label>
                <Input
                  id="firstName"
                  value={editData.firstName ?? ""}
                  onChange={(e) =>
                    setEditData((d) => ({ ...d, firstName: e.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="lastName">Last Name</Label>
                <Input
                  id="lastName"
                  value={editData.lastName ?? ""}
                  onChange={(e) =>
                    setEditData((d) => ({ ...d, lastName: e.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="birthDate">Birthdate</Label>
                <Input
                  id="birthDate"
                  type="date"
                  value={editData.birthDate ?? ""}
                  onChange={(e) =>
                    setEditData((d) => ({ ...d, birthDate: e.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="severity">Severity</Label>
                <Select
                  value={editData.severity ?? "Stage 1"}
                  onValueChange={(v) =>
                    setEditData((d) => ({
                      ...d,
                      severity: v as Patient["severity"],
                    }))
                  }
                >
                  <SelectTrigger id="severity">
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent position="popper" className="z-[60]">
                    <SelectItem value="Stage 1">Stage 1</SelectItem>
                    <SelectItem value="Stage 2">Stage 2</SelectItem>
                    <SelectItem value="Stage 3">Stage 3</SelectItem>
                    <SelectItem value="Stage 4">Stage 4</SelectItem>
                    <SelectItem value="Stage 5">Stage 5</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="height">Height</Label>
                <Input
                  id="height"
                  placeholder="e.g., 170 cm"
                  value={editData.height ?? ""}
                  onChange={(e) =>
                    setEditData((d) => ({ ...d, height: e.target.value }))
                  }
                />
              </div>
              <div>
                <Label htmlFor="weight">Weight</Label>
                <Input
                  id="weight"
                  placeholder="e.g., 70 kg"
                  value={editData.weight ?? ""}
                  onChange={(e) =>
                    setEditData((d) => ({ ...d, weight: e.target.value }))
                  }
                />
              </div>
            </div>

            <div>
              <Label htmlFor="labResults">Lab Results</Label>
              <Textarea
                id="labResults"
                rows={3}
                value={editData.labResults ?? ""}
                onChange={(e) =>
                  setEditData((d) => ({ ...d, labResults: e.target.value }))
                }
              />
            </div>

            <div>
              <Label htmlFor="doctorNotes">Doctor Notes</Label>
              <Textarea
                id="doctorNotes"
                rows={4}
                value={editData.doctorNotes ?? ""}
                onChange={(e) =>
                  setEditData((d) => ({ ...d, doctorNotes: e.target.value }))
                }
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsEditOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit">Save</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Lab Result Modal */}
      <Dialog
        open={isLabResultModalOpen}
        onOpenChange={setIsLabResultModalOpen}
      >
        <DialogContent aria-describedby={undefined} className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Lab Result</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="labResult">Lab Results</Label>
              <Textarea
                id="labResult"
                placeholder="Enter lab results (e.g., CBC: Normal, Dopamine markers: 120 ng/mL...)"
                value={newLabResult}
                onChange={(e) => setNewLabResult(e.target.value)}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsLabResultModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddLabResult}
              disabled={!newLabResult.trim()}
            >
              Add Result
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Doctor Note Modal */}
      <Dialog
        open={isDoctorNoteModalOpen}
        onOpenChange={setIsDoctorNoteModalOpen}
      >
        <DialogContent aria-describedby={undefined} className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Add Doctor's Note</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="doctorNote">Doctor's Note</Label>
              <Textarea
                id="doctorNote"
                placeholder="Enter doctor's notes or observations..."
                value={newDoctorNote}
                onChange={(e) => setNewDoctorNote(e.target.value)}
                rows={4}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDoctorNoteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddDoctorNote}
              disabled={!newDoctorNote.trim()}
            >
              Add Note
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PatientDetails;
