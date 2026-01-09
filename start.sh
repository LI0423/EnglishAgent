#!/bin/bash

# 启动脚本 - 同时启动前端和后端服务

echo "Starting English Agent services..."

# 检查并创建日志目录
mkdir -p logs

# 启动后端服务
echo "Starting backend server..."
cd "$(dirname "$0")" && python main.py > logs/backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend server started with PID: $BACKEND_PID"

# 等待后端服务启动
sleep 2

# 启动前端服务
echo "Starting frontend server..."
PROJECT_ROOT="$(dirname "$0")"
# 保存项目根目录的绝对路径
ABS_PROJECT_ROOT=$(cd "$PROJECT_ROOT" && pwd)
# 使用npm的绝对路径来启动前端服务
NPM_PATH=$(which npm)
if [ -z "$NPM_PATH" ]; then
    echo "Error: npm not found. Please install Node.js and npm first."
    exit 1
fi
# 启动前端服务并将日志写入项目根目录的logs目录
cd "$ABS_PROJECT_ROOT"/frontend && "$NPM_PATH" run dev > "$ABS_PROJECT_ROOT"/logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend server started with PID: $FRONTEND_PID"

# 显示服务状态
echo "Services started successfully!"
echo "================================="
echo "Backend server: http://localhost:8000"
echo "Frontend server: http://localhost:5173"
echo "================================="
echo "To stop all services, run: kill $BACKEND_PID $FRONTEND_PID"
echo "To view logs:"
echo "  Backend: tail -f logs/backend.log"
echo "  Frontend: tail -f logs/frontend.log"
