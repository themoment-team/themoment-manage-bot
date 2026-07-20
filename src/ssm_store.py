"""봇 설정값을 AWS SSM 파라미터 스토어에 저장/조회.

DB 없이 유지해야 하는 영속 상태값을 담는다. SSM 표준 파라미터는 무료(요금 0)이며
서버리스 구조와 잘 맞는다. Worker Lambda에 ssm:GetParameter / ssm:PutParameter
권한이 필요하다 (template.yaml에서 /themoment-bot/* 범위로 부여).

저장하는 값 (길드별):
  - 승인 채널: /themoment-bot/{guild_id}/review-channel    (신청이 오면 관리자가 확인)
  - 전송 채널: /themoment-bot/{guild_id}/broadcast-channel (승인 시 안내 메시지 게시)
  - 역할별 승인 메시지: /themoment-bot/{guild_id}/role-message/{role_id}
"""

import boto3

_ssm = boto3.client("ssm")
_PREFIX = "/themoment-bot"


def _get(name: str) -> str | None:
    try:
        return _ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except _ssm.exceptions.ParameterNotFound:
        return None


def _put(name: str, value: str) -> None:
    _ssm.put_parameter(Name=name, Value=value, Type="String", Overwrite=True)


def _review_name(guild_id: str) -> str:
    return f"{_PREFIX}/{guild_id}/review-channel"


def _broadcast_name(guild_id: str) -> str:
    return f"{_PREFIX}/{guild_id}/broadcast-channel"


def _role_message_name(guild_id: str, role_id: str) -> str:
    return f"{_PREFIX}/{guild_id}/role-message/{role_id}"


def set_channels(guild_id: str, review_channel: str, broadcast_channel: str) -> None:
    """승인 채널과 전송 채널을 함께 저장한다."""
    _put(_review_name(guild_id), review_channel)
    _put(_broadcast_name(guild_id), broadcast_channel)


def get_review_channel(guild_id: str) -> str | None:
    """승인 채널 ID 반환. 미설정이면 None."""
    return _get(_review_name(guild_id))


def get_broadcast_channel(guild_id: str) -> str | None:
    """전송 채널 ID 반환. 미설정이면 None."""
    return _get(_broadcast_name(guild_id))


def set_role_message(guild_id: str, role_id: str, message: str) -> None:
    """역할 승인 시 전송 채널로 보낼 메시지를 역할별로 저장한다."""
    _put(_role_message_name(guild_id, role_id), message)


def get_role_message(guild_id: str, role_id: str) -> str | None:
    """역할 승인 메시지 반환. 미설정이면 None."""
    return _get(_role_message_name(guild_id, role_id))
