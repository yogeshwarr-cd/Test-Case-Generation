import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8006/api/:path*',
      },
    ];
  }
};

export default nextConfig;
