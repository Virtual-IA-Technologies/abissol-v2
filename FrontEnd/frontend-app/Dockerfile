FROM node:24-alpine

WORKDIR /app
COPY package.json package-lock.json ./
COPY scripts/prepare-ocr.mjs scripts/prepare-ocr.mjs
RUN npm ci --no-audit --no-fund
COPY . .

EXPOSE 5185
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5185", "--strictPort"]
