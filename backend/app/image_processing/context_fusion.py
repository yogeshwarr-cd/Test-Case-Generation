def fuse(text_payload,visual_contexts):
    text=" ".join(str(x) for key in ("user_stories","features","epics") for x in text_payload.get(key,[])).lower();warnings=[]
    visual_types={element.get("type") for context in visual_contexts for element in context.get("elements",[])}
    visual_labels=" ".join(str(element.get("label") or "").lower() for context in visual_contexts for element in context.get("elements",[]))
    checks=[("password","password_input"),("email","text_input"),("search","search_box")]
    for keyword,element_type in checks:
        if keyword in text and keyword not in visual_labels and element_type not in visual_types:
            warnings.append({"type":"requirement_visual_mismatch","message":f"Text requirements mention {keyword}, but no matching visible control was detected.","severity":"high"})
    return {"images":visual_contexts,"requirement_visual_mismatches":warnings,"source_priority":["user_stories","features","epics","image_context"]}
