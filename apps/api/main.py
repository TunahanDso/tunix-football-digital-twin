from fastapi import FastAPI

app = FastAPI(
    title="TUNIX Football Digital Twin API",
    version="0.1.0",
    description="Temporal football intelligence and simulation API.",
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "tunix-football-digital-twin"}
