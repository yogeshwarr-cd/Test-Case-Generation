import asyncio
from app.llm.providers import LLMProvider,ProviderResponse,QuotaExceededError
class LLMClient:
    def __init__(self,primary:LLMProvider,fallback:LLMProvider|None=None,timeout:float=60): self.primary=primary;self.fallback=fallback;self.timeout=timeout
    async def generate(self,prompt:str)->ProviderResponse:
        try: return await asyncio.wait_for(self.primary.generate(prompt,timeout=self.timeout),self.timeout)
        except QuotaExceededError: raise
        except Exception:
            if not self.fallback: raise
            return await asyncio.wait_for(self.fallback.generate(prompt,timeout=self.timeout),self.timeout)
