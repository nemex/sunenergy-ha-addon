# Changelog

## v2.5.9
- **Manuelle Konfiguration der PV-Eingänge**: In den Addon-Optionen können die belegten PV-Eingänge (z. B. `pv_inputs_l1: "2,3"` und `pv_inputs_l2: "1,2"`) nun manuell angegeben werden. Dadurch überwacht der Watchdog exakt die installierten PV-Strings und meldet Fehler zuverlässig, selbst wenn das Addon nachts (während eines Solar-Ausfalls) neu gestartet wird.

## v2.5.8
- **Watchdog-Reset bei Addon-Start**: Der PV-Watchdog setzt seine Historie aktiver Eingänge bei jedem Addon-Start zurück. Dadurch wird verhindert, dass nach physischen Änderungen der Solar-Verkabelung (z. B. Umstecken von PV-Modulen) fälschlicherweise Alarme für die nun ungenutzten PV-Eingänge gesendet werden.

## v2.5.7
- **Telegram-Meldungen & PV-Eingangs-Überwachung (Watchdog)**: Optionaler Telegram-Bot-Support für Fehlermeldungen bei Fallback-Aktivierung/Erholung. Zudem wurde ein PV-Watchdog integriert: Fällt ein zuvor aktiver PV-Eingang am Speicher tagsüber (Gesamt-PV > 150W) für mehr als 5 Minuten kontinuierlich auf 0,0V ab (z. B. durch Wackelkontakt oder DC-Automat aus), wird eine Telegram-Warnung gesendet. Bei Wiederkehr der Spannung folgt eine automatische Entwarnung.
