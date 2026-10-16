FROM node:26.11.1-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --ignore-scripts --no-fund
COPY frontend/index.html frontend/vite.config.* ./
COPY frontend/src ./src
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM node:26.11.1-slim
WORKDIR /app
COPY backend/package*.json ./
RUN npm ci --omit=dev --ignore-scripts --no-fund && npm cache clean --force
COPY backend/src ./src
COPY --from=frontend /web/dist ./public
USER node
ENV HOST=0.0.0.0 PORT=8085 SERVE_FRONTEND=true HABIT_MODE=demo
EXPOSE 8085
CMD ["node", "src/server.js"]
