"""Discord REST API 호출 모음.

채널 생성, 역할 조회, 별명 변경 같은 실제 "관리 작업"을 여기서 처리합니다.
봇 토큰(Bot token)으로 인증하며, 이 토큰은 Lambda 환경변수로 주입됩니다.
"""

import os
import requests

API_BASE = "https://discord.com/api/v10"
BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

_HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
}


def create_channel(guild_id: str, name: str, channel_type: int = 0) -> dict:
    """길드(서버)에 채널 생성. channel_type 0=텍스트, 2=음성, 4=카테고리."""
    resp = requests.post(
        f"{API_BASE}/guilds/{guild_id}/channels",
        headers=_HEADERS,
        json={"name": name, "type": channel_type},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def list_members(guild_id: str, limit: int = 100) -> list[dict]:
    """서버 멤버 목록 조회. 소규모(20~30명)라 한 번 호출이면 충분.

    주의: 이 엔드포인트는 봇에 SERVER MEMBERS INTENT 권한이 필요합니다
    (Developer Portal > Bot > Privileged Gateway Intents).
    """
    resp = requests.get(
        f"{API_BASE}/guilds/{guild_id}/members",
        headers=_HEADERS,
        params={"limit": limit},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def set_nickname(guild_id: str, user_id: str, nickname: str) -> None:
    """특정 멤버의 서버 별명(nickname) 변경."""
    resp = requests.patch(
        f"{API_BASE}/guilds/{guild_id}/members/{user_id}",
        headers=_HEADERS,
        json={"nick": nickname},
        timeout=10,
    )
    resp.raise_for_status()


def member_has_role(member: dict, role_id: str) -> bool:
    """멤버가 특정 역할(role)을 가지고 있는지 확인."""
    return role_id in member.get("roles", [])


def send_followup(application_id: str, interaction_token: str, content: str) -> None:
    """deferred 응답 후, 실제 작업 결과를 후속 메시지로 전송.

    이 호출은 봇 토큰이 아니라 interaction_token으로 인증됩니다(공개 웹훅).
    """
    requests.post(
        f"{API_BASE}/webhooks/{application_id}/{interaction_token}",
        json={"content": content},
        timeout=10,
    )
