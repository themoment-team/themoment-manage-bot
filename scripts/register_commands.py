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

# 명령어 정의. option type: 3=문자열, 8=역할(role)
COMMANDS = [
    {
        "name": "create-channel",
        "description": "새 채널을 생성합니다",
        "options": [
            {
                "name": "name",
                "description": "만들 채널 이름",
                "type": 3,
                "required": True,
            }
        ],
    },
    {
        "name": "sync-nicknames",
        "description": "특정 역할을 가진 멤버의 별명에 접두사를 붙입니다",
        "options": [
            {
                "name": "role",
                "description": "대상 역할",
                "type": 8,
                "required": True,
            },
            {
                "name": "prefix",
                "description": "붙일 접두사 (기본: ★)",
                "type": 3,
                "required": False,
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
