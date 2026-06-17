# Skill: OpenCode Agent

Der OpenCode Agent übergibt ausdrücklich adressierte Aufgaben an die lokal
installierte OpenCode CLI. OpenCode arbeitet in einem zuvor freigegebenen
Projektordner und kann dort vorhandene Projektregeln, Agenten und
Automationspipelines nutzen.

## Trigger

- `OpenCode`
- `Open Code`
- `open-code`

Beispiele:

> „Trinity, nutze OpenCode im Projekt Automatismen. Prüfe meine Mails und
> erstelle passende Entwürfe.“

> „Trinity, OpenCode im Projekt Lehre: bereite die PDF-Unterlagen vor.“

## Sicherheit

- OpenCode wird nur über explizite Trigger gestartet.
- OpenCode darf nur in freigegebenen Projektordnern laufen.
- Fernausgelöste Läufe sollen E-Mails, Veröffentlichungen, Deployments,
  Käufe oder irreversible Aktionen nur vorbereiten und nicht selbst ausführen.

## Einrichtung

1. OpenCode auf dem Host installieren und einmal anmelden.
2. In Trinity **Einstellungen → OpenCode** den Agenten aktivieren.
3. Mindestens ein Projekt als `Name = /vollständiger/Pfad` freigeben.
4. Optional `agent` und `model` setzen, z.B. `build` oder `plan`.
