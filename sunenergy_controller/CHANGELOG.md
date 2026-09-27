# Changelog

## v3.4.5
- **Das Text-Log bleibt jetzt 14 Tage erhalten**: Bisher war die Protokolldatei auf 200 KB mit einer Sicherung begrenzt. Bei einer Zeile alle 5 Sekunden reichte das nur fuer etwa eine Stunde, und das Supervisor-Log in Home Assistant verliert bei jedem Neustart und Update seinen Verlauf. Belege fuer eigenmaechtige Verstellungen der Speicher (IS, Ladegrenze) gingen so verloren. Jetzt wird pro Tag eine eigene Datei gefuehrt, abgeschlossene Tage werden komprimiert und 14 Tage aufbewahrt.
- **Alle Warnungen und Fehler zusaetzlich ein Jahr lang** in einer eigenen Datei: IS- und Ladegrenzen-Korrekturen, Entlade-Stillstaende, OP-Einbrueche, Verbindungsfehler. Das ist die Grundlage fuer Hersteller-Tickets und Langzeitauswertungen.
- **Download in der Web-Oberflaeche**: neue Knoepfe „Text-Log heute“ und „Warnungen“. Einzelne Tage gibt es ueber `textlog?day=JJJJ-MM-TT`, die verfuegbaren Tage ueber `textlog/days`.
- **Belastung**: Geschrieben wurde schon bisher jede Zeile, neu ist nur das Aufbewahren. Ein Tag hat etwa 2 MB, komprimiert rund 0,2 MB. Insgesamt sind es unter 5 MB. Das Komprimieren laeuft einmal pro Tag um Mitternacht und dauert Sekundenbruchteile. Die Live-Anzeige liest nur noch das Dateiende statt der ganzen Datei.
- **Unveraendert**: Regelung, CSV-Log und die IS-Ueberwachung aus v3.4.4.
