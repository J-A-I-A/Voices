"use client";

import { motion, type Variants } from "framer-motion";
import type { ReactNode } from "react";
import { Logo } from "@/components/logo";

/**
 * AuthShell — the portal's sign-in / sign-up shell.
 *
 * Originally adapted from the Watermelon UI "auth-07" block
 * (https://registry.watermelon.sh/r/auth-07.json): split screen, header
 * branding, centered title/subtitle with a motion stagger reveal, pill inputs.
 *
 * Restyled to the JAIA brand (jaia.org.jm): warm paper on the left with a
 * white card, and a deep green panel on the right carrying the mission, a
 * live waveform and the association's framing.
 *
 * The props API is unchanged, so /signin, /register and /complete-google
 * keep working without edits.
 */
const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1, delayChildren: 0.2 } },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 15 },
  visible: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } },
};

export function MotionItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  );
}

/* Fixed bar heights so server and client render the same markup. */
const PANEL_WAVEFORM = [
  32, 54, 78, 96, 60, 84, 44, 70, 92, 38, 66, 88, 50, 74, 100, 42, 62, 80, 34, 58,
];

const PANEL_POINTS = [
  "Read a phrase aloud on WhatsApp — no app, no studio.",
  "Automated quality checks tuned for Jamaican Patois.",
  "Recordings stay private; published datasets are de-identified.",
];

export interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** Optional node rendered above the form (e.g. Google button). */
  topExtra?: ReactNode;
  divider?: boolean;
}

export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
  topExtra,
  divider = true,
}: AuthShellProps) {
  return (
    <div className="relative flex min-h-screen w-full bg-[color:var(--paper)] font-sans antialiased">
      {/* Left — form */}
      <div className="cv-canvas relative flex w-full flex-col lg:w-1/2">
        <div className="cv-grid absolute inset-0" aria-hidden="true" />

        <div className="relative z-10 p-6 md:p-10">
          <Logo height={72} />
        </div>

        <div className="relative flex flex-1 items-start justify-center p-6 pt-2 md:p-10 md:pt-0">
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="w-full max-w-[440px]"
          >
            <div className="cv-surface rounded-[1.75rem] p-6 shadow-xl shadow-black/5 sm:p-8">
              <motion.div variants={itemVariants} className="mb-6 text-center">
                <h1 className="mb-1.5 text-3xl font-bold tracking-tight cv-heading md:text-4xl">
                  {title}
                </h1>
                {subtitle && <p className="text-sm cv-body">{subtitle}</p>}
              </motion.div>

              {topExtra && <motion.div variants={itemVariants} className="mb-4">{topExtra}</motion.div>}

              {divider && (
                <motion.div variants={itemVariants} className="relative mb-6 flex items-center">
                  <div className="grow border-t border-[color:var(--line)]" />
                  <span className="px-4 text-sm cv-muted">or</span>
                  <div className="grow border-t border-[color:var(--line)]" />
                </motion.div>
              )}

              {children}

              {footer && (
                <motion.div variants={itemVariants} className="mt-5 text-center text-sm cv-muted">
                  {footer}
                </motion.div>
              )}
            </div>

            <motion.p variants={itemVariants} className="mt-5 text-center text-xs cv-muted">
              Your participation is voluntary.{" "}
              <a href="/privacy" className="cv-link">Read our Privacy Notice</a>
            </motion.p>
          </motion.div>
        </div>
      </div>

      {/* Right — green brand panel */}
      <div className="relative hidden p-4 lg:block lg:w-1/2">
        <div className="cv-brand relative h-full w-full overflow-hidden rounded-[2rem]">
          <div className="relative flex h-full flex-col justify-between p-10">
            <div>
              <div className="inline-flex items-center rounded-full bg-white/15 px-3.5 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] text-white backdrop-blur">
                Jamaica Artificial Intelligence Association
              </div>
              <h2 className="mt-7 max-w-md text-4xl font-bold leading-[1.1] tracking-tight text-white">
                Teach AI to hear{" "}
                <span className="text-[color:var(--jaia-gold)]">the Caribbean.</span>
              </h2>
              <p className="mt-4 max-w-md text-[15px] leading-7 text-white/85">
                Every voice note you send helps build an open dataset of Caribbean
                speech — so voice technology finally understands how we really talk.
              </p>
            </div>

            {/* Waveform */}
            <div aria-hidden="true" className="flex h-20 items-center justify-center gap-1.5">
              {PANEL_WAVEFORM.map((height, i) => (
                <span
                  key={i}
                  className="cv-bar w-1.5 rounded-full bg-gradient-to-t from-white/30 via-white/80 to-[color:var(--jaia-gold)]"
                  style={{
                    height: `${height}%`,
                    ["--cv-delay" as string]: `${(i % 10) * 0.11}s`,
                  }}
                />
              ))}
            </div>

            <ul className="space-y-3 text-sm text-white/90">
              {PANEL_POINTS.map((point) => (
                <li key={point} className="flex items-start gap-3">
                  <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[color:var(--jaia-gold)] text-[color:var(--ink)]">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-3 w-3">
                      <path d="m5 13 4 4L19 7" />
                    </svg>
                  </span>
                  {point}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
