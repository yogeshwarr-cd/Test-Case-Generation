from pathlib import Path
from app.core.config import settings
from app.image_processing.schemas import UIElement,BoundingBox

class UIDetector:
    def detect(self,image):
        model_path=Path(settings.yolo_model_path)
        if model_path.exists():
            try:
                from ultralytics import YOLO
                result=YOLO(str(model_path)).predict(image,conf=settings.yolo_min_confidence,device=settings.yolo_device,verbose=False)[0];names=result.names;items=[]
                for i,box in enumerate(result.boxes):
                    x1,y1,x2,y2=map(int,box.xyxy[0].tolist());items.append(UIElement(element_id=f"ui_{i+1:03d}",type=names[int(box.cls)],confidence=float(box.conf),detection_source="yolo",bounding_box=BoundingBox(x1=x1,y1=y1,x2=x2,y2=y2)))
                return items,"yolo"
            except Exception: pass
        return self._heuristic(image),"opencv_heuristic"
    def _heuristic(self,image):
        try:
            import cv2,numpy as np
            gray=cv2.cvtColor(np.array(image),cv2.COLOR_RGB2GRAY);edges=cv2.Canny(gray,50,150);contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE);items=[]
            for contour in contours:
                x,y,w,h=cv2.boundingRect(contour)
                if w<60 or h<20 or w*h>image.width*image.height*.7: continue
                kind="text_input" if w/h>4 else "button" if 1.5<w/h<6 else "card"
                items.append(UIElement(element_id=f"ui_{len(items)+1:03d}",type=kind,confidence=.55,detection_source="opencv_heuristic",bounding_box=BoundingBox(x1=x,y1=y,x2=x+w,y2=y+h)))
                if len(items)>=40: break
            return items
        except Exception: return []
