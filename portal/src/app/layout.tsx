import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import "./globals.css";

// Poppins is the JAIA brand typeface. Loaded through next/font so it is
// self-hosted and preloaded rather than fetched from Google at runtime.
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Carib Voices",
  description: "Collect and quality-check Jamaican voice notes over WhatsApp.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`h-full ${poppins.variable}`}>
      <body className="h-full font-sans antialiased">{children}</body>
    </html>
  );
}
