#!/bin/bash
# 더블클릭으로: 최신 코드 받기(git pull) -> 로컬 서버(server.py) 켜기 -> builder.html 열기.
# 어느 맥에서든 이 파일 하나만 더블클릭하면 "접속해서 이어서 작업하기"가 끝남.
set -e
cd "$(dirname "$0")"

echo "최신 코드 받는 중..."
git pull --ff-only || { echo "git pull 실패 — 네트워크나 충돌을 먼저 확인하세요."; read -p "엔터를 누르면 창이 닫힙니다..."; exit 1; }

if curl -s -o /dev/null -m 1 http://localhost:8420/ping; then
  echo "server.py는 이미 켜져 있습니다."
else
  echo "server.py 켜는 중..."
  nohup python3 server.py > .server.log 2>&1 &
  sleep 1
fi

open builder.html
echo "완료 — builder.html이 열렸습니다. 이 터미널 창은 닫아도 됩니다."
sleep 2
