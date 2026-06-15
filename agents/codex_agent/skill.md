# Skill: Codex Agent

## Beschreibung

Der Codex Agent übergibt ausdrücklich adressierte Aufgaben an die lokal installierte
Codex CLI. Codex arbeitet in einem zuvor freigegebenen Projektordner und kann dort die
vorhandenen Projektregeln, Skills und auf Anforderung Subagenten verwenden.

Typischer Einsatz:

> „Trinity, nutze Codex im Projekt Automatismen. Prüfe meine aktuellen Mails und
> erstelle passende Antwortentwürfe.“

## Sicherheitsmodell

- Nur in Trinitys Einstellungen freigegebene Projektordner sind auswählbar.
- Standardmäßig gilt Codex `workspace-write`; Schreibzugriff bleibt auf das Projekt
  begrenzt.
- Netzwerkzugriff für von Codex gestartete Befehle ist standardmäßig deaktiviert.
- Der Lauf verwendet keine interaktiven Freigaben. Aktionen außerhalb der Sandbox
  schlagen fehl.
- E-Mails und Nachrichten werden nur als Entwurf vorbereitet.
- Versand, Veröffentlichung, Käufe, Löschungen, Pushes und Deployments sind in
  fernausgelösten Läufen untersagt.

## Einrichtung

1. Codex auf dem Host installieren und einmal anmelden.
2. In Trinity **Einstellungen → Codex** den Agenten aktivieren.
3. Projekte zeilenweise als `Name = vollständiger Ordnerpfad` freigeben.
4. Optional einen Projektnamen als Standard festlegen.

## Trigger

- `Codex`
- `Kodeks`
- `Code X`

Der Trigger muss ausdrücklich genannt werden, damit normale Mail- oder
Recherchebefehle weiterhin von Trinitys eigenen Skills bearbeitet werden.
