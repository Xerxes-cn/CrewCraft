import httpx


class CrewCraftClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=300.0)

    # --- Agents ---

    async def list_agents(self) -> list[dict]:
        r = await self._client.get("/api/agents")
        r.raise_for_status()
        return r.json()

    async def create_agent(self, data: dict) -> dict:
        r = await self._client.post("/api/agents", json=data)
        r.raise_for_status()
        return r.json()

    async def update_agent(self, agent_id: int, data: dict) -> dict:
        r = await self._client.put(f"/api/agents/{agent_id}", json=data)
        r.raise_for_status()
        return r.json()

    async def delete_agent(self, agent_id: int):
        r = await self._client.delete(f"/api/agents/{agent_id}")
        r.raise_for_status()

    # --- Tools & Skills ---

    async def list_tools(self) -> list[dict]:
        r = await self._client.get("/api/tools")
        r.raise_for_status()
        return r.json()

    async def list_skills(self) -> list[dict]:
        r = await self._client.get("/api/skills")
        r.raise_for_status()
        return r.json()

    # --- Tasks ---

    async def run_task(self, task_input: str) -> dict:
        r = await self._client.post("/api/run", json={"input": task_input})
        r.raise_for_status()
        return r.json()

    async def list_tasks(self) -> list[dict]:
        r = await self._client.get("/api/tasks")
        r.raise_for_status()
        return r.json()

    async def get_task(self, task_id: int) -> dict:
        r = await self._client.get(f"/api/tasks/{task_id}")
        r.raise_for_status()
        return r.json()

    async def close(self):
        await self._client.aclose()
