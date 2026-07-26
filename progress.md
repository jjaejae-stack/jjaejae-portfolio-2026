# 2026 포트폴리오 — 진행 상황

최종 업데이트: 2026-07-26

## 최근 변경 — Publish 버튼 + GitHub/Vercel 배포 연동 (2026-07-26)

builder.html의 각 프로젝트 편집 화면에 **PUBLISH** 버튼을 추가했습니다. 누르면 그 프로젝트 데이터가 실제 `index.html`의 `PROJECTS` 배열에 반영되고, GitHub에 커밋·푸시되어 Vercel이 자동 재배포합니다.

- **GitHub**: public 저장소 `https://github.com/jjaejae-stack/jjaejae-portfolio-2026` — 이 폴더(`2026 PF`) 전체가 git 저장소입니다 (451MB, 이미지/영상 포함해서 그대로 커밋). `gh` CLI로 로그인되어 있고 (`gh auth status`로 확인), `gh auth setup-git`로 git push 인증도 연결해둠.
- **Vercel**: 프로젝트명 `jjaejae-portfolio-2026`, GitHub 저장소와 연결되어 **push할 때마다 자동으로 프로덕션 배포**됩니다. 라이브 URL: **https://jjaejae-portfolio-2026.vercel.app**
- **`.vercelignore`**: `builder.html`, `server.py`, `progress.md`, `Ref/`, `TXT/`는 Vercel 배포에서 제외됩니다 (git 저장소에는 포함되지만 공개 사이트에는 안 올라감 — `builder.html`을 라이브 도메인에서 직접 열어도 404).
- **동작 방식** (`server.py`의 `/publish` 엔드포인트):
  1. builder.html이 기존 "코드 내보내기"에 쓰던 `exportProjectCode()`로 프로젝트 JS 객체 텍스트를 생성해 서버로 전송
  2. 서버가 `index.html`을 문자열 단위로 파싱(주석/문자열을 건너뛰는 괄호 매칭)해서, 같은 `id`를 가진 항목이 `PROJECTS` 배열에 이미 있으면 **교체**, 없으면 **배열 끝에 추가**
  3. `git add -A && git commit && git push` 실행 (변경 없으면 커밋 생략)
  4. Vercel이 push를 감지해 자동으로 새 배포 생성
- **주의**: Publish는 **해당 프로젝트만** 반영합니다 (다른 프로젝트는 건드리지 않음). 아직 `REST_OF_PROJECTS`로 주석 처리된 나머지 7개 프로젝트를 builder에서 채워서 Publish하면, 그 프로젝트가 `PROJECTS` 배열에 새로 추가되어 라이브 사이트에 나타납니다.
- **로컬 서버 필요**: 기존과 마찬가지로 `python3 server.py`가 켜져 있어야 PUBLISH 버튼이 동작합니다. 포트(8420)가 이미 사용 중이면(이전 세션에서 백그라운드로 켜둔 채 남아있는 경우) 새로 띄우기 전에 기존 프로세스를 종료해야 합니다 (`lsof -ti :8420 | xargs kill`).

## 최근 변경 — index.html 인트로 화면 (2026-07-26)

기존에 이름/소개글이 있던 첫 화면(`#intro`)을 5개 언어 인사말 마퀴 화면으로 교체했습니다.
- `#intro`: 화면 전체(100svh)를 5등분한 색띠(`.lang-row`), 각 줄에 "안녕하세요! jjaejae의 사이트에 오신 것을 환영합니다." 문구를 한국어/영어/스페인어/프랑스어/일본어로 표시. 텍스트를 10회 반복 후 통째로 한 번 더 복제(`reps+reps`)해서 `translateX(-50%)` 애니메이션으로 무한 루프 시 이음새가 안 보이게 처리(`GREETINGS` 배열, `renderGreetings()` in index.html 스크립트 상단).
- 줄마다 `reverse` 플래그로 애니메이션 방향(좌→우 / 우→좌)을 교차시킴, 속도(`duration`)도 줄마다 다르게 지정.
- 기존 이름/소개글/링크(Jaehoon Choi / Art Director / bio / Instagram·Email 링크)는 `#info`라는 새 섹션으로 이동. 헤더의 "Info" 버튼(`data-go="info"`)이 이 섹션으로 스크롤하도록 JS 라우팅 수정. 브랜드 로고 클릭(`data-go="home"`)은 그대로 맨 위(`#intro`, 마퀴 화면)로 이동.
- 색상: 초록(#4CAF50) / 다크브라운(#2b1710) / 연두(#e3e07a) / 코랄(#ee6f63) / 블루(#3f6fd1) — 사용자가 준 레퍼런스 이미지(`Ref/Main-1.png`) 색감 참고.
- TODO: 실제 브라우저에서 각 줄 반복 횟수(현재 10회 복제)가 초광폭 모니터에서도 끊김 없이 충분한지, 문구 톤(느낌표 등) 확정 필요.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 실제 공개용 포트폴리오 사이트 (정적 단일 HTML) |
| `builder.html` | 프로젝트를 만들고 편집하는 로컬 도구 (3단 패널 에디터) |
| `server.py` | `builder.html`의 GENERATE / KR↔EN 번역 버튼이 사용하는 로컬 도우미 서버 |

세 파일 모두 이 폴더(`2026 PF`)에 있고, 프로젝트 이미지 폴더(`SSF SHOP`, `NIKE 2019` 등)도 같은 위치에 있어야 상대경로가 맞습니다.

---

## 1. index.html — 실제 사이트

**구조**: 인트로(이름/소개) → 스크롤 → Work 리스트(카드) → 클릭 시 프로젝트 상세 뷰
- 프로젝트 메인: 배경 전체를 채우는 이미지/영상 + 좌상단에 라운드 컬러 박스(프로젝트명) + 우하단에 같은 색의 라운드 박스(YouTube/Vimeo/Instagram 아이콘)
- 프로젝트 상세: 사진 아래 캡션(라벨 좌측/번호 우측) + 본문. 사진은 원본 비율 그대로, 높이 고정 상태로 클릭하면 좌우로 롤링
- 하단에 크레딧 그리드

**현재 들어있는 프로젝트**: SSF SHOP 1개만 활성화되어 있습니다 (`PROJECTS` 배열). 나머지 7개(Galaxy Tab S9, Neo QLED 8K, NIKE 2019, YUNJAC, 아이스크림 홈런, 띵크어띵, HNY 2022)는 스크립트 안에 `REST_OF_PROJECTS`로 주석 처리되어 보류 중입니다 — SSF SHOP 포맷이 최종 확정되면 같은 형식으로 활성화하면 됩니다.

**SSF SHOP 프로젝트 세부**
- 컬러 `#C4402A`, 히어로는 비메오 영상(`615843658`) 자동재생
- 블록 3개: Brand Film / Portfolio Film / Digital Film — 실제 캠페인 개요·슬로건 텍스트 포함
- 실제 크레딧 전체 목록 포함 (Client, Agency, CD, AD 등)

**프로젝트 데이터 스키마** (한 항목 기준):
```js
{
  id, title, color, textColor, titleLetterSpacing, titleLineHeight,
  titleFontName, titleFontDataUrl,      // 선택: 커스텀 타이틀 폰트
  boxWidthScale, boxHeightScale,        // 선택: 컬러박스 크기 배율 (기본 1)
  meta, hero, heroType, heroVideoId,
  social:{youtube, vimeo, instagram},
  tag, year,
  blocks:[{label, heading, images:[...], paragraphs:[...]}],
  credits:[[label, value], ...] | null
}
```

---

## 2. builder.html — 제작 도구

브라우저에서 `file:///.../builder.html`로 직접 엽니다. 데이터는 IndexedDB(`pf-builder-db`)에 자동 저장됩니다.

**화면 구성**
- 좌측: 프로젝트 목록 (클릭해서 전환, `+ 새 프로젝트`로 생성, 항목 우측 ✕로 삭제)
- 가운데: 편집 패널
  - 상단 버튼 4개 — **GENERATE / SAVE / KR → EN / EN → KR** (아래 3번 참고)
  - 프로젝트명 / 컬러박스 색상·텍스트색 / 카테고리·연도 / 클라이언트·에이전시
  - **타이틀 타이포그래피** (기본 접힘, 클릭해서 펼침): 자간·행간 슬라이더, 타이틀 폰트 첨부(버튼 클릭 또는 미리보기 박스에 파일 드래그&드롭)
  - **컬러 박스 크기**: 가로/세로 슬라이더 (모바일에서는 이 값과 무관하게 자동으로 작아짐)
  - 메인 히어로(이미지/비메오 영상 자동재생 토글)
  - 소셜 링크
  - 블록(사진 세트): 블록/사진 모두 드래그로 순서 변경, 폴더째 불러오기 지원
  - 크레딧: 라벨/값 반복 입력
- 우측: 실시간 미리보기 (PC / Mobile 토글, 실제 사이트와 동일한 CSS 재사용)
  - 코드 내보내기 버튼 → `PROJECTS` 배열에 붙여넣을 수 있는 JS 객체 텍스트 생성 (클립보드 복사 가능)

**디자인 / 테마**
- 좌하단 원형 버튼으로 빌더 자체 UI 컬러 테마를 순환 전환: **화이트(블랙 텍스트) → 블루 → 다크 → 화이트…**
  - 원의 색은 "지금 상태"가 아니라 **클릭하면 바뀔 다음 테마의 색**을 미리 보여줌 (화이트 원 → 누르면 화이트 화면, 블랙 원 → 누르면 다크 화면)
  - 선택한 테마는 `localStorage`에 저장되어 다음에 열어도 유지됨
- 카드형 요소(사이드바 프로젝트 항목, 블록 카드, 사진 목록 행, 폰트 미리보기 박스, 모달)는 **각진 모서리 + 블러 없는 오프셋 그림자**(6px 6px, 블랙)로 통일 — 3개 테마 모두 같은 그림자 로직, 색상만 테마 변수(`--line-strong`, `--card-shadow`)를 따라감

**기타**
- **Ctrl/Cmd+Z** 실행취소, **Shift+Ctrl/Cmd+Z** 다시실행 (텍스트 입력 중엔 브라우저 기본 undo 우선)
- 이미지는 폴더 선택(`webkitdirectory`) 시 실제 파일의 상대경로를 그대로 기억해서, 내보낸 코드가 index.html에서 바로 동작하도록 설계됨

---

## 3. server.py — GENERATE / 번역 버튼용 로컬 서버

API 키 없이, 이미 로그인된 `claude` CLI를 그대로 호출하는 방식입니다.

**실행 방법**
```bash
cd "/Users/cheil/Desktop/jjaejae/Personal/2026 PF"
python3 server.py
```
`http://localhost:8420`에서 대기하며, 이 창을 켜둔 상태에서 builder.html의 GENERATE/KR→EN/EN→KR 버튼을 눌러야 동작합니다. 끌 때는 터미널에서 `Ctrl+C`.
지금 세션에서는 이미 백그라운드로 켜둔 상태입니다 — 컴퓨터를 재시작했거나 서버가 꺼져 있으면 위 명령을 다시 실행하면 됩니다.

**엔드포인트**
- `POST /generate` — 현재 제목/카테고리/메타 정보를 참고해 `claude -p`(haiku 모델, 호출당 $0.50 상한)로 제목·카테고리·클라이언트 라인·본문 문단을 생성. 프로젝트명과 같은 이름의 폴더가 있으면 그 안 이미지도 자동으로 찾아서 함께 반환.
- `POST /translate` — 현재 프로젝트의 제목/카테고리/메타/모든 블록의 헤드라인·본문을 한→영 또는 영→한으로 번역 (크레딧의 인명·브랜드명은 대상에서 제외).
- `GET /scan-images?folder=이름` — 해당 폴더의 이미지 목록(자연정렬)을 반환.

**참고**: 호출마다 소액의 실제 API 비용이 발생합니다(haiku 모델 기준, 1회 호출에 대략 $0.02~0.2 수준, 번역은 내용량에 따라 변동). 이미지가 매우 많은 폴더를 재귀적으로 스캔하므로, 하위 폴더가 여러 개면 예상보다 많은 이미지가 딸려올 수 있습니다 — 필요하면 빌더에서 수동으로 순서를 정리하거나 불필요한 사진을 삭제하면 됩니다.

---

## 알려진 제약 / 참고 사항

- **비메오 임베드**: 로컬 `file://` 환경에서 비메오 영상이 "특정 도메인에서만 embed 허용"으로 설정되어 있으면 재생이 막힐 수 있습니다 → 비메오 프라이버시 설정을 Anywhere로 변경 필요.
- **IndexedDB는 file:// 오리진 전체에서 공유**됩니다. 즉 이 Mac에서 file://로 여는 모든 로컬 HTML이 같은 저장소를 씁니다(builder.html 전용 스토어 이름을 쓰긴 하지만, 다른 폴더에서 연 사본이어도 같은 데이터를 보게 됨) — 테스트용 사본을 함부로 열지 않도록 주의.
- 폰트/이미지 파일은 base64 또는 상대경로로 다뤄지며, 폰트 파일이 크면 내보내기 코드 텍스트도 그만큼 길어집니다.
- GENERATE/번역 버튼은 `server.py`가 켜져 있어야 동작하며, 꺼져 있으면 안내 메시지와 함께 실행 방법을 alert로 알려줍니다.

## 다음에 이어서 할 만한 것

- [ ] 나머지 7개 프로젝트를 SSF SHOP과 같은 포맷으로 builder에서 하나씩 정리 → index.html에 반영
- [ ] Work 리스트 카드 디자인 최종 점검 (현재 SSF SHOP 1개만 있어 레이아웃 검증이 제한적)
- [ ] 필요시 Generate 프롬프트를 실제 클라이언트/캠페인 사실 기반으로 다듬기 (현재는 초안/플레이스홀더 톤 유지하도록 설계됨)
- [ ] builder.html의 3테마 카드 디자인(각진 모서리 + 오프셋 그림자)을 index.html 쪽에도 적용할지 여부 확인
