# Build from this folder: docker build -t my-bot .
# The match runs it with no network, a read-only root (writable /tmp), 1 CPU, 512 MB, and the map at /arena.
FROM python:3.13-slim
WORKDIR /bot
COPY mechfight.py example_bot.py arena_map.py economy.py bot.py ./
ENTRYPOINT ["python3", "-u", "/bot/bot.py"]
