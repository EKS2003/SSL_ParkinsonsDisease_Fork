import { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Search, User, FileText, AlertCircle, UserPlus, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Patient, DoctorNoteEntry } from '@/types/patient';
import apiService from '@/services/api';
import { useApiStatus } from '@/hooks/use-api-status';
import { getSeverityColor, calculateAge } from '@/lib/utils';

// Remove mock data - will be fetched from API

const PatientList = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { toast } = useToast();
  const { isConnected, isChecking } = useApiStatus();
  const csvFileInputRef = useRef<HTMLInputElement>(null);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvUploading, setCsvUploading] = useState(false);

  // Quick add form state
  const [quickFormData, setQuickFormData] = useState({
    firstName: '',
    lastName: '',
    recordNumber: '',
    birthDate: '',
    severity: '' as Patient['severity'],
  });

  // Fetch patients on component mount
  useEffect(() => {
    fetchPatients();
  }, []);

  const fetchPatients = async () => {
    setLoading(true);
    try {
      const response = await apiService.getPatients();
      console.log('PatientList API Response:', response);
      if (response.success && response.data) {
        console.log('Patient data received:', response.data);
        console.log('First patient historical data:', response.data[0]?.doctorNotesHistory, response.data[0]?.labResultsHistory);
        setPatients(response.data);
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to fetch patients",
          variant: "destructive",
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to connect to the server",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCsvUploadClick = () => {
    if(csvFileInputRef.current){
      csvFileInputRef.current.value = "";
      csvFileInputRef.current.click();
    }
  };

  const handleCsvFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    if (!file.name.endsWith('.csv')) {
      toast({
        title: "Invalid File Type",
        description: "Please upload a valid CSV file.",
        variant: "destructive",
      });
      return;
    }
    setCsvFile(file);
  };

  const parseCSVLine = (line: string) => {
    const result: string[] = [];
    let cur = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"' && line[i + 1] === '"') {
        cur += '"';
        i++; // skip escape
        continue;
      }
      if (ch === '"') {
        inQuotes = !inQuotes;
        continue;
      }
      if (ch === ',' && !inQuotes) {
        result.push(cur.trim());
        cur = '';
        continue;
      }
      cur += ch;
    }
    result.push(cur.trim());
    return result;
  };

  const normalizeHeaderName = (h: string) => {
    return h
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '')
      .trim();
  }

  // Parse several common date formats and return ISO yyyy-mm-dd or null
  // ISO means ISO 8601 date format
  const parseDateToISO = (val: string): string | null => {
    if (!val) return null;
    const s = val.trim();

    // If already ISO yyyy-mm-dd
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

    // Match numeric formats like dd-mm-yyyy, dd/mm/yyyy, mm/dd/yyyy
    const m = s.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/);
    if (m) {
      const a = Number(m[1]);
      const b = Number(m[2]);
      const y = Number(m[3]);

      let day: number;
      let month: number;

      // If first component > 12 it's day
      if (a > 12) {
        day = a; month = b;
      } else if (b > 12) {
        // If second component > 12 treat first as day
        day = a; month = b;
      } else {
        // Ambiguous: use '-' as dd-mm-yyyy heuristic, '/' as mm/dd/yyyy
        if (s.includes('-')) {
          day = a; month = b;
        } else {
          month = a; day = b;
        }
      }

      if (month < 1 || month > 12 || day < 1 || day > 31) return null;
      const mm = String(month).padStart(2, '0');
      const dd = String(day).padStart(2, '0');
      return `${y}-${mm}-${dd}`;
    }

    const d = new Date(s);
    if (!isNaN(d.getTime())) return d.toISOString().slice(0, 10);
    return null;
  };

  const headerToKey = (h:string) => {
    const n = normalizeHeaderName(h);

    if (['firstname', 'first', 'givenname', 'given'].includes(n)) return 'firstName';
    if (['lastname', 'last', 'surname', 'familyname'].includes(n)) return 'lastName';
    if (['fullname', 'name', 'fullName', 'fullname'].includes(n.toLowerCase())) return 'fullName';
    if (['birthdate', 'dob', 'dateofbirth', 'birth'].includes(n)) return 'birthDate';
    if (['height', 'ht'].includes(n)) return 'height';
    if (['weight', 'wt'].includes(n)) return 'weight';
    if (['recordnumber', 'recordno', 'record', 'id', 'patientid'].includes(n)) return 'recordNumber';
    if (['severity', 'stage', 'parkinsonseverity'].includes(n)) return 'severity';
    if (['labresults', 'lab_result', 'labs', 'lab'].includes(n)) return 'labResults';
    if (['doctornotes', 'doctornote', 'notes', 'note'].includes(n)) return 'doctorNotes';
    return n; // fallback: keep original normalized header
  }

  const normalizeSeverity = (val: string | undefined | null) => {
    if (!val) return '';
    const v = val.trim();
    const num = parseInt(v, 10);

    if (!isNaN(num) && num >= 1 && num <= 5) return `Stage ${num}`;

    const m = v.match(/([sS]tage)[_\-\s]?([1-5])/);
    if (m) return `Stage ${m[2]}`;

    const m2 = v.match(/^[Ss]tage\s*[1-5]$/);

    if (m2) return v.startsWith('Stage') ? v : `Stage ${v.replace(/\D/g, '')}`;

    const low = ['mild', 'low', 'stage1', 'stage_1'];
    const med = ['moderate', 'medium', 'stage3', 'stage_3'];
    const high = ['severe', 'high', 'stage5', 'stage_5'];
    const lower = v.toLowerCase();
    if (low.includes(lower)) return 'Stage 1';
    if (med.includes(lower)) return 'Stage 3';
    if (high.includes(lower)) return 'Stage 5';
    return v;
  };

  const processCsvFile = async () => {
    if (!csvFile) return;
    setCsvUploading(true);
    try {
      const text = await csvFile.text();
      const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0);
      if (lines.length < 2) {
        toast({
          title: 'Empty CSV',
          description: 'CSV must contain a header and at least one data row.',
          variant: 'destructive',
        });
        setCsvUploading(false);
        return;
      }

      const rawHeader = parseCSVLine(lines[0]);
      const headerMap: Record<number, string> = {};
      rawHeader.forEach((h, idx) => {
        headerMap[idx] = headerToKey(h);
      });

      const rows = lines.slice(1);
      const toCreate: any[] = [];
      for (const row of rows) {
        const cols = parseCSVLine(row);
        if (cols.every(c => c === '')) continue;

        const item: any = {
          firstName: '',
          lastName: '',
          recordNumber: '',
          birthDate: '',
          height: '',
          weight: '',
          labResults: '{}',
          doctorNotes: '',
          severity: '',
        };

        for (let i = 0; i < cols.length; i++) {
          const key = headerMap[i];
          const val = cols[i] ?? '';
          if (!key) continue;
          switch (key) {
            case 'firstName':
              item.firstName = val;
              break;
            case 'lastName':
              item.lastName = val;
              break;
            case 'fullName':
              {
                const parts = val.split(/\s+/);
                item.firstName = parts.shift() || '';
                item.lastName = parts.join(' ') || '';
              }
              break;
            case 'birthDate':
              {
                // try to normalize common date formats to yyyy-mm-dd
                const iso = parseDateToISO(val);
                if (iso) {
                  item.birthDate = iso;
                } else {
                  item.birthDate = val || '';
                }
              }
              break;
            case 'height':
              item.height = val;
              break;
            case 'weight':
              item.weight = val;
              break;
            case 'recordNumber':
              item.recordNumber = val;
              break;
            case 'severity':
              item.severity = normalizeSeverity(val);
              break;
            case 'labResults':
              try {
                item.labResults = JSON.stringify(JSON.parse(val));
              } catch {
                item.labResults = JSON.stringify({ notes: val });
              }
              break;
            case 'doctorNotes':
              item.doctorNotes = val;
              break;
            default:
              // unknown header, ignores it
              break;
          }
        }

        // Default values for missing fields
        if (!item.firstName && !item.lastName) {
          item.firstName = 'Unknown';
          item.lastName = 'Patient';
        }
        if (!item.recordNumber) {
          item.recordNumber = `csv-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
        }
        if (!item.height) item.height = '170 cm';
        if (!item.weight) item.weight = '70 kg';
        if (!item.labResults) item.labResults = JSON.stringify({});
        if (!item.doctorNotes) item.doctorNotes = '';
        if (!item.severity) item.severity = 'Stage 1';
        if (!item.birthDate) item.birthDate = '';
        toCreate.push(item);
      }

      if (toCreate.length === 0) {
        toast({
          title: 'No valid rows',
          description: 'No valid patient rows found in CSV.',
          variant: 'destructive',
        });
        setCsvUploading(false);
        return;
      }

      let successCount = 0;
      let failCount = 0;
      for (const p of toCreate) {
        try {
          const response = await apiService.createPatient(p);
          if (response.success && response.data) {
            setPatients(prev => [...prev, response.data]);
            successCount++;
          } else {
            failCount++;
            console.error('Create patient failed response:', response);
          }
        } catch (err) {
          failCount++;
          console.error('Create patient error:', err);
        }
      }

      toast({
        title: 'CSV Upload Complete',
        description: `Imported ${successCount} patients. ${failCount} failures.`,
      });

      setCsvFile(null);
      setIsModalOpen(false);
    } catch (error) {
      console.error('Error processing CSV:', error);
      toast({
        title: "Error",
        description: "Failed to read the CSV file.",
        variant: "destructive",
      });
    } finally {
      setCsvUploading(false);
    }
  };

  const filteredPatients = patients.filter(patient =>
    `${patient.firstName} ${patient.lastName}`.toLowerCase().includes(searchTerm.toLowerCase()) ||
    patient.recordNumber.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleQuickFormChange = (field: string, value: string) => {
    setQuickFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleQuickSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate required fields
    if (!quickFormData.firstName || !quickFormData.lastName || !quickFormData.recordNumber || !quickFormData.birthDate || !quickFormData.severity) {
      toast({
        title: "Validation Error",
        description: "Please fill in all required fields.",
        variant: "destructive",
      });
      return;
    }

    // Create new patient data
    const newPatientData = {
      firstName: quickFormData.firstName,
      lastName: quickFormData.lastName,
      recordNumber: quickFormData.recordNumber,
      birthDate: quickFormData.birthDate,
      height: '170 cm', // Default values for quick add
      weight: '70 kg',
      labResults: '{}',
      doctorNotes: '',
      severity: quickFormData.severity,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    try {
      console.log('Creating patient with data:', newPatientData);
      const response = await apiService.createPatient(newPatientData);
      console.log('API response:', response);
      
      if (response.success && response.data) {
        setPatients(prev => [...prev, response.data]);
        setIsModalOpen(false);
        setQuickFormData({
          firstName: '',
          lastName: '',
          recordNumber: '',
          birthDate: '',
          severity: '' as Patient['severity'],
        });

        toast({
          title: "Patient Added",
          description: `${newPatientData.firstName} ${newPatientData.lastName} has been added successfully.`,
        });
      } else {
        toast({
          title: "Error",
          description: response.error || "Failed to add patient",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Error creating patient:', error);
      toast({
        title: "Error",
        description: "Failed to connect to the server",
        variant: "destructive",
      });
    }
  };

  

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b bg-card shadow-card">
        <div className="container mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-foreground">Patient Management</h1>
              <p className="text-muted-foreground mt-1">Parkinson's Disease Monitoring System</p>
              {!isChecking && (
                <div className="flex items-center mt-2">
                  <div className={`w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                  <span className="text-xs text-muted-foreground">
                    {isConnected ? 'Connected to backend' : 'Backend disconnected'}
                  </span>
                </div>
              )}
            </div>
            <div className="flex items-center space-x-3">
              {/* Upload Modal */}
              <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="border-primary text-primary hover:bg-primary hover:text-primary-foreground">
                    <UserPlus className="mr-2 h-4 w-4" />
                    Upload Patient
                  </Button>
                </DialogTrigger>
                <DialogContent className="w-full sm:max-w-4xl max-w-4xl">
                  <DialogHeader>
                    <DialogTitle>Upload Patients CSV</DialogTitle>
                  </DialogHeader>

                  <div className="space-y-4">
                    <p className="text-sm text-muted-foreground">
                      Upload a CSV file with patient rows. Supported headers (case-insensitive, common variants):
                    </p>
                    <code className="block bg-muted p-2 rounded text-xs">
                      firstName,lastName,recordNumber,birthDate,height,weight,severity,labResults,doctorNotes
                    </code>

                    <div className="space-y-2 pt-2">
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        ref={csvFileInputRef}
                        onChange={handleCsvFileChange}
                        className="block w-full text-sm text-muted-foreground file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20"
                      />

                      {csvFile && (
                        <div className="flex items-center justify-between mt-2">
                          <div>
                            <div className="text-sm font-medium">{csvFile.name}</div>
                            <div className="text-xs text-muted-foreground">{(csvFile.size / 1024).toFixed(1)} KB</div>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Button variant="ghost" size="sm" onClick={() => setCsvFile(null)}>
                              Remove
                            </Button>
                            <Button onClick={processCsvFile} disabled={csvUploading}>
                              {csvUploading ? (
                                <>
                                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                  Uploading...
                                </>
                              ) : (
                                'Upload'
                              )}
                            </Button>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex justify-end">
                      <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                        Close
                      </Button>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              {/* Full Form Link */}
              <Link to="/patient-form">
                <Button className="bg-primary hover:bg-primary-hover text-primary-foreground">
                  <Plus className="mr-2 h-4 w-4" />
                  Detailed Form
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Search and Content */}
      <div className="container mx-auto px-6 py-8">
        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search patients by name or record number..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>

        {/* Patient Cards */}
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-2 text-muted-foreground">Loading patients...</span>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {filteredPatients.map((patient) => (
              <Link key={patient.id} to={`/patient/${patient.id}`}>
                <Card className="hover:shadow-medical transition-all duration-200 hover:scale-[1.02] cursor-pointer">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-full bg-medical-light">
                          <User className="h-5 w-5 text-medical-blue" />
                        </div>
                        <div>
                          <CardTitle className="text-lg">
                            {patient.firstName} {patient.lastName}
                          </CardTitle>
                          <p className="text-sm text-muted-foreground">
                            Record: {patient.recordNumber}
                          </p>
                        </div>
                      </div>
                      <Badge className={getSeverityColor(patient.severity)}>
                        {patient.severity}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="flex items-center text-sm text-muted-foreground">
                        <FileText className="mr-2 h-4 w-4" />
                        Age: {patient.birthDate ? `${calculateAge(patient.birthDate) ?? 'Unknown'} years` : 'N/A'}
                      </div>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <AlertCircle className="mr-2 h-4 w-4" />
                        Last updated: {patient.updatedAt.toLocaleDateString()}
                      </div>
                      {(() => {
                        // Get the most recent doctor's note from history
                        let mostRecentNote = null;
                        if (patient.doctorNotesHistory && patient.doctorNotesHistory.length > 0) {
                          // Sort by date (most recent first) and get the first one
                          const sortedNotes = [...patient.doctorNotesHistory].sort((a, b) => {
                            const dateA = new Date(a.date).getTime();
                            const dateB = new Date(b.date).getTime();
                            return dateB - dateA;
                          });
                          mostRecentNote = sortedNotes[0];
                        }
                        
                        // Fallback to legacy doctorNotes if no history exists
                        const noteToDisplay = mostRecentNote?.note || patient.doctorNotes;
                        
                        if (noteToDisplay) {
                          return (
                            <div className="bg-muted/50 border-l-4 border-medical-blue p-3 rounded-md">
                              <div className="flex items-start gap-2">
                                <FileText className="h-4 w-4 text-medical-blue mt-0.5 flex-shrink-0" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium text-foreground">Latest Note:</p>
                                  <p className="text-sm text-muted-foreground mt-1">
                                    "{noteToDisplay.length > 80 
                                      ? noteToDisplay.substring(0, 80) + '...' 
                                      : noteToDisplay}"
                                  </p>
                                  {mostRecentNote && (
                                    <p className="text-xs text-muted-foreground/70 mt-2">
                                      {new Date(mostRecentNote.date).toLocaleDateString()} by {mostRecentNote.addedBy}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        }
                        
                        // Show placeholder if no notes exist
                        return (
                          <div className="bg-muted/30 p-3 rounded-md border border-dashed">
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-muted-foreground/50" />
                              <p className="text-sm text-muted-foreground/70 italic">
                                No doctor's notes available
                              </p>
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        )}

        {!loading && filteredPatients.length === 0 && (
          <div className="text-center py-12">
            <User className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium text-foreground mb-2">No patients found</h3>
            <p className="text-muted-foreground mb-4">
              {searchTerm ? 'Try adjusting your search terms.' : 'Get started by adding your first patient.'}
            </p>
            <Link to="/patient-form">
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add First Patient
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

export default PatientList;