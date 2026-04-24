/** @type {import('next').NextConfig} */
const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';

const nextConfig = {
  transpilePackages: ['@radix-ui/react-icons'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`, // Proxy to FastAPI backend
      },
    ];
  },
};

module.exports = nextConfig;
