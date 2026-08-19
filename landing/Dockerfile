FROM node:20-slim

WORKDIR /app

# Copy the lockfile too so installs are deterministic (matches package-lock.json).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Self-heal the Tailwind engine at startup — same BuildKit/Tailwind-v4 quirk as
# frontend/Dockerfile; see that file's comment for the full explanation.
CMD ["sh", "-c", "node -e \"require('tailwindcss/package.json').version.startsWith('4')||process.exit(1)\" 2>/dev/null || npm ci; exec npm run dev"]
