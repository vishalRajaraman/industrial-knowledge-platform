"use client";

import { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { type AuthSession } from "@/lib/auth";
import { GATEWAY_API_BASE } from "@/lib/gateway";

type SessionContextValue = {
  session: AuthSession | null;
  ready: boolean;
  isAuthenticated: boolean;
  setSession: (session: AuthSession | null) => void;
  logout: () => Promise<void>;
  refreshFromServer: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [ready, setReady] = useState(false);

  const refreshFromServer = useCallback(async () => {
    try {
      const res = await fetch(`${GATEWAY_API_BASE}/auth/me`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setSession(data);
      } else {
        setSession(null);
      }
    } catch {
      setSession(null);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    refreshFromServer();
  }, [refreshFromServer]);

  const value = useMemo<SessionContextValue>(() => ({
    session,
    ready,
    isAuthenticated: Boolean(session),
    setSession,
    logout: async () => {
      try {
        await fetch(`${GATEWAY_API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
      } catch (e) {
        // Ignore network errors on logout
      }
      setSession(null);
    },
    refreshFromServer,
  }), [session, ready, refreshFromServer]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return context;
}
