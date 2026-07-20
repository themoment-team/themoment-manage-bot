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


def send_message(channel_id: str, content: str, components: list | None = None) -> dict:
    """채널에 봇 명의로 메시지 전송. 생성된 메시지 dict(id 포함) 반환."""
    payload: dict = {"content": content}
    if components is not None:
        payload["components"] = components
    resp = requests.post(
        f"{API_BASE}/channels/{channel_id}/messages",
        headers=_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_message(channel_id: str, message_id: str) -> dict:
    """채널의 특정 메시지 조회 (기존 버튼/컴포넌트 보존용)."""
    resp = requests.get(
        f"{API_BASE}/channels/{channel_id}/messages/{message_id}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def edit_message(
    channel_id: str,
    message_id: str,
    content: str | None = None,
    components: list | None = None,
) -> dict:
    """봇이 보낸 메시지의 내용/컴포넌트 수정. 남의 메시지는 수정 불가."""
    payload: dict = {}
    if content is not None:
        payload["content"] = content
    if components is not None:
        payload["components"] = components
    resp = requests.patch(
        f"{API_BASE}/channels/{channel_id}/messages/{message_id}",
        headers=_HEADERS,
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def add_role(guild_id: str, user_id: str, role_id: str) -> None:
    """멤버에게 역할 부여. 봇에 MANAGE_ROLES 권한 + 봇 역할이 대상보다 위여야 함."""
    resp = requests.put(
        f"{API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()


def remove_role(guild_id: str, user_id: str, role_id: str) -> None:
    """멤버에게서 역할 제거. 봇에 MANAGE_ROLES 권한 + 봇 역할이 대상보다 위여야 함."""
    resp = requests.delete(
        f"{API_BASE}/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()


def add_button(components: list | None, label: str, custom_id: str) -> list:
    """기존 components(action row 목록)에 버튼 하나를 추가한 새 목록 반환.

    기존 버튼들을 모두 모아 새 버튼을 뒤에 붙인 뒤, 한 줄(action row)당 5개씩
    다시 나눈다. Discord 제한: row당 버튼 5개, 메시지당 row 5개(=버튼 25개).
    """
    buttons = []
    for row in components or []:
        for comp in row.get("components", []):
            if comp.get("type") == 2:  # 2 = 버튼
                buttons.append(comp)
    buttons.append(
        {"type": 2, "style": 1, "label": label, "custom_id": custom_id}  # style 1 = primary
    )
    rows = []
    for i in range(0, len(buttons), 5):
        rows.append({"type": 1, "components": buttons[i : i + 5]})  # type 1 = action row
    return rows


def send_followup(
    application_id: str,
    interaction_token: str,
    content: str,
    flags: int = 0,
) -> None:
    """deferred 응답 후, 실제 작업 결과를 후속 메시지로 전송.

    이 호출은 봇 토큰이 아니라 interaction_token으로 인증됩니다(공개 웹훅).
    flags=64 를 주면 개인에게만 보이는(ephemeral) 메시지가 됩니다.
    """
    payload: dict = {"content": content}
    if flags:
        payload["flags"] = flags
    requests.post(
        f"{API_BASE}/webhooks/{application_id}/{interaction_token}",
        json=payload,
        timeout=10,
    )
