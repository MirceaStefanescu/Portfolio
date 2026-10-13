FROM node:26.11.1-alpine AS build
WORKDIR /app
COPY package*.json ./
ENV NG_BUILD_CACHE_STORE=sqlite
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM nginx:1.31-alpine
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
