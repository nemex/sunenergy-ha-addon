# Changelog

## v2.6.0
- **Visuelle Schalter für PV-Eingänge (MPPT-Watchdog)**: Die Texteingabe-Felder für die PV-Eingänge wurden durch 8 komfortable visuelle Toggle-Schalter (Schieberegler) in der Home Assistant Benutzeroberfläche ersetzt. Die belegten Kanäle (L1 PV1..4 und L2 PV1..4) können nun einfach per Klick an- oder ausgeschaltet werden.

## v2.5.9
- **Manuelle Konfiguration der PV-Eingänge**: In den Addon-Optionen können die belegten PV-Eingänge (z. B. `pv_inputs_l1: "2,3"` und `pv_inputs_l2: "1,2"`) nun manuell angegeben werden. Dadurch überwacht der Watchdog exakt die installierten PV-Strings und meldet Fehler zuverlässig, selbst wenn das Addon nachts (während eines Solar-Ausfalls) neu gestartet wird.

## v2.5.8
- **Watchdog-Reset bei Addon-Start**: Der PV-Watchdog setzt seine Historie aktiver Eingänge bei jedem Addon-Start zurück. Dadurch wird verhindert, dass nach physischen Änderungen der Solar-Verkabelung (z. B. Umstecken von PV-Modulen) fälschlicherweise Alarme für die nun ungenutzten PV-Eingänge gesendet werden.
