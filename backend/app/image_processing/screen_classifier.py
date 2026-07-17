def classify(ocr_items,elements,image_description=""):
    text=" ".join([x.text for x in ocr_items]+[image_description]).lower();types={x.type for x in elements}
    rules=[("login",("login","sign in","password")),("registration",("register","sign up","create account")),("forgot_password",("forgot password","reset password")),("checkout",("checkout","cart","place order")),("payment",("payment","card number","cvv")),("settings",("settings","preferences")),("profile",("profile","account details")),("search",("search",)),("error",("error","failed","invalid"))]
    for screen,keywords in rules:
        hits=sum(k in text for k in keywords)
        if hits: return screen,min(.95,.55+.13*hits)
    if "table" in types or "pagination" in types:return "table",.7
    if "text_input" in types and "button" in types:return "form",.65
    return "unknown",.35
