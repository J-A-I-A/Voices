import Image from "next/image";

// Ratio of public/carib-voices-mark.svg — the brand file cropped to its
// artwork bounds (the original carries ~40% empty padding).
const MARK_RATIO = 347 / 291;

/** Miniature of the brand waveform, drawn crisply for small sizes. */
function WaveGlyph({ height }: { height: number }) {
  // Heights as a fraction of the box; alternating brand green and gold,
  // echoing the bars in the full lockup.
  const bars = [0.38, 0.62, 0.95, 0.55, 0.8, 0.45, 0.7, 0.3];
  const w = Math.round(height * 1.12);
  return (
    <svg
      width={w}
      height={height}
      viewBox="0 0 112 100"
      aria-hidden="true"
      className="shrink-0"
    >
      {bars.map((h, i) => (
        <rect
          key={i}
          x={i * 14 + 2}
          y={(1 - h) * 50}
          width="8"
          height={h * 100}
          rx="4"
          fill={i % 2 === 0 ? "var(--jaia-green)" : "var(--jaia-gold)"}
        />
      ))}
    </svg>
  );
}


/* Flat-peak lockup.

   The brand file's waveform peaks reach roughly 3x the height of the type
   inside it, which is why it needs ~72px of height before "CaribVoices" can
   be read. Here the waveform sits only at the ends, clear of the wordmark, so
   the name is never competing with bars behind it — and the bars animate,
   echoing the live waveform used across the site.

   Drawn inline rather than loaded as a file so the wordmark inherits Poppins
   from the page; an <img> cannot reach the document's webfonts. */

/* Flank bar heights as a fraction of the maximum amplitude. The right side
   mirrors the left so the lockup stays visually balanced. */
const FLANK = [0.42, 0.68, 1.0, 0.58, 0.34];

function FlatLockup({ height, tone }: { height: number; tone: "ink" | "light" }) {
  const VB_W = 560;
  const VB_H = 120;
  const mid = VB_H / 2;
  const maxAmp = 40;

  const BAR_W = 11;
  const GAP = 18;
  const barColor = (i: number) => (i % 2 === 0 ? "var(--jaia-green)" : "var(--jaia-gold)");

  const bar = (x: number, h: number, i: number, key: string) => {
    const amp = h * maxAmp;
    return (
      <rect
        key={key}
        className="cv-logo-bar"
        x={x}
        y={mid - amp}
        width={BAR_W}
        height={amp * 2}
        rx={BAR_W / 2}
        fill={barColor(i)}
        style={{ ["--cv-delay" as string]: `${i * 0.13}s` }}
      />
    );
  };

  const leftStart = 6;
  const rightStart = VB_W - 6 - (FLANK.length * GAP - (GAP - BAR_W));

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${VB_H}`}
      height={height}
      width={Math.round(height * (VB_W / VB_H))}
      role="img"
      aria-label="Carib Voices"
      className="shrink-0"
    >
      <g opacity={tone === "light" ? 0.95 : 0.85}>
        {/* Left flank: rises toward the wordmark. */}
        {FLANK.map((h, i) => bar(leftStart + i * GAP, h, i, `l${i}`))}
        {/* Right flank: mirrored. */}
        {FLANK.map((h, i) =>
          bar(rightStart + i * GAP, FLANK[FLANK.length - 1 - i], FLANK.length - 1 - i, `r${i}`)
        )}
      </g>

      <text
        x={VB_W / 2}
        y={mid}
        textAnchor="middle"
        dominantBaseline="central"
        fontSize="58"
        fontWeight="800"
        letterSpacing="-1"
        style={{ fontFamily: "inherit" }}
      >
        <tspan fill={tone === "light" ? "#fff" : "var(--ink)"}>Carib</tspan>
        <tspan fill={tone === "light" ? "var(--jaia-gold)" : "var(--jaia-green)"}>Voices</tspan>
      </text>
    </svg>
  );
}

/**
 * Carib Voices logo.
 *
 * Two variants, because the brand file is a full lockup — the "CaribVoices"
 * wordmark set inside the waveform — whose peaks take roughly 70% of the
 * artwork height. That makes the name unreadable at navigation sizes no
 * matter how the file is cropped.
 *
 *   "lockup"   the brand artwork itself, for places with room to show it
 *              properly: the auth panel, the footer, marketing headers.
 *   "wordmark" a compact glyph plus the name set in Poppins, for navigation
 *              and other small contexts — the same pattern jaia.org.jm uses,
 *              pairing its small mark with bold "JAIA" type.
 *   "flat"     the lockup redrawn with flattened peaks, so the name reads at
 *              roughly half the height the original needs.
 */
export function Logo({
  height = 44,
  variant = "lockup",
  href = "/",
  className = "",
  tone = "ink",
  priority = true,
}: {
  height?: number;
  variant?: "lockup" | "wordmark" | "flat";
  href?: string | null;
  className?: string;
  /** Wordmark colour: ink on light surfaces, white on green or dark ones. */
  tone?: "ink" | "light";
  priority?: boolean;
}) {
  const content =
    variant === "flat" ? (
      <FlatLockup height={height} tone={tone} />
    ) : variant === "lockup" ? (
      <Image
        src="/carib-voices-mark.svg"
        alt="Carib Voices"
        width={Math.round(height * MARK_RATIO)}
        height={height}
        priority={priority}
        className={`shrink-0 ${className}`}
        style={{ height, width: "auto" }}
      />
    ) : (
      <span className={`inline-flex items-center gap-2.5 ${className}`}>
        <WaveGlyph height={Math.round(height * 0.78)} />
        <span
          className="font-extrabold leading-none tracking-tight"
          style={{ fontSize: height * 0.52 }}
        >
          <span style={{ color: tone === "light" ? "#fff" : "var(--ink)" }}>CARIB</span>{" "}
          <span style={{ color: tone === "light" ? "var(--jaia-gold)" : "var(--jaia-green)" }}>
            VOICES
          </span>
        </span>
      </span>
    );

  if (!href) return content;
  return (
    <a href={href} className="inline-flex items-center" aria-label="Carib Voices home">
      {content}
    </a>
  );
}
