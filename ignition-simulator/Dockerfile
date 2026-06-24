FROM node:latest

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 4840

CMD ["node", "server.js"]
