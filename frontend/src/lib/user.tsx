"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";

const STORAGE_KEY = "anex.user.v1";

const ADJECTIVES = [
  "Quiet", "Rogue", "Vega", "Apex", "Nova", "Iron", "Onyx", "Lunar",
  "Zephyr", "Cobalt", "Delta", "Sigma", "Helix", "Atlas", "Orion",
];
const NOUNS = [
  "Falcon", "Quant", "Tiger", "Harbor", "Vector", "Summit", "Forge",
  "Crane", "Meridian", "Cartel", "Syndicate", "Holdings", "Capital", "Partners",
];

function randomName(): string {
  const a = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)];
  const n = NOUNS[Math.floor(Math.random() * NOUNS.length)];
  return `${a} ${n}`;
}

interface StoredUser {
  user_id: string;
  name: string;
  email?: string | null;
  guest?: boolean;
}

interface UserContextValue {
  userId: string | null;
  name: string | null;
  email: string | null;
  isGuest: boolean;
  ready: boolean;
  authed: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  continueAsGuest: () => Promise<void>;
  logout: () => void;
}

const UserContext = createContext<UserContextValue | null>(null);

function persist(u: StoredUser) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
}

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as StoredUser;
        if (parsed?.user_id) setUser(parsed);
      }
    } catch {
      /* ignore corrupt storage */
    }
    setReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const u = await api.login(email, password);
    const stored: StoredUser = {
      user_id: u.user_id,
      name: u.name,
      email: u.email,
    };
    persist(stored);
    setUser(stored);
  }, []);

  const register = useCallback(
    async (email: string, password: string, name?: string) => {
      const u = await api.register(email, password, name);
      const stored: StoredUser = {
        user_id: u.user_id,
        name: u.name,
        email: u.email,
      };
      persist(stored);
      setUser(stored);
    },
    [],
  );

  const continueAsGuest = useCallback(async () => {
    const name = randomName();
    const { user_id } = await api.createUser(name);
    const stored: StoredUser = { user_id, name, guest: true };
    persist(stored);
    setUser(stored);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  }, []);

  return (
    <UserContext.Provider
      value={{
        userId: user?.user_id ?? null,
        name: user?.name ?? null,
        email: user?.email ?? null,
        isGuest: user?.guest ?? false,
        ready,
        authed: !!user?.user_id,
        login,
        register,
        continueAsGuest,
        logout,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used within UserProvider");
  return ctx;
}
