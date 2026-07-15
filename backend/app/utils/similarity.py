import re
from difflib import SequenceMatcher
def normalize_text(value:str)->str: return " ".join(re.findall(r"[a-z0-9]+",value.lower()))
def similarity(left:str,right:str)->float: return SequenceMatcher(None,normalize_text(left),normalize_text(right)).ratio()
def duplicate_indexes(values:list[str],threshold:float=.88)->set[int]:
    return {j for j in range(len(values)) for i in range(j) if similarity(values[i],values[j])>=threshold}
