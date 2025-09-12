import { useCallback, useEffect, useState} from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Plus, Calendar, FileText, Activity, Edit, Play } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Patient, Test } from '@/types/patient';
import { getSeverityColor, calculateAge } from '@/lib/utils';
import { mapSeverity } from '@/services/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select';
import { Label } from '@/components/ui/label';

// Mock data - replace with actual data fetching
const mockPatient: Patient = {
  id: '1',
  firstName: 'John',
  lastName: 'Smith',
  recordNumber: 'P001',
  birthDate: '1980-05-15',
  height: '5\'8"',
  weight: '170 lbs',
  labResults: 'Normal CBC, elevated dopamine markers, glucose 95 mg/dL',
  doctorNotes: 'Patient shows mild tremor in right hand. Responds well to L-DOPA treatment. Recommend continued monitoring and physical therapy.',
  severity: 'Stage 1',
  createdAt: new Date('2024-01-15'),
  updatedAt: new Date('2024-01-20'),
};

const mockTests: Test[] = [
  {
    id: 'test1',
    patientId: '1',
    name: 'Stand and Sit Assessment',
    type: 'stand-and-sit',
    date: new Date('2024-01-20'),
    status: 'completed',
  },
  {
    id: 'test2',
    patientId: '1',
    name: 'Palm Open Evaluation',
    type: 'palm-open',
    date: new Date('2024-01-18'),
    status: 'completed',
  },
  {
    id: 'test3',
    patientId: '1',
    name: 'Stand and Sit Assessment',
    type: 'stand-and-sit',
    date: new Date('2024-01-15'),
    status: 'completed',
  },
];



const PatientDetails = () => {
  const { id } = useParams<{ id: string }>();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tests, setTests] = useState<Test[]>([]); // Placeholder – replace with real API if available
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editData, setEditData] = useState<Partial<Patient>>({});

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

  useEffect(() => {
    const fetchPatient = async () => {
      try {
        const response = await fetch(`http://localhost:8000/patients/${id}`);
        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || 'Failed to fetch patient');
        }

        const [firstName, lastName] = data.patient.name.split(' ');

        setPatient({
          id: data.patient.patient_id,
          firstName,
          lastName,
          recordNumber: '', // Add logic if your backend supports it
          birthDate: data.patient.birthDate,
          height: `${data.patient.height}`,
          weight: `${data.patient.weight}`,
          labResults: data.patient.lab_results?.notes || '',
          doctorNotes: data.patient.doctors_notes || '',
          severity: mapSeverity(data.patient.severity),
          createdAt: new Date(), // Optional: replace with actual timestamps
          updatedAt: new Date(),
        });
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchPatient();
  }, [id]);

  const getStatusColor = (status: Test['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-success text-success-foreground';
      case 'in-progress':
        return 'bg-warning text-warning-foreground';
      case 'pending':
        return 'bg-muted text-muted-foreground';
      default:
        return 'bg-muted text-muted-foreground';
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
                  Record: {patient.recordNumber || 'N/A'}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              {/* <Link to={`/patient/${id}/edit`}>
                <Button variant="outline">
                  <Edit className="mr-2 h-4 w-4" />
                  Edit Patient
                </Button>
              </Link> */}
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
                    <p className="text-sm font-medium text-muted-foreground">Age</p>
                    <p className="text-lg font-semibold">  {patient.birthDate ? `${calculateAge(patient.birthDate)} years` : 'N/A'} </p> {/*Create a function to calculate age*/}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Height</p>
                    <p className="text-lg font-semibold">{patient.height}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Weight</p>
                    <p className="text-lg font-semibold">{patient.weight}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Severity</p>
                    <p className="text-lg font-semibold">{patient.severity}</p>
                  </div>
                </div>

                <Separator />

                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Lab Results</p>
                  <p className="text-sm">{patient.labResults}</p>
                </div>

                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Doctor's Notes</p>
                  <div className="bg-muted p-4 rounded-md">
                    <p className="text-sm">{patient.doctorNotes}</p>
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
                          <Badge className={getStatusColor(test.status)} variant="secondary">
                            {test.status}
                          </Badge>
                        </div>
                        {test.status === 'completed' && (
                          <Link to={`/patient/${id}/video-summary/${test.id}`}>
                            <Button size="sm" variant="outline" className="w-full mt-2">
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
                      <p className="text-sm text-muted-foreground">No tests recorded yet</p>
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
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="mb-4 text-lg font-semibold">Edit Patient Details</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="firstName">First Name</Label>
                <Input
                  id="firstName"
                  value={editData.firstName ?? ""}
                  onChange={(e) => setEditData(d => ({ ...d, firstName: e.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="lastName">Last Name</Label>
                <Input
                  id="lastName"
                  value={editData.lastName ?? ""}
                  onChange={(e) => setEditData(d => ({ ...d, lastName: e.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="birthDate">Birthdate</Label>
                <Input
                  id="birthDate"
                  type="date"
                  value={editData.birthDate ?? ""}
                  onChange={(e) => setEditData(d => ({ ...d, birthDate: e.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="severity">Severity</Label>
                <Select
                  value={editData.severity ?? "Stage 1"}
                  onValueChange={(v) => setEditData(d => ({ ...d, severity: v as Patient["severity"] }))}
                >
                  <SelectTrigger id="severity">
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent position='popper' className="z-[60]">
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
                  onChange={(e) => setEditData(d => ({ ...d, height: e.target.value }))}
                />
              </div>
              <div>
                <Label htmlFor="weight">Weight</Label>
                <Input
                  id="weight"
                  placeholder="e.g., 70 kg"
                  value={editData.weight ?? ""}
                  onChange={(e) => setEditData(d => ({ ...d, weight: e.target.value }))}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="labResults">Lab Results</Label>
              <Textarea
                id="labResults"
                rows={3}
                value={editData.labResults ?? ""}
                onChange={(e) => setEditData(d => ({ ...d, labResults: e.target.value }))}
              />
            </div>

            <div>
              <Label htmlFor="doctorNotes">Doctor Notes</Label>
              <Textarea
                id="doctorNotes"
                rows={4}
                value={editData.doctorNotes ?? ""}
                onChange={(e) => setEditData(d => ({ ...d, doctorNotes: e.target.value }))}
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setIsEditOpen(false)}>
                Cancel
              </Button>
              <Button type="submit">Save</Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>


  );
};

export default PatientDetails;
