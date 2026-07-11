# Changelog

## v3.0.0
- **Fehlerbehebungen (Stabilität & Cleanup)**:
  - **`grid_target` Mapping-Fix**: Behebung des fehlenden Mappings für `grid_target` in den `legacy_mappings` von `controller.py` und `web_ui.py`. Der eingestellte Nulleinspeisungs-Offset wird nun korrekt geladen.
  - **Reboot-Sicherheit**: Die Hold-Time `hold_until` wird beim Controller-Startup aus dem State verworfen. Dies verhindert ein tagelanges Einfrieren der Regelung nach Host-Reboots aufgrund der zurückgesetzten System-Uptime (`time.monotonic()`).
  - **NameError Absturz-Fix**: Behebung eines NameErrors (nicht definierte Variable `anteil_l1`/`l2`) im `/meter` Endpoint von `web_ui.py`, wenn kein Transfer oder Kreuzladung vorliegt.
  - **Begrenzung CSV-Wachstum**: Reaktivierung des automatischen Trimmens der CSV-Logdatei auf 2.000 Zeilen bei Überschreitung von 2 MB (RAM- & Speicherplatzschutz).
  - **L2 Integrator Reset**: Behebung des fehlenden Integrator-Resets (`state["last_gs"] = 0.0`) im L2-OP-Einbruchszweig.
  - **Diagramm-CSP-Fix**: Chart.js wird nun lokal unter `/lib/chart.umd.min.js` ausgeliefert, um Ingress-CSP-Sperren bei Nabu Casa zu umgehen.
- **Regelungs-Verbesserungen**:
  - **Zwangsladungs-Timeout**: Automatische Begrenzung der Kalibrierung (Zwangsladung auf 100%) auf maximal 12 Stunden, um BMS-Hänger bei 99% SOC abzufangen und teuren Netzbezug zu verhindern.
  - **Nachtregelung mit `grid_target`**: Der Nulleinspeisungs-Offset wird nun auch nachts konsistent auf die Regelung angewendet.
  - **Shelly-Staleness-Timeout**: Der `/meter` Proxy liefert bei einem Shelly-Ausfall nach 30 Sekunden ein HTTP-500 anstatt des alten Cache-Werts, um die automatische Regelung des Speichers kontrolliert zu stoppen.
  - **Trennung von Poll- und Read-Timestamps**: Die Ticks des Controllers werden in getrennten Keys gesichert, um Fehlalarm-Szenarien bei der Erkennung verlorener MD-Verbindungen zu vermeiden.
  - **IS-Korrektur-Klemmen**: Begrenzung der IS-Sofortkorrektur bei Kreuzladung auf den API-Grenzbereich `[200, 2400]`.
- **Changelog-Kürzung**: Entfernung aller Changelog-Einträge älter als `v2.8.0` zur Bereinigung der Dateigröße.

## v2.8.8
- **Rückgängig Behebung Doppelzählung Hausverbrauch (Revert)**: Die Akku-Entladeleistung fließt wieder voll in die Berechnung des Hausverbrauchs ein, da der Speicher ein AC-gekoppeltes Entladesystem verwendet, dessen AC-Leistung nicht in den Hoymiles-Erzeugungswerten (`solar_p`) enthalten ist. Dies stellt die physikalisch korrekte Berechnung des Hausverbrauchs wieder her.
- **AC-Lade-Drosselungs-Fix**: Die Ladekapazitäten `charge_capacity_l1` und `charge_capacity_l2` werden bei aktivem AC-Laden (`gs_new_rounded < 0`) auf `0.0 W` gesetzt. Dies ermöglicht es dem Regler, die Hoymiles während des Ladevorgangs korrekt zu drosseln, und behebt die ungewollte Dauereinspeisung/Entladung bei hohem SOC.

## v2.8.7
- **Behebung Doppelzählung Hausverbrauch**: Bei der Berechnung des Hausverbrauchs wird die Akku-Entladeleistung nun korrekt ignoriert, da diese bereits in der Hoymiles-AC-Leistung (`solar_p`) enthalten ist. Die Akku-Leistung fließt nur noch in die Formel ein, wenn sie negativ ist (AC-Laden aus dem Netz), um eine Doppelzählung während der Entladungsphasen zu verhindern und den Hausverbrauch im Dashboard physikalisch korrekt anzuzeigen.

## v2.8.6
- **Freigabe AC-Laden & Schwellenwert-Korrektur**: In den normalen Regelungsmodi für Tag (`active`) und Nacht (`night`) wird die Untergrenze des berechneten Sollwerts `gs_new` wieder auf `-max_gs` freigegeben, um das Laden der Akkus aus dem AC-Überschuss der Hoymiles zu ermöglichen. Gleichzeitig wird die hardcodierte Drosselgrenze von `-2350 W` (für einen Speicher) dynamisch an die Gesamtkapazität angepasst (`-max_gs + 50.0 W`), um Fehl-Drosselungen und Schwingungen bei hoher PV-Leistung und zwei installierten Speichern (L2) zu beheben.

## v2.8.5
- **Dämpfung von Regelkreis-Oszillationen**: In den normalen Regelungsmodi für Tag (`active`) und Nacht (`night`) wird die Untergrenze des berechneten Sollwerts `gs_new` nun starr auf `0.0 W` begrenzt. Dies verhindert unerwünschte negative Stellwerte (AC-Netzladung) und unterbricht selbstverstärkende Schwingungen, die durch plötzliche Lastwechsel (z. B. nach dem Kaffeekochen) unter klarem Himmel ausgelöst werden können.

## v2.8.4
- **Einstellbarer Netz-Sollwert (Grid Target Offset)**: Eine neue Option `grid_target` in den Add-on-Einstellungen (Allgemeine Regelungs-Konfiguration) ermöglicht es, einen Offset für die Nulleinspeisung festzulegen (z. B. `-40.0 W` für ständige leichte Einspeisung). Dies puffert die Regellatenz ab und minimiert den Zählerbezug bei schnellen, taktenen Lasten wie 3D-Druckern oder Kühlschränken.

## v2.8.3
- **Bypass-Modus Sollwert-Begrenzung**: Im Bypass-Modus wird die Untergrenze des Sollwerts `gs_new` nun korrekt auf `0.0` begrenzt, um unerwünschte negative Stellwerte zu verhindern.

## v2.8.2
- **Zwangsladung CSV-Logging & Sensor-Freeze behoben**: Während der automatischen Akku-Zwangsladung (Kalibrierung auf 100%) wurde das Schreiben in das CSV-Log sowie das Live-Update der virtuellen Home Assistant-Sensoren fälschlicherweise übersprungen. Dies führte zu großen Lücken in den Auswertungsdaten und zu eingefrorenen Sensorwerten. Beides aktualisiert sich nun auch während der Zwangsladungsphase ordnungsgemäß alle 5 Sekunden.

## v2.8.1
- **Serverseitige Speicherung der PV-Modulkonfigurationen**: Die eingetragenen Daten der PV-Module (Modell, Nennleistung) werden nun dauerhaft in der Datei `/data/pv_modules.json` auf dem Server gesichert. Dies verhindert Datenverluste bei Add-on-Updates oder Cache-Löschungen.
- **Null-Linie im Live-Dashboard**: Im Haupt-Dashboard wurde im Netzleistungsdiagramm eine gestrichelte, weiße Referenzlinie bei `0 W` hinzugefügt, um die Regelungspräzision der Nulleinspeisung visuell besser beurteilen zu können.
- **Live-Log Autoscroll-Standardwert**: Der Standardwert für die automatische Scrollfunktion im Live-Terminal wurde von `AN` auf `AUS` geändert, um das manuelle Lesen älterer Logs bei aktivem Taktbetrieb zu erleichtern.

## v2.8.0
- **Skalierung von PV-Spannung und Stromstärke**: Die vom SunEnergy-Speicher gelieferten Rohwerte für Spannung (V) und Strom (A) der PV-Eingänge (z.B. 368 für 36.8V und 51 für 5.1A) werden nun im Dashboard-Tab „PV Module“ korrekt durch 10.0 geteilt, um die realen Werte mit Dezimalstelle anzuzeigen.
