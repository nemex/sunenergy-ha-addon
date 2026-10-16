# Changelog

## v3.5.4
- **Kein Netzbezug mehr nach dem Add-on-Start**: Der Start zaehlte als Wechsel von Nacht auf Regelung und loeste die 30-s-Wartezeit aus. In dieser Zeit stand der Sollwert der Speicher fest auf 0 W. Jetzt regelt das Add-on ab dem ersten Takt. Die Wartezeit bei echten Moduswechseln (morgens, abends, Kalibrierung, Bypass) bleibt unveraendert.
- **Anlass (16.10.)**: Beim Update auf v3.5.3 zog das Haus von 17:51:36 bis 17:52:02 rund 1050 W aus dem Netz (~8 Wh), obwohl die Akkus bei 86 % standen.
- **Versionsanzeige**: Das Log zeigt beim Start wieder die richtige Version (v3.5.3 meldete sich noch als v3.5.2).
