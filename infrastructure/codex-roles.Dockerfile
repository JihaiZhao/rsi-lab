FROM node:22-bookworm-slim
RUN npm install -g @openai/codex@0.154.0 && codex --version
USER node
WORKDIR /workspace
ENTRYPOINT ["codex"]
