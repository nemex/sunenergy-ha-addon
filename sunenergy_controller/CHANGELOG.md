# Changelog

## v3.6.4
Nur Anzeige und Log, die Regelung ist unverändert (Zwilling identisch mit v3.6.3).

**Systemanalyse**
- **Solarerzeugung mit Speicher L2:** Die PV von L2 fehlte in „Solarerzeugung“, im Solarfluss, in der Eigenverbrauchsquote und beim CO₂. Beispiel 21.10.: 6,93 statt 4,70 kWh.
- **SunEnergy AC und Deckung Hausverbrauch:** jetzt L1 + L2, gemessen am Shelly. Vorher nur die L1-Abgabe laut Gerät.
- **Akku-Laden und -Entladen:** aus der echten Akkuleistung des Geräts. Vorher galt „PV − Abgabe“: Der Eigenverbrauch des Speichers (25–45 W) zählte als Laden, und Laden aus dem Netz fehlte. Ältere Logs ohne die neuen Spalten fallen auf die alte Schätzung zurück, mit Hinweis.
- **Wirkungsgrad:** SOC-bereinigt und nur mit echter Akkuleistung. Vorher war es Entladen geteilt durch Laden für einen einzelnen Tag, also praktisch ein Zufallswert.
- **Reglerpräzision:** Zeiten im Sperrband (10–15 %, Akku gibt nichts ab) und mit leeren Akkus zählen nicht mehr, und zwar für beide Speicher statt nur L1. Gemessen wird gegen das Ziel −5 W statt gegen 0 W. Beispiele: 21.10. 84 % statt 41 % (Ø 23 W statt 206 W), 28.10. 78 % statt 52 %.
- **Tabelle:** alle Werte für L1 und L2 (SOC, Sollwert, Abgabe, PV, Akku).
- **Texte:** Regelung alle 2 s, Log alle 5 s (stand noch „alle 5 s“).

**Dashboard**
- **Nacht:** zeigt „Akkus versorgen das Haus (… W)“ bzw. „Akkus leer oder gesperrt“. Vorher stand dort „kein Betrieb“, obwohl die Akkus nachts regeln.
- **SunEnergyXT Ist gegen IS-Limit:** vergleicht jetzt die AC-Abgabe mit der Grenze. Vorher stand dort die PV-Eingangsleistung, und der Balken zeigte im Sperrband bei IS 10 W „100 % gedrosselt“, obwohl der Akku nur lud.
- **IS-Limit L2:** aus dem Log statt aus einem älteren Zustandswert.
- **„SOC voll“:** erst, wenn beide Speicher voll sind.

**Tageslog**
- **Neue Spalten** `bp`/`bp_l2` (Akkuleistung, + lädt) und `ac`/`ac_l2` (Abgabe am Shelly, + Abgabe).
- **Keine Datenverluste mehr bei neuen Spalten:** Ändern sich die Spalten, übernimmt das Add-on die laufende Tagesdatei ins neue Format. Vorher löschte es sie.
