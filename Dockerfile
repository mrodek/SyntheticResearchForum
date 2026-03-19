FROM node:20-slim

# Install Python 3.11 and pip
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Make python3.11 the default python
RUN update-alternatives --install /usr/local/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/local/bin/python3 python3 /usr/bin/python3.11 1

WORKDIR /app
COPY . .

# Install OpenClaw, Lobster, and SRF Python package at build time
# so startup is fast and failures are visible in build logs not runtime logs
RUN npm install -g @clawdbot/openclaw @clawdbot/lobster \
    && pip install --break-system-packages -e '.[anthropic,openai]'

EXPOSE 8080

CMD ["openclaw", "start"]
