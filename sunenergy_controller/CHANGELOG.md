# Changelog

## v2.3.1
- **Separate Batterie-Sensoren**: Aufteilung der geschätzten AC-Batterieleistung in `sensor.sunenergy_battery_ac_l1` und `sensor.sunenergy_battery_ac_l2`. Behebt visuelle Darstellungsfehler auf Multi-Batterie-Dashboards.

## v2.3.0
- **Optimierung IS-Bypass-Schwellenwerte**: Erhöhung der Schwellenwerte für den automatischen Bypass auf `+400W` (Netzbezug für schnelle Freigabe) und `-400W` (Netzeinspeisung für schnelle Drosselung). Verhindert, dass der Bypass bereits bei kleineren normalen Regelfluuktuationen an der Nulllinie triggert, was zuvor die Oszillationen erneut anstieß.

## v2.2.10
- **L2-Bypass bei fehlendem PV**: Wenn L2 keine PV-Leistung meldet (da keine Module angeschlossen sind), bleibt `is_target_l2` starr auf `2400 W`. Das stoppt jegliche unnötigen HTTP-Schreibzugriffe über WLAN an L2 und halbiert die API-Latenz des Reglers.
- **Dynamische IS Slew-Rate (Regelungsstabilität)**:
  - *Anstieg*: Ramping-Up auf maximal `+100W` pro Tick begrenzt (um Hoymiles-Regelung Zeit zum Folgen zu geben). Bei echtem Netzbezug (`grid_p_raw > 100W`) wird das Limit jedoch sofort auf `2400W` angehoben, um schnelle Entladung bei Lastsprüngen zu sichern.
  - *Abfall*: Ramping-Down auf maximal `-250W` pro Tick begrenzt (um Einspeisespitzen beim Drosseln abzufangen). Bei starker Einspeisung (`grid_p_raw < -300W`) wird jedoch sofort hart gedrosselt.

## v2.2.9
- **IS Ping-Pong Fix bei SOC=95%**: Verhindert das schnelle Wechseln des IS-Limits zwischen 200W und 2400W, wenn der Akku voll ist und `drosseln=False`. Statt sofort auf 2400W zu springen, wird das IS-Limit nun maximal um +400W pro Tick erhöht (Slew-Rate-Begrenzung). Gilt für beide Geräte L1 und L2. Hintergrund: Der sofortige Sprung auf 2400W führte zu einem Leistungsimpuls, der das Netz kurzzeitig negativ machte, `drosseln=True` auslöste und IS wieder auf 200W setzte — ein stabiler Schwingkreis mit ~9 Zyklen/Minute.

## v2.2.7
- **Stabilitäts-Fix Pendeln**: Reduziert den I-Regler-Gain von 0.5 auf 0.3 und begrenzt den GS-Sprung auf ±120W pro 5s-Tick (Rate-Limiting). Verhindert die bisher auftretenden GS-Sprünge von bis zu 1450W in einem einzigen Tick, die bei plötzlichen Lastsprüngen zu massiver Über-/Untereinspeisung (bis -1890W) geführt haben.
- **Integrator-Reset bei OP-Einbruch**: Setzt den GS-Integrator auf 0 zurück, wenn die Batterie von >100W plötzlich auf <10W OP-Ausgang fällt. Verhindert Windup-bedingte Überschwinger beim Wiederanfahren.

## v2.2.6
- **Korrektur Vorzeichen L2-Leistungssensor**: Konvertiert negative Messwerte des Shelly-Sensors (die Einspeisung/Entladung repräsentieren) automatisch in positive Werte für `op_l2`. Positive Messwerte (die Laden repräsentieren) werden ignoriert (auf 0.0 gesetzt), da der Ladebedarf separat berechnet wird.

## v2.2.5
- **L2-Entladeleistung im Hausverbrauch berücksichtigt**: Erlaubt das Konfigurieren von `op_l2_sensor` (z.B. für einen Shelly Pro 1PM), um die AC-Entladeleistung von L2 direkt aus Home Assistant einzulesen. Dies korrigiert die Hausverbrauchsberechnung bei Installationen mit zwei Speichereinheiten, wenn die Entladeleistung von L2 nicht über die SunEnergy-API gemeldet wird.

## v2.2.4
- **Vollsymmetrischer AC-AC-Transfer**: Macht die Ausgleichslogik komplett richtungsneutral. Wenn L2 zukünftig PV-Module erhält, kann der Transfer auch in die Gegenrichtung (L2 -> L1) erfolgen, basierend auf dem Vorzeichen von `soc_diff`.
- **Symmetrische IS-Grenzwerterhöhung (Fix 1)**: Hebt das IS-Limit des jeweiligen Quellspeichers während des Transfers dynamisch an, um DC-Drosselung bei aktivem AC-AC-Transfer zu verhindern.

## v2.2.3
- **Lastverschiebung zur Vermeidung von SOC-Drift**: Erlaubt den AC-AC-Transfer auch dann, wenn L1 einen lokalen PV-Überschuss relativ zu seiner AC-Einspeisung (`pv_current > gs_l1_rounded`) hat, anstatt auf globalen Überschuss (`pv_current > haus_p`) zu prüfen. Das verhindert, dass L1 bei hohem Hausverbrauch weiter geladen wird, während L2 entlädt.

## v2.2.2
- **Hoymiles-Freigabe bei L2-Ladebedarf**: Verhindert das Drosseln der Hoymiles-Wechselrichter (HMS), wenn L1 voll (95%) ist, L2 aber noch geladen werden kann. Beide Bedingungen (vollständiges Öffnen und stufenlose Regelung) prüfen nun, ob mindestens eine der Batterien noch nicht voll ist.

## v2.2.1
- **IS-Sägezahn Root-Cause-Fix**: Der Anstiegs-Limiter für das IS-Limit wurde komplett entfernt. Da die Geräte intern bereits sanft hochrampen, ist eine zusätzliche softwareseitige Drosselung des Anstiegs (+1000W/Tick) nicht nötig. Dies behebt den verbleibenden Sägezahn-Effekt bei Drosselung an der Lade-Grenze.

## v2.2.0
- **Beseitigung der Doppel-Drosselung**: Verhindert das gleichzeitige Abregeln von Hoymiles (HMS) und L1 DC-PV (Carport-Module via IS) bei aktivem AC-AC-Transfer (Fix 1 & Fix 2).
- **HMS-Anpassung bei Transfer**: Erlaubt den Hoymiles bei aktivem Transfer, so viel einzuspeisen, wie Hausverbrauch und Transferleistung zusammen benötigen.
- **IS-Anpassung bei Transfer**: Das IS-Limit von L1 wird um die Transferleistung angehoben (`is_floor = max(200, restbedarf + p_transfer)`), um genügend PV-Leistung für den Transfer freizugeben.
- **Kreuzladungs-Bypass**: Unterdrückt fälschliche Kreuzladungs-Erkennungen und Warnungen im Haupt-Controller und im Web-Proxy, sobald ein AC-AC-Transfer aktiv ist.

## v2.1.9
- **IS-Sägezahn-Fix**: Führt eine dynamische Mindestgrenze (`is_floor = max(200, restbedarf)`) für das IS-Limit bei vollem Akku (SOC=95%) ein, um das ständige Auf- und Abspringen des Ladereglers zu verhindern.
- **Transfer-Boost bei vollem L1**: Leitet bei vollem L1-Speicher (SOC=95%) den gesamten solaren Überschuss direkt als Transfer zu L2 um, statt den Transfer proportional zur SOC-Differenz zu deckeln.

## v2.1.8
- **Manueller SOC-Ausgleich L1/L2**: Implementiert eine automatische Angleichung der Speicherlevel via AC-AC-Transfer (Einspeisen über L1, zeitgleiches AC-Laden über L2), ohne die Nulleinspeisung zu verletzen.
- **Slew-Rate & Wolkenschutz**: Limitiert den Anstieg der Transferleistung auf +50W/Tick. Bei Einbruch des solaren Überschusses wird der Transfer sofort (ohne Slew-Rate-Verzögerung) auf 0W gestoppt, um Netzbezug zu verhindern.
- **L2-Lade-Fade-Out**: Reduziert die Transferleistung linear ab 90% SOC von L2 stufenlos auf 0W bei 95% SOC.

## v2.1.7
- **Version Bump**: Stellt durch einen sauberen Versions-Bump auf v2.1.7 sicher, dass Home Assistant das Update korrekt erkennt und baut, und korrigiert den im Start-Log angezeigten Versionsstring.

## v2.1.6
- **Kreuzladungs-Rampdown-Fix**: Ändert die Richtungs-Koordination im Proxy so, dass bei erkannter AC-AC Kreuzladung sowohl die entladende Batterie (sieht künstlichen Export) als auch die ladende Batterie (sieht künstlichen Import) gleichzeitig heruntergeregelt werden. Dies unterbricht Oszillationen und beendet die Kreuzladung sofort und stabil.

## v2.1.5
- **Permanente native PV-Drosselung**: Begrenzt das IS-Limit für PV-ausgestattete Batterien (`pv_power > 50W`) im nativen Modus permanent vorausschauend auf `max(10, haus_p - solar_p)` zur Beseitigung von DC-Einspeiseüberschüssen. Batterien ohne PV (wie L2) bleiben voll geöffnet für AC-Laden.
- **State-Trennung (Race-Condition-Fix)**: Führt eine separate `/data/proxy_state.json` für Proxy-Polls ein, wodurch Schreibkonflikte und Verzögerungen beim Zustandsaustausch vollständig behoben werden.
- **Konfliktfreies Splitting**: Nutzt neue, vom Controller gesetzte `discharge_active_l1/l2` Flags im Proxy-Splitting, sodass PV-gedrosselte Batterien aktiv bleiben, leere Batterien jedoch sauber ausgegrenzt werden.
- **Low-Latency Shelly-Direktabfrage**: Liest die Netzleistung im nativen Modus standardmäßig direkt vom Shelly Pro 3EM aus, um Verzögerungen durch HA-Sensoren zu vermeiden.
- **Echtzeit-Dynamik & Shelly-Schutz**: Reduziert Shelly-Abfragen durch 500ms-Cache im Proxy auf ein sicheres Niveau bei gleichzeitig hoher PID-Reaktionsgeschwindigkeit.

## v2.1.4
- **Stabilität im nativen Polling**: Deaktiviert den BMS-Blocker-Detektor (IS-Throttling) im nativen Modus. Dies verhindert, dass sich das Ladesystem (insb. L2) dauerhaft bei IS=10W festfrisst.
- **BMS-Blocker-Sign-Fix**: Korrigiert den Vorzeichen-Vergleich im manuellen BMS-Blocker, sodass Entladevorgänge (negative BP-Werte) nicht fälschlicherweise als blockiertes Laden interpretiert werden.

## v2.1.3
- **Richtungs-Koordination (Cross-Charging-Schutz)**: Implementiert eine oszillationsfreie, proxy-basierte Steuerung (Zuweisung von 0W / realem Netzwert) bei gegenseitiger AC-AC Kreuzladung von L1 und L2.
- **Speicher-Telemetrie**: Erweitert den geteilten Zustand um Echtzeit-Leistungswerte (OP, PV, IW) beider Inverter.

## v2.1.2
- **Fix NameError**: Behebt einen Absturz (`NameError: name 'shelly_ip' is not defined`) im Regelzyklus, der auftrat, wenn der Home Assistant Grid-Sensor offline ging und auf den Shelly-Direkt-Fallback zugegriffen wurde.

## v2.1.1
- **MM-Selbstheilung**: Erzwingt kontinuierlich den korrekten Betriebsmodus (`MM=1` für nativ, `MM=0` für Fallback) bei Abweichungen, um gegenseitiges AC-Laden/Entladen (Cross-Charging) bei Kommunikationsstörungen oder Neustarts zu verhindern.

## v2.1.0
- **Natives PID-Polling**: Ermöglicht die Selbstregelung der Speicher über den Add-on-Proxy (MD-Zählerbindung & MM=1).
- **Prozess-sicheres State-Saving**: Atomares Schreiben der State-Updates verhindert Datenverlust zwischen Controller und Proxy-Server.
- **Intelligentes Proxy-Splitting**: IP-sensitives Splitting am `/meter`-Proxy (Laden nach Headroom, Entladen nach usable SOC).
- **Hysteretischer Fallback**: Automatisches Umschalten auf GS-Regelung (MM=0) bei Signalverlust (>15s) und kontrollierte Rückkehr erst nach 3 aufeinanderfolgenden erfolgreichen Polls (kein unzuverlässiger MS-Status-Check).
- **Online-Status-Synchronisation**: Sofortiges Speichern des Systemzustands bei Erreichbarkeitsänderungen sorgt für verzögerungsfreies Splitting.

## v2.0.1
- **Zweiter Speicher (L2) Support**: Vollständige Integration eines optionalen zweiten Speichers auf Phase L2.
- **Koordiniertes Laden/Entladen**: Paralleles, ausgeglichenes Laden (proportional zum Headroom) und Entladen (proportional zum SOC) beider Speicher, um gegenseitige Schwingungen zu vermeiden.
- **Nachtmodus- & Zwangsladungs-Integration**: Vollwertige Steuerung beider Speicher auch im Nachtmodus und bei der regelmäßigen Zwangsladung/Kalibrierung.
- **Dynamisches Web-UI**: Automatische Erweiterung des Dashboards um separate L2-Werte (SOC L2, GS L2, IS L2) und eine zusätzliche Spalte für L2 in der Wechselrichter-Ansicht, falls konfiguriert.

## v2.0.0
- **Nulleinspeisung-Bypass für morgen**: Neuer Schalter `input_boolean.sunenergy_bypass_tomorrow` ermöglicht es, die Nulleinspeisung am nächsten Kalendertag (von 0:00 bis 24:00 Uhr) komplett auszusetzen, um die maximale Erzeugung bei perfektem Solarwetter zu testen. Hoymiles und Carport-Module laufen dabei zu 100 % ungedrosselt. Am Folgetag kehrt das System automatisch wieder zur Nulleinspeisung zurück.
- **Web-UI Erweiterung**: Unterstützung des Bypass-Modus auf dem Live-Dashboard mit passenden Statusmeldungen und optischer Kennzeichnung.

## v1.9.9
- **Fix Dockerfile**: Kopieren von `analyse.html` in den Docker-Container hinzugefügt, um den Fehler "Analyse-Datei nicht gefunden" zu beheben.

## v1.9.8
- **Analyse-Dashboard Integration**: Das Premium-Analyse-Dashboard wurde direkt in die Weboberfläche eingebaut und ist über den Button "Systemanalyse" im Footer erreichbar. Die Logdaten werden vollautomatisch geladen.
- **Unbegrenztes Logging**: Das automatische Kürzen des CSV-Logs nach 2 MB wurde deaktiviert, um den gesamten Verlauf dauerhaft zu speichern.

## v1.9.7
- **Fix Manuelle Einspeisung**: Verhindert das Drosseln der DC-PV-Module (Carport) am SunEnergy XT auf Minimalwerte (z. B. 30 W / 1 %) während der manuellen Einspeisung. Setzt das IS-Limit während dieser Phase dauerhaft auf 2400 W (100 %).

## v1.9.6
- **Konfigurations-Update**: Standard-Zielmenge für die manuelle Einspeisung (`manual_feed_in_target`) von 0,5 kWh auf 1,0 kWh erhöht.

## v1.9.5
- **Stabilitäts-Fix Sonnenstand**: Cacht den letzten bekannten Sonnenstand (aus `sun.sun`). Verhindert, dass kurzzeitige Verbindungsabbrüche oder Timeouts der Home Assistant API das Add-on fälschlicherweise mitten am Tag in den Nachtmodus (mit Deaktivierung von MM) versetzen.

## v1.9.4
- **Priorisierung Batterieladung**: Wenn die Batterie leer ist und geladen werden kann, werden die Hoymiles-Wechselrichter voll geöffnet (3600 W). Dies maximiert die Solarstrom-Erzeugung zum Laden der Batterie und verhindert künstliches Drosseln am Morgen oder bei wechselhaftem Wetter.

## v1.9.3
- **Optimierung Hoymiles-Freigabe**: Bezieht die aktive Batterie-Entladung als virtuellen Bedarf in die Hoymiles-Drosselregelung ein. Verhindert, dass die Hoymiles bei aktivem Akkubetrieb künstlich gedrosselt bleiben, und schont so die Batteriekapazität.

## v1.9.2
- **Ingress-Support**: Web-UI direkt in der HA-Sidebar (auch remote via Nabu Casa).
- **Shelly-Direkt-Fallback**: Holt Grid-Daten bei HA-API-Störungen direkt vom Shelly (vermeidet Fehl-Safety-Stopps).
- **Zwangsladung Spam-Schutz**: Schreibt GS- und MM-Werte nur bei Eintritt/Änderung (schont den Geräte-Flash des SunEnergyXT).
- **Hardware-Schonung**: Throttled State-Saving schont die SD-Karte/SSD durch selteneres Schreiben des Zustands.
- **Sauberer Shutdown**: Übergibt Steuerung bei Addon-Stopp an die Geräte-Selbstregelung.
- **Persistent HTTP-Sessions**: Reduziert Latenz durch Keep-Alive-Verbindungen.
- **Stabilitäts- & Web-Fixes**: Supervisor-Watchdog für `/state`, Threading-Webserver (kein Blockieren bei Shelly-Timeout), `/log/delete` auf POST beschränkt (Schutz vor Browser-Prefetching).

## v1.9.1
- **Morgendliche Kalibrierung**: Kalibrierung wird am Fälligkeitstag ab 10:00 Uhr freigegeben, um die Sonnenstunden maximal zu nutzen.

## v1.9.0
- **Solare Kalibrierung**: Erhöht das Ladelimit tagsüber auf 100 % für kostenloses Laden mit PV-Überschuss. Netzladung dient nur noch als Nacht-Backup.

## v1.8.9
- **API-Fix**: Wechsel zurück zu `python:3.11-alpine` löst den *401 Unauthorized* Fehler der HA-API.

## v1.8.8
- **Boot-Fix**: Deaktivierung des Init-Systems löst die s6-overlay PID-1 Endlosschleife.

## v1.8.7
- **Inverter-Schutz**: Sanfter Anstieg (+1000W pro Tick) verhindert Firmware-Spikes beim Entdrosseln.
- **Stabilitäts-Fix**: run.sh überwacht beide Prozesse (`wait -n`) für sauberen Container-Neustart.

## v1.8.6
- **Verbrauchs-Fix**: Korrektur der Hausverbrauchs-Berechnung während der Akku-Ladung.

## v1.8.5
- **Virtuelle HA-Sensoren**: Pusht berechnete Werte alle 5s direkt als native HA-Entitäten.

## v1.8.4
- **Bugfixes**: Behebt Probleme beim Initial-Write, Kalibrierungs-Direkt-Write, Moduswechsel-Reset und setzt HMS-Baseline-Boden auf 300W.
