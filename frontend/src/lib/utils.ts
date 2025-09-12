import { Patient } from "@/types/patient";
import { clsx, type ClassValue } from "clsx"
import { parse } from "path";
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const getSeverityColor = (severity: Patient['severity']) => {
    switch (severity) {
      case 'Stage 1':
        return 'bg-success text-success-foreground';
      case 'Stage 1':
        return 'bg-success text-success-foreground';
      case 'Stage 1':
        return 'bg-success text-success-foreground';
      case 'Stage 1':
        return 'bg-success text-success-foreground';
      case 'Stage 1':
        return 'bg-success text-success-foreground';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

export const calculateAge = (birthdate: Patient['birthDate']) => {
  // yyyy-mm-dd
  try {
    const [year, month, day] = birthdate.split('-').map(Number);
    const today = new Date();
    let age = today.getFullYear() - year;

    if(
      today.getMonth() < month - 1 ||
      (today.getMonth() === month -1 && today.getDate() < day)
    ){
      age--
    }

    return age;
  } catch (error) {
    console.error("Invalid birthdate format:");
    return null;
  }
}