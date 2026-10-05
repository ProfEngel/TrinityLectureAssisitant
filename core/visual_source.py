"""The selected speech output is the sole owner of visual context."""
import json
from pathlib import Path


def visual_output(home):
    try:
        config = json.loads((Path(home) / 'core/config.json').read_text(encoding='utf-8'))
        output = config.get('system', {}).get('speech_output', {})
        return output if isinstance(output, dict) else {}
    except (OSError, ValueError):
        return {}


def owns_visual_context(home, device_id, kind, updated_at=None):
    output = visual_output(home)
    return bool(device_id and output.get('device_id') == device_id
                and output.get('kind') == kind
                and (updated_at is None or updated_at >= float(output.get('updated_at') or 0)))
