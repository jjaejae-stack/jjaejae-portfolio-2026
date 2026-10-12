# jjaejae.com — 2026 Portfolio

운영 중인 포트폴리오 사이트. `index.html`이 실제 배포되는 사이트(Vercel이 git push마다 자동 재배포),
`builder.html`은 그 콘텐츠를 편집하는 로컬 전용 도구, `server.py`는 `builder.html`이 쓰는 로컬 보조 서버
(이미지/영상 처리, GitHub에 Publish, 다른 기기와의 동기화)입니다.

## 완전히 새 맥에서 처음 시작하기 (아무것도 안 깔려있는 전제)

터미널(Spotlight에서 "터미널" 검색)을 열고 아래 순서대로 실행하세요. **이 문서는 github.com 저장소
페이지에서 그냥 읽을 수 있으니, clone하기 전에도 브라우저로 먼저 열어서 따라와도 됩니다.**

### 1. Xcode Command Line Tools (git이 여기 포함돼 있음)
```
xcode-select --install
```
팝업이 뜨면 설치 클릭, 몇 분 기다림. (이미 깔려 있으면 "이미 설치되어 있습니다" 에러가 뜨는데, 그건 정상이니 다음 단계로.)

### 2. Homebrew (ffmpeg 등 설치용 패키지 매니저)
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
설치 끝나고 터미널에 **직접 출력해주는 2줄짜리 PATH 설정 명령**이 있으면 그것도 그대로 복사해서 실행
(없으면 터미널을 새로 열었다가 다시 열면 됨).

### 3. GitHub 로그인
```
brew install gh
gh auth login
```
→ `GitHub.com` 선택 → `HTTPS` 선택 → 브라우저로 로그인 승인.

### 4. 이미지/영상 처리 도구
```
brew install python ffmpeg
pip3 install pillow
```

### 5. 저장소 받기 (원하는 위치에서, 예: 바탕화면)
```
cd ~/Desktop
git clone https://github.com/jjaejae-stack/jjaejae-portfolio-2026.git
```

### 6. 작업 시작
Finder에서 방금 받은 폴더로 들어가서 **`start-builder.command`를 더블클릭**. 최신 코드를 받고
(`git pull`), 로컬 서버(`server.py`)를 켜고, `builder.html`을 자동으로 엽니다.

## 그 다음부터 — 매번 작업 시작할 때

어느 맥이든 그 폴더의 **`start-builder.command`만 더블클릭**하면 끝. (git 로그인은 맥마다 한 번만
해두면 계속 유지됩니다.)

## 작업 중/작업 끝낼 때

- `builder.html`에서 편집하면 자동으로(15초 디바운스) 서버에 저장되고 git에 커밋/push됩니다 —
  발행(Publish) 전 초안도 포함. 사이드바 하단에 동기화 상태가 표시됩니다.
- 다른 맥에서 이어서 하려면: 그 맥에서 `start-builder.command` 실행 → 사이드바에 "☁ 서버에 더
  최신 작업이 있어요"가 보이면 그 버튼으로 받아오기.
- `server.py`가 꺼져 있으면(터미널 창을 닫았거나) 동기화는 조용히 "오프라인"으로 표시되고, 그
  기기의 로컬 작업 자체는 평소처럼 계속됩니다 — 나중에 다시 켜면 그때 동기화됩니다.
