# Changelog

## v3.5.3
- **Bezug bei vollen Akkus schneller weg**: Steht bei vollen Akkus mehr als 100 W Netzbezug an, wird die Einspeisegrenze (IS) beider Speicher sofort auf 2400 W freigegeben, damit der Akku das Haus deckt. Bisher lag diese Schwelle bei 400 W.
- **Anlass (16.10.)**: Solange IS unter 2400 W steht, geben die Speicher nur ihre eigene PV ab und entladen den Akku nicht, auch wenn IS mehr erlauben wuerde. Dadurch blieb Bezug zwischen 60 und 400 W minutenlang stehen, z. B. 16:22-16:30 mit 130-200 W (16.10.: 29 Wh, 13.10.: 46 Wh). Die sanfte Drosselung bei Einspeisung bleibt unveraendert.
