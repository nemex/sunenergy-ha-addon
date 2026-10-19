# Changelog

## v3.5.8
- **Regeltakt 2 s statt 5 s**: Der Regler reagiert schneller auf Laständerungen und hält das Netz genauer bei null. Im digitalen Zwilling (10 echte Herbsttage, 3 Sommerwochen, 1 Winterwoche) sank der Netzbezug um ~71 Wh pro Tag, ohne dass die Regelung unruhiger wurde. Am Volltag 19.10. mit echtem 1-s-Hausprofil: Bezug bei vollen Akkus −24 %.
- **Gerätetest vorab (19.10.)**: 230 von 230 Schreibvorgängen an die Speicher kamen an (~17 ms), die Leistung folgte einem Wechsel alle 2 s voll.
- **Fristen in Sekunden statt in Takten**: Aussetzer-Filter (15 s), PV-Watchdog (5 min), MPPT-Hänger-Erkennung (20 s) und Nachsenden der Hoymiles-Grenze (30 s) behalten ihre bisherige Dauer.
- **Hoymiles-Grenze höchstens alle 5 s** je Wechselrichter, wie bisher. Die DTU funkt jeden Befehl einzeln.
- **HA-Sensoren und Tageslog weiter im 5-s-Raster**, damit der HA-Recorder, die Analyse-Seite und die Auswertungen unverändert bleiben.
- **Sollwert nicht mehr zusätzlich über HA**: Das Add-on schrieb jede Sollwert-Änderung direkt an den Speicher und zusätzlich über die HA-Entität. Die Integration schickte sie dann ein zweites Mal übers WLAN, ~4 700-mal pro Speicher und Tag, und eine verspätete Kopie konnte kurz einen alten Wert setzen. Die Entität zeigt den Sollwert weiterhin an, weil die Integration ihn vom Gerät zurückliest. Beim Start, beim Stopp und im Sicherheits-Stopp setzt das Add-on GS = 0 weiterhin auch über HA, als Rückfall.
