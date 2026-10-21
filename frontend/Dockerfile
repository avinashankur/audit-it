# Build stage
FROM node:20-alpine AS builder
WORKDIR /app

# Support passing backend URL at build time for static deployments
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production serve stage
FROM nginx:alpine
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL

# Copy built frontend assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx template for runtime BACKEND_URL substitution and fallback default
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s|\${BACKEND_URL}|$BACKEND_URL|g" /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
