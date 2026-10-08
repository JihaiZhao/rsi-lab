FROM node:22-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl python3 && rm -rf /var/lib/apt/lists/*
RUN npm install -g @openai/codex@0.154.0 && codex --version
USER node
WORKDIR /workspace
ENTRYPOINT ["codex"]
