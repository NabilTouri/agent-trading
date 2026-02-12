/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    experimental: {
        serverActions: {
            bodySizeLimit: '2mb',
        }
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: `${process.env.API_INTERNAL_URL || 'http://api:8000'}/api/:path*`,
            },
        ]
    },
}

module.exports = nextConfig
