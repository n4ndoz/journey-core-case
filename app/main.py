from fastapi import FastAPI

app = FastAPI(title="AINA Health journey-core")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
