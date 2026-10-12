FROM node:26.10.0-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

COPY src ./src
COPY public ./public
COPY templates ./templates

ENV PORT=8080
EXPOSE 8080

CMD ["node", "src/server.js"]
