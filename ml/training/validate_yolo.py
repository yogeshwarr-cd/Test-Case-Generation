import argparse
from ultralytics import YOLO
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--model",required=True);p.add_argument("--data",default="ml/datasets/ui_elements/data.yaml");p.add_argument("--split",default="test");a=p.parse_args();metrics=YOLO(a.model).val(data=a.data,split=a.split);print({"precision":metrics.box.mp,"recall":metrics.box.mr,"mAP50":metrics.box.map50,"mAP50-95":metrics.box.map})
