# themoment-manage-bot

Discord 서버 관리 봇. 슬래시 명령어로 채널 생성 · 역할 기반 별명 일괄 변경 같은
배치성 관리 작업을 수행합니다. **AWS Lambda(서버리스) + HTTP Interactions** 구조라
상시 서버가 필요 없고, 명령이 올 때만 실행되어 비용이 거의 들지 않습니다.

## 아키텍처

```
Discord ──HTTP POST──▶ API Gateway ──▶ Front Lambda (app.py)
                                          │ 1. 서명 검증
                                          │ 2. PING→PONG
                                          │ 3. 명령이면:
                                          │    - Worker를 비동기 invoke
                                          │    - 즉시 deferred 응답 (3초 규칙 준수)
                                          ▼
                                       Worker Lambda (worker.py)
                                          │ 실제 배치 작업 (채널 생성, 별명 변경)
                                          ▼
                                       Discord REST API + followup 웹훅
```

### 왜 Lambda가 두 개인가? (3초 규칙)

Discord는 슬래시 명령에 **3초 안의 응답**을 요구합니다. 30명 별명 변경 같은
배치 작업은 이를 넘길 수 있습니다. 그래서:

- **Front Lambda**는 실제 작업을 하지 않고, Worker에게 넘긴 뒤 즉시 "생각 중..."
  (deferred) 응답만 반환합니다. → 항상 3초 안에 끝남.
- **Worker Lambda**는 시간 제약 없이 작업하고, 끝나면 followup 웹훅으로 결과를 보냅니다.

---

## 셋업 가이드 (처음부터)

### 1. Discord 앱 만들기

1. https://discord.com/developers/applications → **New Application**
2. 좌측 **Bot** → 봇 추가 → **Reset Token**으로 토큰 확보 (`DISCORD_BOT_TOKEN`)
3. **Bot** 화면에서 **Privileged Gateway Intents → SERVER MEMBERS INTENT** 켜기
   (별명 일괄 변경 시 멤버 목록 조회에 필요)
4. 좌측 **General Information** → **Public Key**(`DISCORD_PUBLIC_KEY`),
   **Application ID**(`DISCORD_APPLICATION_ID`) 확보
5. 좌측 **OAuth2 → URL Generator**:
   - scopes: `bot`, `applications.commands`
   - Bot Permissions: `Manage Channels`, `Manage Nicknames`, `Manage Roles`
   - 생성된 URL로 봇을 내 서버에 초대

### 2. 필요한 도구 설치 (배포용)

```bash
brew install aws-sam-cli awscli
aws configure          # AWS 액세스 키 입력
```

### 3. 배포

```bash
sam build
sam deploy --guided \
  --parameter-overrides \
    DiscordPublicKey=<PUBLIC_KEY> \
    DiscordApplicationId=<APP_ID> \
    DiscordBotToken=<BOT_TOKEN>
```

배포가 끝나면 출력에 **InteractionsEndpoint** URL이 나옵니다.

### 4. Interactions Endpoint URL 등록

Discord Developer Portal → **General Information** →
**Interactions Endpoint URL**에 위 URL을 붙여넣고 저장.
(저장 시 Discord가 PING을 보내 서명 검증을 확인합니다 — Front Lambda가
통과시켜야 저장됩니다.)

### 5. 슬래시 명령어 등록

```bash
export DISCORD_APPLICATION_ID=<APP_ID>
export DISCORD_BOT_TOKEN=<BOT_TOKEN>
export DISCORD_GUILD_ID=<내 서버 ID>   # 테스트: 즉시 반영됨
python scripts/register_commands.py
```

### 6. 테스트

Discord 서버에서 `/create-channel name:테스트` 실행 → 채널이 생기고
"✅ 채널 생성 완료!" 메시지가 뜨면 성공.

---

## 명령어 추가하는 법

1. `scripts/register_commands.py`의 `COMMANDS`에 정의 추가 → 스크립트 재실행
2. `src/worker.py`의 `_handle_command()`에 `elif name == "..."` 분기 추가
3. `sam build && sam deploy` (아래 참고)

## 코드 수정 후 재배포 (일상 배포)

프로젝트 루트에서. 대부분은 아래 두 줄이면 끝난다.

```bash
export PATH="/opt/homebrew/opt/python@3.13/bin:$PATH"   # 새 터미널마다 (아래 참고)
sam build && sam deploy
```

2회차 배포부터 `sam deploy`는 스택 이름·리전·파라미터를 기억하므로 옵션을
붙일 필요가 없다. 단, **파라미터(토큰 등)를 바꾸지 않았을 때만** 그렇다.

| 무엇을 수정했나 | 필요한 작업 |
|---|---|
| `src/*.py` 코드 로직 | `sam build && sam deploy` |
| 슬래시 명령어 **정의**(이름/옵션) | 위 + `register_commands.py` 재실행 (아래) |
| 토큰 등 파라미터 | `source deploy.env` 후 `--parameter-overrides` 붙여 배포 |

명령어 정의를 바꿨을 때만 등록 스크립트를 다시 돌린다:
```bash
source deploy.env && unset DISCORD_GUILD_ID && \
  .venv/bin/python scripts/register_commands.py
```

## 배포 팁 (실전 메모)

### `sam build` 시 Python 3.13 PATH

`template.yaml`의 런타임은 `python3.13`입니다. 로컬 파이썬이 3.14 등 다른
버전이면 SAM이 3.13 인터프리터를 못 찾아 빌드가 실패합니다. 3.13을 설치하고
빌드 전에 PATH 앞에 추가하세요:

```bash
brew install python@3.13
export PATH="/opt/homebrew/opt/python@3.13/bin:$PATH"
sam build
```

(대안: Docker가 있으면 `sam build --use-container`로 로컬 파이썬 버전과
무관하게 빌드 가능)

### 비밀값 없이 배포 (deploy.env)

Bot Token을 명령줄에 직접 치지 않도록, `deploy.env.example`을 복사해 값을
채우고 `source`로 불러 배포합니다. `deploy.env`는 `.gitignore`로 커밋에서
제외됩니다.

```bash
cp deploy.env.example deploy.env   # 열어서 DISCORD_BOT_TOKEN 채우기
source deploy.env
sam deploy \
  --stack-name themoment-manage-bot \
  --region ap-northeast-2 \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --parameter-overrides \
    DiscordPublicKey=$DISCORD_PUBLIC_KEY \
    DiscordApplicationId=$DISCORD_APPLICATION_ID \
    DiscordBotToken=$DISCORD_BOT_TOKEN
```

### 슬래시 명령어 전역 등록

`DISCORD_GUILD_ID`를 비우면 전역 등록됩니다(반영에 최대 1시간). 특정 서버
ID를 주면 즉시 반영되어 테스트에 좋습니다.

## 비용

20~30명 서버 기준, 명령 실행이 하루 수십~수백 번이라도 Lambda/API Gateway
**프리 티어 안**에 들어갑니다. 사실상 무료.
