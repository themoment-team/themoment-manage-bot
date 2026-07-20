"""Lambda 진입점 (Front) — Discord Interaction 수신 및 즉시 응답.

이 함수의 유일한 임무는 "3초 안에 Discord에 응답"하는 것입니다.
  1. Discord 서명 검증 (실패 시 401)
  2. PING(type 1)이면 즉시 PONG 응답 (엔드포인트 등록 검증용)
  3. 슬래시 명령(type 2)이면:
       - Worker Lambda를 비동기(Event)로 invoke 해서 실제 배치 작업을 넘기고
       - 즉시 deferred("생각 중...") 응답을 반환

배치 작업(채널 여러 개 생성, 30명 별명 변경 등)은 3초를 넘길 수 있으므로
절대 이 함수 안에서 실행하지 않습니다. → worker.py가 담당.

주의: API Gateway "Lambda 프록시 통합"을 전제로 합니다.
"""

import json
import os

import boto3

import verify

PUBLIC_KEY = os.environ.get("DISCORD_PUBLIC_KEY", "")
WORKER_FUNCTION_NAME = os.environ.get("WORKER_FUNCTION_NAME", "")

PING = 1
APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3  # 버튼 클릭 등

PONG = 1
DEFERRED_CHANNEL_MESSAGE = 5  # "생각 중..." 후 followup으로 채우는 응답
EPHEMERAL = 64  # 응답을 실행 당사자에게만 표시

_lambda = boto3.client("lambda")


def _response(status: int, body: dict) -> dict:
    return {"statusCode": status, "body": json.dumps(body)}


def handler(event, context):
    raw_body = event.get("body") or ""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    signature = headers.get("x-signature-ed25519", "")
    timestamp = headers.get("x-signature-timestamp", "")

    if not verify.verify_signature(PUBLIC_KEY, signature, timestamp, raw_body):
        return _response(401, {"error": "invalid request signature"})

    interaction = json.loads(raw_body)
    itype = interaction.get("type")

    if itype == PING:
        return _response(200, {"type": PONG})

    if itype in (APPLICATION_COMMAND, MESSAGE_COMPONENT):
        # 실제 작업(명령 실행, 버튼 처리)은 Worker Lambda에 비동기로 넘긴다
        # (InvocationType="Event"). 이 invoke는 결과를 기다리지 않으므로
        # 수십 ms 안에 끝난다.
        _lambda.invoke(
            FunctionName=WORKER_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps(interaction).encode(),
        )
        # Discord에는 즉시 deferred 응답 → 실행 당사자에게만 "생각 중..." 표시.
        # 이후 Worker의 followup 메시지도 ephemeral로 이어진다.
        return _response(
            200,
            {"type": DEFERRED_CHANNEL_MESSAGE, "data": {"flags": EPHEMERAL}},
        )

    return _response(400, {"error": "unhandled interaction type"})
