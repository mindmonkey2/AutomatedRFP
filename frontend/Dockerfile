# Next.js frontend, built as a standalone server (no node_modules in the final image).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Baked in at build time: where the API is (inside the compose network) and whether the
# site is served over HTTPS (adds HSTS).
ARG BACKEND_URL=http://api:8000
ARG FRONTEND_HTTPS=false
ENV BACKEND_URL=$BACKEND_URL FRONTEND_HTTPS=$FRONTEND_HTTPS NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=5 \
  CMD wget -q -O /dev/null http://127.0.0.1:3000/login || exit 1
CMD ["node", "server.js"]
