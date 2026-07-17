from app.image_processing.context_fusion import fuse
def test_requirement_visual_conflict_is_reported():
    result=fuse({"user_stories":["Login with email and password"]},[{"elements":[{"type":"text_input","label":"Email"}]}])
    assert any(x["type"]=="requirement_visual_mismatch" for x in result["requirement_visual_mismatches"])
