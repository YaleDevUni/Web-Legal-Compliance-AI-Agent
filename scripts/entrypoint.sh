#!/bin/bash
set -e

# Qdrant가 준비될 때까지 대기
echo "Waiting for Qdrant..."
until curl -sf "${QDRANT_URL:-http://localhost:6333}/healthz" > /dev/null; do
  sleep 1
done
echo "Qdrant ready."

# laws 컬렉션 존재 여부 확인
LAWS_EXISTS=$(curl -sf "${QDRANT_URL:-http://localhost:6333}/collections/laws/exists" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('exists','false'))" 2>/dev/null || echo "false")
GRAPH_EXISTS=false
[ -f "data/graph/law_graph.pkl" ] && GRAPH_EXISTS=true

if [ "$LAWS_EXISTS" = "True" ] && [ "$GRAPH_EXISTS" = "true" ]; then
  echo "Index and graph already exist. Skipping setup."
else
  echo "Running initial indexing..."
  python scripts/setup_index.py --reset

  echo "Building law graph..."
  python scripts/build_graph.py
fi

# API 서버 시작
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
