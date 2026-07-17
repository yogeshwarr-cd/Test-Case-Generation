from app.image_processing.schemas import OCRItem,BoundingBox
from app.core.config import settings

class OCRService:
    def extract(self,image):
        if settings.ocr_provider.lower()=="paddleocr":
            try:
                import numpy as np
                from paddleocr import PaddleOCR
                result=PaddleOCR(use_doc_orientation_classify=False,use_doc_unwarping=False,use_textline_orientation=False,lang=settings.ocr_language).predict(np.array(image));items=[]
                for page in result:
                    payload=page.json.get("res",page.json) if hasattr(page,"json") else {}
                    for text,confidence,poly in zip(payload.get("rec_texts",[]),payload.get("rec_scores",[]),payload.get("rec_polys",[])):
                        if text.strip() and float(confidence)>=settings.ocr_min_confidence:
                            xs=[int(p[0]) for p in poly];ys=[int(p[1]) for p in poly];items.append(OCRItem(text=text.strip(),confidence=float(confidence),bounding_box=BoundingBox(x1=min(xs),y1=min(ys),x2=max(xs),y2=max(ys))))
                return items,"paddleocr"
            except Exception: pass
        try:
            import pytesseract
            data=pytesseract.image_to_data(image,output_type=pytesseract.Output.DICT,config="--psm 6")
            items=[]
            for i,text in enumerate(data["text"]):
                confidence=max(0,float(data["conf"][i]))/100
                if text.strip() and confidence>=settings.ocr_min_confidence:
                    x,y,w,h=(data[k][i] for k in ("left","top","width","height"));items.append(OCRItem(text=text.strip(),confidence=confidence,bounding_box=BoundingBox(x1=x,y1=y,x2=x+w,y2=y+h)))
            return items,"tesseract"
        except Exception:
            return [],"unavailable"
