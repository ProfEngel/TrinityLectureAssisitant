from content_vault import (
    PHASE1_VAULT_DIRECTORIES,
    ensure_content_vault_layout,
    inspect_content_vault,
    normalize_profile,
    validate_content_vault_location,
)
from trinity_paths import TrinityPaths


def test_new_private_vault_gets_understandable_phase1_structure(tmp_path):
    root = tmp_path / "BrainVault"

    result = ensure_content_vault_layout(root, profile="PRIVAT")

    assert result["created_root"] is True
    assert result["preserved_entries"] == []
    assert (root / "README.md").is_file()
    assert all((root / name).is_dir() for name in PHASE1_VAULT_DIRECTORIES)
    assert not (root / "Projects").exists()
    assert not (root / "Outputs").exists()


def test_existing_content_is_adopted_without_being_moved_or_overwritten(tmp_path):
    root = tmp_path / "Existing"
    existing = root / "Mein altes Projekt"
    existing.mkdir(parents=True)
    source = existing / "wichtig.txt"
    source.write_text("Original", encoding="utf-8")

    result = ensure_content_vault_layout(root, profile="BIZ")

    assert result["created_root"] is False
    assert result["preserved_entries"] == ["Mein altes Projekt"]
    assert source.read_text(encoding="utf-8") == "Original"
    inventory = root / "90 Inhaltsverzeichnis und Schlagwörter" / "BESTAND_BEI_EINRICHTUNG.md"
    assert inventory.is_file()
    assert "Mein altes Projekt" in inventory.read_text(encoding="utf-8")


def test_repeated_setup_does_not_duplicate_or_rewrite_existing_files(tmp_path):
    root = tmp_path / "BrainVault"
    ensure_content_vault_layout(root, profile="PRIVAT")
    readme = root / "README.md"
    readme.write_text("Meine eigene Erklärung\n", encoding="utf-8")

    result = ensure_content_vault_layout(root, profile="PRIVAT")

    assert result["created_directories"] == []
    assert result["readme_created"] is False
    assert readme.read_text(encoding="utf-8") == "Meine eigene Erklärung\n"
    assert inspect_content_vault(root)["missing_directories"] == []


def test_vault_must_not_contain_installation_or_runtime(tmp_path):
    installation = tmp_path / "Trinity"
    vault = installation / "BrainVault"

    try:
        validate_content_vault_location(vault, forbidden_roots=[installation])
    except ValueError as exc:
        assert "getrennt" in str(exc)
    else:
        raise AssertionError("Vault inside installation should be rejected")


def test_profile_names_are_normalized_for_visible_german_choices():
    assert normalize_profile("beruf") == "BIZ"
    assert normalize_profile("Privat") == "PRIVAT"
    assert normalize_profile("Testbereich") == "TEST"


def test_business_onedrive_vault_is_recognized_as_cloud_location(tmp_path):
    config = {
        "system": {"profile": "BIZ"},
        "control_plane": {
            "runtime_root": str(tmp_path / "local" / "TrinityRuntime"),
            "vault_root": str(tmp_path / "OneDrive-Hochschule" / "BizVault"),
        },
    }

    paths = TrinityPaths.from_config(tmp_path / "Trinity", config)

    assert paths.profile == "BIZ"
    assert not any(
        "nicht in einem erkennbaren Cloud-Ordner" in item
        for item in paths.separation_warnings()
    )
