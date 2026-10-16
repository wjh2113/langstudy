#!/usr/bin/env bash
# 一键启动：后端 http://127.0.0.1:8000 + 前端 http://localhost:5173
set -e
cd "$(dirname "$0")"

# ---- backend ----
PY=""
for c in python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY=$c
    break
  fi
done
if [ -z "$PY" ]; then
  echo "需要 Python 3.10 或更高版本（当前 python3 太旧，类型注解无法运行）"
  exit 1
fi
if [ -d backend/.venv ] && ! backend/.venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "▶ 现有虚拟环境 Python 低于 3.10，重新创建…"
  rm -rf backend/.venv
fi
if [ ! -d backend/.venv ]; then
  echo "▶ 创建 Python 虚拟环境并安装依赖（$PY）…"
  "$PY" -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
[ -f backend/.env ] || { cp backend/.env.example backend/.env; echo "▶ 已生成 backend/.env，记得填写 LLM_API_KEY（不填为演示模式）"; }

# ---- frontend ----
if [ ! -d frontend/node_modules ]; then
  echo "▶ 安装前端依赖…"
  (cd frontend && npm install)
fi

(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM

echo "▶ 打开 http://localhost:5173 （推荐 Edge 浏览器，语音识别在国内可用）"
cd frontend && npm run dev
