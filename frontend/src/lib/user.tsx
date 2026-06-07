"use client";

import {
  createContext,
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
}

interface UserContextValue {
  userId: string | null;
  name: string | null;
  ready: boolean;
  error: string | null;
  retry: () => void;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<StoredUser | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setError(null);
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw) as StoredUser;
          if (parsed?.user_id) {
            if (!cancelled) {
              setUser(parsed);
              setReady(true);
            }
            return;
          }
        }
        const name = randomName();
        const { user_id } = await api.createUser(name);
        const created = { user_id, name };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(created));
        if (!cancelled) {
          setUser(created);
          setReady(true);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Failed to create account");
          setReady(true);
        }
      }
    }

    bootstrap();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  return (
    <UserContext.Provider
      value={{
        userId: user?.user_id ?? null,
        name: user?.name ?? null,
        ready,
        error,
        retry: () => {
          setReady(false);
          setAttempt((a) => a + 1);
        },
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
