#!/bin/bash
set -e

cd "$(dirname "$0")"

DC="docker compose -f docker-compose.full.yml"

echo "1. 启动基础设施..."
$DC up -d postgres redis
sleep 5
echo "✓"

echo "2. 启动AI引擎..."
$DC up -d ai-engine
sleep 3
echo "✓"

echo "3. 启动后端API..."
$DC up -d backend
sleep 5
echo "✓"

echo "4. 启动WebSocket网关..."
$DC up -d websocket
sleep 3
echo "✓"

echo "5. 启动前端..."
$DC up -d frontend nginx
sleep 3
echo "✓"

echo "6. 健康检查..."
curl -f http://localhost/api/health >/dev/null
curl -f http://localhost/ai/health >/dev/null
echo "✓"

echo "✓ 全部启动成功，访问 http://localhost"
