# Changelog

## v3.6.0
- **Morgen-PV ohne Schwingen**: Im Sperrband (SOC 10–15 %) setzte v3.5.9 die Einspeisegrenze IS beim Durchreichen auf die erlaubte Abgabe (PV × 0,96 − 60 W). Ein niedriges IS bremst dort aber auch das Laden: Der Speicher fährt seine PV auf etwa IS herunter (22.10.: IS 60 → PV 124 → 65 W, Akku +1 W). Weil die erlaubte Abgabe aus der gemeldeten PV kam, sank IS mit der PV weiter. Das ergab einen Kreis im ~6-s-Takt (IS 250 → 50 → 10), bei Sonne lud der Akku kaum, und die Werte im Dashboard sprangen.
- **Jetzt**: Beim Durchreichen steht IS auf 2400, die Abgabe begrenzt allein der Sollwert GS (weiter höchstens PV × 0,96 − 60 W). Der Speicher lädt den Überschuss wieder voll (22.10.: IS 270 / GS 50 → PV 340 W, Akku +240 W). Entladen kann der Akku dabei nicht, denn GS bleibt unter der eigenen PV, und das Gerät sperrt im Sperrband ohnehin.
- **Digitaler Zwilling** (13 echte Tage, 4 Saisonwochen) gegen v3.5.8 (Akku zuerst): −945 Wh Netzbezug in 13 Tagen, an keinem Tag spürbar schlechter. Heute früh nachgerechnet: Bezug 08:30–10:45 397 Wh statt 600 Wh (v3.5.8) bzw. 565 Wh (v3.5.9).
