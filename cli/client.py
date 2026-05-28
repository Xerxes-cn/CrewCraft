import httpx


class CrewCraftClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=300.0)

    async def list_crews(self) -> list[dict]:
        r = await self._client.get("/api/crews")
        r.raise_for_status()
        return r.json()

    async def get_crew(self, crew_id: int) -> dict:
        r = await self._client.get(f"/api/crews/{crew_id}")
        r.raise_for_status()
        return r.json()

    async def run_task(self, crew_id: int, task_input: str) -> dict:
        r = await self._client.post(
            f"/api/crews/{crew_id}/run",
            json={"input": task_input},
        )
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self._client.aclose()
