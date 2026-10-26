# Changelog

## v3.6.3
- **Durchreichen der Morgen-PV im Sperrband wieder aus**: v3.6.2 lief stabil, ohne Schwingen. Die genaue Messung des Eigenverbrauchs (25.10., ~150 000 s) zeigt aber: Beim Durchreichen braucht der Speicher 37–48 W, beim reinen Laden nur 25 W. Bei schwacher Sonne frisst der Wechselrichter damit einen großen Teil dessen, was er ans Haus liefert.
- **Digitaler Zwilling** mit dem neuen Modell gegen „Akku zuerst“: im Herbst je nach Schwelle −35 bis +4 Wh pro Tag, im Winter +40 bis +55 Wh pro Tag. Unterm Strich kein Gewinn, aber zwei Gerätemacken (Sprung-Drosselung, kurzes Ergänzen aus dem Akku bei Wolken).
- **Verhalten jetzt wie v3.6.1/v3.5.8**: Im Sperrband (SOC 10–15 %) geht die Speicher-PV zuerst in den Akku. Rampe, Grenze und Schwelle bleiben im Code und lassen sich mit einem Schalter wieder einschalten.
