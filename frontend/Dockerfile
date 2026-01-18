FROM node:22-alpine AS builder

WORKDIR /app
COPY package*.json ./
COPY vite.config.* ./
COPY tsconfig*.json ./
COPY . .

RUN npm install && npm run build

EXPOSE 8080

CMD [ "npm", "run", "start" ]
