from app.orchestrator.graph import build_graph
class WorkflowOrchestrator:
    def __init__(self): self.graph=build_graph()
    async def run(self,state): return await self.graph.ainvoke(state)
