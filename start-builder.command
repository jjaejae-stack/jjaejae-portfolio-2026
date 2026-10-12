#!/bin/bash
# 더블클릭으로: 최신 코드 받기(git pull) -> 로컬 서버(server.py) 켜기 -> builder.html 열기.
# 어느 맥에서든 이 파일 하나만 더블클릭하면 "접속해서 이어서 작업하기"가 끝남.
# 이 파일을 실행하려면 git clone + 아래 도구들이 그 맥에 이미 한 번 설치돼 있어야 함 — 처음
# 셋업하는 맥이라면 이 폴더를 받기 전에 README.md(github.com에서 바로 읽힘)를 먼저 따라오세요.
set -e
cd "$(dirname "$0")"

for cmd in python3 ffmpeg; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "'$cmd'가 설치되어 있지 않습니다. README.md의 설치 순서를 먼저 따라주세요 (brew install $cmd)."
    read -p "엔터를 누르면 창이 닫힙니다..."
    exit 1
  fi
done
if ! python3 -c "import PIL" >/dev/null 2>&1; then
  echo "Python의 pillow 패키지가 없습니다. 터미널에서 'pip3 install pillow'를 먼저 실행해주세요."
  read -p "엔터를 누르면 창이 닫힙니다..."
  exit 1
fi

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
