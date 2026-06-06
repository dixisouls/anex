# Backend image. Used now to run migrations and the seeder, and reused later for
# the API and broker (B4, B2) by overriding the command in docker-compose.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Contract package, backend package, tests, and the Alembic setup. All importable
# from /app, so "from contracts.schemas import Agent", "from backend.market.registry
# import ...", and "alembic upgrade head" all resolve.
COPY contracts/ ./contracts/
COPY backend/ ./backend/
COPY tests/ ./tests/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Default command seeds the market. B4 overrides this with the API server, and
# the migrate service (compose) overrides it with "alembic upgrade head".
CMD ["python", "-m", "backend.market.seeder"]