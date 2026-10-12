# Changelog

## v3.4.9
- **Kein IS-Pendeln mehr bei vollen Akkus**: Die Einspeisegrenze (IS) eines vollen, nicht ladenden Speichers sprang bisher im 5-s-Takt zwischen Restbedarf und 2400 W hin und her. Gedrosselt wurde nur, solange gerade Einspeisung anlag, im naechsten Tick gab es wieder 2400 W. Jetzt wird IS schrittweise auf Netz = 0 nachgefuehrt, ausgehend von der tatsaechlichen Abgabe des Speichers. Bei echtem Bezug ueber 400 W wird weiter sofort freigegeben.
- **Keine Lade-Neuprobe im Hysterese-Band des BMS**: Liegt der SOC zwischen Ladegrenze minus 5 % und der Ladegrenze, laedt das Geraet ohnehin nicht. Die Neuprobe alle 20 min entfaellt dort, sie startet erst wieder, wenn der SOC darunter gefallen ist.
- **Schnellerer Abbruch der Lade-Probe**: Nimmt ein Speicher die angeforderte Ladung nicht an und speist das Haus dabei mehr als 200 W ein, gilt die Ladesperre schon nach 20 s statt nach 60 s.
- **Anlass (12.10.)**: Ab 14 Uhr bei SOC 91 % und Ladegrenze 95 % pendelte das Netz dauerhaft zwischen -50 und -110 W, dazu alle 20 min rund 80 s lang 400-530 W Einspeisung durch die Neuprobe.
