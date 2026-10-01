# Changelog

## v3.4.7
- **Keine Fehlalarme mehr bei vollem Akku**: Ab Ladegrenze minus 1 (normal 94 %) drosselt das Add-on bei Ueberschuss die Ausgabe der Speicher selbst, bis auf 10 W. Dass dann keine Leistung fliesst, ist gewollt. Der Stillstand-Waechter („Speicher Lx entlaedt nicht“) warnt in diesem Bereich nicht mehr, und „OP-Einbruch erkannt“ wird nur noch als INFO statt als WARNING geloggt.
- **Anlass (29./30.09.)**: Bei vollen Akkus meldete der Waechter beide Speicher als blockiert (IS=10 bei SOC 95), und am Nachmittag fuellten 24 Einbruch-Meldungen in 35 Minuten die Warnungsliste. Echte Probleme waren darunter schwer zu finden.
- **Unveraendert**: Unter der Grenze warnen beide Pruefungen wie bisher. Das Zuruecksetzen des GS-Integrators beim Einbruch bleibt in jedem Fall. Eine von aussen verstellte Einspeisegrenze korrigiert weiterhin der IS-Abgleich gegen das Geraet, auch bei vollem Akku, nur ohne Stillstand-Warnung.
