# CLAUDE.md

이 파일은 Claude Code(및 다른 세션)가 이 repo를 열었을 때 바로 맥락을 잡도록
작성된 안내서입니다. 상세 셋업/배경은 `README.md` 참고.

## 이 프로젝트가 뭔가

Discord 서버 관리 봇. 슬래시 명령어로 **채널 생성 · 역할 기반 별명 일괄 변경**
같은 배치성 관리 작업을 수행한다. **AWS Lambda(서버리스) + HTTP Interactions**
방식이라 상시 서버가 없고, 명령이 올 때만 실행된다. 대상 서버 규모 20~30명.

## 아키텍처: Lambda 2개 (반드시 이해할 것)

Discord는 슬래시 명령에 **3초 안의 응답**을 요구한다. 배치 작업(30명 별명 변경
등)은 이를 넘길 수 있으므로 함수를 둘로 나눴다.

```
Discord ─▶ API Gateway ─▶ Front Lambda (app.py, themoment-bot-front)
                              │  서명검증 → 3초 안에 "생각 중..." 응답만
                              └─▶ Worker Lambda (worker.py, themoment-bot-worker)
                                     실제 배치 작업 → followup 웹훅으로 "완료!" 전송
```

- **Front (`src/app.py`)** = 입구. Ed25519 서명 검증, PING→PONG, deferred 응답.
  실제 작업은 절대 여기서 하지 않는다(3초 제약). Worker를 비동기 invoke만 한다.
- **Worker (`src/worker.py`)** = 일꾼. 시간 제약 없이 채널 생성/별명 변경 수행.
- 둘의 연결은 `template.yaml`의 `!Ref WorkerFunction` → 환경변수
  `WORKER_FUNCTION_NAME`로 자동 주입. 이름을 바꿔도 코드 수정 불필요.

## ⚠️ 빌드 함정: Python 3.13 PATH

`template.yaml` 런타임이 `python3.13`이다. 로컬 파이썬이 다른 버전이면
`sam build`가 인터프리터를 못 찾아 실패한다. **build/deploy 전에 항상**:

```bash
export PATH="/opt/homebrew/opt/python@3.13/bin:$PATH"
```

(미설치 시 `brew install python@3.13`. Docker가 있으면 `sam build --use-container`로 우회 가능.)

## 배포 방법 (일상)

프로젝트 루트에서. `deploy.env`(gitignore됨)에 비밀값이 들어있다.

### 코드(`src/*.py`)만 수정했을 때 — 제일 흔함
```bash
export PATH="/opt/homebrew/opt/python@3.13/bin:$PATH"
sam build && sam deploy
```
2회차부터 `sam deploy`는 스택 이름·리전·파라미터를 기억한다. 파라미터를 안
바꾸면 옵션 없이 이대로 된다.

### 파라미터(토큰 등)를 바꿨을 때
```bash
export PATH="/opt/homebrew/opt/python@3.13/bin:$PATH"
source deploy.env && sam build && sam deploy \
  --stack-name themoment-manage-bot --region ap-northeast-2 \
  --resolve-s3 --capabilities CAPABILITY_IAM --no-confirm-changeset \
  --parameter-overrides \
    DiscordPublicKey=$DISCORD_PUBLIC_KEY \
    DiscordApplicationId=$DISCORD_APPLICATION_ID \
    DiscordBotToken=$DISCORD_BOT_TOKEN
```

### 슬래시 명령어 "정의"(이름/옵션)를 바꿨을 때 — 배포와 별개!
`scripts/register_commands.py`의 `COMMANDS`를 수정했다면 배포 후 등록도 다시:
```bash
source deploy.env && unset DISCORD_GUILD_ID && \
  .venv/bin/python scripts/register_commands.py    # 전역 등록(반영 최대 1시간)
```
코드 로직만 바꾸고 명령어 정의는 그대로면 이 단계는 불필요.

## 명령어 추가하는 법 (3단계)

1. `scripts/register_commands.py`의 `COMMANDS`에 정의 추가 → 등록 스크립트 재실행
2. `src/worker.py`의 `_handle_command()`에 `elif name == "..."` 분기 추가
3. `sam build && sam deploy`

## 배포 환경 (사실들)

- AWS 리전: `ap-northeast-2` (서울)
- CloudFormation 스택: `themoment-manage-bot`
- Lambda 함수: `themoment-bot-front`, `themoment-bot-worker` (template에서 고정)
- Discord Interactions Endpoint URL은 API Gateway 주소라 **재배포해도 안 바뀐다**
  → Discord 쪽 재등록 불필요.

## 🔴 하지 말 것

- **비밀값 커밋 금지.** `deploy.env`(실제 토큰)는 `.gitignore`로 제외됨.
  커밋 전 `git status`로 `deploy.env`가 스테이징에 없는지 확인.
- Bot Token을 로그·PR·채팅에 노출하지 말 것. 노출 시 서버 장악 위험.
- **AWS 콘솔에서 Lambda/리소스를 직접 수정하지 말 것**(드리프트). 모든 변경은
  `template.yaml` 수정 후 `sam deploy`로.

## 디버깅

명령이 "앱이 응답하지 않았습니다"로 실패하면 CloudWatch 로그 확인:
```bash
sam logs --stack-name themoment-manage-bot --region ap-northeast-2 -n InteractionFunction
sam logs --stack-name themoment-manage-bot --region ap-northeast-2 -n WorkerFunction
```
흔한 원인: 서명 검증 실패(Public Key 불일치), 봇 권한/역할 순서 부족,
SERVER MEMBERS INTENT 미설정(별명 명령), 봇 역할이 대상보다 아래에 있음.
