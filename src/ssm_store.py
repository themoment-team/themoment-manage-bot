"""관리자 확인 채널 설정을 AWS SSM 파라미터 스토어에 저장/조회.

이 봇의 유일한 영속 상태값(길드별 "신청 확인 채널")을 담는다. SSM 표준
파라미터는 무료(요금 0)이며, 별도 DB 없이 서버리스 구조와 잘 맞는다.

파라미터 이름: /themoment-bot/{guild_id}/review-channel
Worker Lambda에 ssm:GetParameter / ssm:PutParameter 권한이 필요하다
(template.yaml에서 부여).
"""

import boto3

_ssm = boto3.client("ssm")


def _param_name(guild_id: str) -> str:
    return f"/themoment-bot/{guild_id}/review-channel"


def get_review_channel(guild_id: str) -> str | None:
    """길드의 신청 확인 채널 ID 반환. 미설정이면 None."""
    try:
        resp = _ssm.get_parameter(Name=_param_name(guild_id))
        return resp["Parameter"]["Value"]
    except _ssm.exceptions.ParameterNotFound:
        return None


def set_review_channel(guild_id: str, channel_id: str) -> None:
    """길드의 신청 확인 채널 ID 저장 (덮어쓰기)."""
    _ssm.put_parameter(
        Name=_param_name(guild_id),
        Value=channel_id,
        Type="String",
        Overwrite=True,
    )
