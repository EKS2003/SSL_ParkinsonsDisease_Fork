import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from "react";
import apiService from "@/services/api";

interface AuthUser {
  fullName: string;
  email: string;
  title: string;
  speciality: string;
  location: string;
  profileImage: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({ user: null, refresh: async () => {} });

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);

  const refresh = useCallback(async () => {
    if (!apiService.getToken()) return;
    const res = await apiService.getMe().catch(() => null);
    if (res?.success && res.data) {
      setUser({
        fullName: res.data.full_name ?? "",
        email: res.data.email ?? "",
        title: res.data.title ?? "",
        speciality: res.data.speciality ?? "",
        location: res.data.location ?? "",
        profileImage: res.data.profile_image ?? "",
      });
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return <AuthContext.Provider value={{ user, refresh }}>{children}</AuthContext.Provider>;
};

export const useAuth = () => useContext(AuthContext).user;
export const useAuthRefresh = () => useContext(AuthContext).refresh;
