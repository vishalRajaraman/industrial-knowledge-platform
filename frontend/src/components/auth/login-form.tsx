"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getRoleLandingPath, type UserRole } from "@/lib/auth";
import { GATEWAY_API_BASE, type LoginResponse } from "@/lib/gateway";
import { useSession } from "./session-provider";

type LoginFormState = {
  username: string;
  password: string;
};

const DEFAULT_STATE: LoginFormState = {
  username: "",
  password: "",
};

const ROLE_HINTS: Record<UserRole, string> = {
  field_tech: "Quick access to field summaries and operational dashboards.",
  manager: "Cross-functional search, compliance, and executive-level visibility.",
  engineer: "Search, analysis, and deep technical troubleshooting.",
};

export function LoginForm() {
  const router = useRouter();
  const { session, ready, refreshFromServer } = useSession();
  const [form, setForm] = useState<LoginFormState>(DEFAULT_STATE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready && session) {
      router.replace(getRoleLandingPath(session.role));
    }
  }, [ready, router, session]);

  const submitLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${GATEWAY_API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: form.username.trim(), password: form.password }),
        credentials: "include",
      });

      if (!response.ok) {
        throw new Error(response.status === 401 ? "Invalid credentials" : `Login failed (${response.status})`);
      }

      await refreshFromServer();
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "1.1fr 0.9fr", background: "radial-gradient(circle at top left, rgba(37,99,235,0.25), transparent 40%), linear-gradient(180deg, #050816 0%, #0f172a 48%, #08111f 100%)" }}>
      <section style={{ padding: "4rem", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
            <div style={{ width: "42px", height: "42px", borderRadius: "12px", background: "linear-gradient(135deg, var(--primary), var(--accent))", display: "grid", placeItems: "center" }}>
              <span style={{ fontWeight: 800 }}>IK</span>
            </div>
            <div>
              <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Industrial Knowledge Intelligence</div>
              <div style={{ fontSize: "1.35rem", fontWeight: 700 }}>Gateway Auth Portal</div>
            </div>
          </div>
          <h1 style={{ fontSize: "clamp(2.8rem, 5vw, 5rem)", lineHeight: 1.02, marginBottom: "1rem", maxWidth: "12ch" }}>
            Sign in to the operational knowledge layer.
          </h1>
          <p style={{ maxWidth: "58ch", color: "var(--text-muted)", fontSize: "1.05rem", lineHeight: 1.75 }}>
            Secure access to the engineering and management dashboard, vector search portal, and role-aware workflows backed by the API Gateway.
          </p>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: "1rem", marginTop: "2rem" }}>
          {(["field_tech", "manager", "engineer"] as UserRole[]).map((role) => (
            <div key={role} className="glass-card" style={{ padding: "1rem 1.1rem", minHeight: "110px" }}>
              <div style={{ fontSize: "0.78rem", textTransform: "uppercase", letterSpacing: "0.12em", color: "var(--accent)", marginBottom: "0.5rem" }}>{role}</div>
              <div style={{ fontSize: "0.93rem", lineHeight: 1.6, color: "var(--text-muted)" }}>{ROLE_HINTS[role]}</div>
            </div>
          ))}
        </div>
      </section>

      <section style={{ display: "grid", placeItems: "center", padding: "2rem" }}>
        <form onSubmit={submitLogin} className="glass-panel" style={{ width: "100%", maxWidth: "460px", padding: "2rem", boxShadow: "0 24px 80px rgba(0,0,0,0.35)" }}>
          <div style={{ marginBottom: "1.5rem" }}>
            <div style={{ fontSize: "1.8rem", fontWeight: 700, marginBottom: "0.4rem" }}>Login</div>
            <div style={{ color: "var(--text-muted)", lineHeight: 1.6 }}>Use one of the gateway roles to continue.</div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <label style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Username</span>
              <input
                value={form.username}
                onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                autoComplete="username"
                placeholder="manager"
                className="auth-input"
                style={{ padding: "0.95rem 1rem", borderRadius: "12px", background: "rgba(15, 23, 42, 0.82)", border: "1px solid var(--border-color)", color: "white", outline: "none" }}
              />
            </label>

            <label style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
              <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Password</span>
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                autoComplete="current-password"
                placeholder="manager-pass"
                className="auth-input"
                style={{ padding: "0.95rem 1rem", borderRadius: "12px", background: "rgba(15, 23, 42, 0.82)", border: "1px solid var(--border-color)", color: "white", outline: "none" }}
              />
            </label>

            {error && (
              <div style={{ padding: "0.9rem 1rem", borderRadius: "12px", background: "rgba(239, 68, 68, 0.12)", border: "1px solid rgba(239, 68, 68, 0.35)", color: "#fecaca", fontSize: "0.92rem" }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn-primary" disabled={loading} style={{ width: "100%", justifyContent: "center", padding: "0.95rem 1rem", marginTop: "0.3rem" }}>
              {loading ? "Signing in..." : "Enter Gateway"}
            </button>
          </div>

          <div style={{ marginTop: "1.5rem", paddingTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.06)", color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.7 }}>
            Demo credentials: manager / manager-pass, engineer / engineer-pass, field.tech / field-tech-pass.
          </div>
        </form>
      </section>
    </div>
  );
}
