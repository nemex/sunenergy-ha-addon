# Changelog

## v3.0.5
- **Fix: Kalibrierung endet erst, wenn BEIDE Speicher 100 % haben**: Bisher setzte die „Vollladung erkennen"-Logik den Kalibrierungs-Timer bereits zurück, sobald L1 100 % erreichte (`if curr_soc >= 100`). Dadurch wurde die Zwangsladung abgebrochen und das Ladelimit `SA` fiel auf `soc_normal_max` (95 %) zurück, bevor L2 fertig war — L2 blieb unkalibriert bei ~95 % hängen (Befund 13.07.: L1 = 100 %, L2 = 95 %). Der Timer wird jetzt nur zurückgesetzt, wenn beide Speicher 100 % erreicht haben. Der automatische 7-/15-Tage-Zyklus bringt damit zuverlässig beide Speicher gemeinsam auf 100 %.
- **Neu: Manueller „Jetzt kalibrieren"-Button**: Eine neue Option `manual_calibration_switch` (Standard `input_boolean.sunenergy_calibrate_now`) erlaubt es, die Kalibrierung jederzeit manuell auszulösen — Tag wie Nacht, unabhängig vom Timer. Beim Einschalten lädt der Controller beide Speicher sofort auf 100 % (tagsüber solar, nachts per Netz), schaltet den Button nach Abschluss automatisch wieder aus und setzt `SA` auf 95 % zurück. Wird der Button vor Erreichen der 100 % wieder ausgeschaltet, bricht die manuelle Kalibrierung sauber ab, ohne den automatischen 7-Tage-Zyklus zu beeinflussen. Das 12h-Sicherheitsnetz bleibt als Notaus aktiv.

## v3.0.4
- **Start-Härtung gegen Netzbezug-Transient**: Direkt nach dem v3.0.3-Update zog der Akku kurzzeitig ~2000 W aus dem Netz. Ursache waren zwei zusammenfallende Startprobleme, die jetzt behoben sind:
  - **GS-Integrator wird beim Start auf 0 gesetzt**: Ein aus einer Vorversion bzw. einem fehlerhaften Lauf aufgezogener `last_gs`-Wert (gemessen bis −4800 W) wurde beim ersten Tick sofort als harter Ladebefehl ans Gerät geschrieben. Der Integrator startet nun neutral bei 0 (analog zum `hold_until`-Reset).
  - **Kein Fehl-Nachtflip beim Start**: War der Sensor `sun.sun` beim allerersten Tick noch nicht lesbar, fiel der Controller auf den Default „below_horizon" zurück, flippte für einen Tick in den Nachtmodus und schrieb dabei einen harten GS-Wert. Solange der Sonnenstand nach dem Start noch nie gelesen wurde, wird der Tick jetzt übersprungen (nach dem ersten erfolgreichen Lesen gilt weiterhin der letzte bekannte Zustand als Fallback bei kurzen API-Aussetzern).

## v3.0.3
- **Hotfix MPPT-Schutz-Schwelle**: Der in v3.0.2 eingeführte MPPT-Schutz (GS ≥ 0 für fast volle Speicher) griff schon ab `Limit − 3 %` und blockierte damit auch Speicher mit echtem Ladeheadroom — Live-Befund direkt nach dem Update: L1 stand bei 92 % (Limit 95 %), durfte nicht laden, und der Überschuss des vollen L2 (~400 W Durchleitung) floss dauerhaft ins Netz. Die Schwelle liegt jetzt auf `Limit − 1 %` (BMS-Abriegelgrenze, konsistent mit `charge_capacity`/Headroom-Logik).
- **GS-Integrator Anti-Windup**: Wenn Floors/Klemmen (MPPT-Schutz, Low-SOC, Kreuzladungs-Hold) die tatsächlich kommandierten GS-Werte begrenzen, wird der Integrator jetzt auf ±100 W um die reale Kommandosumme geklemmt. Vorher zog er bei anhaltender Klemmung bis −4800 W auf (live gemessen) — eine „gespannte Feder", die beim Wegfall der Klemme (z. B. Wolkendurchgang) schlagartig als 2400-W-Ladebefehl freigesetzt worden wäre.

## v3.0.2
- **Anti-Schwingungs-Release**: Behebt den am 12.07. gemessenen Regelkreis-Limit-Cycle (222 HMS-Limit-Flaps/Tag, Netz-Pendeln ±1900 W, Hausverbrauchs-Sprünge 800→1600 W im 15-Sekunden-Takt), der auftrat, sobald ein Speicher fast voll war und die SOC-Angleichung lief:
  - **Transfer-HMS-Override entschärft**: Bei aktivem SOC-Transfer wird das Hoymiles-Limit nicht mehr hart auf `haus_p + p_transfer` gesetzt (Drosselung an das verrauschte `haus_p` gekoppelt), sondern dieser Wert wirkt nur noch als Untergrenze. Der Transfer läuft über AC zwischen den Speichern und erzeugt keinen Netz-Export, den man wegdrosseln müsste.
  - **Ladekapazität proportional statt binär**: Der v2.8.8-Kippschalter (`gs_new_rounded >= 0`) ließ das HMS-Limit bei jedem Nulldurchgang der GS-Summe um bis zu 2000 W springen — genau das passiert während der SOC-Angleichung ständig (ein Speicher lädt, einer entlädt). Die bereits genutzte AC-Ladeleistung wird jetzt stufenlos von der verbleibenden Kapazität abgezogen.
  - **HMS-Limit-Slew + Richtungs-Hysterese**: Das Limit ändert sich nur noch um max. ±200 W/Tick (Notabsenkung 600 W/Tick bei Einspeisung > 600 W) und wechselt die Richtung frühestens alle 30 s. Die schnelle Nulleinspeisungs-Korrektur übernimmt die Batterie (GS), das HMS-Limit ist der langsame Trimm-Regler. Bypass und manuelle Einspeisung sind ausgenommen.
  - **SOC-Angleichung mit Hysterese, Netz-Gate und Cooldown**: Start erst ab >5 % SOC-Differenz bei ruhigem Netz (|Netz| ≤ 300 W); ein laufender Transfer darf bis 2 % Differenz weiterlaufen und wird von Netzspitzen nicht abgewürgt. Nach Transfer-Ende gilt ein 120-s-Cooldown gegen Sekundentakt-Flattern.
  - **MPPT-Schutz für fast volle Speicher**: Einem Speicher ≥ (Limit − 3 %) mit aktivem PV-Ertrag wird kein AC-Laden mehr aufgezwungen (GS ≥ 0) und sein GS-Sollwert sinkt nur noch mit max. 250 W/Tick. Vorher wurde der AC-Ausgang des vollen Speichers im 5-s-Takt zwischen −90 und +650 W hin- und hergerissen, worauf das Gerät seine eigenen MPPTs abwürgte (gemessen: 42 `pv_l2`-Einbrüche ≥ 200 W in 2 h bei L2 = 92 %).
  - **`is_l2` im CSV-Log**: Das IS-Limit des zweiten Speichers wird jetzt mitgeloggt (war bei der Diagnose ein blinder Fleck). Hinweis: Durch die neue Spalte wird die bestehende CSV beim ersten Start einmalig neu angelegt.

## v3.0.1
- **Fehlerbehebungen (Stabilität & Cleanup)**:
  - **`grid_target` Mapping-Fix**: Behebung des fehlenden Mappings für `grid_target` in den `legacy_mappings` von `controller.py` und `web_ui.py`. Der eingestellte Nulleinspeisungs-Offset wird nun korrekt geladen.
  - **Reboot-Sicherheit**: Die Hold-Time `hold_until` wird beim Controller-Startup aus dem State verworfen. Dies verhindert ein tagelanges Einfrieren der Regelung nach Host-Reboots aufgrund der zurückgesetzten System-Uptime (`time.monotonic()`).
  - **NameError Absturz-Fix**: Behebung eines NameErrors (nicht definierte Variable `anteil_l1`/`l2`) im `/meter` Endpoint von `web_ui.py`, wenn kein Transfer oder Kreuzladung vorliegt.
  - **Begrenzung CSV-Wachstum**: Reaktivierung des automatischen Trimmens der CSV-Logdatei auf 2.000 Zeilen bei Überschreitung von 2 MB (RAM- & Speicherplatzschutz).
  - **L2 Integrator Reset**: Behebung des fehlenden Integrator-Resets (`state["last_gs"] = 0.0`) im L2-OP-Einbruchszweig.
  - **Diagramm-CSP-Fix**: Chart.js wird nun lokal unter `lib/chart.umd.min.js` ausgeliefert, um Ingress-CSP-Sperren bei Nabu Casa zu umgehen.
- **Regelungs-Verbesserungen**:
  - **Thread-Safety für `/meter` Proxy**: Thread-sicheres Schreiben des Proxy-States mit Mutex-Lock zur Vermeidung von Lost-Updates bei parallelen Anfragen von L1 und L2.
  - **Fallback-Grace-Periode**: 60-Sekunden-Schonfrist nach dem Start und bei Re-entry-Versuchen, um Falsch-Auslösungen der Fallback-Regelung zu verhindern, bis die Speicher das Polling wieder aufgenommen haben.
  - **Zwangsladungs-Timeout**: Automatische Begrenzung der Kalibrierung (Zwangsladung auf 100%) auf maximal 12 Stunden, um BMS-Hänger bei 99% SOC abzufangen und teuren Netzbezug zu verhindern, inklusive Telegram-Benachrichtigung bei Abbruch.
  - **Nachtregelung mit `grid_target`**: Der Nulleinspeisungs-Offset wird nun auch nachts konsistent auf die Regelung angewendet.
  - **Shelly-Staleness-Timeout**: Der `/meter` Proxy liefert bei einem Shelly-Ausfall nach 30 Sekunden ein HTTP-503 (Service Unavailable) anstatt des alten Cache-Werts, um die automatische Regelung des Speichers kontrolliert zu stoppen.
  - **Trennung von Poll- und Read-Timestamps**: Die Ticks des Controllers werden in getrennten Keys gesichert, um Fehlalarm-Szenarien bei der Erkennung verlorener MD-Verbindungen (wenn der Speicher nicht mehr pollt) zu vermeiden.
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
