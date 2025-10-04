FROM node:20-alpine
WORKDIR /app

# ติดตั้ง dependency ก่อน เพื่อ cache layer ดีขึ้น
COPY package.json package-lock.json* pnpm-lock.yaml* yarn.lock* ./
RUN npm ci || npm install

# คัดลอกซอร์สโค้ดที่เหลือ
COPY . .

RUN rm -rf .next

# Build
RUN npm run build

EXPOSE 3000
CMD ["npm", "run", "start"]
