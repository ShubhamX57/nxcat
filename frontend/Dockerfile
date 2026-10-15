# nxcat web app image. Stage 1 builds the static files with Node; stage 2 serves
# them with nginx (no Node, no source code, no node_modules in the final image).

# The build output is plain static files, so this stage always runs on the build
# machine's own platform, even when the image is built for another one.
FROM --platform=$BUILDPLATFORM node:24-alpine AS build
WORKDIR /app
# Dependencies first: this layer is cached until package-lock.json changes.
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# The "unprivileged" nginx image runs as a normal user and listens on 8080.
FROM nginxinc/nginx-unprivileged:1.27-alpine
# The official entrypoint fills in ${NXCAT_API_UPSTREAM} from the environment at start-up.
ENV NXCAT_API_UPSTREAM=http://api:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --retries=10 \
  CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/healthz"]
