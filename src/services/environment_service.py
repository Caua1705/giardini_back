from sqlalchemy.orm import Session

from src.repositories.environment_repository import EnvironmentRepository
from src.utils.storage import build_image_url
from src.core import config as settings


class EnvironmentService:
    def __init__(self, db: Session):
        self.db = db
        self.environment_repo = EnvironmentRepository(db)

    def get_active_environments(self) -> list[dict]:
        environments = self.environment_repo.get_all_active()
        result = []
        for env in environments:
            env_dict = {
                "id": env.id,
                "name": env.name,
                "max_capacity": env.max_capacity,
                "is_active": env.is_active,
                "created_at": env.created_at,
                "updated_at": env.updated_at,
                "image_url": build_image_url(
                    env.image_path,
                    settings.SUPABASE_ENVIRONMENTS_BUCKET,
                ),
            }
            result.append(env_dict)

        return result
