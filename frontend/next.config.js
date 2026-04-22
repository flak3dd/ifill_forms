/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@radix-ui/react-icons'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*', // Proxy to FastAPI backend
      },
    ];
  },
};

module.exports = nextConfig;
