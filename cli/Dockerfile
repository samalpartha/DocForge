FROM node:20-alpine

WORKDIR /app

COPY package.json .
RUN npm install --production

COPY . .

RUN chmod +x src/index.js

ENTRYPOINT ["node", "src/index.js"]
