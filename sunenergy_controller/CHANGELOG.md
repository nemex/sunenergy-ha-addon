# Changelog

## v2.7.0
- **Strukturierte Konfigurations-Übersicht (Gliederung & Sektionen)**: Die gesamte Addon-Konfiguration wurde im Home Assistant UI in übersichtliche, einklappbare Kategorien unterteilt (Speicher 1, Speicher 2, Shelly 3EM, Externe Wechselrichter (Hoymiles), Telegram Watchdog und Allgemeine Regelung). Dies macht die Konfiguration extrem aufgeräumt und professionell. Ein interner Translation-Layer sorgt für abwärtskompatibles Laden im Code.

## v2.6.1
- **Allgemeinere Namensgebung in der Konfiguration**: Die Bezeichner für die PV-Eingangs-Schalter wurden von `l1_pv*_active` / `l2_pv*_active` in allgemeines `speicher1_pv*_active` / `speicher2_pv*_active` umbenannt. Dies verbessert die Verständlichkeit für alle Anwender, da die Speicher phasenunabhängig allgemein als Speicher 1 und Speicher 2 benannt sind.

## v2.6.0
- **Visuelle Schalter für PV-Eingänge (MPPT-Watchdog)**: Die Texteingabe-Felder für die PV-Eingänge wurden durch 8 komfortable visuelle Toggle-Schalter (Schieberegler) in der Home Assistant Benutzeroberfläche ersetzt. Die belegten Kanäle (L1 PV1..4 und L2 PV1..4) können nun einfach per Klick an- oder ausgeschaltet werden.
