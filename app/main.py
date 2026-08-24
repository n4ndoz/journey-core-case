from fastapi import FastAPI

from app.api import router
from app.domain.errors import DomainError
from app.error_handlers import domain_error_handler

app = FastAPI(title="AINA Health journey-core")
app.add_exception_handler(DomainError, domain_error_handler)
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
