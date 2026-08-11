from fastapi import APIRouter

router = APIRouter(
    tags=["Health"]
)

@router.get("/")
async def root():
    status = {
        "status": "healthy",
        "service": "Healthbridge Care API",
        "version": "3.0.0",
        "architecture": "RAG"
    }

    return status