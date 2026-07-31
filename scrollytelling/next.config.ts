/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["three", "three-stdlib"],
  experimental: {
    optimizePackageImports: ["@react-three/drei", "@react-three/postprocessing"],
  },
};

export default nextConfig;
