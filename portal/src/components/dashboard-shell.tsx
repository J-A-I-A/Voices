"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Logo } from "@/components/logo";
import { SiteFooter } from "@/components/site-footer";
import { useAuth } from "@/lib/store";

/**
 * DashboardShell — app shell on the JAIA brand.
 *
 * Follows jaia.org.jm: warm paper canvas, a floating white pill navigation
 * with uppercase tracked links and a gold underline on the active section,
 * and a dark ink footer band. Guards auth: redirects to /signin with no session.
 */
export function DashboardShell({ children, title, actions, active }: {
  children: React.ReactNode;
  title: string;
  actions?: React.ReactNode;
  /** Which nav item to mark with the gold underline. */
  active?: "notes" | "review" | "admin" | "profile";
}) {
  const router = useRouter();
  const { user, loading, bootstrap, logout } = useAuth();

  useEffect(() => { bootstrap(); }, [bootstrap]);

  if (loading) {
    return (
      <div className="cv-canvas flex min-h-screen items-center justify-center cv-muted">
        Loading…
      </div>
    );
  }
  if (!user) {
    router.replace("/signin");
    return null;
  }

  const link = (key: string, href: string, label: string) => (
    <a href={href} className={"cv-navlink" + (active === key ? " cv-navlink-active" : "")}>
      {label}
    </a>
  );

  return (
    <div className="flex min-h-screen flex-col bg-[color:var(--paper)]">
      {/* Canvas wash behind the header */}
      <div className="cv-canvas relative">
        <div className="cv-grid absolute inset-0" aria-hidden="true" />

        <header className="relative z-30 px-4 pt-5">
          <div className="cv-navbar mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-2.5">
            <div className="flex items-center gap-7">
              <Logo height={42} variant="flat" />
              <nav className="hidden items-center gap-6 md:flex">
                {link("notes", "/dashboard", "My Voice Notes")}
                {(user.is_reviewer || user.is_admin) && link("review", "/reviewer", "Review Queue")}
                {user.is_admin && link("admin", "/admin", "Admin")}
                {link("profile", "/profile", "My Profile")}
              </nav>
            </div>

            <div className="flex items-center gap-3">
              <a href="/profile" className="hidden text-right sm:block">
                <div className="text-sm font-semibold leading-tight cv-heading">
                  {user.first_name} {user.last_name}
                </div>
                <div className="text-xs cv-muted">{user.email}</div>
              </a>
              <button
                onClick={() => { logout(); router.push("/signin"); }}
                className="cv-btn-ghost cv-cta px-4 py-2 text-xs"
              >
                Sign out
              </button>
            </div>
          </div>
        </header>

        <div className="relative mx-auto max-w-6xl px-4 pb-6 pt-10">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h1 className="text-3xl font-bold tracking-tight cv-heading sm:text-4xl">{title}</h1>
            {actions}
          </div>
        </div>
      </div>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>

      <SiteFooter />
    </div>
  );
}
