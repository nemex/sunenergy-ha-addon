# Changelog

## v3.5.0
- **Volle Akkus duerfen ohne IS-Deckel entladen**: Seit v3.4.9 wird IS bei vollen Akkus schrittweise nachgefuehrt. Reicht die PV gegen Abend nicht mehr und der Akku entlaedt (Batterie unter -50 W), stieg IS nur um 20-30 W pro Takt und es blieb Netzbezug stehen (live 12.10. 16:52-16:53 rund 100 W). Jetzt wird IS in diesem Fall sofort freigegeben und GS regelt allein wie nachts. Einspeisung ist dabei ausgeschlossen, weil die PV kleiner ist als die Abgabe.
