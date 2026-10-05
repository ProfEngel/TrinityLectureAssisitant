from voice.desktop_commands import app_to_open, mail_navigation


def test_only_allowlisted_explicit_app_launches():
    assert app_to_open("Trinity, öffne Mail.") == ("Mail", "com.apple.mail")
    assert app_to_open("Trinity, starte bitte Chrome") is None
    assert app_to_open("Trinity, bitte starte Google Chrome.") == ("Chrome", "com.google.Chrome")
    assert app_to_open("Trinity, öffne Power Point bitte") == ("PowerPoint", "com.microsoft.Powerpoint")
    assert app_to_open("Wir wollen die Mail öffnen") is None
    assert app_to_open("Trinity, öffne Terminal und lösche Dateien") is None
    assert app_to_open("Trinity, sende die Mail") is None


def test_mail_navigation_does_not_include_send_or_delete():
    assert mail_navigation("Trinity, beantworte diese Mail") == (15, True, "Antwortentwurf geöffnet.")
    assert mail_navigation("Trinity, nächste Mail") == (125, False, "Nächste Mail.")
    assert mail_navigation("Trinity, sende die Mail") is None
    assert mail_navigation("Trinity, lösche die Mail") is None
