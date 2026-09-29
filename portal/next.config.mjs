/** @type {import('next').NextConfig} */

// Where the Next server (not the browser) reaches the API. Inside docker
// compose that's the `backend` service. On Vercel it must be the backend's
// public URL — the compose hostname doesn't exist there, so fail the build
// rather than deploy a portal whose every API call 404s.
if (process.env.VERCEL && !process.env.BACKEND_INTERNAL_URL) {
  throw new Error("BACKEND_INTERNAL_URL must be set on Vercel (e.g. https://api.example.com).");
}
const BACKEND_INTERNAL_URL = (process.env.BACKEND_INTERNAL_URL || "http://backend:8000").replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  // The auth panel image is a bundled local SVG (/public/caribbean-auth.svg),
  // so no remote image patterns are required.

  // Proxy /api/* to the backend so the browser only ever talks to the portal's
  // own origin. Lets one ngrok tunnel serve everything, and avoids Chrome's
  // Local Network Access block on public pages calling http://localhost:8000.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_INTERNAL_URL}/:path*` },
      // Meta's WhatsApp webhook callback URL points at /whatsapp/webhook on
      // the tunnel, so pass it through unprefixed.
      { source: "/whatsapp/:path*", destination: `${BACKEND_INTERNAL_URL}/whatsapp/:path*` },
    ];
  },
};
export default nextConfig;
