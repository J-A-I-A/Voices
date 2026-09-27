import type { Metadata } from "next";
import { Logo } from "@/components/logo";
import { SiteFooter } from "@/components/site-footer";

export const metadata: Metadata = {
  title: "Privacy Notice · Carib Voices",
  description:
    "How the Jamaica Artificial Intelligence Association (JAIA) collects, uses, and protects your personal data when you contribute to CaribVoices.",
};

const EFFECTIVE_DATE = "October 1, 2026";
const JAIA_PRIVACY_POLICY = "https://www.jaia.org.jm/privacy-notice/";
const DPO_EMAIL = "admin@jaia.org";

const SECTIONS = [
  { id: "information-we-collect", title: "Information We Collect" },
  { id: "lawful-basis", title: "Lawful Basis for Processing" },
  { id: "how-we-use-your-data", title: "How We Use Your Data" },
  { id: "data-sharing", title: "Data Sharing and Disclosure" },
  { id: "data-security", title: "Data Security" },
  { id: "data-retention", title: "Data Retention" },
  { id: "your-rights", title: "Your Rights" },
  { id: "more-information", title: "More Information" },
  { id: "acknowledgement", title: "Acknowledgement and Consent" },
];

/** Section wrapper: anchor target + consistent heading treatment. */
function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="mt-12 border-b border-[color:var(--line)] pb-2 text-xl font-bold tracking-tight cv-heading">
        {title}
      </h2>
      <div className="mt-4 space-y-4 text-[15px] leading-7 cv-body">
        {children}
      </div>
    </section>
  );
}

function Bullets({ children }: { children: React.ReactNode }) {
  return (
    <ul className="ml-1 list-outside list-disc space-y-2 pl-5 marker:text-[color:var(--jaia-green)]">
      {children}
    </ul>
  );
}

function Term({ children }: { children: React.ReactNode }) {
  return <span className="font-medium cv-heading">{children}</span>;
}

function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="cv-link"
    >
      {children}
    </a>
  );
}

export default function PrivacyNoticePage() {
  return (
    <div className="relative isolate min-h-screen bg-[color:var(--paper)]">
      {/* Atmosphere is confined to a top band: a full-page aurora washes long
          documents in bright teal and hurts text contrast. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[460px] overflow-hidden" aria-hidden="true">
        <div className="cv-canvas cv-bloom absolute inset-0" />
        <div className="cv-grid absolute inset-0" />
        <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[color:var(--paper)] to-transparent" />
      </div>

      <header className="sticky top-0 z-30 border-b border-[color:var(--line)] bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-2.5">
          <Logo height={44} variant="flat" />
          <div className="flex items-center gap-2">
            <a href="/" className="cv-navlink hidden sm:inline-flex">Home</a>
            <a href="/dashboard" className="cv-btn-ghost px-4 py-2 text-xs cv-cta">Back to portal</a>
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-5xl px-4 py-10">
        <div className="lg:grid lg:grid-cols-[1fr_220px] lg:gap-12">
          <article className="min-w-0">
            {/* Title block */}
            <div className="cv-brand rounded-3xl border border-[color:var(--jaia-green)]/20 px-6 py-8 text-white shadow-xl shadow-black/10 sm:px-8 sm:py-10">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[color:var(--jaia-gold)]">
                Jamaica Artificial Intelligence Association
              </p>
              <h1 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">
                Privacy Notice
              </h1>
              <p className="mt-4 text-sm text-white/80">
                Effective date: {EFFECTIVE_DATE}
              </p>
            </div>

            {/* Introduction */}
            <div className="mt-8 space-y-4 text-[15px] leading-7 cv-body">
              <p>
                CaribVoices is a project of the{" "}
                <Term>Jamaica Artificial Intelligence Association (JAIA)</Term>{" "}
                (&ldquo;JAIA&rdquo;, &ldquo;we&rdquo;, &ldquo;our&rdquo;, or
                &ldquo;us&rdquo;). This notice explains how JAIA collects, uses, and
                protects your personal data when you contribute to CaribVoices, in
                accordance with Jamaica&apos;s{" "}
                <Term>Data Protection Act, 2020</Term>.
              </p>
              <p>
                We are building an open dataset of Caribbean speech so that artificial
                intelligence and voice technologies understand and respect Caribbean
                languages, dialects, and accents.{" "}
                <Term>Your participation is voluntary.</Term>
              </p>
            </div>

            <Section id="information-we-collect" title="Information We Collect">
              <p>When you take part in CaribVoices through WhatsApp, we collect:</p>
              <Bullets>
                <li>
                  <Term>Voice recordings:</Term> audio files of the voice submissions
                  you share via WhatsApp.
                </li>
                <li>
                  <Term>Metadata:</Term> optional information you choose to provide,
                  including your geographic region within Jamaica or diaspora
                  location, and your age range (not your exact age).
                </li>
                <li>
                  <Term>WhatsApp contact information:</Term> your WhatsApp phone
                  number, used to manage your session and communicate with you through
                  the platform.
                </li>
              </Bullets>
            </Section>

            <Section id="lawful-basis" title="Lawful Basis for Processing">
              <p>We process your personal data on the following lawful bases:</p>
              <ol className="ml-1 list-outside list-decimal space-y-2 pl-5 marker:font-medium marker:text-[color:var(--jaia-green)]">
                <li>
                  <Term>Explicit consent:</Term> you give your explicit consent before
                  submitting any voice recording.
                </li>
                <li>
                  <Term>Performance of a contract:</Term> processing needed to carry
                  out your participation in CaribVoices.
                </li>
              </ol>
            </Section>

            <Section id="how-we-use-your-data" title="How We Use Your Data">
              <Bullets>
                <li>Open dataset creation</li>
                <li>AI model training</li>
                <li>Linguistic research</li>
                <li>Platform operations</li>
                <li>Quality assurance</li>
              </Bullets>
            </Section>

            <Section id="data-sharing" title="Data Sharing and Disclosure">
              <p>
                <Term>Public open datasets.</Term> Voice recordings and associated
                metadata (such as region and age range) will be published as open
                datasets available to the public. These datasets will not include any
                data that could reasonably identify you.
              </p>
              <p>
                <Term>Service providers.</Term> We share data with trusted service
                providers who help us run the platform:
              </p>
              <Bullets>
                <li>
                  <Term>Meta (WhatsApp Business Platform):</Term> WhatsApp messaging
                </li>
                <li>
                  <Term>Amazon Web Services (AWS):</Term> hosting and secure storage
                  (Amazon S3)
                </li>
                <li>
                  <Term>Label Studio:</Term> data labelling and transcription review
                </li>
              </Bullets>
              <p>
                These providers are bound by confidentiality agreements and may only
                process your data on our behalf for the purposes stated here.
              </p>
              <p>
                <Term>Research partners.</Term> We may collaborate with academic
                institutions, research organisations, and non-profit entities. Any data
                shared with research partners will be de-identified and subject to data
                use agreements.
              </p>
              <p>
                <Term>Legal authorities.</Term> We may disclose your personal data when
                required by law.
              </p>
              <p>
                <Term>International transfers.</Term> Some of our service providers are
                located outside Jamaica. When personal data is transferred
                internationally, we make sure adequate safeguards are in place.
              </p>

              {/* Negative commitments — called out so they are hard to miss. */}
              <div className="mt-6 rounded-2xl border border-[color:var(--jaia-green)]/25 bg-[color:var(--jaia-green-soft)] px-5 py-4 backdrop-blur-sm">
                <p className="font-bold cv-heading">We do not:</p>
                <ul className="mt-3 list-outside list-disc space-y-2 pl-5 marker:text-[color:var(--jaia-green)]">
                  <li>Sell your personal data to third parties</li>
                  <li>Share your phone number publicly or with data users</li>
                  <li>Use your data for commercial advertising or marketing</li>
                </ul>
              </div>
            </Section>

            <Section id="data-security" title="Data Security">
              <p>
                We apply appropriate technical and organisational measures to protect
                your personal data. Details are set out in the{" "}
                <ExternalLink href={JAIA_PRIVACY_POLICY}>
                  JAIA Privacy Policy
                </ExternalLink>
                .
              </p>
            </Section>

            <Section id="data-retention" title="Data Retention">
              <p>
                We retain your personal data for up to <Term>5 years</Term> to fulfil
                our contract with you and meet our legal obligations.
              </p>
              <p>
                Please note that once voice recordings are published in the open
                dataset in de-identified form, they cannot be withdrawn from copies
                already released.
              </p>
            </Section>

            <Section id="your-rights" title="Your Rights">
              <p>You have the right to:</p>
              <Bullets>
                <li>Access, rectify, or delete your data.</li>
                <li>Withdraw your consent at any time.</li>
                <li>Object to marketing communications.</li>
              </Bullets>
              <p>
                For concerns relating to this notice, or to exercise your rights, please
                contact our Data Protection Officer at{" "}
                <a
                  href={`mailto:${DPO_EMAIL}`}
                  className="cv-link"
                >
                  {DPO_EMAIL}
                </a>
                .
              </p>
            </Section>

            <Section id="more-information" title="More Information">
              <p>
                You can read the full{" "}
                <ExternalLink href={JAIA_PRIVACY_POLICY}>
                  JAIA Privacy Policy here
                </ExternalLink>
                .
              </p>
            </Section>

            <Section id="acknowledgement" title="Acknowledgement and Consent">
              <p>
                Before you submit a voice recording, you will be asked to confirm that:
              </p>
              <Bullets>
                <li>You have read and understood this Privacy Notice; and</li>
                <li>
                  You give your explicit consent for JAIA to collect and process your
                  voice recording and metadata for the purposes described above.
                </li>
              </Bullets>
              <p>
                You will not be able to submit a recording until you have given this
                confirmation. A record of your consent is kept so it can be provided to
                the Office of the Information Commissioner on request.
              </p>
            </Section>

            <p className="cv-surface mt-12 px-6 py-6 text-center text-[15px] font-medium leading-7 cv-body">
              Thank you for helping build AI that understands and celebrates Caribbean
              languages and cultures.
            </p>
          </article>

          {/* On this page — desktop only; the article order carries small screens. */}
          <nav aria-label="On this page" className="hidden lg:block">
            <div className="sticky top-24">
              <p className="cv-eyebrow">
                On this page
              </p>
              <ul className="mt-3 space-y-2 border-l border-[color:var(--line)] text-sm">
                {SECTIONS.map((s) => (
                  <li key={s.id}>
                    <a
                      href={`#${s.id}`}
                      className="-ml-px block border-l border-transparent pl-3 cv-muted transition hover:border-[color:var(--jaia-green)] hover:text-[color:var(--jaia-green)]"
                    >
                      {s.title}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </nav>
        </div>
      </main>

      <SiteFooter links={[{ href: "/", label: "Home" }]} />

    </div>
  );
}
