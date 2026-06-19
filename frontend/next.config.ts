import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dashboard talks to the backend purely from the browser via
  // NEXT_PUBLIC_API_URL, so no rewrites/proxy are needed.
};

export default nextConfig;
