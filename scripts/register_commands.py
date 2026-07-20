"""슬래시 명령어를 Discord에 등록하는 1회성 스크립트.

명령어 정의를 바꿀 때마다 다시 실행하세요.

실행법:
    export DISCORD_APPLICATION_ID=...
    export DISCORD_BOT_TOKEN=...
    export DISCORD_GUILD_ID=...      # (선택) 특정 서버에만 즉시 등록할 때
    python scripts/register_commands.py

참고:
  - GUILD_ID를 주면 해당 서버에 "즉시" 반영됩니다 (개발/테스트에 좋음).
  - GUILD_ID 없이 전역(global) 등록하면 반영에 최대 1시간 걸릴 수 있습니다.
"""

import os
import sys
import requests

API_BASE = "https://discord.com/api/v10"

APP_ID = os.environ["DISCORD_APPLICATION_ID"]
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD_ID = os.environ.get("DISCORD_GUILD_ID")

# 명령어 정의.
#   option type: 3=문자열(string), 7=채널(channel), 8=역할(role)
#   default_member_permissions "8" = ADMINISTRATOR → 관리자에게만 명령어가 보임.
_ADMIN_ONLY = "8"

COMMANDS = [
    {
        "name": "역할지급-전송",
        "description": "역할 신청 버튼을 붙일 메시지를 채널로 전송합니다",
        "default_member_permissions": _ADMIN_ONLY,
        "options": [
            {
                "name": "내용",
                "description": "전송할 메시지 내용",
                "type": 3,
                "required": True,
            },
            {
                "name": "채널",
                "description": "메시지를 보낼 채널",
                "type": 7,
                "channel_types": [0],  # 0=텍스트 채널
                "required": True,
            },
        ],
    },
    {
        "name": "역할지급-추가",
        "description": "전송한 메시지에 역할 신청 버튼을 추가합니다 (메시지가 있는 채널에서 실행)",
        "default_member_permissions": _ADMIN_ONLY,
        "options": [
            {
                "name": "메시지id",
                "description": "버튼을 추가할 메시지의 ID (이 명령을 그 메시지가 있는 채널에서 실행)",
                "type": 3,
                "required": True,
            },
            {
                "name": "역할",
                "description": "신청 버튼으로 지급할 역할",
                "type": 8,
                "required": True,
            },
        ],
    },
    {
        "name": "역할지급-설정",
        "description": "역할 신청이 올 때 관리자가 확인할 채널을 설정합니다",
        "default_member_permissions": _ADMIN_ONLY,
        "options": [
            {
                "name": "채널",
                "description": "신청 확인용 관리자 채널",
                "type": 7,
                "channel_types": [0],  # 0=텍스트 채널
                "required": True,
            },
        ],
    },
    {
        "name": "기수-역할추가",
        "description": "특정 기수 역할을 가진 서버 내 모든 멤버에게 역할을 추가합니다",
        "default_member_permissions": _ADMIN_ONLY,
        "options": [
            {
                "name": "기수역할",
                "description": "대상이 될 기수 역할 (이 역할을 가진 모든 멤버가 대상)",
                "type": 8,
                "required": True,
            },
            {
                "name": "추가역할",
                "description": "대상 멤버들에게 추가할 역할",
                "type": 8,
                "required": True,
            },
        ],
    },
    {
        "name": "기수-역할삭제",
        "description": "특정 기수 역할을 가진 서버 내 모든 멤버에게서 역할을 삭제합니다",
        "default_member_permissions": _ADMIN_ONLY,
        "options": [
            {
                "name": "기수역할",
                "description": "대상이 될 기수 역할 (이 역할을 가진 모든 멤버가 대상)",
                "type": 8,
                "required": True,
            },
            {
                "name": "삭제역할",
                "description": "대상 멤버들에게서 삭제할 역할",
                "type": 8,
                "required": True,
            },
        ],
    },
]


def main():
    if GUILD_ID:
        url = f"{API_BASE}/applications/{APP_ID}/guilds/{GUILD_ID}/commands"
        scope = f"guild {GUILD_ID}"
    else:
        url = f"{API_BASE}/applications/{APP_ID}/commands"
        scope = "global"

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    # PUT = 전체 덮어쓰기 (여기 없는 기존 명령어는 삭제됨)
    resp = requests.put(url, headers=headers, json=COMMANDS, timeout=10)

    if resp.status_code >= 300:
        print(f"❌ 등록 실패 ({resp.status_code}): {resp.text}", file=sys.stderr)
        sys.exit(1)

    print(f"✅ {scope} 범위에 명령어 {len(COMMANDS)}개 등록 완료")
    for c in resp.json():
        print(f"   /{c['name']}")


if __name__ == "__main__":
    main()
