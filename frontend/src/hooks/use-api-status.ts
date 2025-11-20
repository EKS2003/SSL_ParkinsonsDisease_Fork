import { useState, useEffect } from 'react';
import apiService from '@/services/api/api';

export const useApiStatus = () => {
  const [isConnected, setIsConnected] = useState<boolean | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  const checkConnection = async () => {
    setIsChecking(true);
    try {
      // First test the health endpoint
      const healthResponse = await fetch('http://localhost:8000/health');
      if (healthResponse.ok) {
        const response = await apiService.getPatients(0, 1);
        setIsConnected(response.success);
      } else {
        setIsConnected(false);
      }
    } catch (error) {
      setIsConnected(false);
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  return {
    isConnected,
    isChecking,
    checkConnection,
  };
}; 