from app.core.config import settings

class VisionFallback:
    """Disabled-by-default single-call extension point; never fans out to providers."""
    _calls={}
    async def analyze(self,checksum,image):
        if not settings.enable_vision_llm_fallback:return None
        if self._calls.get(checksum,0)>=settings.vision_llm_max_calls_per_image:return None
        self._calls[checksum]=self._calls.get(checksum,0)+1
        # Wire exactly one approved vision provider here when explicitly configured.
        return None
