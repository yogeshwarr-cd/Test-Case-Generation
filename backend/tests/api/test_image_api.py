from io import BytesIO
import httpx,pytest
from PIL import Image
from app.main import app
from app.core.config import settings

def png_bytes():
    stream=BytesIO();Image.new("RGB",(240,160),"white").save(stream,"PNG");return stream.getvalue()
@pytest.mark.asyncio
async def test_upload_image_api_and_cache(tmp_path):
    old=settings.image_storage_path;settings.image_storage_path=str(tmp_path)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            files={"image":("screen.png",png_bytes(),"image/png")}
            first=await client.post("/api/v1/images/upload",files=files,data={"image_description":"Login wireframe"})
            second=await client.post("/api/v1/images/upload",files=files,data={"image_description":"Login wireframe"})
        assert first.status_code==200 and first.json()["status"]=="analyzed"
        assert second.json()["cached"] is True
    finally:settings.image_storage_path=old
@pytest.mark.asyncio
async def test_upload_rejects_unsupported_file(tmp_path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
        response=await client.post("/api/v1/images/upload",files={"image":("bad.gif",b"GIF89a","image/gif")})
    assert response.status_code==422
