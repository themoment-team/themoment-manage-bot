"""Discord 요청 서명 검증 (Ed25519).

Discord는 모든 Interaction 요청에 서명을 붙여 보냅니다. 이 검증을 통과하지
못하면 Discord가 Interactions Endpoint URL 등록조차 거부합니다. Lambda가
받은 요청이 정말 Discord에서 온 것인지 반드시 확인해야 합니다.
"""

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError


def verify_signature(public_key: str, signature: str, timestamp: str, body: str) -> bool:
    """서명이 유효하면 True, 아니면 False.

    public_key: Discord Developer Portal의 Application "Public Key"
    signature:  요청 헤더 X-Signature-Ed25519
    timestamp:  요청 헤더 X-Signature-Timestamp
    body:       요청 본문 (원본 문자열 그대로 — 파싱 전)
    """
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False
