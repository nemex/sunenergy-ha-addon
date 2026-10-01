# Changelog

## v3.4.8
- **Ladesperre-Erkennung funktioniert jetzt auch bei Sonne**: Das Add-on erkennt einen Speicher, der angeforderte Ladung nicht annimmt, jetzt an der Batterieleistung (BP unter 50 W) statt an der Eingangsleistung (IW unter 50 W). IW enthaelt die PV-Leistung und lag tagsueber nie unter 50 W, die Erkennung war dadurch bei Sonne blind.
- **Anlass (01.10.)**: Nach dem Vollladen nahmen beide Speicher bei 92 % keine Ladung an (Batterie 0 W), das Add-on forderte trotzdem weiter Ladung an und drosselte nicht. Die PV der Speicher ging von 15:20 bis 17:00 komplett ins Netz, rund 0,55 kWh. Mit dem Fix waere die Sperre um 15:27 gegriffen.
- **Restbedarf bei vollen Akkus wird aufgeteilt**: Bisher bekam jeder Speicher den vollen Restbedarf (Haus minus Hoymiles) als Einspeisegrenze, beide zusammen lieferten das Doppelte. Jetzt wird er nach PV-Anteil auf beide verteilt. Anlass: 01.10. 14:46-14:58 zwoelf Minuten durchgehend 120-240 W Einspeisung.
- **Gesperrter Speicher zaehlt nicht mehr als Aufnahme fuer den anderen**: Die IS-Drosselung beruecksichtigt beim Durchreichen an den zweiten Speicher jetzt dessen Ladesperre, nicht nur den SOC.
- **Unveraendert**: Netzregelung, Nachtbetrieb und die Wiederholsperre (Neuprobe alle 20 min).
