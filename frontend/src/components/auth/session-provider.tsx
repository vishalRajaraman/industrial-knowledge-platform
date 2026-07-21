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
  refreshFromServer: () => Promise<boolean>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [ready, setReady] = useState(false);

  const refreshFromServer = useCallback(async (): Promise<boolean> => {
    let success = false;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const res = await fetch(`${GATEWAY_API_BASE}/auth/me`, {
        credentials: "include",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      
      if (res.ok) {
        const data = await res.json();
        setSession(data);
        success = true;
      } else {
        setSession(null);
      }
    } catch {
      setSession(null);
    } finally {
      setReady(true);
    }
    return success;
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshFromServer();
  }, [refreshFromServer]);

  const value = useMemo<SessionContextValue>(() => ({
    session,
    ready,
    isAuthenticated: Boolean(session),
    setSession,
    logout: async () => {
      try {
        await fetch(`${GATEWAY_API_BASE}/auth/logout`, { method: "POST", credentials: "include" });
      } catch {
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
