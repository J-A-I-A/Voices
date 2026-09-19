"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/store";

/**
 * DashboardShell — Watermelon-style app shell: top nav with brand, user menu,
 * verification banner, and content area. Guards auth: redirects to /signin
 * if there is no session.
 */
export function DashboardShell({ children, title, actions }: {
  children: React.ReactNode;
  title: string;
  actions?: React.ReactNode;
}) {
  const router = useRouter();
  const { user, loading, bootstrap, logout } = useAuth();

  useEffect(() => { bootstrap(); }, [bootstrap]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-neutral-400">Loading…</div>
    );
  }
  if (!user) {
    router.replace("/signin");
    return null;
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <a href="/dashboard" className="text-lg font-bold tracking-tight">
              CARIB <span className="text-emerald-600">VOICES</span>
            </a>
            <nav className="hidden sm:flex items-center gap-4 text-sm">
              <a href="/dashboard" className="text-neutral-600 hover:text-neutral-900">My Voice Notes</a>
              {user.is_reviewer && <a href="/reviewer" className="text-neutral-600 hover:text-neutral-900">Review Queue</a>}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right hidden sm:block">
              <div className="text-sm font-medium text-neutral-900">{user.first_name} {user.last_name}</div>
              <div className="text-xs text-neutral-500">{user.email}</div>
            </div>
            <button onClick={() => { logout(); router.push("/signin"); }}
              className="rounded-full border border-neutral-200 px-3 py-1.5 text-sm text-neutral-700 hover:bg-neutral-50">
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between gap-4">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {actions}
        </div>
        {children}
      </main>
    </div>
  );
}
