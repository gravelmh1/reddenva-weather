# Red Denva 날씨 자동 게시

매일 아침 06:00에 캐릭터 날씨 카드를 만들어 Instagram과 Threads에 올려요. 사람도 Claude도 필요 없고, GitHub가 알아서 실행해요.

| | 한국판 | 미국판 |
|---|---|---|
| 지역 | 서울 (°C) | Los Angeles (°F) |
| 게시 시각 | 한국 06:00 | LA 06:00 (서머타임 자동 처리) |
| 계정 | reddenva.kr | reddenva.us |
| 채널 | Instagram + Threads | Instagram + Threads |

- 날씨: Open-Meteo (무료, 키 없음)
- 문구와 포즈: `messages.py`의 규칙으로 생성 (LLM 호출 없음)
- 이미지 주소: 이 저장소의 `out/` 폴더 (Instagram/Threads는 공개 주소가 필요해서 **공개(Public) 저장소**여야 해요)
- 같은 이미지와 캡션을 Instagram, Threads에 그대로 올려요

## 준비 (컴퓨터로 1회, 약 30~60분)

### 1. GitHub 저장소
1. github.com에서 새 저장소를 **Public**으로 만들어요 (예: `redenva-weather`).
2. 이 폴더의 파일을 전부 올려요 (`.github` 폴더 포함).

### 2. Meta 개발자 앱 (Instagram + Threads)
Meta 화면은 자주 바뀌어서, 막히면 화면을 캡처해서 Claude에게 보여주세요.
1. developers.facebook.com 에서 앱을 만들고 **Instagram API (Instagram 로그인)** 와 **Threads API** 사용 사례를 추가해요.
2. 계정 4개(Instagram 한국/미국, Threads 한국/미국)를 테스터로 추가하고 수락해요. 게시 권한은 `instagram_business_content_publish`, `threads_content_publish`예요.
3. 각 계정마다 **장기 액세스 토큰**과 **사용자 ID**를 발급해요 (총 토큰 4개, ID 4개).

### 3. GitHub Secrets 입력
저장소 Settings → Secrets and variables → Actions → New repository secret 에서 아래 8개를 넣어요. **값은 형이 직접 입력하세요.**

`IG_USER_ID_KR`, `IG_TOKEN_KR`, `THREADS_USER_ID_KR`, `THREADS_TOKEN_KR`
`IG_USER_ID_US`, `IG_TOKEN_US`, `THREADS_USER_ID_US`, `THREADS_TOKEN_US`

(선택) `OPEN_METEO_API_KEY` — 아래 "주의" 참고.

### 4. 테스트
1. Actions 탭 → `weather-kr` → Run workflow → **테스트만 하기**가 체크된 채로 실행해요.
2. 실행이 끝나면 Artifacts의 `card-kr`에서 카드 이미지를 받아 확인해요. (게시는 안 돼요)
3. 괜찮으면 Run workflow에서 체크를 **해제**하고 한 번 실행해요. **이때는 진짜로 게시돼요.**
4. 미국판(`weather-us`)도 똑같이 해요.

## 주의
- **토큰 만료:** 장기 토큰은 약 60일이에요. 만료되면 실행이 실패하고 GitHub가 메일로 알려줘요. 그때 토큰을 다시 발급해서 Secret만 바꾸면 돼요. (자동 갱신은 아직 안 넣었어요.)
- **Open-Meteo 이용 조건:** 무료 API는 비상업 용도예요. 이 계정을 사업과 연결해 쓰신다면 Open-Meteo의 상업용 요금제를 확인하고, 키를 `OPEN_METEO_API_KEY`에 넣으면 자동으로 그 서버를 써요.
- **시각:** GitHub 예약 실행은 몇 분 늦게 시작될 수 있어요. 그래서 05:45에 시작해서 카드를 만들어 두고 06:00에 맞춰 게시해요. 아주 많이 늦으면 늦게 올라가요.
- **중복 방지:** 채널별로 오늘 게시했는지 `state/` 폴더에 기록해요. 다시 실행해도 같은 날 두 번 올리지 않아요.
- **저장소 휴면:** GitHub는 활동이 없는 저장소의 예약 실행을 멈출 수 있어요. 이 프로그램이 매일 기록을 커밋하므로 보통은 괜찮지만, Actions 탭에서 가끔 확인하세요.
- **아직 못 해본 것:** 실제 Meta 토큰으로 게시하는 부분은 형 계정이 있어야 해서 테스트하지 못했어요. 첫 실제 게시는 꼭 지켜봐 주세요.

## 로컬에서 미리보기
```
pip install -r requirements.txt
python run.py --region kr --mock rain --dry-run     # 가짜 예보로 카드만 만들기
```
시나리오: `kr_mild`, `rain`, `cold`, `us_warm`, `hot`
