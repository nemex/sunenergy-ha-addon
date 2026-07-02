# Changelog

## v2.5.7
- **Telegram-Meldungen & PV-Eingangs-Überwachung (Watchdog)**: Optionaler Telegram-Bot-Support für Fehlermeldungen bei Fallback-Aktivierung/Erholung. Zudem wurde ein PV-Watchdog integriert: Fällt ein zuvor aktiver PV-Eingang am Speicher tagsüber (Gesamt-PV > 150W) für mehr als 5 Minuten kontinuierlich auf 0,0V ab (z. B. durch Wackelkontakt oder DC-Automat aus), wird eine Telegram-Warnung gesendet. Bei Wiederkehr der Spannung folgt eine automatische Entwarnung.

## v2.5.6
- **Korrektur Entladung bei vollem Akku im Bypass**: Im Bypass-Modus wurde die L1/L2-Vollladungs-Erkennung korrigiert. Volle Akkus (z. B. L2 bei >=92%) werden nun beim Entladen (gs_new > 0) nicht mehr blockiert, sondern dürfen sich wie gewohnt proportional zu ihrem SOC entladen, um den Hausverbrauch abzudecken. Das "Durchreichen" (gs = PV) greift jetzt nur noch beim Laden (gs_new <= 0).

## v2.5.5
- **Bypass PID-Integration & Transfer-Sicherung**: Im Bypass-Modus wird die Batterieladung nun über den normalen PID-Regler berechnet. Dadurch kann L2 mit der vollen AC-Ladeleistung (bis zu 2400W) laden, um überschüssiges Solar von L1 und den Hoymiles aufzunehmen. Zudem wurde eine Sicherung in die Transferlogik eingebaut: Ist L2s AC-Ladung blockiert, wird der Transfer von L1 nach L2 sofort gestoppt, um ungewollte Einspeisung ins Netz zu verhindern.
