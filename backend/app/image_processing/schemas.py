from typing import Literal
from pydantic import BaseModel, Field

class BoundingBox(BaseModel): x1:int; y1:int; x2:int; y2:int
class OCRItem(BaseModel): text:str; confidence:float; bounding_box:BoundingBox
class UIElement(BaseModel):
    element_id:str; type:str; label:str|None=None; placeholder:str|None=None
    required:bool=False; enabled:bool=True; visible:bool=True; confidence:float
    detection_source:Literal["yolo","opencv_heuristic"]; bounding_box:BoundingBox
class ImageAnalysis(BaseModel):
    image_id:str; image_type:str="application_screenshot"; platform:str="web"; screen_type:str="unknown"
    screen_confidence:float=0; page_titles:list[str]=Field(default_factory=list); ui_elements:list[UIElement]=Field(default_factory=list)
    visible_messages:list[str]=Field(default_factory=list); possible_actions:list[str]=Field(default_factory=list)
    test_hints:list[str]=Field(default_factory=list); warnings:list[str]=Field(default_factory=list)
    confidence_scores:dict[str,float]=Field(default_factory=dict); overall_confidence:float=0
    ocr_items:list[OCRItem]=Field(default_factory=list); model_versions:dict[str,str]=Field(default_factory=dict)
