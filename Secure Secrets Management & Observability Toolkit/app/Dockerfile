FROM node:26.10.0-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

COPY src ./src

FROM base AS test
COPY test ./test
RUN npm test

FROM base AS production
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV NODE_ENV=production
EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
