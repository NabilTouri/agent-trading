FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy source
COPY . .

# Build
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
