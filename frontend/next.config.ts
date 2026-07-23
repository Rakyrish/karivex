import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "karivex.co.ke" },
      { protocol: "http", hostname: "karivex_backend" },
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
