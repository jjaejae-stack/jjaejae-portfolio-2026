# 2026 포트폴리오 — 진행 상황

최종 업데이트: 2026-07-26

## 최근 변경 — builder.html 편의 기능 모음 (2026-07-26)

- **프로젝트 순서 변경**: 사이드바 프로젝트 항목에 드래그 핸들(`⠿`) 추가 — 블록/사진과 같은 방식으로 드래그해서 순서 변경. `project.order` 필드로 저장되며, 기존 프로젝트는 최초 로드 시 자동으로 order가 채워짐(마이그레이션). 단, 이건 빌더 안에서의 표시 순서만 바꾸는 것 — Publish는 여전히 프로젝트 단위로만 index.html을 갱신하므로, 순서를 실제 사이트에 반영하려면 별도 작업이 필요함(아직 안 만듦).
- **카테고리 탭 UI**: "카테고리"(=`project.tag`, 예: Campaign/Digital Campaign) 필드가 텍스트 입력창 대신 **알약 버튼 탭**으로 바뀜. 기존에 쓰인 카테고리가 자동으로 버튼화되고, "+ 새 카테고리"로 새 값 추가 가능(값은 `localStorage`의 `pf-builder-custom-tags`에 저장). 각 알약 우상단에 ✕ 버튼으로 삭제 가능 — 삭제하면 그 카테고리를 쓰던 다른 프로젝트들의 카테고리도 함께 비워짐(확인창 있음).
- **타이포그래피 섹션 자동 닫힘 버그 수정**: 폰트 파일을 첨부하면 `renderEditor()`가 전체를 다시 그리면서 접힘 상태가 매번 기본값(닫힘)으로 리셋되던 문제 — 열림/닫힘 상태를 `openSections`(Set)로 별도 추적하도록 고침.
- **크레딧 이미지 → 데이터 반영**: Galaxy Tab S9 프로젝트의 실제 크레딧 슬라이드 이미지를 읽어서 크레딧 22개 항목을 builder에 입력함.
- (참고) 블록을 자유롭게 추가하는 기능은 이미 있었음 — 편집 패널 "블록 (사진 세트)" 섹션 제목 옆 **"+ 블록 추가"** 버튼.

## 최근 변경 — 프로젝트 상세뷰 첫 화면에서 브랜드 로고/Email/IG 숨김 (2026-07-26)

프로젝트 상세뷰를 열면 첫 화면(`.p-main`)에 이미 자체 좌상단 컬러박스(제목)와 우하단 소셜 아이콘 박스가 있어서, 같은 위치에 뜨는 사이트 공용 `.brand-logo`(좌상단)·`#frame-email`(좌하단)·`#frame-ig`(우하단)이 겹쳐 보이던 걸 정리함.
- 프로젝트를 열면 이 3개는 완전히 숨김(`opacity:0`), 헤더 nav(우상단)와 `#frame-day`/`#frame-clock`(좌우 중단)은 기존처럼 40%로 그대로 보임.
- `#project-view`(`viewRoot`) 스크롤 이벤트로 스크롤량이 `.p-main` 높이의 **2/3를 넘으면** `body.project-past-hero` 클래스를 붙여서, 그 3개도 다시 기존 40%-옅게(호버 시 100%) 규칙으로 복귀. 프로젝트를 새로 열 때마다 이 클래스는 리셋됨.

## 최근 변경 — Work/Play 리스트 썸네일을 가로 비율로 (2026-07-26)

`.work-card .thumb`(Work/Play 공용, `#work-grid`/`#play-grid`의 카드)의 `aspect-ratio`를 세로형 `4/5`에서 **가로형 `16/10`**으로 변경. 2열 그리드 레이아웃은 그대로 유지.

## 버그 수정 — Galaxy Tab S9 이미지 로드 안 되던 문제 (2026-07-26)

원인: 크레딧 이미지 동기화 작업 때 개별 파일을 직접 업로드해서 넣은 이미지 10개(히어로 1개 + 블록 이미지 9개)의 `relPath`가 `"Galaxy Tab S9/"` 폴더 접두사 없이 파일명만 저장됨 (builder의 파일 업로드 핸들러는 `webkitRelativePath`가 없으면 `file.name`만 씀 — 폴더 스캔으로 넣은 이미지와 달리 접두사가 안 붙음). 그 결과 `index.html`에도 접두사 없는 잘못된 경로로 퍼블리시되어 브라우저가 사이트 루트에서 파일을 찾다가 실패.
- `index.html`의 galaxy-tab-s9 항목 이미지 경로 10곳에 `Galaxy Tab S9/` 접두사 직접 추가.
- builder의 IndexedDB(`pf-builder-db`)에 저장된 같은 프로젝트의 `relPath` 10곳도 동일하게 수정 — 그래야 다음에 Publish 눌러도 다시 깨지지 않음.
- 이후 Publish 흐름에서 다시 발생 가능: 개별 파일 업로드로 이미지를 추가할 땐 항상 폴더 접두사가 붙는지 확인 필요.

## 최근 변경 — Info 배경 사진, 톤 보정 없이 원본 그대로 (2026-07-26)

바로 아래 항목("Info 배경을 실제 사진으로 교체 + 톤 보정")에서 했던 하늘 톤 보정(밝기/채도/대비 낮추고 헤이즈 블렌드)을 되돌림 — 사용자가 원본 그대로의 진한 파란 하늘 그라데이션을 더 마음에 들어해서, `info-bg.jpg`를 **원본 `Untitled-1.jpg`을 색 보정 없이 그대로**(품질 90 JPG로만 재인코딩) 다시 저장함. 마스킹/블렌드 코드는 더 이상 쓰지 않지만 필요하면 이전 대화 기록에 남아있음. 그레인 오버레이(`.info-grain`, opacity .09)는 그대로 유지.

## 최근 변경 — Info 배경을 실제 사진(계란 빨래줄)으로 교체 + 톤 보정 (2026-07-26)

Info 오버레이 배경을 CSS 그라데이션 하늘에서 **사용자가 준 실제 사진**(`none/Ref/Untitled-1.jpg`, 빨랫줄에 걸린 계란후라이 사진)으로 교체.
- 원본은 색이 꽤 진하고 채도 높은 파란 하늘이라, 레퍼런스(`none/Ref/info.png`, Cecilia Pignocchi 톤)의 더 뿌옇고 채도 낮은 하늘색에 맞춰 **Pillow로 톤 보정**: 밝기 ×1.35, 채도 ×0.58, 대비 ×0.92, 옅은 회청색(`#d2d8d8`)과 14% 블렌드로 헤이즈 효과. 보정 전/후 하늘 색 샘플이 레퍼런스와 거의 일치하도록 값을 맞춤(둘 다 대략 RGB 135~140/173~176/193~197).
- **계란 색은 그대로 유지**: 처음엔 이미지 전체에 톤 보정을 걸어서 계란도 같이 washed-out 되는 문제가 있었음 → numpy로 "파란기(B - max(R,G))" 기반 마스크를 만들어(가장자리는 GaussianBlur로 페더링) **하늘(파란 픽셀)에만** 보정을 블렌드하고, 계란·나무 집게·빨랫줄(주황/노랑/미색 계열, blueness 낮음)은 원본 픽셀 그대로 통과시킴. 계란 중심 샘플 색이 보정 전/후 완전히 동일함을 확인함.
- 결과물은 `/Users/cheil/Desktop/jjaejae/Personal/2026 PF/info-bg.jpg`(루트, 110KB)로 저장 — **원본이 있던 `none/Ref/`는 `.vercelignore`에 걸려 배포에서 빠지므로, 반드시 이 파일처럼 루트에 저장해야 라이브 사이트에서 보임** (지난번 로고 PNG와 동일한 이유).
- `.info-bg`는 이제 이 JPG를 `background-image`로 사용(`background-size:cover; background-position:center 35%`), 기존 CSS 그라데이션 정의는 제거. 노이즈 레이어(`.info-grain`, SVG feTurbulence)는 그대로 유지하되 레퍼런스 사진의 그레인이 더 잘 보이는 편이라 opacity를 `.06 → .09`로 살짝 올림.

## 최근 변경 — 마퀴 줄 순서 변경 + 블랙 팔레트를 레퍼런스 색상으로 교체 (2026-07-26)

- **줄 순서**: 일본어 → 영어 → 한국어(가운데, 3번째 그대로 유지) → 프랑스어 → 스페인어로 재배치. `GREETINGS`와 `PALETTES`(5개 전부)의 배열 순서를 동일하게 다시 맞춤.
- **블랙 모노톤 팔레트 교체**: 사용자가 준 `mono-workshop-black-gray-color-palette.avif` 레퍼런스에서 실제 5색을 추출(`sips`로 PNG 변환 후 확인) — `#0A0B0D → #1C1F24 → #3A3F47 → #7F8792 → #E5E8ED`. 기존 흑백 교차 대신 **위(일본어)에서 아래(스페인어)로 어둡게→밝게 이어지는 그라데이션**으로 배치, 각 줄 글자색은 대비가 더 좋은 쪽(어두운 3줄은 밝은 글자, 밝은 2줄은 어두운 글자)으로 지정.

## 최근 변경 — 마퀴 클릭 시 컬러 팔레트 순환 (2026-07-26)

메인 마퀴(`#intro`) 클릭의 동작을 "Work로 스크롤"에서 **"5줄 색 팔레트 순환"**으로 바꿈(스크롤은 그대로 자연스럽게 Work로 이어지므로 기능이 사라지는 건 아님).
- 색은 더 이상 `GREETINGS` 배열에 하드코딩하지 않고, 새 `PALETTES` 배열(5개 팔레트, 각각 영어/스페인어/한국어/프랑스어/일본어 순서의 `{bg,fg}` 5쌍)에서 가져옴. `applyPalette(index)`가 `.lang-row` 5개의 인라인 배경/글자색을 갈아끼움.
- **팔레트 0 = 기존 컬러 조합 그대로**(요청대로 유지), **팔레트 1 = 블랙 모노톤**(검정/흰색 교차), 나머지 2~4는 선셋·쿨파스텔·어스톤 배리에이션. 마퀴를 클릭할 때마다 `paletteIndex`가 1씩 순환(0→1→2→3→4→0…), 새로고침하면 다시 팔레트 0으로 시작(저장 안 함 — 필요하면 나중에 localStorage로 유지시킬 수 있음).

## 최근 변경 — Work/Play 데이터 연동 (builder.html) (2026-07-26)

위 "Play" 탭/섹션 항목에서 남겨뒀던 TODO("PLAY_PROJECTS 데이터 배열/builder 편집 패널은 아직 없음")를 처리했습니다.

- **데이터 모델**: 프로젝트에 `category` 필드 추가(`"work"` | `"play"`, 기본값 `"work"`) — `newProject()`, `buildSSFSampleProject()`, `exportProjectCode()` 모두 반영. 기존에 저장된 프로젝트처럼 `category` 필드가 아예 없는 경우도 전부 "work"로 취급(하위호환, 마이그레이션 불필요).
- **index.html**: `PROJECTS`를 `category`로 나눠 `#work-grid`/`#play-grid`에 각각 렌더링. Play 프로젝트가 하나도 없으면 기존 "Coming soon" 문구 그대로 유지.
- **builder.html**: 좌측 사이드바 맨 위에 **Work / Play 탭 버튼**을 추가 — 클릭하면 그 섹션에 속한 프로젝트만 목록에 표시. "+ 새 프로젝트"는 현재 활성 탭의 섹션으로 생성됨. 편집 패널에도 프로젝트명 바로 아래 **"섹션 (Work / Play)"** 토글을 추가해서 기존 프로젝트도 언제든 섹션을 바꿀 수 있음(바꾸면 사이드바 목록에서 즉시 다른 탭으로 이동).
- Publish를 누르면 `category` 필드도 그대로 index.html에 반영되므로, Play 프로젝트를 채우고 Publish하면 실제 사이트의 `#play-grid`에 나타남.

## 최근 변경 — "Play" 탭/섹션 추가 (2026-07-26)

헤더 nav에 Work 옆 **"Play"** 탭을 추가(순서: Work → Play → Info). Work 섹션 바로 아래에 `#play` 섹션을 새로 만들고(`#play-grid`), Work와 동일한 2열 그리드/카드 CSS를 공유하도록 셀렉터를 `#work-grid, #play-grid` 등으로 일반화함. 지금은 `#play-grid` 안에 "Coming soon" 플레이스홀더 문구만 있음 — **실제 개인 작업물 콘텐츠는 사용자가 빌더에서 채울 예정** (아직 `PLAY_PROJECTS` 같은 데이터 배열이나 builder.html 쪽 편집 패널은 만들지 않음, 프론트엔드 라우팅/레이아웃만 준비된 상태). 다음에 이어서 할 일 목록에 추가해둠.

## 최근 변경 — Info 카피 다듬기 + 스크롤 버그 수정 + 브랜드 로고 이미지화 (2026-07-26)

- **Info 카피**: 첫 인사 문장에서 "AKA. jjaejae" 삭제(그냥 "아트디렉터 최재훈입니다."). 두 태그라인("A RAW NAME FOR SHARP IDEAS", "LOOK AGAIN")을 큰 헤드라인 크기에서 **본문과 같은 크기 + 볼드**로 축소(`.info-tagline` 폰트 크기를 `.info-body`와 동일하게). "LOOK AGAIN"의 대괄호 `[ ]` 제거.
- **Info 오버레이 스크롤 버그**: 내용이 길어 스크롤할 때 macOS/iOS의 elastic bounce로 뒤에 있는 Work 리스트(SSF SHOP 카드 등)가 살짝 비쳐 보이던 문제 수정. `#info-view` 자체는 이제 `overflow:hidden`(절대 스크롤 안 됨, 배경이 항상 뷰포트 전체를 덮음)이고, 그 안에 새로 넣은 `.info-scroll` 래�퍼만 `overflow-y:auto; overscroll-behavior:contain`로 스크롤을 전담 + 바깥으로 스크롤 체이닝 안 되게 막음. JS `openInfo()`/`closeInfo()`에서도 `document.documentElement.style.overflow`를 직접 토글해 이중 안전장치를 둠.
- **브랜드 로고 이미지화**: 좌상단 "jjaejae" 텍스트를 사용자가 준 실제 로고(`jjaejae.jpg`, 검정 배경+흰색 워드마크)에서 **배경 투명 + 워드마크 블랙**으로 가공한 PNG로 교체. 가공은 Pillow로 luminance 값을 알파 채널로 변환해서 만듦(`/Users/cheil/Desktop/jjaejae/Personal/2026 PF/jjaejae-wordmark-black.png`, 691×387, 원본 대비 여백 크롭됨). 헤더(`#site-header`)는 `mix-blend-mode:difference`라서 검정 이미지를 넣으면 안 보이게 되므로, **브랜드 로고는 `#site-header` 밖으로 빼서 별도의 `.brand-logo` 요소**(블렌드 모드 없음, 항상 순수 검정)로 만듦 — 표시/숨김 규칙(메인 마퀴에서 숨김 → past-hero 시 100%, project/info 오버레이에서 40%)은 헤더·코너 프레임과 동일하게 공유.

## 최근 변경 — Info 오버레이 카피 교체 (2026-07-26)

Info 오버레이 본문을 "jjaejae" 이름 유래·매니페스토 톤의 실제 카피로 교체함. 구조를 3단계 클래스로 나눔:
- `.info-lead` — 첫 인사 문장(700, 중간 크기)
- `.info-body` — 일반 본문 문단(500, 작은 크기, 여러 개)
- `.info-tagline` — "A RAW NAME FOR SHARP IDEAS", "[ LOOK AGAIN ]" 같은 굵은 독립 헤드라인(800, 큰 크기)
기존에 있던 `.bio`/`.hl`(밑줄 강조 span) 클래스는 이 구조로 대체되어 제거됨. 이후 카피를 더 수정하고 싶으면 `#info-view` 안의 `.info-content` 블록(HTML)만 편집하면 됨 — 새 문단/태그라인을 추가할 때는 `.info-body`/`.info-tagline` 클래스를 그대로 재사용.

## 최근 변경 — 디테일 페이지에서 코너 프레임 40% 옅게 (2026-07-26)

Work 리스트(마퀴만 지난 상태, `body.past-hero`)에서는 헤더/코너 프레임이 기존처럼 100% 또렷하게 보이지만, **프로젝트 상세뷰(`body.project-open`)나 Info 오버레이(`body.info-open`)에 들어가면 opacity 0.4로 옅어지도록** 분리함. 마우스를 올리면(`:hover`) 다시 opacity 1로 또렷해짐. `mix-blend-mode:difference`는 그대로 유지해서 어떤 배경색 위에서도 읽히긴 하되, 배경 위에 자연스럽게 얹히는 느낌을 줌.

## 최근 변경 — 코너 프레임(요일/시계/Email/IG) 추가 (2026-07-26)

레퍼런스(Cargo 템플릿)처럼 화면 네 모서리·중간 사이드에 작은 UI 텍스트를 띄우는 "프레임" 요소를 추가했습니다.
- 위치: 좌측 중단 `#frame-day`(요일, 예: "Saturday"), 우측 중단 `#frame-clock`(HH:MM:SS 실시간 시계), 좌하단 `#frame-email`(mailto 링크), 우하단 `#frame-ig`(Instagram 링크). 모두 `.frame-item` 클래스 공유, `mix-blend-mode:difference`로 헤더와 동일한 방식.
- **표시 규칙은 기존 헤더와 동일**: 메인 마퀴 화면에서는 안 보이고, `body.past-hero`(스크롤로 마퀴를 벗어남) / `body.project-open`(프로젝트 상세뷰) / `body.info-open`(Info 오버레이) 중 하나라도 켜지면 페이드인. 즉 "메인 롤링 화면에는 없고, 스크롤하거나 다른 페이지에 들어갔을 때 항상 떠있게" 요구사항 그대로.
- 요일/시계는 JS `setInterval(tickFrameClock, 1000)`으로 매초 갱신. 모바일(≤600px)에서는 요일/시계를 숨겨 좁은 화면에서 겹치지 않게 함(Email/IG는 유지).

## 최근 변경 — Info를 풀스크린 오버레이로 부활 (2026-07-26)

앞서 삭제했던 소개글을 **헤더 nav의 "Info" 버튼 클릭 시 열리는 풀스크린 오버레이**(`#info-view`)로 다시 추가했습니다 (스크롤로 도달하는 섹션이 아님).
- 배경은 실제 사진 대신 **CSS만으로 만든 하늘색 그라데이션 + SVG feTurbulence 노이즈 오버레이**(`.info-bg` + `.info-grain`, opacity .06, mix-blend-mode:overlay)로 레퍼런스의 "약간 노이즈 있는 하늘 사진" 느낌을 재현. 실제 이미지 파일은 쓰지 않음 — 나중에 진짜 사진으로 교체하고 싶으면 `.info-bg`의 `background`를 이미지로 바꾸면 됨.
- 내용은 큰 좌측 정렬 본문 텍스트(`Hey! 안녕하세요...`) + 일부 단어 이탤릭+밑줄 강조(`.hl`, 삼성/나이키/SSF SHOP) + Instagram/Email 링크. 이름(jjaejae)과 "Work/Info" 텍스트는 오버레이 안에 따로 안 넣고 **항상 떠 있는 헤더를 그대로 재사용**(레퍼런스처럼 좌상단 이름·우상단 nav 구조).
- `openInfo()`/`closeInfo()` 함수 추가, `data-go="info"` 클릭 시 스크롤 대신 오버레이를 열도록 라우팅 분기. Esc 키·다른 nav 클릭(Work/브랜드)으로 닫힘. `z-index:450`(헤더 500보다 낮음, project-view 400보다 높음)이라 오버레이가 열려 있어도 헤더는 계속 보이고 클릭 가능.
- 헤더 자체의 "메인 화면에서 숨김 → 스크롤 지나면 표시" 로직(`past-hero`)은 그대로 유지됨 — Info 버튼도 스크롤을 지나야 보임.

## 최근 변경 — Info 섹션 제거 + 헤더 스크롤 연동 (2026-07-26)

- 이름/소개/링크가 있던 `#info` 섹션을 **완전히 삭제**. 이제 구조는 `#intro`(마퀴) → 스크롤 → `#work`(Work 리스트)로 단순화됨.
- `#intro`(마퀴 화면)를 클릭하면 `#work`로 스무스 스크롤(`introEl.addEventListener("click", ...)`). 자연스러운 스크롤로도 바로 Work가 이어짐(사이에 있던 info가 없어졌으므로).
- 헤더(`#site-header`)는 이제 **메인(마퀴) 화면에서는 완전히 숨김**(`opacity:0`)이고, `IntersectionObserver`로 `#intro`가 뷰포트에서 벗어나면 `body.past-hero` 클래스를 붙여 페이드인. 프로젝트 상세뷰가 열려있을 때(`body.project-open`)도 항상 보이게 처리.
- 헤더 텍스트를 볼드(brand 800, nav 700)로, "Info" 탭은 섹션 삭제와 함께 제거(현재 nav는 "Work"만 남음). 브랜드 텍스트 "Jaehoon Choi" → **"jjaejae"**로 변경(헤더, `<title>`, 푸터 저작권 표기 모두). 단, SSF SHOP 크레딧의 실명 "Jaehoon Choi (@jjaejae__)"는 실제 크레딧 정보라 그대로 둠.

## 최근 변경 — 마퀴 튜닝 + 프로젝트 메인 박스 디자인 (2026-07-26)

- **마퀴**: 폰트 크기를 `vw` 대신 `svh` 기준(`clamp(2.6rem, 16svh, 9rem)`, `line-height:1`)으로 바꿔 각 줄(row) 높이를 거의 꽉 채우도록 키움. 5줄 속도(duration)도 전체적으로 더 느리게 상향(예: 한국어 64→84, 영어 76→100 등).
- **줄 순서/컬러**: 한국어가 5줄 중 정확히 가운데(3번째)에 오도록 배열 순서를 `영어 → 스페인어 → 한국어 → 프랑스어 → 일본어`로 재배치. 스페인어는 레드(`#c62828`), 프랑스어는 블루(`#3f6fd1`)로 변경, 일본어는 기존 연두색(`#e3e07a`)을 넘겨받음(5색 팔레트 재사용, 새 색상 추가 없음). 방향 교차(`reverse`)는 이제 언어별 수동 플래그가 아니라 **줄 인덱스 홀/짝으로 자동 계산**하도록 `renderGreetings()` 로직을 정리함.
- **프로젝트 메인 박스**(`.p-colorbox`, `.p-social`): 기존 라운드 코너(`border-radius:var(--pradius)`)를 없애고, 사용자가 준 레퍼런스(Cargo 스타일 카드) 그대로 **각진 모서리 + 3px 블랙 보더 + 블러 없는 오프셋 그림자**(`box-shadow:10px 10px 0 #111` / 소셜박스는 `8px 8px 0`, 모바일은 2px 보더·6px 그림자)로 교체. 배경색 자체는 그대로 `project.color`를 써서 빌더에서 커스터마이징 가능. `--pradius` CSS 변수는 더 이상 쓰이지 않아 제거함.
- **builder.html도 동일하게 수정**: 미리보기 CSS(`.p-main`/`.p-colorbox`/`.p-social`, 1223~1235번째 줄 근처)에 같은 각진+오프셋그림자 스타일을 반영해 실제 사이트와 미리보기가 어긋나지 않게 함.

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
- [x] ~~"Play"(개인 작업물) 섹션 데이터 연동~~ — `category` 플래그를 기존 `PROJECTS`에 추가하는 방식으로 완료 (2026-07-26, 위 "Work/Play 데이터 연동" 항목 참고). 이제 builder에서 Play 탭으로 프로젝트를 만들고 채운 뒤 Publish하면 됨.
- [ ] "Play" 섹션에 실제 콘텐츠 채우기 (아직 프로젝트 0개 — Coming soon 문구만 있음)
