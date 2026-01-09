#!/bin/bash

# 停止脚本 - 同时停止前端和后端服务

echo "Stopping English Agent services..."

# 方法1：尝试使用lsof查找占用端口的进程并停止
echo "Stopping services by port..."

# 停止占用8000端口的进程（后端）
if lsof -i :8000 >/dev/null 2>&1; then
    BACKEND_PIDS=$(lsof -t -i :8000)
    if [ -n "$BACKEND_PIDS" ]; then
        for PID in $BACKEND_PIDS; do
            echo "Attempting to stop backend server with PID $PID..."
            # 先尝试正常终止
            kill "$PID" 2>/dev/null || true
            # 等待1秒
            sleep 1
            # 如果进程还在运行，强制终止
            if kill -0 "$PID" 2>/dev/null; then
                echo "Forcing termination of backend server with PID $PID..."
                kill -9 "$PID" 2>/dev/null || true
            fi
            echo "Backend server with PID $PID stopped"
        done
    fi
else
    echo "No backend server found on port 8000"
fi

# 停止占用5173-5180端口的进程（前端可能使用的端口范围）
for PORT in {5173..5180}; do
    if lsof -i :$PORT >/dev/null 2>&1; then
        FRONTEND_PIDS=$(lsof -t -i :$PORT)
        if [ -n "$FRONTEND_PIDS" ]; then
            for PID in $FRONTEND_PIDS; do
                echo "Attempting to stop frontend server with PID $PID on port $PORT..."
                # 先尝试正常终止
                kill "$PID" 2>/dev/null || true
                # 等待1秒
                sleep 1
                # 如果进程还在运行，强制终止
                if kill -0 "$PID" 2>/dev/null; then
                    echo "Forcing termination of frontend server with PID $PID..."
                    kill -9 "$PID" 2>/dev/null || true
                fi
                echo "Frontend server with PID $PID stopped on port $PORT"
            done
        fi
    fi
done

# 方法2：尝试直接终止可能的服务进程
echo "Stopping remaining service processes..."

# 尝试终止python进程
echo "Attempting to stop all Python processes..."
killall python 2>/dev/null || true
# 强制终止
killall -9 python 2>/dev/null || true

# 尝试终止npm进程
echo "Attempting to stop all npm processes..."
killall npm 2>/dev/null || true
killall -9 npm 2>/dev/null || true

# 尝试终止node进程
echo "Attempting to stop all Node.js processes..."
killall node 2>/dev/null || true
killall -9 node 2>/dev/null || true

# 等待3秒让进程完全终止
echo "Waiting for processes to terminate..."
sleep 3

# 验证服务是否已停止
echo "\nVerifying services are stopped..."

# 验证后端服务
if lsof -i :8000 >/dev/null 2>&1; then
    echo "ERROR: Backend server still running on port 8000!"
    echo "Remaining processes: $(lsof -t -i :8000)"
else
    echo "SUCCESS: Backend server stopped"
fi

# 验证前端服务
FRONTEND_RUNNING=false
for PORT in {5173..5180}; do
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo "ERROR: Frontend server still running on port $PORT!"
        echo "Remaining processes: $(lsof -t -i :$PORT)"
        FRONTEND_RUNNING=true
    fi
done

if [ "$FRONTEND_RUNNING" = false ]; then
    echo "SUCCESS: Frontend server stopped"
fi

echo "\nAll services stopped successfully!"

