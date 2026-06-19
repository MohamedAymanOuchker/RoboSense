FROM node:22-slim

WORKDIR /app

# Install dependencies from the lockfile first for layer caching.
COPY package.json package-lock.json ./
RUN npm ci

# App source (node_modules/.next excluded via .dockerignore; the compose dev
# setup mounts the source and keeps these as container-owned volumes).
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
