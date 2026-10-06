import concurrent.futures
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from sound_deck import SoundDeck
from trinity_bridge import TrinityBridge, make_handler


@pytest.fixture
def deck(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "core/config.json").write_text(json.dumps({"system": {"profile": "PRIVAT",
        "speech_output": {"device_id": "ipad", "kind": "companion"}}}))
    library = tmp_path / "TrinityRuntime/sounddeck"
    library.mkdir(parents=True)
    (library / "igel.mp3").write_bytes(b"private audio")
    (library / "jubel.mp3").write_bytes(b"private audio 2")
    (library / "manifest.json").write_text(json.dumps({"sounds": [
        {"id": "igel", "name": "Igel", "duration": 3}, {"id": "jubel", "name": "Jubel", "duration": 10}]}))
    return SoundDeck(tmp_path)


@pytest.mark.parametrize("command", ["Trinity, Igel!", "Trinity, spiele Igel", "Trinity, Igel bitte", "Trinity, spiel Igel ab."])
def test_named_voice_command(deck, command):
    assert deck.execute_voice(command)
    assert deck.state()["sound_id"] == "igel"


@pytest.mark.parametrize("prose", ["Der Igel ist ein Tier", "Trinity, was ist ein Igel?", "Erkläre Jubel", "Igel und Jubel", "Erstelle ein Lied"])
def test_prose_is_never_a_play_command(deck, prose):
    assert deck.command(prose) is None


def test_toggle_and_replacement_one_sound(deck):
    first = deck.toggle("igel")
    assert first["active"]
    assert not deck.toggle("igel")["active"]
    assert deck.toggle("igel")["active"]
    latest = deck.toggle("jubel")
    assert latest["sound_id"] == "jubel" and latest["active"]
    assert deck.acknowledge(first["revision"], "ipad", "ended")["revision"] == latest["revision"]


def test_owner_fence_and_natural_end(deck):
    state = deck.toggle("igel")
    assert not deck.acknowledge(state["revision"], "iphone", "playing")["playing"]
    assert deck.acknowledge(state["revision"], "ipad", "playing")["playing"]
    assert not deck.acknowledge(state["revision"], "ipad", "ended")["active"]


def test_output_handoff_stops_not_replays(deck):
    deck.toggle("igel")
    (deck.home / "core/config.json").write_text(json.dumps({"system": {"speech_output": {"device_id": "iphone", "kind": "companion"}}}))
    assert not deck.state()["active"]


def test_offline_timeout(deck, monkeypatch):
    state = deck.toggle("igel")
    monkeypatch.setattr("sound_deck.time.time", lambda: state["lease_until"] + 1)
    assert not deck.state()["active"]


def test_stop_voice_command(deck):
    deck.toggle("igel")
    assert deck.execute_voice("Trinity, Deck stoppen!")
    assert not deck.state()["active"]


def test_serialized_two_clicks(deck):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        list(pool.map(lambda _: deck.toggle("igel"), range(2)))
    assert not deck.state()["active"]


def test_paths_whitelisted_and_symlinks_blocked(deck, tmp_path):
    with pytest.raises(ValueError):
        deck.media("../core/config")
    (tmp_path / "secret.mp3").write_bytes(b"secret")
    (deck.root / "igel.mp3").unlink()
    (deck.root / "igel.mp3").symlink_to(tmp_path / "secret.mp3")
    with pytest.raises(ValueError):
        deck.media("igel")


def test_auth_catalog_and_audio(deck):
    bridge = TrinityBridge(deck.home, token="test-secret")
    bridge.is_loopback_request = lambda _: False
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(bridge))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(url + "/deck/catalog")
        assert error.value.code == 401
        with urlopen(Request(url + "/deck/catalog", headers={"Authorization": "Bearer test-secret"})) as response:
            catalog = json.load(response)
        assert len(catalog["sounds"]) == 2
        assert "source" not in catalog["sounds"][0]
        with urlopen(Request(url + "/deck/audio/igel", headers={"Authorization": "Bearer test-secret"})) as response:
            assert response.read() == b"private audio"
    finally:
        server.shutdown(); server.server_close(); thread.join()
