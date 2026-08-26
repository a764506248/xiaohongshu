import {
  createContext,
  ReactNode,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, TOKEN_KEY } from "./api/client";

export interface AuthUser {
  id: string;
  username: string;
  display_name: string;
  role: string;
  status: string;
  permission_codes: string[];
  created_at?: string;
  last_login_at?: string | null;
}
interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
}
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  };
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    api<AuthUser>("/auth/me")
      .then(setUser)
      .catch(logout)
      .finally(() => setLoading(false));
    const expired = () => logout();
    window.addEventListener("auth:expired", expired);
    return () => window.removeEventListener("auth:expired", expired);
  }, []);
  async function login(username: string, password: string) {
    const result = await api<{ access_token: string; user: AuthUser }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ username, password }) },
    );
    localStorage.setItem(TOKEN_KEY, result.access_token);
    setUser(result.user);
  }
  const can = (permission: string) =>
    user?.role === "admin" || !!user?.permission_codes.includes(permission);
  return (
    <AuthContext.Provider value={{ user, loading, login, logout, can }}>
      {children}
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider missing");
  return value;
}
