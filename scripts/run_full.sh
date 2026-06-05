#!/bin/bash
set -euo pipefail

# Полный запуск среды
# Клонировать репозиторий и перейти в папку проекта
# git clone https://github.com/your-org/ai-conductor-platform
# cd ai-conductor-platform

# 1. Секреты
cp .env.example .env
# Заполнить: OPENAI_API_KEY, GITHUB_TOKEN, LANGFUSE_SECRET и т.д.

# 2. Подготовка Firecracker (однократно)
# sudo ./scripts/setup_firecracker.sh

# 3. Старт инфраструктуры
docker compose up -d postgres redis qdrant langfuse

# 4. Инициализация БД + индексация репозитория
docker compose run --rm webhook-indexer python -m indexer.initial_index \
  --repo your-org/your-saas-repo \
  --branch main

# 5. Запуск оркестратора
docker compose up -d langgraph-server sandbox-manager approval-gateway

# 6. Conductor UI
docker compose up -d conductor-ui

# 7. Запуск задачи (пример)
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "sprint_goal": "Implement JWT authentication for user service",
    "token_budget_usd": 2.50,
    "require_approval_before_commit": true,
    "max_iterations": 10
  }'

# Дирижёр открывает: http://localhost:3001 — пульт управления
