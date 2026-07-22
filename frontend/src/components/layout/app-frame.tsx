"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { getRoleLandingPath } from "@/lib/auth";
import { useSession } from "@/components/auth/session-provider";

export function AppFrame({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, ready, logout } = useSession();

  useEffect(() => {
    if (!ready) return;
    if (pathname === "/login") return;
    if (!session) {
      router.replace("/login");
      return;
    }

    // RBAC: Engineers cannot access restricted pages
    if (session.role === "engineer" && (pathname.startsWith("/upload") || pathname.startsWith("/graph"))) {
      router.replace("/");
    }
  }, [pathname, ready, router, session]);

  if (pathname === "/login" || pathname.startsWith("/mobile")) {
    return <>{children}</>;
  }

  if (!ready) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", flexDirection: "column", gap: "1rem" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1.5rem" }}>
          <div style={{ width: "48px", height: "48px", border: "3px solid var(--border-color)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <p style={{ color: "var(--text-muted)", fontSize: "0.95rem" }}>Connecting to secure workspace...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    );
  }

  if (!session) {
    // Session check resolved but no session — redirect happens via useEffect above
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1.5rem" }}>
          <p style={{ color: "var(--text-muted)" }}>Redirecting to login...</p>
        </div>
      </div>
    );
  }

  const navItems = [
    { href: "/", label: "Dashboard", icon: "▦" },
    { href: "/chat", label: "Ask Copilot", icon: "✦" },
    ...(session?.role === "plant admin" ? [
      { href: "/graph", label: "Knowledge Graph", icon: "⟐" },
      { href: "/upload", label: "Ingest Data", icon: "⇪" },
    ] : []),
  ];

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <span>Industrial Knowledge Platform</span>
        </div>

        <nav className="nav-links">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className={`nav-link ${pathname === item.href ? "active" : ""}`}>
              <span style={{ width: 18, textAlign: "center", opacity: 0.9 }}>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div style={{ marginTop: "auto", paddingTop: "2rem", borderTop: "1px solid var(--border-color)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "1rem" }}>
            <div style={{ width: "40px", height: "40px", borderRadius: "50%", background: "linear-gradient(45deg, var(--accent), var(--primary))", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>
              {session.username.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <div style={{ fontSize: "0.875rem", fontWeight: 600 }}>{session.username}</div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{session.role}</div>
            </div>
          </div>

          <button
            className="btn-secondary"
            onClick={() => {
              logout().then(() => {
                router.replace("/login");
              });
            }}
            style={{ width: "100%", justifyContent: "center" }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div style={{ fontSize: "1.25rem", fontWeight: 600 }}>
          </div>
          <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
            <div className="btn-secondary" style={{ padding: "0.5rem 1rem", display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ color: "var(--accent)" }}>●</span>
              Authenticated: {session.role}
            </div>
          </div>
        </header>

        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}
