import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Carib Voices",
  description: "Collect and quality-check Jamaican voice notes over WhatsApp.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-white font-sans text-neutral-950 antialiased">
        {children}
      </body>
    </html>
  );
}
