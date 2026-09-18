import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";
import path from "node:path";

// Next may already have loaded frontend/.env; reload from the shared repository root.
loadEnvConfig(
  path.resolve(__dirname, ".."),
  process.env.NODE_ENV !== "production",
  undefined,
  true,
);

const config: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};
export default config;
