import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const currentDir = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  reactStrictMode: true,

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
