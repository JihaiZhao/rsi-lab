FROM node:22-bookworm-slim
ARG CLAUDE_VERSION=2.1.293
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION} && claude --version
USER node
WORKDIR /workspace
ENTRYPOINT ["claude"]
