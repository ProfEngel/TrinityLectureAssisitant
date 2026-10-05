"""Reuse the installed VAD cache without a GitHub default-branch probe."""
from pathlib import Path


def install_cached_vad_loader():
    import torch
    if getattr(torch.hub.load, '_trinity_cached_vad', False):
        return
    original = torch.hub.load

    def load(repo_or_dir, model, *args, **kwargs):
        if repo_or_dir == 'snakers4/silero-vad' and kwargs.get('source', 'github') == 'github':
            cache = Path(torch.hub.get_dir()) / 'snakers4_silero-vad_master'
            if (cache / 'hubconf.py').is_file():
                repo_or_dir = str(cache)
                kwargs['source'] = 'local'
        return original(repo_or_dir, model, *args, **kwargs)

    load._trinity_cached_vad = True
    torch.hub.load = load
