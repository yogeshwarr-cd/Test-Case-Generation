import argparse,random
import numpy as np
from ultralytics import YOLO
def main():
    p=argparse.ArgumentParser();p.add_argument("--data",default="ml/datasets/ui_elements/data.yaml");p.add_argument("--model",default="yolo11n.pt");p.add_argument("--epochs",type=int,default=100);p.add_argument("--batch",type=int,default=16);p.add_argument("--imgsz",type=int,default=960);p.add_argument("--patience",type=int,default=20);p.add_argument("--device",default="cpu");p.add_argument("--seed",type=int,default=42);a=p.parse_args();random.seed(a.seed);np.random.seed(a.seed)
    YOLO(a.model).train(data=a.data,epochs=a.epochs,batch=a.batch,imgsz=a.imgsz,patience=a.patience,device=a.device,seed=a.seed,project="ml/runs",name="ui_detector",save=True,plots=True)
if __name__=="__main__":main()
