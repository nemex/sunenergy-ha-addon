# Changelog

## v3.4.6
- **Hausverbrauch wird gemessen statt zusammengeschaetzt**: Neue optionale Felder fuer die Shelly Pro 1PM an der Hoymiles-Einspeisung und an beiden Speichern (Hoymiles `shelly_ip`, Speicher 1 `shelly_ip`, Speicher 2 `shelly_ip_l2`). Der Controller liest sie direkt per RPC, gleich nach dem Netzzaehler. Der Hausverbrauch ist damit Netz + Hoymiles + Speicher, alle vier Werte gemessen und aus demselben Moment.
- **Anlass (28.09.)**: Die DTU war nach einem gelockerten Stecker weg. Ihre Leistungssensoren wurden `unavailable`, der „reachable“-Sensor blieb aber auf `on` stehen, weil ihn niemand mehr aktualisiert hat. Der Controller hielt die Wechselrichter fuer online und rechnete eine Dreiviertelstunde mit eingefrorenen 676 W Solar weiter, gemessen waren 100 W. Der Hausverbrauch stand dadurch bei ~990 W statt ~410 W.
- **Speicher in beide Richtungen gemessen**: Beim Laden aus dem Netz wurde die AC-Leistung bisher aus den DC-Werten mit pauschal 90 % Wirkungsgrad geschaetzt. Jetzt kommt sie vom Shelly.
- **Unveraendert**: Die Regelung der Speicher (OP/PV fuer IS, GS, Stillstand- und Einbruch-Erkennung) bleibt bei der Geraete-API. Die DTU liefert weiter die Aufteilung des Drossellimits auf HMS-2000 und HMS-1600. Ist ein Feld leer oder der Shelly nicht erreichbar, greift die bisherige Quelle (Wechsel wird einmal geloggt, ein toter Shelly wird 15 s uebersprungen).
- **Nach dem Update**: Die Felder sind bei einer bestehenden Installation zunaechst leer, bis die Konfiguration einmal mit den IPs gespeichert wird. Bis dahin laeuft alles wie in v3.4.5.
