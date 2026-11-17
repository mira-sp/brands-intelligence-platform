# Frontend Dockerfile - Next.js dashboard
# Multi-stage build for both development and production

# ---- Base Stage ----
# Node 22 = current LTS (23 is a short-lived odd release, already end-of-life)
FROM node:22-alpine AS base
WORKDIR /app
COPY package.json package-lock.json* ./

# ---- Development Stage ----
FROM base AS development
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

# ---- Build Stage ----
FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm ci
COPY . .
RUN npm run build

# ---- Production Stage ----
# Runs the Next.js standalone server (so the security headers in next.config.ts apply)
# as an unprivileged user, with only the build output - no source or dev dependencies.
FROM node:22-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup -S -g 1001 nodejs && adduser -S -u 1001 -G nodejs nextjs
COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:3000/ || exit 1
CMD ["node", "server.js"]
