FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json ./

RUN npm install

FROM node:22-alpine AS builder

WORKDIR /app

# Next.js evaluates server modules during build. These placeholders satisfy that
# validation without baking production credentials into image layers.
ENV AUTH_SECRET=build-time-placeholder-not-for-runtime \
    AUTH_DISCORD_ID=build-time-discord-client-id \
    AUTH_DISCORD_SECRET=build-time-discord-client-secret \
    BACKEND_URL=http://backend:8000 \
    BACKEND_INTERNAL_AUTH_SECRET=build-time-placeholder-not-for-runtime

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build

FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
