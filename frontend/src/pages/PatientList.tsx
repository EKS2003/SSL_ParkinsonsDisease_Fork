import { useState, useEffect } from 'react';
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
import { Patient } from '@/types/patient';
import apiService from '@/services/api';
import { useApiStatus } from '@/hooks/use-api-status';
import { getSeverityColor } from '@/lib/utils';

// Remove mock data - will be fetched from API

const PatientList = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { toast } = useToast();
  const { isConnected, isChecking } = useApiStatus();

  // Quick add form state
  const [quickFormData, setQuickFormData] = useState({
    firstName: '',
    lastName: '',
    recordNumber: '',
    age: '',
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
      if (response.success && response.data) {
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
    if (!quickFormData.firstName || !quickFormData.lastName || !quickFormData.recordNumber || !quickFormData.age || !quickFormData.severity) {
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
      age: parseInt(quickFormData.age),
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
          age: '',
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
              {/* Quick Add Modal */}
              <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="border-primary text-primary hover:bg-primary hover:text-primary-foreground">
                    <UserPlus className="mr-2 h-4 w-4" />
                    Quick Add
                  </Button>
                </DialogTrigger>
                <DialogContent className="sm:max-w-md">
                  <DialogHeader>
                    <DialogTitle>Quick Add Patient</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleQuickSubmit} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="quick-firstName">First Name *</Label>
                        <Input
                          id="quick-firstName"
                          placeholder="John"
                          value={quickFormData.firstName}
                          onChange={(e) => handleQuickFormChange('firstName', e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="quick-lastName">Last Name *</Label>
                        <Input
                          id="quick-lastName"
                          placeholder="Smith"
                          value={quickFormData.lastName}
                          onChange={(e) => handleQuickFormChange('lastName', e.target.value)}
                          required
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="quick-recordNumber">Record Number *</Label>
                        <Input
                          id="quick-recordNumber"
                          placeholder="P004"
                          value={quickFormData.recordNumber}
                          onChange={(e) => handleQuickFormChange('recordNumber', e.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="quick-age">Age *</Label>
                        <Input
                          id="quick-age"
                          type="number"
                          placeholder="65"
                          value={quickFormData.age}
                          onChange={(e) => handleQuickFormChange('age', e.target.value)}
                          required
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="quick-severity">Parkinson's Severity *</Label>
                      <Select value={quickFormData.severity} onValueChange={(value) => handleQuickFormChange('severity', value)}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select severity level" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="Mild">Mild</SelectItem>
                          <SelectItem value="Moderate">Moderate</SelectItem>
                          <SelectItem value="Severe">Severe</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex justify-end space-x-3 pt-4">
                      <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                        Cancel
                      </Button>
                      <Button type="submit" className="bg-primary hover:bg-gradient-primary-hover">
                        <UserPlus className="mr-2 h-4 w-4" />
                        Add Patient
                      </Button>
                    </div>
                  </form>
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
                        Age: {patient.birthDate} years
                      </div>
                      <div className="flex items-center text-sm text-muted-foreground">
                        <AlertCircle className="mr-2 h-4 w-4" />
                        Last updated: {patient.updatedAt.toLocaleDateString()}
                      </div>
                      {patient.doctorNotes && (
                        <div className="bg-muted p-3 rounded-md">
                          <p className="text-sm text-muted-foreground">
                            "{patient.doctorNotes.length > 60 
                              ? patient.doctorNotes.substring(0, 60) + '...' 
                              : patient.doctorNotes}"
                          </p>
                        </div>
                      )}
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