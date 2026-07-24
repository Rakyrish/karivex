import type { NextConfig } from "next";
import path from "path";
import dotenv from "dotenv";

// Single source of truth is the .env file at the project root (one level
// above frontend/). Next.js only auto-loads .env files from its own project
// root, so without this, `npm run dev`/`npm run build` outside Docker would
// see none of the SITE_*, INTERNAL_API_URL, etc. values. In Docker,
// docker-compose's `env_file: .env` already injects these before the process
// starts, and dotenv.config() never overrides an already-set variable — so
// this is a no-op there.
dotenv.config({ path: path.resolve(process.cwd(), "..", ".env") });

const config: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "karivex.co.ke" },
      { protocol: "http", hostname: "karivex_backend" },
      { protocol: "https", hostname: "res.cloudinary.com" },
    ],
  },
  async rewrites() {
    // Browser-side form posts proxy through Next to the backend container.
    // Runtime env, container-name upstream — no shared aliases.
    return [
      {
        source: "/api/proxy/:path*",
        destination: `${process.env.INTERNAL_API_URL ?? "http://karivex_backend:8000"}/api/:path*`,
      },
    ];
  },
};

export default config;
