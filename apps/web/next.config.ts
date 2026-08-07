import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

/**
 * Where the Next.js server reaches the API.
 *
 * Server-side only: the browser never uses this value directly unless
 * `NEXT_PUBLIC_API_URL` is set explicitly (see `lib/api-client.ts`).
 */
const apiTarget = (
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000"
).replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,

  /**
   * Same-origin proxy for browser-issued API calls.
   *
   * Client components (Advance, the create-project form, approval decisions) and
   * the SSE stream run in the browser, so they are cross-origin to the API and
   * subject to CORS. The API allows exactly one origin — `http://localhost:3000`
   * — so opening the workspace on `http://127.0.0.1:3000`, a LAN IP, or any
   * other host makes every one of those calls fail preflight while the
   * server-rendered page still loads. That asymmetry is what makes it look like
   * "the API is down" from a backend that is demonstrably healthy.
   *
   * Proxying through Next's own origin removes CORS from the picture entirely:
   * the browser talks to the host it was served from, and this server forwards
   * to the API. Nothing about the API changes.
   */
  async rewrites() {
    return [
      { source: "/api/v1/:path*", destination: `${apiTarget}/api/v1/:path*` },
      { source: "/health/:path*", destination: `${apiTarget}/health/:path*` },
    ];
  },

  // Emits a self-contained server bundle so the production Docker image can ship
  // without node_modules. See ADR-0002.
  output: "standalone",

  // Pin the trace root to this app. Next.js otherwise walks up looking for a
  // lockfile and can select an unrelated ancestor directory, which produces a
  // standalone bundle missing its dependencies.
  outputFileTracingRoot: currentDir,

  typescript: {
    // Never ship a build that does not typecheck. Stated explicitly because the
    // default is easy to relax under deadline pressure.
    ignoreBuildErrors: false,
  },

  eslint: {
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
