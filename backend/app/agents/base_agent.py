import asyncio,json,time
from dataclasses import dataclass,field
from typing import Any,Generic,TypeVar
from pydantic import BaseModel
from app.llm.parser import parse_model
T=TypeVar("T",bound=BaseModel)
@dataclass
class ExecutionContext: request_id:str; workflow_id:str; metadata:dict[str,Any]=field(default_factory=dict)
class AgentExecutionError(RuntimeError): pass
class BaseAgent(Generic[T]):
    output_model:type[T]
    def __init__(self,llm_client=None,max_retries:int=2): self.llm_client=llm_client;self.max_retries=max_retries
    async def execute(self,input_data:Any,execution_context:ExecutionContext)->T:
        started=time.perf_counter()
        try:
            result=await self.run(input_data,execution_context)
            return result if isinstance(result,self.output_model) else self.output_model.model_validate(result)
        except Exception as exc: raise AgentExecutionError(f"{self.__class__.__name__} failed: {exc}") from exc
    async def run(self,input_data:Any,execution_context:ExecutionContext)->T: raise NotImplementedError
    async def llm_json(self,prompt:str)->T:
        if not self.llm_client: raise AgentExecutionError("LLM client is not configured")
        for attempt in range(self.max_retries+1):
            try: return parse_model((await self.llm_client.generate(prompt)).content,self.output_model)
            except (TimeoutError,asyncio.TimeoutError,json.JSONDecodeError):
                if attempt==self.max_retries: raise
