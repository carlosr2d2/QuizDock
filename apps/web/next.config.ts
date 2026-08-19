import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  watchOptions: {
    pollIntervalMs: 1000,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }],
      },
    ];
  },
};

export default nextConfig;
