from PIL import Image,ImageEnhance,ImageFilter,ImageOps,ImageStat

def preprocess(image:Image.Image):
    normalized=image.copy();normalized.thumbnail((1920,1920))
    gray=ImageOps.grayscale(normalized);quality=max(0.0,min(1.0,ImageStat.Stat(gray).stddev[0]/64))
    optimized=ImageEnhance.Contrast(gray).enhance(1.25).filter(ImageFilter.SHARPEN)
    blank=ImageStat.Stat(gray).stddev[0]<3
    return normalized,optimized,quality,blank
