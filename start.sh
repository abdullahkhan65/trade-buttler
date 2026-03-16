#!/bin/bash
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Kill anything already on these ports
lsof -ti :8000,5173 | xargs kill -9 2>/dev/null

# Start backend
cd "$ROOT/backend"
source .venv/bin/activate 2>/dev/null || true
uvicorn main:app --port 8000 &
BACKEND_PID=$!

# Start frontend
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID  |  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
