from typing import Any
def item_id(item:Any,prefix:str,index:int)->str:
    if isinstance(item,dict): return str(item.get("id") or item.get(f"{prefix}_id") or f"{prefix}-{index+1}")
    return f"{prefix}-{index+1}"
def item_text(item:Any)->str:
    if isinstance(item,str): return item.strip()
    if isinstance(item,dict): return str(item.get("title") or item.get("description") or item.get("text") or item.get("name") or "").strip()
    return str(item).strip()
def deduplicate(items:list[Any])->list[Any]:
    seen=set(); out=[]
    for item in items:
        key=item_text(item).casefold()
        if key and key not in seen: seen.add(key); out.append(item)
    return out
def is_structured_tech_stack(stack:dict[str,Any])->bool:
    return bool(stack) and all(isinstance(k,str) and isinstance(v,(str,list,dict)) for k,v in stack.items())
