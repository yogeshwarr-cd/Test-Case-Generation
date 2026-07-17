from math import hypot

def match_labels(elements,ocr_items,max_distance=140):
    unused=set(range(len(ocr_items)))
    for element in elements:
        box=element.bounding_box;cx=(box.x1+box.x2)/2;cy=(box.y1+box.y2)/2;best=None
        for i in unused:
            text=ocr_items[i];b=text.bounding_box;tx=(b.x1+b.x2)/2;ty=(b.y1+b.y2)/2
            contained=b.x1>=box.x1 and b.x2<=box.x2 and b.y1>=box.y1 and b.y2<=box.y2
            aligned=abs(tx-cx)<max(box.x2-box.x1,120) and b.y2<=box.y1
            distance=0 if contained else hypot(tx-cx,ty-cy)
            if (contained or aligned or distance<=max_distance) and (best is None or distance<best[0]): best=(distance,i,text.text)
        if best:
            element.label=best[2];unused.discard(best[1])
    return elements
