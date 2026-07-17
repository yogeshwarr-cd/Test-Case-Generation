def calculate(image_quality,ocr_items,elements,screen_confidence):
    ocr=sum(x.confidence for x in ocr_items)/len(ocr_items) if ocr_items else 0
    detection=sum(x.confidence for x in elements)/len(elements) if elements else 0
    matching=sum(bool(x.label) for x in elements)/len(elements) if elements else 0
    scores={"image_quality":image_quality,"ocr_extraction":ocr,"ui_detection":detection,"coordinate_matching":matching,"screen_classification":screen_confidence}
    overall=.2*image_quality+.2*ocr+.25*detection+.15*matching+.2*screen_confidence
    return {k:round(v,3) for k,v in scores.items()},round(overall,3)
