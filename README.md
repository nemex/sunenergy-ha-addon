SunEnergy XT Controller

Home-Assistant-Add-on für echte Nulleinspeisung mit dem SunEnergyXT 500 Pro Batteriespeicher – inklusive optionaler Drosselung von Hoymiles HMS-Mikrowechselrichtern (über OpenDTU) und Unterstützung für einen zweiten SunEnergyXT-Speicher (L2).

Der Regler misst kontinuierlich die Netzleistung (z. B. über einen Shelly Pro 3EM) und steuert Lade-/Entladeleistung sowie DC-Eingangsbegrenzung so, dass so wenig wie möglich ins Netz eingespeist wird – ohne die Herstellersoftware der SunEnergyXT-Geräte zu bevormunden.


Features


Nulleinspeise-Regelung (GS) – aktive Lade-/Entladesteuerung des Speichers bei jedem Ladezustand (SOC), nicht nur tagsüber
PV-Eingangsbegrenzung (IS) – drosselt die DC-Carport-Eingänge, wenn mehr Solarleistung anliegt als benötigt wird
Hoymiles-Drosselung (HMS) – begrenzt angeschlossene Hoymiles-Mikrowechselrichter über OpenDTU, wenn der Speicher allein nicht ausreicht
Dual-Speicher-Unterstützung (L1 + L2) – SOC-basierte Lastaufteilung, AC-AC-Transferlogik zum Ladungsausgleich zwischen beiden Speichern, Schutz vor gegenseitigem "Kreuzladen"
Nachtmodus – aktive Entladeregelung bis zum eingestellten Mindest-SOC, danach Übergabe an die geräteeigene Regelung
Zwangsladung / Kalibrierung – lädt den Speicher in einem konfigurierbaren Intervall automatisch auf 100 %, um den SOC neu zu kalibrieren
Watchdog & Safe-State – bei Absturz oder Stopp übernimmt automatisch die lokale Nulleinspeisung des Geräts (MM = 1), damit nie unkontrolliert eingespeist wird
PV-Eingangs-Überwachung – erkennt Wackelkontakte/ausgelöste DC-Automaten tagsüber und meldet sich per Telegram
Telegram-Benachrichtigungen (optional) bei Fallback-Aktivierung/-Erholung und PV-Ausfall
Web-UI mit Live-Dashboard und Log-Analyse, direkt in die Home-Assistant-Sidebar integriert (auch remote über Nabu Casa, ohne Port-Freigabe)
CSV-Logging aller Regelgrößen zur späteren Auswertung



Voraussetzungen


Laufende Home Assistant OS/Supervised-Installation (Add-ons werden nur dort unterstützt, nicht bei Home Assistant Container/Core)
SunEnergyXT 500 Pro im lokalen Netzwerk erreichbar (optional ein zweiter für L2)
Ein Netz-Leistungsmesser, z. B. Shelly Pro 3EM, im lokalen Netzwerk
Optional: Hoymiles HMS-Wechselrichter mit OpenDTU und in Home Assistant eingebundenen number-Entitäten zur Leistungsbegrenzung
Optional: Telegram-Bot-Token und Chat-ID für Benachrichtigungen



Installation

1. Repository zu Home Assistant hinzufügen


In Home Assistant zu Einstellungen → Add-ons → Add-on Store gehen
Oben rechts auf die drei Punkte klicken → Repositories
Folgende URL eintragen und mit Hinzufügen bestätigen:


   https://github.com/nemex/sunenergy-ha-addon


Die Store-Seite neu laden – das Add-on "SunEnergy XT Controller" erscheint in der Liste


2. Add-on installieren


Auf das Add-on klicken und Installieren wählen (Download kann je nach Hardware ein paar Minuten dauern)
Zum Tab Konfiguration wechseln und die Optionen an die eigene Anlage anpassen (siehe Konfiguration unten)
Speichern, dann im Tab Info auf Starten klicken
"Beim Start starten" und "In Seitenleiste anzeigen" aktivieren, damit das Add-on nach einem Neustart automatisch läuft und über die Sidebar erreichbar ist


3. Funktion prüfen


Im Log-Tab des Add-ons sollte der Controller ohne Fehler starten
Über die Sidebar (Icon "SunEnergy XT") öffnet sich das Web-UI mit Live-Werten



Konfiguration

Alle Optionen werden im Tab Konfiguration des Add-ons gesetzt (UI-Formular, kein manuelles YAML nötig).

Pflichtfelder (L1 / Basis-Setup)

OptionBeschreibungBeispielshelly_ipIP-Adresse des Shelly Pro 3EM (Netz-Messpunkt)192.168.178.98sunenergy_ipIP-Adresse des SunEnergyXT 500 Pro (L1)192.168.178.94ha_ipIP-Adresse der Home-Assistant-Instanz192.168.178.132grid_sensorHA-Sensor mit der aktuellen Netzleistungsensor.shellypro3em_leistungsoc_sensorHA-Sensor mit dem Ladezustand des Speicherssensor.sunenergyxt_500_pro_system_speicherlevelgs_entityHA-number-Entität für den Sollwert Netzanschlussleistungnumber.sunenergyxt_500_pro_sollwert_leistung_netzanschlussmm_switchHA-Schalter für den lokalen Nulleinspeisemodus des Gerätsswitch.sunenergyxt_500_pro_lokaler_nulleinspeisemodussa_entityHA-number-Entität für die Systemladegrenzenumber.sunenergyxt_500_pro_system_ladegrenzehaus_power_sensorHA-Sensor mit dem aktuellen Hausverbrauchsensor.hausverbrauch_aktuellsoc_normal_maxOberes SOC-Limit im Normalbetrieb (%)95soc_minUnteres SOC-Limit, ab dem nicht mehr entladen wird (%)10calibration_daysIntervall in Tagen für die automatische Zwangsladung auf 100 %15dry_runtrue = nur simulieren, keine Werte an die Geräte senden (zum Testen)false

Hoymiles / OpenDTU (optional)

OptionBeschreibunghms_2000_entity / hms_1600_entitynumber-Entitäten zur Leistungsbegrenzung der jeweiligen Hoymiles-Wechselrichterhms_2000_power_sensor / hms_1600_power_sensorSensoren mit der aktuellen Ausgangsleistunghms_2000_reachable_sensor / hms_1600_reachable_sensorbinary_sensor, ob der jeweilige Wechselrichter online ist

Nicht benötigte Hoymiles-Felder können leer bleiben, wenn kein entsprechender Wechselrichter vorhanden ist.

Zweiter Speicher – L2 (optional)

OptionBeschreibungsunenergy_ip_l2IP-Adresse des zweiten SunEnergyXTsoc_sensor_l2SOC-Sensor des L2-Speichersgs_entity_l2Sollwert-Entität des L2-Speichersmm_switch_l2Nulleinspeisemodus-Schalter des L2-Speicherssa_entity_l2Systemladegrenze des L2-Speichersop_l2_sensorLeistungssensor am AC-Ausgang des L2-Speichers (z. B. Shelly Pro 1PM)use_native_pidInterne Lastaufteilung zwischen L1/L2 aktivierenproxy_split_modeAufteilungsstrategie zwischen den Speichern, z. B. "soc"

Leer lassen, falls nur ein Speicher vorhanden ist – das Add-on läuft dann automatisch im Single-Storage-Modus.

Manuelle Volladung (optional)

OptionBeschreibungmanual_feed_in_switchinput_boolean, um kurzzeitig gezielte Einspeisung zu erzwingen (z. B. für Balkonkraftwerk-Bypass)manual_feed_in_targetZiel-Einspeiseleistung in kWmanual_feed_in_min_socMindest-SOC, ab dem diese Funktion aktiv werden darfmanual_feed_in_powerMaximale Leistung in Wattbypass_tomorrow_switchinput_boolean, um die nächste automatische Zwangsladung zu überspringen

Telegram-Benachrichtigungen (optional)

OptionBeschreibungtelegram_tokenBot-Token, leer lassen zum Deaktivierentelegram_chat_idZiel-Chat-ID für Warn-/Entwarnmeldungen


Nutzung

Nach dem Start ist das Web-UI erreichbar über:


die Home-Assistant-Sidebar (Ingress, auch remote via Nabu Casa nutzbar), oder
direkt per Browser unter http://<home-assistant-ip>:8765


Verfügbare Ansichten/Endpunkte:

PfadInhalt/Live-Dashboard mit aktuellen Regelgrößen/analyseGrafische Auswertung des CSV-Logs/stateAktueller Reglerzustand als JSON/logDownload des vollständigen CSV-Logs


Fehlerbehebung


Add-on startet nicht: Log-Tab prüfen – meist fehlt eine Pflichtoption oder eine Entität existiert (noch) nicht in Home Assistant
Werte werden nicht übernommen: dry_run: true prüfen – in diesem Modus wird nichts an die Geräte gesendet
L2 wird ignoriert: sunenergy_ip_l2 muss gesetzt sein, sonst läuft der Regler im Single-Storage-Modus
Web-UI in der Sidebar nicht sichtbar: Unter Info des Add-ons "In Seitenleiste anzeigen" aktivieren
Watchdog startet das Add-on ständig neu: prüfen, ob Port 8765 von einem anderen Dienst belegt ist



Hinweis

Dieses Add-on greift aktiv in die Regelung des Speichers ein. Eine fehlerhafte Konfiguration kann zu unerwünschter Netzeinspeisung oder Tiefentladung führen. Nutzung auf eigene Verantwortung – vor dem produktiven Einsatz wird empfohlen, dry_run: true zu testen und die Logs zu prüfen.

Changelog

Siehe CHANGELOG.md für die Versionshistorie.
