import base64
import json

from desktop_context import DesktopContextStore
from lecture_context import LectureContextStore


def test_only_output_can_upload_and_stale_frames_stay_revoked(tmp_path):
    config = tmp_path / 'core/config.json'
    config.parent.mkdir()
    def output(kind, device, timestamp=0):
        config.write_text(json.dumps({'system': {'speech_output': {
            'kind': kind, 'device_id': device, 'updated_at': timestamp},
            'audio_input': {'kind': 'g2', 'device_id': 'glasses'}}}))
    mac = DesktopContextStore(tmp_path)
    slides = LectureContextStore(tmp_path)
    image = base64.b64encode(b'\xff\xd8\xfftest').decode()
    frame = {'client_id': 'mac-process', 'device_id': 'desktop:mac', 'sequence': 1,
             'active': True, 'image_base64': image}
    slide = {**frame, 'client_id': 'ipad-process', 'device_id': 'ipad'}
    scope = {'profile': 'TEST', 'session_id': 'one'}
    output('desktop', 'desktop:mac')
    assert mac.update(frame, **scope)['has_image']
    assert slides.update(slide, **scope)['ignored']
    assert mac.current(**scope, device_id='desktop:mac')
    output('companion', 'ipad')
    assert mac.current(**scope, device_id='desktop:mac') is None
    assert mac.update({**frame, 'sequence': 2}, **scope)['ignored']
    assert slides.update(slide, **scope)['has_image']
    assert slides.current(**scope)
    assert slides.update({**slide, 'device_id': 'iphone', 'sequence': 3}, **scope)['ignored']
    # Returning to a device never revives its old frame from the previous lease.
    output('desktop', 'desktop:mac', mac._read()['updated_at'] + .01)
    assert mac.current(**scope, device_id='desktop:mac') is None
    assert slides.current(**scope) is None
    output('none', 'none')
    assert slides.update({**slide, 'sequence': 4}, **scope)['ignored']
    assert mac.update({**frame, 'sequence': 4}, **scope)['ignored']
