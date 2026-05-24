#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[1/3] 后端核心冒烟（错题/词汇/听力/阅读）"
PYTHONPATH=. ./venv/bin/pytest -q tests/test_week2_backend_progress.py -k "mistakes or vocabulary or reading or listening"

echo "[2/3] 后端鉴权与会话冒烟"
PYTHONPATH=. ./venv/bin/pytest -q tests/test_week2_backend_progress.py -k "auth_password_reset_flow or speaking_session_user_isolation"

echo "[3/3] 前端构建冒烟"
npm --prefix frontend run build

echo "Smoke checks passed."
