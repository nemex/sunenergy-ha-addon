# Changelog

## v2.5.8
- **Watchdog-Reset bei Addon-Start**: Der PV-Watchdog setzt seine Historie aktiver Eingänge bei jedem Addon-Start zurück. Dadurch wird verhindert, dass nach physischen Änderungen der Solar-Verkabelung (z. B. Umstecken von PV-Modulen) fälschlicherweise Alarme für die nun ungenutzten PV-Eingänge gesendet werden.

## v2.5.7
- **Telegram-Meldungen & PV-Eingangs-Überwachung (Watchdog)**: Optionaler Telegram-Bot-Support für Fehlermeldungen bei Fallback-Aktivierung/Erholung. Zudem wurde ein PV-Watchdog integriert: Fällt ein zuvor aktiver PV-Eingang am Speicher tagsüber (Gesamt-PV > 150W) für mehr als 5 Minuten kontinuierlich auf 0,0V ab (z. B. durch Wackelkontakt oder DC-Automat aus), wird eine Telegram-Warnung gesendet. Bei Wiederkehr der Spannung folgt eine automatische Entwarnung.

## v2.5.6
- **Korrektur Entladung bei vollem Akku im Bypass**: Im Bypass-Modus wurde die L1/L2-Vollladungs-Erkennung korrigiert. Volle Akkus (z. B. L2 bei >=92%) werden nun beim Entladen (gs_new > 0) nicht mehr blockiert, sondern dürfen sich wie gewohnt proportional zu ihrem SOC entladen, um den Hausverbrauch abzudecken. Das "Durchreichen" (gs = PV) greift jetzt nur noch beim Laden (gs_new <= 0).
