import httpx

from app.core.config import get_settings


class MlflowService:
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.mlflow_base_url

    async def list_experiments(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/api/2.0/mlflow/experiments/search", timeout=10)
            resp.raise_for_status()
            return resp.json().get("experiments", [])

    async def list_runs(self, experiment_id: str, max_results: int = 50) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/2.0/mlflow/runs/search",
                json={"experiment_ids": [experiment_id], "max_results": max_results},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("runs", [])

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/2.0/mlflow/registered-models/search",
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("registered_models", [])

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/health", timeout=5)
                return resp.status_code == 200
        except Exception:
            return False

    def get_ui_url(self) -> str:
        return self.base_url
