FROM node:20-slim

WORKDIR /app

# Copy the lockfile too so installs are deterministic (matches package-lock.json).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Self-heal the Tailwind engine at startup. BuildKit's `RUN npm ci` can bake a
# stale Tailwind v3 into the image layer (a builder-specific npm resolution
# quirk, a plain *runtime* `npm ci` correctly resolves the v4 engine the
# lockfile pins). The dev container's node_modules is an anonymous volume seeded
# from the image, so it inherits that staleness and `@import "tailwindcss"` then
# fails to compile. Guard: if the installed Tailwind isn't v4, reconcile
# node_modules against the lockfile (fast no-op once it's correct) before dev.
CMD ["sh", "-c", "node -e \"require('tailwindcss/package.json').version.startsWith('4')||process.exit(1)\" 2>/dev/null || npm ci; exec npm run dev"]
