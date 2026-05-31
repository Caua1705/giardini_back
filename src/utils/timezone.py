from datetime import datetime, timezone
from zoneinfo import ZoneInfo


FORTALEZA_TZ = ZoneInfo("America/Fortaleza")


def to_fortaleza_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(FORTALEZA_TZ)


def to_local_time(value: datetime | None) -> str | None:
    local_datetime = to_fortaleza_datetime(value)
    if local_datetime is None:
        return None

    return local_datetime.strftime("%H:%M")
