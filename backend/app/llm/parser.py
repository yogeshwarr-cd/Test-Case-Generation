import json,re
from pydantic import BaseModel
def parse_json(content:str)->dict:
    clean=re.sub(r"^```(?:json)?|```$","",content.strip(),flags=re.I).strip()
    value=json.loads(clean)
    if not isinstance(value,dict): raise ValueError("LLM response must be a JSON object")
    return value
def parse_model(content:str,model:type[BaseModel])->BaseModel: return model.model_validate(parse_json(content))
