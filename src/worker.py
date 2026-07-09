"""Worker Lambda — 실제 배치 작업 수행.

Front(app.py)가 비동기로 넘긴 interaction 페이로드를 받아 실제 관리 작업
(채널 생성, 별명 일괄 변경 등)을 수행하고, 결과를 Discord followup 웹훅으로
전송합니다. 이 함수는 3초 제약을 받지 않습니다 (Discord와 직접 연결 없음).

타임아웃은 template.yaml에서 넉넉히(예: 60초) 설정하세요.
"""

import os

import discord_api

APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID", "")


def handler(interaction, context):
    """interaction: Front가 넘긴 Discord Interaction dict (그대로)."""
    try:
        _handle_command(interaction)
    except Exception as e:  # noqa: BLE001 - 실패해도 사용자에게 알림
        _safe_followup(interaction, f"⚠️ 처리 중 오류가 발생했어요: {e}")


def _handle_command(interaction: dict) -> None:
    data = interaction.get("data", {})
    name = data.get("name")
    guild_id = interaction.get("guild_id")
    options = {o["name"]: o.get("value") for o in data.get("options", [])}

    if name == "create-channel":
        channel_name = options.get("name", "새-채널")
        discord_api.create_channel(guild_id, channel_name)
        _safe_followup(interaction, f"✅ 채널 `#{channel_name}` 생성 완료!")

    elif name == "sync-nicknames":
        # 특정 역할을 가진 멤버의 별명 앞에 접두사를 붙이는 예시.
        role_id = options.get("role")
        prefix = options.get("prefix", "★")
        members = discord_api.list_members(guild_id)
        changed = 0
        for m in members:
            if discord_api.member_has_role(m, role_id):
                user = m.get("user", {})
                base = m.get("nick") or user.get("username", "")
                if base and not base.startswith(prefix):
                    discord_api.set_nickname(guild_id, user["id"], f"{prefix}{base}")
                    changed += 1
        _safe_followup(interaction, f"✅ 별명 {changed}명 변경 완료!")

    else:
        _safe_followup(interaction, f"❓ 모르는 명령어예요: `{name}`")


def _safe_followup(interaction: dict, content: str) -> None:
    try:
        discord_api.send_followup(APPLICATION_ID, interaction["token"], content)
    except Exception:  # noqa: BLE001
        print(f"followup failed: {content}")
