#!/usr/bin/env bash
# 一键启动：后端 http://127.0.0.1:8000 + 前端 http://localhost:5173
set -e
cd "$(dirname "$0")"

# ---- backend ----
if [ ! -d backend/.venv ]; then
  echo "▶ 创建 Python 虚拟环境并安装依赖…"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
elif [ backend/requirements.txt -nt backend/.venv/pyvenv.cfg ]; then
  backend/.venv/bin/pip install -q -r backend/requirements.txt && touch backend/.venv/pyvenv.cfg
fi
[ -f backend/.env ] || { cp backend/.env.example backend/.env; echo "▶ 已生成 backend/.env，记得填写 LLM_API_KEY（不填为演示模式）"; }

# ---- frontend ----
# 第一次运行，或 package.json 更新过（比如新增了 vue-router / TypeScript）时安装依赖
if [ ! -d frontend/node_modules ] || [ frontend/package.json -nt frontend/node_modules/.package-lock.json ]; then
  echo "▶ 安装前端依赖…"
  (cd frontend && npm install)
fi

(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT INT TERM

echo "▶ 打开 http://localhost:5173 （推荐 Edge 浏览器，语音识别在国内可用）"
cd frontend && npm run dev
