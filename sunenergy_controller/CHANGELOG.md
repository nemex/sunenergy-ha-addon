# Changelog

## v3.5.6
- **Eingabefelder statt Schieberegler**: Arbeitspreis und Einspeiseverguetung werden in ct/kWh eingegeben, Grundpreis in €/Monat, Anschaffungskosten in €. Alle Felder nehmen Nachkommastellen mit Komma oder Punkt an (z. B. 31,78 ct/kWh).
- **Grundpreis des Stromanbieters**: neues Feld. Er wird anteilig fuer den angezeigten Zeitraum zu den Stromkosten gerechnet (ein Monat = 1/12 Jahr, 19,24 €/Monat = 0,63 € pro Tag). Ersparnis und Amortisation bleiben ohne Grundpreis, weil er mit und ohne Anlage gleich anfaellt.
- **Neue Karte „Stromkosten“** in der Regler-Analyse: Netzbezug × Arbeitspreis + Grundpreisanteil. Bisher gab es die Kosten nur bei Smart-Plug-Logs.
- Bereits gespeicherte Einstellungen bleiben gueltig. Ohne eingetragenen Grundpreis wird 0 € gerechnet.
- Der Regler ist nicht betroffen.
