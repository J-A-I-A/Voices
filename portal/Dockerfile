# Portal dev image. Installs deps and runs `next dev` with HMR.
# Bind-mounts the portal source so edits on the host hot-reload in the container.
FROM node:20-alpine

WORKDIR /app

# Install deps using the host lockfile so the container matches local installs.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# Source is bind-mounted at runtime (see docker-compose), but copy a baseline
# so the image is usable standalone too.
COPY . .

EXPOSE 3000

# Next dev with HMR; bind to all interfaces so the host can reach it.
ENV NEXT_TELEMETRY_DISABLED=1
ENV WATCHPACK_POLLING=true
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0", "-p", "3000"]
