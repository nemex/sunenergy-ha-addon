# Changelog

## v2.5.4
- **Sofortiger & dauerhafter Nulleinspeisungs-Bypass**: Der Bypass-Schalter (`sunenergy_bypass_tomorrow`) wurde auf sofortige und manuelle Steuerung umgestellt. Sobald der Schalter aktiviert wird, wird die Nulleinspeisung unverzüglich ausgesetzt (nicht erst am Folgetag) und bleibt so lange aktiv, bis der Schalter manuell wieder ausgeschaltet wird. Die automatische zeitliche Begrenzung auf 24 Stunden entfällt.

## v2.5.3
- **Korrektur UnboundLocalError (soc_max_limit)**: Die Lade-Blockade-Erkennung für L2 in der Hauptschleife greift nun auf `last_written_sa` (bzw. `soc_normal_max` als Fallback) zu, um einen `UnboundLocalError` bei Schleifenbeginn zu verhindern.

## v2.5.2
- **Korrektur Start-Absturz (TypeError)**: Die Lade-Blockade-Erkennung für L2 nutzt nun `safe_float()`, um beim allerersten Regelzyklus (wenn `last_device_gs_l2` noch `None` ist) einen Absturz zu verhindern.
