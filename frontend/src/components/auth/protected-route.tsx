"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getRoleLandingPath, type UserRole } from "@/lib/auth";
import { useSession } from "./session-provider";

type ProtectedRouteProps = {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
};

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const router = useRouter();
  const { session, ready, logout } = useSession();

  useEffect(() => {
    if (!ready) return;
    if (!session) {
      router.replace("/login");
      return;
    }

    if (allowedRoles && !allowedRoles.includes(session.role)) {
      router.replace(getRoleLandingPath(session.role));
    }
  }, [allowedRoles, ready, router, session]);

  if (!ready) {
    return (
      <div style={{ minHeight: "60vh", display: "grid", placeItems: "center", color: "var(--text-muted)" }}>
        Loading secure session...
      </div>
    );
  }

  if (!session) {
    return null;
  }

  if (allowedRoles && !allowedRoles.includes(session.role)) {
    return (
      <div className="glass-panel" style={{ padding: "2rem", maxWidth: "720px", margin: "2rem auto" }}>
        <h2 style={{ marginBottom: "0.75rem" }}>Access restricted</h2>
        <p style={{ color: "var(--text-muted)", marginBottom: "1.25rem" }}>
          Your role ({session.role}) does not have permission to access this portal.
        </p>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button className="btn-primary" onClick={() => router.replace(getRoleLandingPath(session.role))}>
            Go to my dashboard
          </button>
          <button className="btn-secondary" onClick={() => { logout(); router.replace("/login"); }}>
            Sign out
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
