import hashlib
from io import BytesIO
from PIL import Image,ImageOps
from app.core.config import settings

def validate_and_decode(content:bytes,mime_type:str):
    if not content: raise ValueError("The uploaded image is empty")
    if len(content)>settings.image_max_size_mb*1024*1024: raise ValueError(f"Image exceeds {settings.image_max_size_mb} MB")
    if mime_type not in set(settings.image_allowed_types.split(",")): raise ValueError("Unsupported image type")
    try:
        image=Image.open(BytesIO(content));detected={"PNG":"image/png","JPEG":"image/jpeg","WEBP":"image/webp"}.get(image.format);image.verify();image=Image.open(BytesIO(content));image=ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc: raise ValueError("Image is corrupt or unreadable") from exc
    if detected!=mime_type: raise ValueError("File content does not match its declared image type")
    if image.width>settings.image_max_width or image.height>settings.image_max_height: raise ValueError("Image dimensions exceed configured limits")
    if image.width*image.height>20_000_000: raise ValueError("Image resolution is unsafe")
    return image,hashlib.sha256(content).hexdigest()
