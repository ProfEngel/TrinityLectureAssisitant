import copy
from types import SimpleNamespace

from agents.comfyui_agent import script as agent


def test_qwen_prompt_injection_keeps_models_and_changes_seed():
    workflow = agent._load_workflow('qwenimage2.1_t2i_API.json')
    original = copy.deepcopy(workflow)
    updated = agent._inject_prompt(workflow, 'An English pastel infographic about attention.')
    assert workflow == original
    nodes = [n for n in updated.values() if n['class_type'] == 'TextEncodeQwenImage21']
    assert nodes[0]['inputs']['prompt'].startswith('An English')
    assert updated['459:451'] == original['459:451']
    assert updated['459:458']['inputs']['seed'] != original['459:458']['inputs']['seed']


def test_qwen_reference_input_uses_actual_nodes():
    workflow = agent._load_workflow('qwenimage2.1_1i2i_API.json')
    updated = agent._inject_i2i_inputs(workflow, 'Make the background pastel.', 'uploaded.png')
    assert updated['470']['inputs']['image'] == 'uploaded.png'
    assert updated['459:474']['inputs']['prompt'] == 'Make the background pastel.'


def test_qwen_has_dedicated_english_prompt_policy():
    messages = []
    brain = SimpleNamespace(comfyui_workflow='qwenimage2.1_t2i_API.json',
        ask_llm=lambda m: messages.extend(m) or 'A coherent English infographic with pastel colors.')
    assert agent._extract_prompt('Eine Infografik zu KI', brain).startswith('A coherent')
    assert messages[0]['role'] == 'system'
    assert 'English' in messages[0]['content'] and 'pastel' in messages[0]['content']
    assert messages[1]['content'] == 'Eine Infografik zu KI'


def test_download_keeps_subfolder_and_safe_name(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(agent, 'MEDIA_OUTPUT_DIR', str(tmp_path))
    def get(url, **kwargs):
        seen.append(kwargs['params'])
        return SimpleNamespace(status_code=200, content=b'PNG test')
    monkeypatch.setattr(agent.requests, 'get', get)
    assert agent._download_image('http://comfy', {'filename': 'one.png', 'subfolder': 'Qwen', 'type': 'output'})
    assert seen[0]['subfolder'] == 'Qwen'
    assert agent._download_image('http://comfy', {'filename': '../escape.png'}) is None


def test_legacy_flux_and_html_escape():
    flux = {'14': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'old'}}}
    assert agent._inject_prompt(flux, 'new')['14']['inputs']['text'] == 'new'
    assert '<script>' not in agent._build_image_payload('/tmp/test.png', '<script>bad</script>')
