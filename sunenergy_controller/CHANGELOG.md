# Changelog

## v3.5.7
- **Gesamtersparnis zählt dauerhaft weiter**: Bisher zeigte „Ersparnis (Gesamt)“ nur den gewählten Tag, und der Amortisationsfortschritt rechnete einen einzelnen Tag gegen die Anschaffungskosten. Jetzt zeigt die Karte die Summe über alle Tage. Darunter stehen die Amortisation dieser Summe und die Ersparnis des gewählten Tags.
- **Tagesbilanz im Add-on**: Für jeden abgeschlossenen Tag werden Hausverbrauch, Netzbezug und Einspeisung in kWh dauerhaft in `/data/tagesbilanz.json` gespeichert, wenige Bytes pro Tag. Die Prüfung läuft stündlich, so geht kein Tag verloren, bevor das Tageslog nach 7 Tagen gelöscht wird. Bereits vorhandene Tageslogs werden beim Start nachgetragen.
- **Vorwert**: Neues Feld „PV-Strom genutzt bis …“ in kWh für die Zeit vor der Tagesbilanz, z. B. aus der Langzeitstatistik von Home Assistant. Die Summe rechnet immer mit dem eingestellten Arbeitspreis.
- Der Regler ist nicht betroffen.
