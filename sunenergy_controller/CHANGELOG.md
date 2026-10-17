# Changelog

## v3.5.5
- **ROI-Einstellungen bleiben gespeichert**: Strompreis, Einspeiseverguetung und Anschaffungskosten in der Systemanalyse werden jetzt im Add-on gespeichert (`/data/roi_settings.json`). Sie gelten auf allen Geraeten und ueberstehen Neuladen, Updates und Neustarts. Gespeichert wird 1 s nach der letzten Aenderung.
- Ohne gespeicherte Werte gelten die bisherigen Startwerte (0,35 €/kWh, 0,082 €/kWh, 1500 €).
- Der Regler ist nicht betroffen.
