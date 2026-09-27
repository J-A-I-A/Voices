import { Logo } from "@/components/logo";

const DPO_EMAIL = "admin@jaia.org";

/**
 * SiteFooter — the one footer, used on every surface.
 *
 * It previously existed three times over (landing page, app shell, privacy
 * notice), which is how the privacy page ended up with a thin cream strip
 * while everywhere else had the dark ink band. Keeping one component means
 * they cannot drift apart again.
 *
 * "full"    marketing footer: logo, blurb, link column, bottom rule.
 * "compact" single band for in-app and document pages.
 */
export function SiteFooter({
  variant = "compact",
  links,
}: {
  variant?: "full" | "compact";
  /** Extra links for the compact band, beyond the Privacy Notice. */
  links?: { href: string; label: string }[];
}) {
  const year = new Date().getFullYear();

  const tagline = (
    <p className="uppercase tracking-[0.14em]">
      Shaping the{" "}
      <span className="text-[color:var(--jaia-green)]">Caribbean&apos;s</span> AI future, together.
    </p>
  );

  if (variant === "compact") {
    return (
      <footer className="bg-[color:var(--ink)] text-xs text-white/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-col gap-3">
            <Logo height={40} variant="flat" tone="light" />
            {tagline}
          </div>
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            {links?.map((l) => (
              <a key={l.href} href={l.href} className="transition hover:text-white">
                {l.label}
              </a>
            ))}
            <a href="/privacy" className="transition hover:text-white">Privacy Notice</a>
            <a href={`mailto:${DPO_EMAIL}`} className="transition hover:text-white">{DPO_EMAIL}</a>
            <span className="text-white/35">© {year} JAIA</span>
          </div>
        </div>
      </footer>
    );
  }

  return (
    <footer className="border-t border-white/10 bg-[color:var(--ink)] text-sm text-white/65">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="flex flex-col gap-8 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-sm">
            <Logo height={52} variant="flat" tone="light" href={null} />
            <p className="mt-4 leading-6">
              An open dataset of Caribbean speech, built by the Jamaica Artificial
              Intelligence Association.
            </p>
          </div>

          <nav className="flex flex-col gap-3 sm:text-right" aria-label="Footer">
            <a href="/#how-it-works" className="transition hover:text-white">How it works</a>
            <a href="/#why" className="transition hover:text-white">Why it matters</a>
            <a href="/privacy" className="transition hover:text-white">Privacy Notice</a>
            <a href="/signin" className="transition hover:text-white">Sign in</a>
            <a href={`mailto:${DPO_EMAIL}`} className="transition hover:text-white">{DPO_EMAIL}</a>
          </nav>
        </div>

        <div className="mt-10 flex flex-col gap-3 border-t border-white/10 pt-6 text-xs sm:flex-row sm:items-center sm:justify-between">
          {tagline}
          <p>© {year} Carib Voices · Jamaica Artificial Intelligence Association</p>
        </div>
      </div>
    </footer>
  );
}
