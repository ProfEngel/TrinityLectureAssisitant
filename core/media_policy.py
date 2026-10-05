"""Explicit local requests and strict song-creation intent."""
import re
from image_routing import is_image_request


def wants_local_media(query):
    return bool(re.search(r"\b(lokal\w*|comfyui)\b", str(query or "").lower()))


def wants_song(query):
    text = str(query or "").lower()
    if is_image_request(text) or re.search(r"was hältst du|was haeltst du|was meinst du davon|wie funktioniert", text):
        return False
    medium = re.search(r"\b(?:\w*musik\w*|\w*lied\w*|\w*song\w*)\b", text)
    action = re.search(r"\b(?:erstell\w*|erzeug\w*|generier\w*|komponier\w*|produzier\w*|mach(?:e)?|möchte|hätte)\b", text)
    return bool(medium and action)
