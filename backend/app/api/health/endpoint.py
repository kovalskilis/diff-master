from fastapi import APIRouter
from starlette.responses import Response
from starlette import status

health = APIRouter()

@health.get("/health")
async def health_endpoint() -> Response:
    return Response(status_code=status.HTTP_200_OK)