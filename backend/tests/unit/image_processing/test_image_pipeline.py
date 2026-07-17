from io import BytesIO
from PIL import Image
import pytest
from app.image_processing.image_validator import validate_and_decode
from app.image_processing.coordinate_matcher import match_labels
from app.image_processing.screen_classifier import classify
from app.image_processing.confidence_service import calculate
from app.image_processing.schemas import BoundingBox,OCRItem,UIElement
from app.image_processing.image_pipeline import ImagePipeline
from app.core.config import settings
from app.agents.context_preparation_agent import ContextPreparationAgent
from app.agents.base_agent import ExecutionContext
import uuid

def image_bytes(fmt="PNG",color="white"):
    stream=BytesIO();Image.new("RGB",(320,200),color).save(stream,fmt);return stream.getvalue()
def test_valid_png_and_jpeg_decode():
    assert validate_and_decode(image_bytes("PNG"),"image/png")[0].size==(320,200)
    assert validate_and_decode(image_bytes("JPEG"),"image/jpeg")[0].size==(320,200)
def test_unsupported_and_corrupt_images_rejected():
    with pytest.raises(ValueError):validate_and_decode(image_bytes(),"image/gif")
    with pytest.raises(ValueError):validate_and_decode(b"broken","image/png")
def test_coordinate_matching_assigns_one_label():
    element=UIElement(element_id="ui_001",type="button",confidence=.7,detection_source="opencv_heuristic",bounding_box=BoundingBox(x1=10,y1=10,x2=150,y2=60))
    text=OCRItem(text="Login",confidence=.9,bounding_box=BoundingBox(x1=50,y1=20,x2=100,y2=40))
    assert match_labels([element],[text])[0].label=="Login"
def test_screen_classification_and_confidence():
    texts=[OCRItem(text="Email Password Login",confidence=.9,bounding_box=BoundingBox(x1=0,y1=0,x2=10,y2=10))]
    assert classify(texts,[])[0]=="login"
    scores,overall=calculate(.8,texts,[],.8);assert scores["ocr_extraction"]==.9 and 0<=overall<=1
@pytest.mark.asyncio
async def test_duplicate_checksum_reuses_cached_analysis(tmp_path):
    old=settings.image_storage_path;settings.image_storage_path=str(tmp_path)
    try:
        first,cached1=await ImagePipeline().analyze(image_bytes(),"image/png","screen.png")
        second,cached2=await ImagePipeline().analyze(image_bytes(),"image/png","screen.png")
        assert not cached1 and cached2 and first["image_id"]==second["image_id"]
    finally: settings.image_storage_path=old
@pytest.mark.asyncio
async def test_existing_context_flow_accepts_optional_image(tmp_path):
    old=settings.image_storage_path;settings.image_storage_path=str(tmp_path)
    try:
        record,_=await ImagePipeline().analyze(image_bytes(),"image/png","screen.png","Login wireframe")
        result=await ContextPreparationAgent().execute({"project_id":uuid.uuid4(),"source_type":"manual","input_payload":{"user_stories":["As a user I can login"],"epics":["Authentication"],"features":["Login"],"image_ids":[record["image_id"]]}},ExecutionContext(request_id="image",workflow_id="image"))
        assert result.image_ids==[record["image_id"]] and result.visual_context
    finally: settings.image_storage_path=old
