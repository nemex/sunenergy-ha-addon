# Changelog

## v2.5.3
- **Korrektur UnboundLocalError (soc_max_limit)**: Die Lade-Blockade-Erkennung für L2 in der Hauptschleife greift nun auf `last_written_sa` (bzw. `soc_normal_max` als Fallback) zu, um einen `UnboundLocalError` bei Schleifenbeginn zu verhindern.

## v2.5.2
- **Korrektur Start-Absturz (TypeError)**: Die Lade-Blockade-Erkennung für L2 nutzt nun `safe_float()`, um beim allerersten Regelzyklus (wenn `last_device_gs_l2` noch `None` ist) einen Absturz zu verhindern.

## v2.5.1
- **Dynamisches AC-Laden für L2 & L1->L2 Transfer**: L2 kann nun wieder über AC aus dem Überschuss der Hoymiles und von L1 geladen werden. Ein neuer Lade-Blockade-Schutz erkennt automatisch, wenn L2 die Ladung verweigert (BMS voll, App-Limit, unplugged), blockiert temporär L2s Headroom und drosselt die Hoymiles, um Einspeise-Deadlocks zu verhindern. Zudem wurde die Transferlogik (L1->L2) für solaren Überschuss von L1 freigegeben, indem nun geprüft wird, ob die Quelle (L1) PV-Erzeugung hat.
