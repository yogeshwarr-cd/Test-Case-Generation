from pathlib import Path
class PromptLoader:
    def __init__(self,root:Path|None=None): self.root=root or Path(__file__).parents[1]/"prompts"
    def render(self,name:str,**values)->str:
        text=(self.root/name).read_text(encoding="utf-8")
        for key,value in values.items(): text=text.replace("{{ "+key+" }}",str(value)).replace("{{"+key+"}}",str(value))
        return text
