# Changelog

## v2.7.1
- **Schnellere Regelung bei hohen Lastwechseln (z. B. Waschmaschine/Trockner)**: Das Slew-Limit (maximale Leistungsänderung pro 5-Sekunden-Tick) wurde bei zwei aktiven Speichern (L2) bei großen Regelungsfehlern ($\ge 800$W) von $\pm 250$W auf $\pm 1000$W vervierfacht (bei mittleren Fehlern auf $\pm 500$W verdoppelt). Dadurch regeln die Speicher hohe Lastsprünge innerhalb von nur ca. 10 Sekunden (statt bisher 40 Sekunden) aus.
- **Fehlerbehebung Bypass-Betriebszustand**: Ein Einrückungsfehler in der Status-Zuweisung wurde korrigiert. Der Betriebszustand wird nun in Home Assistant korrekt als `bypass` angezeigt, wenn der Bypass aktiv ist.

## v2.7.0
- **Strukturierte Konfigurations-Übersicht (Gliederung & Sektionen)**: Die gesamte Addon-Konfiguration wurde im Home Assistant UI in übersichtliche, einklappbare Kategorien unterteilt (Speicher 1, Speicher 2, Shelly 3EM, Externe Wechselrichter (Hoymiles), Telegram Watchdog und Allgemeine Regelung). Dies macht die Konfiguration extrem aufgeräumt und professionell. Ein interner Translation-Layer sorgt für abwärtskompatibles Laden im Code.

## v2.6.1
- **Allgemeinere Namensgebung in der Konfiguration**: Die Bezeichner für die PV-Eingangs-Schalter wurden von `l1_pv*_active` / `l2_pv*_active` in allgemeines `speicher1_pv*_active` / `speicher2_pv*_active` umbenannt. Dies verbessert die Verständlichkeit für alle Anwender, da die Speicher phasenunabhängig allgemein als Speicher 1 und Speicher 2 benannt sind.
