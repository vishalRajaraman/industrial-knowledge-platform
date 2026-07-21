import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";

const withSerwist = withSerwistInit({
  swSrc: "src/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

const nextConfig: NextConfig = {
  // NOTE: "output: export" is for production static hosting only.
  // Do NOT enable it in dev — it breaks cookies, dynamic routes, and SessionProvider.
  // Uncomment the line below only when running `npm run build` for static deployment:
  // output: "export",

  // Allow HMR websocket connections from 127.0.0.1 and localhost in development.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default withSerwist(nextConfig);
