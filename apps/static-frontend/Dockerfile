FROM node:22.14.0-alpine3.21 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.28.0-alpine3.21
COPY nginx.conf /etc/nginx/nginx.conf
COPY errors/ /usr/share/nginx/html/errors/
COPY --from=build /app/dist/ /usr/share/nginx/html/
EXPOSE 8080
USER 101
