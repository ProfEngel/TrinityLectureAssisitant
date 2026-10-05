"""Reversible runtime switch; preserves all other config and credentials."""
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1]).resolve() / 'core/config.json'
enabled = sys.argv[2] == 'on'
data = json.loads(path.read_text())
backup = path.with_name('config.json.pre-sentence-stream-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
shutil.copy2(path, backup)
data.setdefault('system', {})['voice_sentence_streaming'] = enabled
temp = path.with_suffix('.sentence-stream.tmp')
temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
temp.chmod(0o600)
temp.replace(path)
print('Sentence streaming:', enabled, '; configuration backup created')
