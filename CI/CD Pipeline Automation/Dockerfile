FROM node:26.11.1-slim

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts

COPY src ./src
COPY public ./public

ENV NODE_ENV=production
EXPOSE 8080

USER node
CMD ["node", "src/server.js"]
