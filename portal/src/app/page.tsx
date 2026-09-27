import type { Metadata } from "next";
import { Logo } from "@/components/logo";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Carib Voices — Teach AI to hear the Caribbean",
  description:
    "Record a phrase over WhatsApp and help build an open dataset of Caribbean speech, so voice technology understands Jamaican Patois, dialects, and accents.",
};

/* Waveform bar heights (%) — a fixed, hand-tuned shape so the hero renders
   identically on server and client (no Math.random hydration drift). */
const WAVEFORM = [
  28, 46, 62, 88, 54, 72, 96, 40, 66, 82, 34, 58, 92, 48, 70, 100, 44, 60, 78, 36,
  64, 86, 30, 52, 74, 94, 42, 68, 56, 38,
];

const STEPS = [
  {
    n: "01",
    title: "Create your account",
    body: "Sign up with Google or an email address. Contributors must be 18 or older.",
  },
  {
    n: "02",
    title: "Verify your WhatsApp number",
    body: "We send a 6-digit code to your Jamaican WhatsApp number (876 or 658) to confirm it's really you.",
  },
  {
    n: "03",
    title: "Read a phrase aloud",
    body: "Message the Carib Voices agent on WhatsApp. It sends you a phrase — read it out and reply with a voice note.",
  },
  {
    n: "04",
    title: "Track every submission",
    body: "Automated quality checks run on each recording. Watch its status move to accepted in your dashboard.",
  },
];

const FEATURES = [
  {
    title: "Patois-first recognition",
    body: "Quality control runs on JAIA's Jamaican-Patois speech recognition model — not a generic English recognizer that flattens how we actually speak.",
    icon: (
      <path d="M12 3v18M7.5 7v10M17 7v10M3 10.5v3M21 10.5v3" />
    ),
  },
  {
    title: "Automated quality control",
    body: "Every note passes structural checks — duration, speech ratio, signal-to-noise, clipping — before a content check compares what you said to the phrase.",
    icon: (
      <path d="m4 12 3.2 3.2L12 7l4.8 8.2L20 12" />
    ),
  },
  {
    title: "Private by default",
    body: "Audio lives in a private store and is served only through short-lived signed links. Your phone number is never published and never shared with data users.",
    icon: (
      <>
        <path d="M12 3 5 6v5.5c0 4.2 2.9 7.9 7 9.5 4.1-1.6 7-5.3 7-9.5V6l-7-3Z" />
        <path d="M9.5 12.2 11.3 14l3.4-3.6" />
      </>
    ),
  },
  {
    title: "Open for everyone",
    body: "De-identified recordings are released as an open dataset, so researchers and builders across the region can train on Caribbean speech.",
    icon: (
      <>
        <circle cx="12" cy="12" r="8.5" />
        <path d="M3.5 12h17M12 3.5c2.4 2.4 2.4 14.6 0 17M12 3.5c-2.4 2.4-2.4 14.6 0 17" />
      </>
    ),
  },
];

function Icon({ children }: { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-5 w-5"
    >
      {children}
    </svg>
  );
}

/** Animated waveform used as the hero's visual anchor. */
function Waveform() {
  return (
    <div
      aria-hidden="true"
      className="flex h-24 items-center justify-center gap-[3px] sm:h-32 sm:gap-1"
    >
      {WAVEFORM.map((height, i) => (
        <span
          key={i}
          className="cv-bar w-1 rounded-full bg-gradient-to-t from-[color:var(--jaia-green)] to-[color:var(--jaia-gold)] sm:w-1.5"
          style={{
            height: `${height}%`,
            // Offset each bar so the pulse reads as a travelling wave.
            ["--cv-delay" as string]: `${(i % 10) * 0.11}s`,
          }}
        />
      ))}
    </div>
  );
}

export default function LandingPage() {
  return (
    <div className="relative bg-[color:var(--paper)]">
      {/* ─── Nav ─────────────────────────────────────────────── */}
      <header className="absolute inset-x-0 top-0 z-40 px-4 pt-5">
        <div className="cv-navbar mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-2.5">
          <Logo height={46} variant="flat" />
          <nav className="hidden items-center gap-7 md:flex">
            <a href="#how-it-works" className="cv-navlink">How it works</a>
            <a href="#why" className="cv-navlink">Why it matters</a>
            <a href="/privacy" className="cv-navlink">Privacy</a>
          </nav>
          <div className="flex items-center gap-2">
            <a href="/signin" className="cv-navlink hidden px-2 sm:inline-flex">Sign in</a>
            <a href="/register" className="cv-btn cv-cta px-5 py-2.5 text-xs">
              Join in <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>
      </header>

      {/* ─── Hero ────────────────────────────────────────────── */}
      <section className="cv-canvas cv-bloom relative isolate overflow-hidden">
        <div className="cv-grid absolute inset-0" aria-hidden="true" />

        <div className="relative mx-auto max-w-4xl px-4 pb-24 pt-36 text-center sm:pb-28 sm:pt-44">
          <p className="cv-rise cv-eyebrow">
            Inspire. Innovate. <span className="text-[color:var(--jaia-gold)]">Impact.</span>
          </p>

          <h1
            className="cv-rise mt-6 text-4xl font-extrabold leading-[1.05] tracking-tight cv-heading sm:text-6xl"
            style={{ ["--cv-delay" as string]: "0.08s" }}
          >
            Teach AI to hear
            <br />
            <span className="text-[color:var(--jaia-green)]">the Caribbean.</span>
          </h1>

          <p
            className="cv-rise mx-auto mt-6 max-w-2xl text-base leading-7 cv-body sm:text-lg sm:leading-8"
            style={{ ["--cv-delay" as string]: "0.16s" }}
          >
            Voice technology still stumbles over Patois. We&apos;re building an open
            dataset of Caribbean speech so the next generation of AI understands and
            respects how we really talk. It takes one voice note on WhatsApp.
          </p>

          <div
            className="cv-rise mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row"
            style={{ ["--cv-delay" as string]: "0.24s" }}
          >
            <a href="/register" className="cv-btn group w-full px-7 py-3.5 sm:w-auto">
              Lend your voice
              <span aria-hidden="true" className="transition group-hover:translate-x-0.5">→</span>
            </a>
            <a href="#how-it-works" className="cv-btn-ghost w-full px-7 py-3.5 sm:w-auto">
              See how it works
            </a>
          </div>

          <div className="cv-rise mt-14" style={{ ["--cv-delay" as string]: "0.32s" }}>
            <Waveform />
          </div>

          <p className="cv-rise mt-6 text-xs cv-muted" style={{ ["--cv-delay" as string]: "0.4s" }}>
            Voluntary participation · Explicit consent before every recording ·{" "}
            <a href="/privacy" className="cv-link">Read our Privacy Notice</a>
          </p>
        </div>
      </section>

      {/* ─── Why it matters ─────────────────────────────────── */}
      <section id="why" className="scroll-mt-20 bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-4">
          <div className="max-w-3xl">
            <p className="cv-eyebrow">
              Why it matters
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight cv-heading sm:text-4xl">
              Millions speak Patois. Almost no machine listens.
            </h2>
            <p className="mt-5 text-[17px] leading-8 cv-body">
              Speech systems are trained mostly on a handful of accents, so Caribbean
              voices get mistranscribed, misunderstood, or ignored altogether — in call
              centres, in classrooms, in healthcare, in the tools we all use every day.
              That gap closes only when the data exists. Every recording you send helps
              build it.
            </p>
          </div>

          <div className="mt-14 grid gap-5 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="group cv-surface p-6 transition hover:border-[color:var(--jaia-green)] hover:shadow-md"
              >
                <div className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-[color:var(--jaia-green-soft)] text-[color:var(--jaia-green)] transition group-hover:bg-[color:var(--jaia-green)]/25">
                  <Icon>{f.icon}</Icon>
                </div>
                <h3 className="mt-4 text-base font-semibold cv-heading">
                  {f.title}
                </h3>
                <p className="mt-2 text-[15px] leading-7 cv-body">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ─── How it works ───────────────────────────────────── */}
      <section id="how-it-works" className="scroll-mt-20 border-y border-[color:var(--line)] bg-[color:var(--paper)] py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-4">
          <div className="max-w-2xl">
            <p className="cv-eyebrow">
              How it works
            </p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight cv-heading sm:text-4xl">
              Four steps, all inside WhatsApp.
            </h2>
            <p className="mt-5 text-[17px] leading-8 cv-body">
              No app to download and no studio required — if you can send a voice note,
              you can contribute.
            </p>
          </div>

          <ol className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s) => (
              <li
                key={s.n}
                className="cv-surface relative p-6"
              >
                <span className="cv-eyebrow text-[color:var(--jaia-gold)]">
                  {s.n}
                </span>
                <h3 className="mt-3 text-base font-semibold cv-heading">
                  {s.title}
                </h3>
                <p className="mt-2 text-[15px] leading-7 cv-body">{s.body}</p>
              </li>
            ))}
          </ol>

          <p className="mt-8 text-sm cv-muted">
            Contributors must be 18 or older, and WhatsApp numbers must be Jamaican
            (876 or 658).
          </p>
        </div>
      </section>

      {/* ─── Trust / privacy band ───────────────────────────── */}
      <section className="bg-white py-20 sm:py-24">
        <div className="mx-auto max-w-6xl px-4">
          <div className="cv-brand relative overflow-hidden rounded-3xl shadow-lg shadow-black/10">
            <div className="relative grid gap-10 p-8 sm:p-12 lg:grid-cols-[1.2fr_1fr] lg:items-center">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--jaia-gold)]">
                  Your voice, your terms
                </p>
                <h2 className="mt-3 text-2xl font-bold tracking-tight text-white sm:text-3xl">
                  Consent first — every single time.
                </h2>
                <p className="mt-5 text-[15px] leading-7 text-white/85">
                  Carib Voices is governed by Jamaica&apos;s Data Protection Act, 2020.
                  You give explicit consent before submitting a recording, you can
                  withdraw it at any time, and you can ask us to access, correct, or
                  delete your data. Published datasets are de-identified.
                </p>
                <div className="mt-7 flex flex-wrap items-center gap-3">
                  <a
                    href="/privacy"
                    className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-[color:var(--jaia-green)] transition hover:bg-[color:var(--jaia-gold)] hover:text-[color:var(--ink)]"
                  >
                    Read the Privacy Notice
                    <span aria-hidden="true">→</span>
                  </a>
                  <a
                    href="mailto:admin@jaia.org"
                    className="text-sm font-medium text-white underline decoration-white/40 underline-offset-2 hover:decoration-white"
                  >
                    Contact our Data Protection Officer
                  </a>
                </div>
              </div>

              <ul className="space-y-3 text-[15px] text-white/90">
                {[
                  "We never sell your personal data",
                  "Your phone number is never published",
                  "No advertising or marketing use",
                  "Recordings stay private; datasets are de-identified",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-3">
                    <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[color:var(--jaia-gold)] text-[color:var(--ink)]">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-3 w-3">
                        <path d="m5 13 4 4L19 7" />
                      </svg>
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Closing CTA ────────────────────────────────────── */}
      <section className="relative isolate overflow-hidden bg-[color:var(--ink)]">
        <div className="relative mx-auto max-w-3xl px-4 py-20 text-center sm:py-24">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--jaia-gold)]">
            Become a contributor
          </p>
          <h2 className="mt-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Your voice belongs in the dataset.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-base leading-7 text-white/75">
            Help build AI that understands and celebrates Caribbean languages and
            cultures. It starts with one phrase, read in your own voice.
          </p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a href="/register" className="cv-btn group w-full px-7 py-3.5 sm:w-auto">
              Create your account
              <span aria-hidden="true" className="transition group-hover:translate-x-0.5">→</span>
            </a>
            <a
              href="/signin"
              className="inline-flex w-full items-center justify-center rounded-full border border-white/25 px-7 py-3.5 text-sm font-semibold text-white transition hover:border-[color:var(--jaia-gold)] hover:text-[color:var(--jaia-gold)] sm:w-auto"
            >
              I already have an account
            </a>
          </div>
        </div>
      </section>

      {/* ─── Footer ─────────────────────────────────────────── */}
      <SiteFooter variant="full" />

    </div>
  );
}
