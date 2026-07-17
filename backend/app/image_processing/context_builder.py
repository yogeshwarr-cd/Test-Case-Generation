HINTS={"text_input":["Verify the field is visible","Verify valid text can be entered","Verify required empty-field behavior"],"password_input":["Verify password characters are masked","Verify empty-password validation"],"button":["Verify button visibility and keyboard focus","Verify duplicate submissions are prevented"],"dropdown":["Verify options open and keyboard selection works"],"checkbox":["Verify checked and unchecked states"],"error_message":["Verify the error is associated with the correct field"]}
def build_context(image_id,screen_type,screen_confidence,elements,ocr_items,image_description):
    headings=[x.text for x in ocr_items if len(x.text)<80][:5];hints=[];actions=[]
    for element in elements:
        hints.extend(HINTS.get(element.type,[]))
        if element.label: actions.append(f"Use {element.label} {element.type.replace('_',' ')}")
    warnings=[]
    if screen_type=="unknown":warnings.append("Screen type could not be classified confidently")
    return {"image_id":image_id,"screen_type":screen_type,"screen_confidence":round(screen_confidence,3),"description":image_description,"page_titles":headings,"elements":[{"element_id":x.element_id,"type":x.type,"label":x.label,"required":x.required,"enabled":x.enabled,"confidence":round(x.confidence,3),"source":x.detection_source} for x in elements[:30]],"visible_messages":headings[:10],"possible_actions":list(dict.fromkeys(actions))[:20],"test_hints":list(dict.fromkeys(hints))[:30],"warnings":warnings}
