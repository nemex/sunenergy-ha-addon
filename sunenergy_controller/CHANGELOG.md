# Changelog

## v3.6.1
- **Durchreichen der Morgen-PV im Sperrband vorerst aus**: Bei Sonne drosselt der Speicher im Sperrband (SOC 10–15 %) seine PV auf etwa Abgabe + 40 W, sobald er etwas abgeben soll, auch mit IS 2400 (23.10. ab 09:59: PV 287 → 104 W, Akku +241 → +2 W). Das tut er aber nicht immer (um 09:2x lud er bei gleicher Lage den Überschuss voll). Dadurch entstand wieder der Kreis aus v3.5.9: Werte sprangen, und der Akku lud bei Sonne kaum.
- **Verhalten jetzt wie bis v3.5.8**: Im Sperrband geht die Speicher-PV zuerst in den Akku, bis 15 %. 2-s-Takt, Hoymiles und alles andere bleiben unverändert.
- Das Durchreichen kommt zurück, sobald ein gezielter Gerätetest geklärt hat, wann der Speicher drosselt.
