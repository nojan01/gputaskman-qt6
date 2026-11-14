# Messwerte: Vergleich zwischen TUI und Qt-6-Oberfläche

Stand: 14. November 2026. Verglichen wurden die lokale **TUI 0.4.1-8compact1**
und **Qt-GUI 0.2.0-2** für Linux amd64.

## Ergebnis

Die Qt-GUI benutzt weiterhin den Collector von **gputaskman 0.4.1**. Die
ursprünglichen Module für NVIDIA-, Intel- und AMD-Messwerte wurden für die GUI
nicht ersetzt oder umgeschrieben. Eine andere Oberfläche bedeutet deshalb keine
neue Sensorquelle. Zusätzliche Qt-Module organisieren die Erfassung mehrerer
Karten und übertragen die Ergebnisse an das Fenster.

**Nicht vollständig identisch sind jedoch Abtastzeitpunkte, Zugriffsrechte,
Geräteverwaltung, Exporthülle und Anzeige.** Deshalb sind zwei gleichzeitig
laufende Programme nicht automatisch auf die letzte Nachkommastelle identisch.

Das eingefrorene TUI-DEB wurde bei den GUI-Änderungen nicht geändert. SHA-256:

```
f7533cecf58a7611ad1c9cfdcf6497e3610e027b57909373f9b00fd59fa6acf8
```

## Woher die Werte stammen

| Anzeige / Wert | Datenquelle in beiden Varianten | Bedeutung / Einschränkung |
|---|---|---|
| NVIDIA GPU-Auslastung | NVML, `nvmlDeviceGetUtilizationRates().gpu` | Vom NVIDIA-Treiber gemeldete Auslastung. |
| NVIDIA Memory activity | NVML, `nvmlDeviceGetUtilizationRates().memory` | Speicheraktivität; **nicht** Anteil des belegten VRAM. |
| NVIDIA GPU-Speicher | NVML-Gerätespeicher und ursprüngliche Collector-Auswertung | Belegt / Kapazität der ausgewählten dedizierten GPU, soweit lesbar. |
| NVIDIA Temperatur | NVML, `nvmlDeviceGetTemperature` | GPU-Sensor, soweit vom Treiber verfügbar. |
| NVIDIA Leistung | NVML, `nvmlDeviceGetPowerUsage` | Treiberwert, von Milliwatt in Watt umgerechnet. |
| NVIDIA GPU clock | NVML, `nvmlDeviceGetClockInfo(..., NVML_CLOCK_SM)` | SM-Takt; kein neu hinzugefügter eigener Frequenzsensor. |
| NVIDIA Encoder / Decoder | NVML Encoder-/Decoder-Auslastung | Unabhängige Auslastungswerte, soweit verfügbar. |
| Intel GT-Auslastung / Video | Linux-i915-Performance-Counter über `perf_event_open` | Benötigt je nach System zusätzliche Rechte. Fehlende Rechte ergeben n/a. |
| Intel GPU-Takt | Vorhandene sysfs-GT-/RPS-Knoten | Bevorzugt tatsächlicher Takt; angeforderter Takt als vorhandener Backend-Fallback. 0 MHz im Ruhezustand kann ein echter Wert sein. |
| Intel GPU-Speicher | Ursprüngliche DRM-/fdinfo-Erfassung | Summe erreichbarer Client-Speicher, **kein garantierter vollständiger Gerätespeicher-Gesamtwert**. Gemeinsame Puffer können überlappen; nicht einsehbare Prozesse fehlen. |
| Intel Speicherkapazität | Ursprüngliche Backend-Schätzung bzw. unbekannt | Kann aus einem PCI-Fenster geschätzt sein. Bei integrierter Grafik häufig unbekannt; keine neue feste VRAM-Größe angenommen. |
| Intel Temperatur | hwmon; bei integrierter GPU gegebenenfalls vorhandener CPU-Package-Fallback | `CPU package` bezeichnet die CPU-Package-Temperatur, nicht einen separaten GPU-Sensor. Die Qt-Kachel zeigt diese Herkunft an. |
| Intel Leistung | Unterstützte hwmon-Energiezähler, alternativ RAPL-uncore | Fehlt ein geeigneter Zähler, bleibt der Wert n/a. Die Umstellung auf Qt behebt keinen fehlenden RAPL-Zähler. |
| AMD Gerätedaten | Ursprüngliche amdgpu-/sysfs-/hwmon-Erfassung | Grafik-Engine-Aktivität ist nicht automatisch gleichbedeutend mit NVIDIA-GPU-Auslastung. |
| Prozessspeicher und Engines | Ursprüngliche NVML- bzw. DRM-fdinfo-Auswertung | Unbekannte, gemessene und abgeleitete Angaben werden nicht gleichgesetzt. |
| System-RAM / CPU | Vorhandener `HostSampler` / Betriebssystem | Keine GPU-Sensoren. System-RAM und GPU-Speicher können überlappen und werden nicht addiert. |

Die verfügbaren Werte hängen weiterhin von GPU, Treiber, Kernel, Rechten und
Sichtbarkeit der Prozesse ab. Volle Rechte können keine nicht vorhandenen
Sensoren erzeugen. Insbesondere bedeutet die Meldung `no RAPL uncore zone found`
keinen Wechsel der Messmethode durch die GUI.

## Was bei der Qt-Variante geändert wurde

| Bereich | TUI | Qt-GUI 0.2.0-2 |
|---|---|---|
| Zugriffsrechte | Starter erhöht das gesamte TUI-Programm über Polkit. | Nur der separate Collector wird erhöht; das Fenster läuft unter dem aufrufenden Benutzer. `--standard-access` erlaubt einen Start ohne Erhöhung. In einer Rootshell läuft der Aufruf bereits als Root. |
| Kartenanzahl / Auswahl | Auf Linux werden beim Start die vorhandenen Karten bzw. `--gpu N` gewählt. | Persistenter Collector beobachtet alle erkannten physischen Karten; Auswahl in der GUI filtert nur die Ansicht. |
| Identität | Interne Adapter-/PCI-Zuordnung des vorhandenen Backends; TUI-Verläufe verwenden Listenindizes. | Bevorzugt PCI-verifizierte NVIDIA-UUID, sonst verifizierte PCI-Adresse, sonst ausdrücklich nur Sitzungskennung. Seriennummer zusätzlich, sofern lesbar. Kein Abgleich allein über Modellnamen. |
| Kartenwechsel | Kein entsprechender Qt-Auswahlablauf. | Kein Neustart des Collectors, keine neue Passwortabfrage nur durch Auswahlwechsel; Verlauf bleibt je Gerätekennung erhalten. |
| Geräteänderungen | Linux-Kartenauswahl wird zu Beginn aufgebaut. | Inventar wird alle fünf Sekunden geprüft. Nicht mehr erkannte Karten bleiben offline markiert. Andere Karten laufen bei gewöhnlichen Einzelfehlern weiter. |
| NVIDIA-Gerätetelemetrie | Der ursprüngliche NVML-Sampler kann die verfügbaren Geräte durchlaufen. | Die teurere Gerätetelemetrie eines Collectors wird auf dessen PCI-verifiziertes Handle eingeschränkt. Dieselben NVML-Funktionen liefern die Werte. Die vorhandene geräteübergreifende Prozess-/PID-Namensraumlogik bleibt unangetastet. |
| Prozessinspektion | Scan-Budget wird unter den beim Start gewählten Karten aufgeteilt. | Dasselbe Gesamtbudget wird unter den aktuell erkannten Karten aufgeteilt. Bei mehr Karten kann die Detailerkennung mehr Aktualisierungen benötigen. |
| System-RAM / CPU | Host-Abtastung nach den GPU-Samples eines Durchlaufs. | Ein Host-Sample pro Durchlauf vor den GPU-Samples; keine Aufsummierung pro Karte. |
| Zeitplanung | Nach der Erfassung wird das eingestellte Intervall gewartet. | Die Erfassungsdauer wird auf das gewünschte Intervall angerechnet. Lange Abfragen können das Intervall trotzdem überschreiten. |
| Verlauf | Bis zu 60 Samples; sichtbarer Ausschnitt hängt auch von der Terminalbreite ab. | Bis zu 300 Samples gespeichert; Diagramme zeigen den zurückliegenden Zeitraum von 120 Sekunden. |
| Darstellung | Zeichenbasierte Balken / Kurven; teils mehr Nachkommastellen. | Gezeichnete Kurven, gerundete Anzeigewerte und teilweise andere Einheiten. Das ändert nicht den zugrunde liegenden Sensor. |

GPU-Samples werden in beiden Abläufen nacheinander gelesen, nicht durch ein
Hardware-Synchronisationssignal gleichzeitig aufgenommen. Auch bei gleichem
Intervall können schwankende Last und unterschiedliche Abtastzeitpunkte zu
abweichenden Momentwerten führen.

Die Qt-Version setzt den Collector mit `host=False` ein. Die besondere
Windows-Host-Erfassung der TUI unter WSL wird damit nicht übernommen. Für die
hier vorgesehenen nativen Debian-/Ubuntu-/Mint-Systeme ist das kein Wechsel der
GPU-Sensorquelle. Separate MIG-Instanzen sind in der Qt-Version nicht implementiert.

## Warum das Speicherdiagramm zuletzt anders aussah

In „All GPUs“ wird die absolute Nutzung `vram_used` angezeigt. Das bisherige
Performance-Diagramm benötigte zusätzlich `vram_total` für:

```
Prozent = 100 × vram_used / vram_total
```

War die Kapazität unbekannt, war der Prozentwert ebenfalls unbekannt, obwohl
die genutzten Bytes bereits vorlagen. **Es fehlten also nicht zwangsläufig die
Nutzungsdaten, sondern die Grundlage für einen Prozentwert.** Auch das
VRAM-Verlaufsdiagramm der eingefrorenen TUI benötigt eine bekannte Kapazität.

Seit Qt-Version **0.2.0-2** gilt für Übersicht, Performance und Einzelchart:

- Kapazität bekannt: Verlauf als Prozentwert der gemeldeten Kapazität.
- Kapazität unbekannt, Nutzung bekannt: Verlauf als absolute MB/GB-Nutzung.
- Nutzung unbekannt: n/a beziehungsweise eine Lücke, kein erfundener Nullwert.
- Intel-Client-Summe bzw. Kapazitätsschätzung bleiben gekennzeichnet.

Die automatische Obergrenze eines absoluten Diagramms wird aus dem Verlauf
bestimmt. **Sie ist keine ermittelte GPU-Gesamtkapazität.** Der Fallback fügt
keinen Sensor hinzu und macht die Intel-Client-Summe nicht zu einem gemessenen
VRAM-Gesamtwert.

Beide Oberflächen verwenden bei Speichergrößen 1024er-Faktoren. Die aktuellen
Beschriftungen MB/GB entsprechen rechnerisch MiB/GiB. Die TUI rundet kleine
MB-Werte anders als die Qt-Formatierung; das kann Textanzeigen zusätzlich
unterscheiden.

## Unterschiede beim Abgreifen / Exportieren von Daten

Der gemeinsame ursprüngliche JSON-Reporter liefert weiterhin die GPU-Felder
wie `device`, `vram_used`, `vram_total`, `processes` und die Herkunftshinweise.
Die Qt-Variante ergänzt diese Daten:

- `gpu_id` und `gpu_identity`: eindeutige Gerätekennung, PCI-Adresse, UUID und
  gegebenenfalls Seriennummer sowie aktuelle Indizes.
- Prozess-RAM und Prozess-CPU aus demselben vorhandenen Host-Sampler.
- „Export snapshot“: Daten der ausgewählten Karte einschließlich Identität.
- „Export all GPUs“: Hülle mit `protocol`, `gpus`, `snapshots`, `errors`,
  `system`, `taken` und `sample_ms`.

In dieser Hülle ist `snapshot` zusätzlich eine Kompatibilitätskopie eines
Eintrags aus `snapshots`. **Nicht beide zusammen als zusätzliche GPU zählen.**
Systemwerte innerhalb einzelner Snapshots ebenfalls nicht pro GPU addieren.

Die JSON-Gerätetelemetrie bewahrt die vom Backend gelieferten Zahlen und
unbekannten Werte; die Rundung im Fenster ist eine Anzeigeentscheidung.
Nicht jedes TUI-Zusatzfeld hat in der Qt-GUI ein eigenes sichtbares Feld;
beispielsweise können weitere Takt-, PCIe- und Treiberwerte weiterhin im
`device`-Objekt des Exports stehen. Ein nicht eingeblendetes Feld bedeutet
nicht automatisch, dass die Datenerfassung dafür entfernt wurde.

## Grundlage und Grenzen der Prüfung

Verglichen wurden die vorhandenen Quellen:

- Gemeinsamer Kern: `gputaskman-source/src/gputaskman/collector.py`,
  `nvml.py`, `linux.py`, `drm.py`, `host.py`, `report.py`, `telemetry.py`.
- TUI: `gputaskman-source/src/gputaskman/app.py`.
- Qt: `gputaskman-qt6/worker.py`, `fleet.py`, `identity.py`, `gui.py`.

Die native Intel-Erfassung und das Verhalten der Oberflächen wurden geprüft.
Für Qt 0.2.0-2 sind 27 automatisierte Tests erfolgreich. Systeme mit 4, 8 und
16 gleichnamigen NVIDIA-Karten wurden simuliert. Das ist **keine Messvalidierung
auf einem realen Multi-NVIDIA-Server** und keine Zusage identischer Messwerte
bei unterschiedlichen Treibern oder Rechten.

Diese Dokumentation beschreibt den bestehenden Stand. Für ihre Erstellung
wurden weder die TUI noch die Qt-Programme, Collector-Dateien oder DEB-Pakete
verändert.

## Nachtrag: Refresh-Rate ab Qt 0.2.0-3

Eine Änderung der Refresh-Rate wird jetzt als validierte Intervallnachricht
über die bestehende Verbindung an den laufenden Collector gesendet. Sein
Prozess und seine Berechtigung bleiben bestehen; es gibt dafür keine neue
Passwortabfrage. GPU-Verläufe und Pausenzustand bleiben erhalten. Die Werte
werden weiterhin mit denselben Sensorfunktionen erfasst. Der Export der
Gesamthülle enthält zusätzlich `interval_seconds` als bestätigten Collector-Takt.
Ein expliziter Neustart/Reconnect oder ein Wechsel des Zugriffsmodus kann
weiterhin eine Authentifizierung benötigen.
