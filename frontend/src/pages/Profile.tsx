import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { useToast } from '@/hooks/use-toast';
import { Camera, Save, Edit2, X, Check } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

const Profile = () => {
  const { toast } = useToast();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [profileImage, setProfileImage] = useState<string>('');
  const [userData, setUserData] = useState({
    // Mock user data, replace with actual data from your auth context/API
    firstName: 'John',
    lastName: 'Doe',
    email: 'john.doe@hospital.com',
    department: 'Neurology',
    specialty: 'Movement Disorders',
    title: 'MD, PhD',
    location: 'Boston, MA',
  });

  const [editedData, setEditedData] = useState(userData);

  const handleImageClick = () => {
    fileInputRef.current?.click();
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        toast({
          title: 'File too large',
          description: 'Please select an image smaller than 5MB',
          variant: 'destructive',
        });
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        setProfileImage(reader.result as string);
        toast({
          title: 'Profile picture updated',
          description: 'Your profile picture has been changed successfully',
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
    setEditedData(userData);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedData(userData);
  };

  const handleSave = () => {
    //need to send data to backend
    setUserData(editedData);
    setIsEditing(false);
    toast({
      title: 'Profile updated',
      description: 'Your changes have been saved successfully',
    });
  };

  const handleInputChange = (field: keyof typeof userData, value: string) => {
    setEditedData(prev => ({ ...prev, [field]: value }));
  };

  const getInitials = () => {
    return `${userData.firstName[0]}${userData.lastName[0]}`.toUpperCase();
  };

  return (
    <div className="min-h-screen bg-background py-8">
      <div className="container mx-auto px-6 max-w-4xl">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-2xl">Profile Settings</CardTitle>
                <CardDescription>Manage your account information</CardDescription>
              </div>
              {!isEditing ? (
                <Button onClick={handleEdit} variant="outline">
                  <Edit2 className="mr-2 h-4 w-4" />
                  Edit Profile
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button onClick={handleCancel} variant="outline">
                    <X className="mr-2 h-4 w-4" />
                    Cancel
                  </Button>
                  <Button onClick={handleSave}>
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Profile Picture Section */}
            <div className="flex flex-col items-center space-y-4">
              <div className="relative">
                <Avatar className="h-32 w-32">
                  <AvatarImage src={profileImage} alt="Profile picture" />
                  <AvatarFallback className="text-2xl">{getInitials()}</AvatarFallback> {/*Sets avatar to initals for no avatar*/}
                </Avatar>
                <button
                  onClick={handleImageClick}
                  className="absolute bottom-0 right-0 bg-primary text-primary-foreground rounded-full p-2 hover:bg-primary/90 transition-colors shadow-lg"
                  aria-label="Upload profile picture"
                >
                  <Camera className="h-5 w-5" />
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleImageChange}
                  className="hidden"
                />
              </div>
              <div className="text-center">
                <h3 className="text-xl font-semibold">
                  {userData.firstName} {userData.lastName}
                </h3>
                <p className="text-sm text-muted-foreground">{userData.title}</p>
              </div>
            </div>

            <Separator />

            {/* Personal Information */}
            <div className="space-y-4">
              <h4 className="text-lg font-semibold">Personal Information</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="firstName">First Name</Label>
                  <Input
                    id="firstName"
                    value={isEditing ? editedData.firstName : userData.firstName}
                    onChange={(e) => handleInputChange('firstName', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="lastName">Last Name</Label>
                  <Input
                    id="lastName"
                    value={isEditing ? editedData.lastName : userData.lastName}
                    onChange={(e) => handleInputChange('lastName', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    value={isEditing ? editedData.email : userData.email}
                    onChange={(e) => handleInputChange('email', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
              </div>
            </div>

            <Separator />

            {/* Professional Information */}
            <div className="space-y-4">
              <h4 className="text-lg font-semibold">Professional Information</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="department">Department</Label>
                  <Input
                    id="department"
                    value={isEditing ? editedData.department : userData.department}
                    onChange={(e) => handleInputChange('department', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="specialty">Specialty</Label>
                  <Input
                    id="specialty"
                    value={isEditing ? editedData.specialty : userData.specialty}
                    onChange={(e) => handleInputChange('specialty', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={isEditing ? editedData.title : userData.title}
                    onChange={(e) => handleInputChange('title', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="location">Location</Label>
                  <Input
                    id="location"
                    value={isEditing ? editedData.location : userData.location}
                    onChange={(e) => handleInputChange('location', e.target.value)}
                    disabled={!isEditing}
                  />
                </div>
              </div>
              
              {/* Done Button */}
              <div className="pt-4">
                <Button 
                  onClick={() => navigate('/')} 
                  className="w-full"
                >
                  <Check className="mr-2 h-4 w-4" />
                  Done
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Profile;