# Changelog

## v3.5.1
- **SOC-Ausgleich beim Laden ueber AC**: Der Ueberschuss der Hoymiles, der in die Akkus geladen wird, geht jetzt bevorzugt an den leereren Speicher. Pro Prozentpunkt SOC-Unterschied bekommt er 100 W mehr, bei 2 % Unterschied also 200 W. Grundlage bleibt die Aufteilung nach freiem Platz bis zur Ladegrenze, die Grenze von 2400 W je Speicher gilt weiter.
- **Anlass (13.10.)**: Bei 44 zu 46 % bekam Speicher L1 nur 51 % des Ueberschusses, obwohl er vormittags weniger eigene PV hatte. Der Rueckstand von 2-3 % blieb dadurch bis kurz vor voll stehen.
