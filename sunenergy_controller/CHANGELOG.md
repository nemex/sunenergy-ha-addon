# Changelog

## v1.9.9
- **Fix Dockerfile**: Kopieren von `analyse.html` in den Docker-Container hinzugefügt, um den Fehler "Analyse-Datei nicht gefunden" zu beheben.

## v1.9.8
- **Analyse-Dashboard Integration**: Das Premium-Analyse-Dashboard wurde direkt in die Weboberfläche eingebaut und ist über den Button "Systemanalyse" im Footer erreichbar. Die Logdaten werden vollautomatisch geladen.
- **Unbegrenztes Logging**: Das automatische Kürzen des CSV-Logs nach 2 MB wurde deaktiviert, um den gesamten Verlauf dauerhaft zu speichern.

## v1.9.7
- **Fix Manuelle Einspeisung**: Verhindert das Drosseln der DC-PV-Module (Carport) am SunEnergy XT auf Minimalwerte (z. B. 30 W / 1 %) während der manuellen Einspeisung. Setzt das IS-Limit während dieser Phase dauerhaft auf 2400 W (100 %).

## v1.9.6
- **Konfigurations-Update**: Standard-Zielmenge für die manuelle Einspeisung (`manual_feed_in_target`) von 0,5 kWh auf 1,0 kWh erhöht.

## v1.9.5
- **Stabilitäts-Fix Sonnenstand**: Cacht den letzten bekannten Sonnenstand (aus `sun.sun`). Verhindert, dass kurzzeitige Verbindungsabbrüche oder Timeouts der Home Assistant API das Add-on fälschlicherweise mitten am Tag in den Nachtmodus (mit Deaktivierung von MM) versetzen.

## v1.9.4
- **Priorisierung Batterieladung**: Wenn die Batterie leer ist und geladen werden kann, werden die Hoymiles-Wechselrichter voll geöffnet (3600 W). Dies maximiert die Solarstrom-Erzeugung zum Laden der Batterie und verhindert künstliches Drosseln am Morgen oder bei wechselhaftem Wetter.

## v1.9.3
- **Optimierung Hoymiles-Freigabe**: Bezieht die aktive Batterie-Entladung als virtuellen Bedarf in die Hoymiles-Drosselregelung ein. Verhindert, dass die Hoymiles bei aktivem Akkubetrieb künstlich gedrosselt bleiben, und schont so die Batteriekapazität.

## v1.9.2
- **Ingress-Support**: Web-UI direkt in der HA-Sidebar (auch remote via Nabu Casa).
- **Shelly-Direkt-Fallback**: Holt Grid-Daten bei HA-API-Störungen direkt vom Shelly (vermeidet Fehl-Safety-Stopps).
- **Zwangsladung Spam-Schutz**: Schreibt GS- und MM-Werte nur bei Eintritt/Änderung (schont den Geräte-Flash des SunEnergyXT).
- **Hardware-Schonung**: Throttled State-Saving schont die SD-Karte/SSD durch selteneres Schreiben des Zustands.
- **Sauberer Shutdown**: Übergibt Steuerung bei Addon-Stopp an die Geräte-Selbstregelung.
- **Persistent HTTP-Sessions**: Reduziert Latenz durch Keep-Alive-Verbindungen.
- **Stabilitäts- & Web-Fixes**: Supervisor-Watchdog für `/state`, Threading-Webserver (kein Blockieren bei Shelly-Timeout), `/log/delete` auf POST beschränkt (Schutz vor Browser-Prefetching).

## v1.9.1
- **Morgendliche Kalibrierung**: Kalibrierung wird am Fälligkeitstag ab 10:00 Uhr freigegeben, um die Sonnenstunden maximal zu nutzen.

## v1.9.0
- **Solare Kalibrierung**: Erhöht das Ladelimit tagsüber auf 100 % für kostenloses Laden mit PV-Überschuss. Netzladung dient nur noch als Nacht-Backup.

## v1.8.9
- **API-Fix**: Wechsel zurück zu `python:3.11-alpine` löst den *401 Unauthorized* Fehler der HA-API.

## v1.8.8
- **Boot-Fix**: Deaktivierung des Init-Systems löst die s6-overlay PID-1 Endlosschleife.

## v1.8.7
- **Inverter-Schutz**: Sanfter Anstieg (+1000W pro Tick) verhindert Firmware-Spikes beim Entdrosseln.
- **Stabilitäts-Fix**: run.sh überwacht beide Prozesse (`wait -n`) für sauberen Container-Neustart.

## v1.8.6
- **Verbrauchs-Fix**: Korrektur der Hausverbrauchs-Berechnung während der Akku-Ladung.

## v1.8.5
- **Virtuelle HA-Sensoren**: Pusht berechnete Werte alle 5s direkt als native HA-Entitäten.

## v1.8.4
- **Bugfixes**: Behebt Probleme beim Initial-Write, Kalibrierungs-Direkt-Write, Moduswechsel-Reset und setzt HMS-Baseline-Boden auf 300W.
