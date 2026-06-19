import pytest

from server_auth import ServerAuth


def test_first_account_is_admin_and_password_is_not_persisted(tmp_path):
    auth = ServerAuth(tmp_path)

    issued = auth.register_first_admin("Mathias", "ein-langes-passwort")

    assert issued["user"]["role"] == "admin"
    assert auth.authenticate(issued["token"])["username"] == "Mathias"
    persisted = (tmp_path / "memory" / "server_users.json").read_text(encoding="utf-8")
    assert "ein-langes-passwort" not in persisted


def test_only_admin_can_create_additional_account(tmp_path):
    auth = ServerAuth(tmp_path)
    admin = auth.register_first_admin("Admin", "ein-langes-passwort")
    actor = auth.authenticate(admin["token"])

    user = auth.create_user(actor, "Kollegin", "zweites-langes-passwort")

    assert user["role"] == "user"
    assert auth.login("Kollegin", "zweites-langes-passwort")["user"]["username"] == "Kollegin"
    with pytest.raises(PermissionError):
        auth.create_user({"role": "user"}, "Dritter", "noch-ein-passwort")
