# Datenschutz- und Compliance-Dokumentation (DSGVO)
**Projekt:** Trinity KI-Assistent
**Einsatzort:** Hochschule für Wirtschaft und Umwelt Nürtingen-Geislingen (HfWU)
**Verantwortlich:** Prof. Dr. Mathias Engel

---

## 1. Systemarchitektur & Datenfluss
Der "Trinity"-Assistent ist eine hybride KI-Lösung, die zur Unterstützung der Lehre im Hörsaal eingesetzt wird. Die Architektur wurde nach dem Prinzip "Privacy by Design" (Art. 25 DSGVO) konzipiert.

- **Audio-Verarbeitung (Gehör):** Erfolgt zu **100% lokal** auf der Hardware (Apple Silicon M-Prozessor) via `mlx-whisper`. Es werden **keine** Audio- oder Sprachaufzeichnungen an externe Server oder Cloud-Dienste gesendet.
- **Sprachausgabe (Stimme):** Erfolgt lokal über die systeminterne Text-to-Speech Engine (macOS Siri-Voice).
- **Text-Verarbeitung (Gehirn):** Nur wenn das dedizierte Wake-Word ("Trinity") durch den Dozenten ausgesprochen wird, wird der unmittelbar vorhergehende Text-Kontext via API an ein Large Language Model (LLM) gesendet.

---

## 2. Rechtliche Bedenken & Schutzmaßnahmen

### 2.1 Verletzung der Vertraulichkeit des Wortes (§ 201 StGB)
Das System nutzt "Ambient Listening", um das Wake-Word zu erkennen. Nach § 201 StGB ist die unbefugte Aufnahme des nichtöffentlich gesprochenen Wortes strafbar.
* **Maßnahme (Hardware-Filter):** Es wird ein **Lavalier-Headset** (Richtmikrofon nah am Körper des Dozenten) verwendet. 
* **Wirkung:** Durch die physische Distanz und die Software-seitige Pegel-Schwelle (Silence Threshold) werden Wortmeldungen von Studierenden aus dem Plenum herausgefiltert und weder erfasst noch transkribiert. Das System zeichnet faktisch nur den Dozenten auf.

### 2.2 Verarbeitung personenbezogener Daten (Art. 4 Nr. 1, Art. 5 DSGVO)
Sollten trotz der Hardware-Filterung versehentlich persönliche Äußerungen von Studierenden (z.B. Namen) in Text transkribiert werden, greift die DSGVO.
* **Maßnahme (Datenminimierung & Zero-Retention):** Für die LLM-Verarbeitung wird der Dienstleister OpenRouter genutzt. Der Account ist auf **"Zero Data Retention"** konfiguriert. Das bedeutet, dass übermittelte Text-Prompts von den Servern der Modell-Anbieter (z.B. OpenAI, Google, Anthropic) **nicht** für das Training eigener KI-Modelle gespeichert oder weiterverwendet werden dürfen. Die Datenverarbeitung erfolgt streng flüchtig.
* **Perspektive:** Die Architektur ist modular aufgebaut und sieht den baldigen Wechsel auf ein vollständig lokal gehostetes LLM (z.B. Llama 3 via Ollama) vor, womit auch die Text-Übermittlung an Drittanbieter vollständig entfällt.

### 2.3 Rechtmäßigkeit der Verarbeitung & Einwilligung (Art. 6 Abs. 1 lit. a DSGVO)
Um absolute Rechtssicherheit zu gewährleisten, bedarf es der Transparenz gegenüber den betroffenen Personen (Studierenden).
* **Organisatorische Maßnahme:** Zu Beginn der Veranstaltung bzw. des Semesters werden die Studierenden explizit auf den Einsatz des lokalen KI-Assistenten hingewiesen (z.B. durch eine Präsentationsfolie). 
* Wer sich aktiv an der Vorlesung beteiligt (Fragen stellt), stimmt der potenziellen, temporären und anonymisierten Verschriftlichung konkludent zu. 

---

## 3. Lokale Speicherung (Speicherbegrenzung gem. Art. 5 Abs. 1 lit. e DSGVO)
Das System speichert die transkribierten Texte der Vorlesung in einer lokalen Markdown-Datei (`Sitzung_YYYY-MM-DD.md`) im Projektverzeichnis.
* **Schutz:** Diese Daten verlassen das lokale Dateisystem (bzw. den gesicherten iCloud-Vault des Dozenten) nicht. 
* Da die Aufzeichnung durch das Headset primär nur den Dozenten erfasst, handelt es sich bei dem Transkript inhaltlich um ein automatisch erstelltes **Vorlesungsskript** und nicht um ein Verzeichnis von Studierendendaten.

## Fazit
Durch die Kombination aus lokaler Audio-Verarbeitung, restriktiver Mikrofon-Hardware (Lavalier), Zero-Data-Retention-Policies bei der Textverarbeitung und organisatorischer Transparenz ist der Einsatz von Trinity DSGVO-konform und datenschutzrechtlich unbedenklich umsetzbar.
