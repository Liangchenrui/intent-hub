ARG BASE_IMAGE=node:20-alpine
ARG NGINX_BASE=nginx:alpine

FROM ${BASE_IMAGE} AS builder

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM ${NGINX_BASE}

# 复制构建好的静态文件到 nginx 的 html 目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置文件
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

# 启动 nginx
CMD ["nginx", "-g", "daemon off;"]
