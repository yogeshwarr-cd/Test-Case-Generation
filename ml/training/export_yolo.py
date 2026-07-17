import argparse
from ultralytics import YOLO
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--model",required=True);p.add_argument("--imgsz",type=int,default=960);a=p.parse_args();YOLO(a.model).export(format="onnx",imgsz=a.imgsz,dynamic=True,simplify=True)
