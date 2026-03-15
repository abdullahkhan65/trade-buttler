#!/bin/bash
set -e

echo "╔════════════════════════════════════════╗"
echo "║     Trade Buttler Signal Engine        ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 not found"
    exit 1
fi

# Check Node
if ! command -v node &> /dev/null; then
    echo "ERROR: node not found"
    exit 1
fi

# Setup .env if not exists
if [ ! -f backend/.env ]; then
    cp .env.example backend/.env
    echo "Created backend/.env from template"
fi

# Start Backend
echo "[1/2] Starting backend..."
cd backend
pip3 install -r requirements.txt -q
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
sleep 3

# Start Frontend
echo "[2/2] Starting frontend..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle shutdown
cleanup() {
    echo ""
    echo "Stopping services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

wait
