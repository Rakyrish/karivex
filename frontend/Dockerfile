FROM node:22-alpine AS deps
WORKDIR /app
RUN npm config set fetch-timeout 3600000 \
    && npm config set fetch-retries 8 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 180000
COPY package.json package-lock.json* ./
RUN --mount=type=cache,target=/root/.npm npm ci || npm install

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# INTERNAL_API_URL deliberately NOT passed as build ARG — all backend-data
# fetches are runtime (ISR/webhook), since the backend isn't reachable during
# `docker build`. Those pages generate on first request, then stay static.
#
# SITE_* identity vars ARE passed as build ARGs: routes with no backend fetch
# (e.g. /contact, /about) have nothing to make Next defer them to runtime, so
# they fully prerender during this build step — without these, lib/site.ts's
# fallback defaults would get baked in permanently instead of the real values.
ARG SITE_URL
ARG SITE_NAME
ARG SITE_SHORT_NAME
ARG SITE_TAGLINE
ARG SITE_LEGAL_NAME
ARG SITE_PHONE
ARG SITE_WHATSAPP
ARG SITE_EMAIL
ARG SITE_ADDRESS_STREET
ARG SITE_ADDRESS_LOCALITY
ARG SITE_ADDRESS_REGION
ARG SITE_ADDRESS_POSTAL_CODE
ARG SITE_ADDRESS_COUNTRY
ARG SITE_REGIONS
ARG SITE_HOURS
ARG SITE_DELIVERY_NAIROBI
ARG SITE_DELIVERY_REGIONAL
ARG SITE_CERTIFICATIONS
ENV SITE_URL=$SITE_URL \
    SITE_NAME=$SITE_NAME \
    SITE_SHORT_NAME=$SITE_SHORT_NAME \
    SITE_TAGLINE=$SITE_TAGLINE \
    SITE_LEGAL_NAME=$SITE_LEGAL_NAME \
    SITE_PHONE=$SITE_PHONE \
    SITE_WHATSAPP=$SITE_WHATSAPP \
    SITE_EMAIL=$SITE_EMAIL \
    SITE_ADDRESS_STREET=$SITE_ADDRESS_STREET \
    SITE_ADDRESS_LOCALITY=$SITE_ADDRESS_LOCALITY \
    SITE_ADDRESS_REGION=$SITE_ADDRESS_REGION \
    SITE_ADDRESS_POSTAL_CODE=$SITE_ADDRESS_POSTAL_CODE \
    SITE_ADDRESS_COUNTRY=$SITE_ADDRESS_COUNTRY \
    SITE_REGIONS=$SITE_REGIONS \
    SITE_HOURS=$SITE_HOURS \
    SITE_DELIVERY_NAIROBI=$SITE_DELIVERY_NAIROBI \
    SITE_DELIVERY_REGIONAL=$SITE_DELIVERY_REGIONAL \
    SITE_CERTIFICATIONS=$SITE_CERTIFICATIONS
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
