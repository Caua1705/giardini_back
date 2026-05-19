from src.core import config as settings


def build_image_url(
    image_path: str | None,
    bucket: str,
) -> str | None:
    if not image_path:
        return None

    return f"{settings.SUPABASE_STORAGE_BASE_URL}/{bucket}/{image_path}"