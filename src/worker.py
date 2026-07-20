"""Worker Lambda — 실제 배치 작업 수행.

Front(app.py)가 비동기로 넘긴 interaction 페이로드를 받아 실제 작업을 수행하고,
결과를 Discord followup 웹훅으로 전송합니다. 이 함수는 3초 제약을 받지 않습니다.

처리하는 두 종류의 인터랙션:
  - type 2 (슬래시 명령): 역할지급-전송 / 역할지급-추가 / 역할지급-설정
  - type 3 (버튼 클릭):   apply:{role_id}          → 신청 접수
                          ok:{user_id}:{role_id}   → 관리자 수락 → 역할 지급
"""

import os

import discord_api
import ssm_store

APPLICATION_ID = os.environ.get("DISCORD_APPLICATION_ID", "")

APPLICATION_COMMAND = 2
MESSAGE_COMPONENT = 3

EPHEMERAL = 64  # 개인에게만 보이는 메시지 flag


def handler(interaction, context):
    """interaction: Front가 넘긴 Discord Interaction dict (그대로)."""
    try:
        itype = interaction.get("type")
        if itype == APPLICATION_COMMAND:
            _handle_command(interaction)
        elif itype == MESSAGE_COMPONENT:
            _handle_component(interaction)
        else:
            _safe_followup(interaction, f"❓ 처리할 수 없는 인터랙션입니다: type={itype}")
    except Exception as e:  # noqa: BLE001 - 실패해도 사용자에게 알림
        _safe_followup(interaction, f"⚠️ 처리 중 오류가 발생했어요: {e}")


# --- 슬래시 명령 처리 -------------------------------------------------------

def _handle_command(interaction: dict) -> None:
    data = interaction.get("data", {})
    name = data.get("name")
    guild_id = interaction.get("guild_id")
    options = {o["name"]: o.get("value") for o in data.get("options", [])}

    if name == "역할지급-전송":
        content = options.get("내용", "")
        channel_id = options.get("채널")
        msg = discord_api.send_message(channel_id, content)
        _safe_followup(
            interaction,
            f"✅ <#{channel_id}> 에 메시지를 전송했어요.\n"
            f"메시지 ID: `{msg['id']}`\n"
            f"→ 그 채널에서 `/역할지급-추가 메시지id:{msg['id']} 역할:...` 로 버튼을 추가하세요.",
        )

    elif name == "역할지급-추가":
        message_id = options.get("메시지id")
        role_id = options.get("역할")
        approval_message = options.get("승인메시지", "")
        # 대상 메시지는 이 명령을 실행한 채널에 있다고 전제한다.
        channel_id = interaction.get("channel_id")
        role_name = _resolved_role_name(data, role_id)

        message = discord_api.get_message(channel_id, message_id)
        new_components = discord_api.add_button(
            message.get("components"),
            label=role_name,
            custom_id=f"apply:{role_id}",
        )
        discord_api.edit_message(channel_id, message_id, components=new_components)
        # 이 역할이 승인될 때 전송 채널로 보낼 메시지를 역할별로 저장.
        ssm_store.set_role_message(guild_id, role_id, approval_message)
        _safe_followup(
            interaction,
            f"✅ 메시지 `{message_id}` 에 **{role_name}** 신청 버튼을 추가했어요.\n"
            f"승인 시 전송 채널로 보낼 메시지도 저장했어요.",
        )

    elif name == "역할지급-설정":
        review_channel = options.get("승인채널")
        broadcast_channel = options.get("전송채널")
        ssm_store.set_channels(guild_id, review_channel, broadcast_channel)
        _safe_followup(
            interaction,
            f"✅ 승인 채널을 <#{review_channel}>, 전송 채널을 <#{broadcast_channel}> 로 설정했어요.",
        )

    elif name == "기수-역할추가":
        _bulk_role(interaction, guild_id, options, "추가역할", add=True)

    elif name == "기수-역할삭제":
        _bulk_role(interaction, guild_id, options, "삭제역할", add=False)

    else:
        _safe_followup(interaction, f"❓ 모르는 명령어예요: `{name}`")


def _bulk_role(
    interaction: dict, guild_id: str, options: dict, target_key: str, add: bool
) -> None:
    """기수 역할을 가진 모든 멤버에게 대상 역할을 일괄 추가/삭제한다.

    add=True 면 추가, False 면 삭제. 서버 규모가 작아(20~30명) 한 번의 멤버
    조회로 충분하다. 이미 원하는 상태인 멤버는 건너뛰어 API 호출을 줄인다.
    """
    grade_role = options.get("기수역할")
    target_role = options.get(target_key)
    action = "추가" if add else "삭제"

    # limit=1000 = 이 엔드포인트의 최대치. SERVER MEMBERS INTENT 필요.
    members = discord_api.list_members(guild_id, limit=1000)

    changed = 0
    skipped = 0
    failed = 0
    for m in members:
        user = m.get("user", {})
        if user.get("bot"):
            continue  # 봇 계정은 제외
        if not discord_api.member_has_role(m, grade_role):
            continue  # 대상 기수 역할이 없는 멤버는 무시

        has_target = discord_api.member_has_role(m, target_role)
        if add == has_target:
            # 추가인데 이미 있음 / 삭제인데 이미 없음 → 변경 불필요
            skipped += 1
            continue

        try:
            if add:
                discord_api.add_role(guild_id, user["id"], target_role)
            else:
                discord_api.remove_role(guild_id, user["id"], target_role)
            changed += 1
        except Exception as e:  # noqa: BLE001 - 개별 실패는 건너뛰고 집계
            failed += 1
            print(f"{action} 실패 user={user.get('id')}: {e}")

    msg = (
        f"✅ <@&{grade_role}> 기수 멤버에게 <@&{target_role}> 역할 {action} 완료!\n"
        f"• {action}: {changed}명 · 건너뜀(이미 처리됨): {skipped}명"
    )
    if failed:
        msg += f" · 실패: {failed}명 (봇 권한/역할 순서 확인)"
    _safe_followup(interaction, msg)


# --- 버튼 클릭 처리 ---------------------------------------------------------

def _handle_component(interaction: dict) -> None:
    custom_id = interaction.get("data", {}).get("custom_id", "")
    guild_id = interaction.get("guild_id")

    if custom_id.startswith("apply:"):
        _handle_apply(interaction, guild_id, custom_id)
    elif custom_id.startswith("ok:"):
        _handle_approve(interaction, guild_id, custom_id)
    else:
        _safe_followup(interaction, f"❓ 알 수 없는 버튼이에요: `{custom_id}`")


def _handle_apply(interaction: dict, guild_id: str, custom_id: str) -> None:
    role_id = custom_id.split(":", 1)[1]
    member = interaction.get("member", {})
    applicant_id = member.get("user", {}).get("id")
    applicant_name = _member_display_name(member)

    review_channel = ssm_store.get_review_channel(guild_id)
    if not review_channel:
        _safe_followup(
            interaction,
            "⚠️ 아직 신청 확인 채널이 설정되지 않았어요. 관리자에게 `/역할지급-설정` 을 요청해주세요.",
        )
        return

    # 역할을 멘션(<@&id>)하면 그 역할을 가진 모두에게 알림이 가므로, 이름 텍스트로 보낸다.
    role = discord_api.role_name(guild_id, role_id)

    approve_row = [
        {
            "type": 1,  # action row
            "components": [
                {
                    "type": 2,  # 버튼
                    "style": 3,  # 3 = success(초록)
                    "label": "수락",
                    "custom_id": f"ok:{applicant_id}:{role_id}",
                }
            ],
        }
    ]
    discord_api.send_message(
        review_channel,
        f"📥 **{applicant_name}** 님이 **{role}** 역할을 신청했어요.",
        components=approve_row,
        allowed_mentions={"parse": []},  # 어떤 멘션도 알림이 가지 않도록
    )
    _safe_followup(
        interaction,
        "✅ 신청이 접수됐어요. 관리자 확인을 기다려 주세요!",
    )


def _handle_approve(interaction: dict, guild_id: str, custom_id: str) -> None:
    _, user_id, role_id = custom_id.split(":", 2)
    approver_id = interaction.get("member", {}).get("user", {}).get("id")

    discord_api.add_role(guild_id, user_id, role_id)

    role = discord_api.role_name(guild_id, role_id)

    # 승인 채널의 원본 신청 메시지를 "지급 완료"로 바꾸고 버튼 제거.
    # 역할은 이름 텍스트로, allowed_mentions로 알림이 가지 않게 한다.
    channel_id = interaction.get("channel_id")
    message_id = interaction.get("message", {}).get("id")
    if channel_id and message_id:
        discord_api.edit_message(
            channel_id,
            message_id,
            content=(
                f"✅ <@{user_id}> 님에게 **{role}** 역할을 지급했어요. "
                f"(처리: <@{approver_id}>)"
            ),
            components=[],  # 버튼 제거
            allowed_mentions={"parse": []},  # 멘션 알림 억제
        )

    # 전송 채널에 승인 안내 메시지 게시(설정돼 있고 승인 메시지가 있으면).
    # 승인된 유저만 멘션으로 알림이 가고, 본문 속 다른 멘션은 알림이 가지 않게 한다.
    broadcast_channel = ssm_store.get_broadcast_channel(guild_id)
    approval_message = ssm_store.get_role_message(guild_id, role_id)
    broadcast_note = ""
    if broadcast_channel and approval_message:
        discord_api.send_message(
            broadcast_channel,
            f"<@{user_id}> {approval_message}",
            allowed_mentions={"users": [user_id]},
        )
        broadcast_note = f" 전송 채널(<#{broadcast_channel}>)에도 안내 메시지를 보냈어요."

    _safe_followup(interaction, f"✅ 역할을 지급했어요.{broadcast_note}")


# --- 헬퍼 -------------------------------------------------------------------

def _member_display_name(member: dict) -> str:
    """멤버의 표시 이름을 반환. 서버 별명 > 글로벌 이름 > 유저명 순."""
    user = member.get("user", {})
    return (
        member.get("nick")
        or user.get("global_name")
        or user.get("username")
        or "알 수 없음"
    )


def _resolved_role_name(data: dict, role_id: str) -> str:
    """슬래시 명령의 resolved 데이터에서 역할 이름을 꺼낸다. 없으면 ID를 반환."""
    roles = data.get("resolved", {}).get("roles", {})
    role = roles.get(role_id, {})
    return role.get("name", role_id)


def _safe_followup(interaction: dict, content: str) -> None:
    try:
        discord_api.send_followup(
            APPLICATION_ID, interaction["token"], content, flags=EPHEMERAL
        )
    except Exception:  # noqa: BLE001
        print(f"followup failed: {content}")
