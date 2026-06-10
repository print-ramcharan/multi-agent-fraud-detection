#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting Fraud Detection Server in the background ==="
# Start the server and redirect logs
PYTHONPATH=. uv run uvicorn src.simple_server:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
SERVER_PID=$!

echo "=== Starting React Frontend Dev Server (Vite) ==="
# Start the dev server from dashboard-react folder and redirect logs
cd dashboard-react
npm run dev -- --host 127.0.0.1 --port 5173 > vite.log 2>&1 &
VITE_PID=$!
cd ..

# Function to clean up the servers on exit
cleanup() {
    echo ""
    echo "=== Shutting down servers ==="
    kill $SERVER_PID 2>/dev/null || true
    kill $VITE_PID 2>/dev/null || true
}
trap cleanup EXIT

# Wait for server to become healthy
echo "Waiting for the server to start on http://127.0.0.1:8000/health ..."
max_attempts=30
attempt=1
while [ $attempt -le $max_attempts ]; do
    if curl -s http://127.0.0.1:8000/health >/dev/null; then
        echo "Server is healthy and ready!"
        break
    fi
    sleep 0.5
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "Error: Server failed to start. Check server.log for details."
    cat server.log
    exit 1
fi

echo ""
echo "=== Running Demo Transactions ==="
PYTHONPATH=. uv run python3 demo.py

echo ""
echo "======================================================================"
echo " The React Frontend is running at:  http://127.0.0.1:5173/"
echo " The API documentation is at:      http://127.0.0.1:8000/docs"
echo "======================================================================"
echo ""
read -p "Press [Enter] to stop the servers and exit..."

