"""Image creation is raster-only; never route it to diagram/code tools."""
import re


def is_image_request(query):
    text = str(query or "").lower()
    medium = re.search(r"\b(bild(?:er)?|schaubild(?:er)?|diagramm(?:e)?|(?:info)?grafik(?:en)?|illustration(?:en)?|zeichnung(?:en)?|chart(?:s)?)\b", text)
    action = re.search(r"\b(erstell\w*|erzeug\w*|generier\w*|produzier\w*|render\w*|zeichn\w*|visualisier\w*|mach(?:e)?(?=\s+(?:uns|mir|bitte|ein|eine|daraus|das))|zeige?|hätte|haette|möchte|moechte|brauche|will)\b", text)
    implicit_request = re.search(r"\b(ein(?:e|en)?|neue[sn]?)\s+(?:bild|schaubild|diagramm|(?:info)?grafik|illustration|zeichnung|chart)\b", text)
    explanation = re.search(r"\b(erklär\w*|erklaer\w*|analysier\w*|was ist|was zeigt|wie funktioniert|was siehst)\b", text)
    return bool(medium and (action or (implicit_request and not explanation)))


def external_image_requested(query):
    text = str(query or "").lower()
    return is_image_request(text) and ("extern" in text or "fal.ai" in text or "fal ai" in text or "kie.ai" in text)


def image_skill_allowed(skill, query, provider="comfyui"):
    name = getattr(skill, "__name__", "")
    from media_policy import wants_local_media
    if provider == "kie" and not wants_local_media(query):
        return "kie_media_agent" in name
    if wants_local_media(query):
        return "comfyui_agent" in name
    expected = "image_agent" if external_image_requested(query) else "comfyui_agent"
    return expected in name and (expected != "image_agent" or "comfyui_agent" not in name)
