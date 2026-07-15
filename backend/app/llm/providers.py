from abc import ABC,abstractmethod
from dataclasses import dataclass
from typing import Any
@dataclass
class ProviderResponse: content:str; provider:str; model:str; token_usage:dict[str,int]|None=None
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self,prompt:str,*,timeout:float)->ProviderResponse: ...
class ProviderError(RuntimeError): recoverable=True
class QuotaExceededError(ProviderError): recoverable=False
class UnconfiguredProvider(LLMProvider):
    async def generate(self,prompt:str,*,timeout:float)->ProviderResponse: raise ProviderError("No LLM provider configured")
