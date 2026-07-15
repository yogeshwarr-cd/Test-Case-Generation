import uuid

from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        try:
            response = await call_next(request)
        except Exception:
            # Keep the ID on request.state for the global exception handler and
            # preserve the original exception and traceback.
            raise

        response.headers["X-Request-ID"] = request_id
        return response
