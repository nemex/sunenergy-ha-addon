# Changelog

## v2.5.5
- **Bypass PID-Integration & Transfer-Sicherung**: Im Bypass-Modus wird die Batterieladung nun über den normalen PID-Regler berechnet. Dadurch kann L2 mit der vollen AC-Ladeleistung (bis zu 2400W) laden, um überschüssiges Solar von L1 und den Hoymiles aufzunehmen. Zudem wurde eine Sicherung in die Transferlogik eingebaut: Ist L2s AC-Ladung blockiert, wird der Transfer von L1 nach L2 sofort gestoppt, um ungewollte Einspeisung ins Netz zu verhindern.

## v2.5.4
- **Sofortiger & dauerhafter Nulleinspeisungs-Bypass**: Der Bypass-Schalter (`sunenergy_bypass_tomorrow`) wurde auf sofortige und manuelle Steuerung umgestellt. Sobald der Schalter aktiviert wird, wird die Nulleinspeisung unverzüglich ausgesetzt (nicht erst am Folgetag) und bleibt so lange aktiv, bis der Schalter manuell wieder ausgeschaltet wird. Die automatische zeitliche Begrenzung auf 24 Stunden entfällt.

## v2.5.3
- **Korrektur UnboundLocalError (soc_max_limit)**: Die Lade-Blockade-Erkennung für L2 in der Hauptschleife greift nun auf `last_written_sa` (bzw. `soc_normal_max` als Fallback) zu, um einen `UnboundLocalError` bei Schleifenbeginn zu verhindern.
