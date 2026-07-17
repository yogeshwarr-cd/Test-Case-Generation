import json,uuid
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
from app.core.config import settings
from app.image_processing.image_validator import validate_and_decode
from app.image_processing.preprocessor import preprocess
from app.image_processing.ocr_service import OCRService
from app.image_processing.yolo_detector import UIDetector
from app.image_processing.coordinate_matcher import match_labels
from app.image_processing.screen_classifier import classify
from app.image_processing.context_builder import build_context
from app.image_processing.confidence_service import calculate
from app.image_processing.schemas import ImageAnalysis
from app.image_processing.vision_fallback import VisionFallback

class ImagePipeline:
    _locks={}
    async def analyze(self,content,mime_type,original_name,image_description="",project_id=None):
        if Path(original_name).suffix.lower() not in {".png",".jpg",".jpeg",".webp"}: raise ValueError("Unsupported image file extension")
        image,checksum=validate_and_decode(content,mime_type);root=Path(settings.image_storage_path).resolve();root.mkdir(parents=True,exist_ok=True);cache=root/f"{checksum}.json"
        if settings.image_analysis_cache_enabled and cache.exists(): return json.loads(cache.read_text(encoding="utf-8")),True
        image_id=str(uuid.uuid4());normalized,ocr_image,quality,blank=preprocess(image);safe_path=root/f"{checksum}.webp";normalized.save(safe_path,"WEBP",quality=88)
        ocr_items,ocr_version=OCRService().extract(ocr_image);elements,detector_version=UIDetector().detect(normalized);elements=match_labels(elements,ocr_items);screen,screen_confidence=classify(ocr_items,elements,image_description)
        compact=build_context(image_id,screen,screen_confidence,elements,ocr_items,image_description);scores,overall=calculate(quality,ocr_items,elements,screen_confidence);warnings=list(compact["warnings"])
        if overall<settings.vision_llm_min_local_confidence: await VisionFallback().analyze(checksum,normalized)
        if blank:warnings.append("Image appears blank or unreadable")
        if overall<.6:warnings.append("Low-confidence visual analysis; manual review recommended")
        full=ImageAnalysis(image_id=image_id,image_type="wireframe" if "wireframe" in image_description.lower() else "application_screenshot",screen_type=screen,screen_confidence=screen_confidence,page_titles=compact["page_titles"],ui_elements=elements,visible_messages=compact["visible_messages"],possible_actions=compact["possible_actions"],test_hints=compact["test_hints"],warnings=warnings,confidence_scores=scores,overall_confidence=overall,ocr_items=ocr_items,model_versions={"ocr":ocr_version,"detector":detector_version}).model_dump(mode="json")
        now=datetime.now(timezone.utc).isoformat();record={"image_id":image_id,"checksum":checksum,"original_name":Path(original_name).name,"safe_file_name":safe_path.name,"mime_type":mime_type,"file_size":len(content),"storage_path":str(safe_path),"project_id":str(project_id) if project_id else None,"upload_status":"stored","analysis_status":"analyzed","created_at":now,"updated_at":now,"full_analysis":full,"compact_context":{**compact,"overall_confidence":overall,"warnings":warnings}}
        cache.write_text(json.dumps(record),encoding="utf-8");(root/f"{image_id}.ref").write_text(checksum,encoding="utf-8");return record,False
    @staticmethod
    def get(image_id):
        root=Path(settings.image_storage_path).resolve();ref=root/f"{image_id}.ref"
        if not ref.exists(): return None
        cache=root/f"{ref.read_text(encoding='utf-8')}.json";return json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
