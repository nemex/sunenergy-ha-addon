# Changelog

## v2.7.2
- **Lademaximum bis 94 % SOC erhöht**: Der Puffer für das Erkennen einer vollen Batterie wurde von 3 % auf 1 % (also 94 % SOC bei 95 % Limit) reduziert. Dadurch können die Speicher länger über das AC-Netz geladen werden.
- **Dynamischer Anti-Windup-Schutz**: Die Begrenzung der internen Regler-Akkumulation (Integrator) wurde direkt mit dem neuen 94-%-Ladelimit synchronisiert. Sobald die Batterien voll sind und keine AC-Ladung mehr aufnehmen, friert der Regler bei `0 W` ein. Dadurch wird jegliche Verzögerung beim Übergang zum Entladen (z. B. beim plötzlichen Einschalten von Großverbrauchern) eliminiert.

## v2.7.1
- **Schnellere Regelung bei hohen Lastwechseln (z. B. Waschmaschine/Trockner)**: Das Slew-Limit (maximale Leistungsänderung pro 5-Sekunden-Tick) wurde bei zwei aktiven Speichern (L2) bei großen Regelungsfehlern ($\ge 800$W) von $\pm 250$W auf $\pm 1000$W vervierfacht (bei mittleren Fehlern auf $\pm 500$W verdoppelt). Dadurch regeln die Speicher hohe Lastsprünge innerhalb von nur ca. 10 Sekunden (statt bisher 40 Sekunden) aus.
- **Fehlerbehebung Bypass-Betriebszustand**: Ein Einrückungsfehler in der Status-Zuweisung wurde korrigiert. Der Betriebszustand wird nun in Home Assistant korrekt als `bypass` angezeigt, wenn der Bypass aktiv ist.

## v2.7.0
- **Strukturierte Konfigurations-Übersicht (Gliederung & Sektionen)**: Die gesamte Addon-Konfiguration wurde im Home Assistant UI in übersichtliche, einklappbare Kategorien unterteilt (Speicher 1, Speicher 2, Shelly 3EM, Externe Wechselrichter (Hoymiles), Telegram Watchdog und Allgemeine Regelung). Dies macht die Konfiguration extrem aufgeräumt und professionell. Ein interner Translation-Layer sorgt für abwärtskompatibles Laden im Code.
