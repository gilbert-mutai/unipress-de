/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone build => small runtime image (see Dockerfile).
  output: "standalone",
};

export default nextConfig;
