# Changelog

## v2.7.4
- **Lokale Auslieferung von Frontend-Bibliotheken (Ingress CSP Fix)**: Alle externen Javascript-Bibliotheken (React, Recharts, Tailwind CSS, Lucide, Babel Standalone und HTML2Canvas) werden nun lokal aus dem Addon-Verzeichnis heraus ausgeliefert. Dies behebt die leere/weiße Seite bei der Systemanalyse im Home Assistant Ingress, welche durch die restriktive Content-Security-Policy (CSP) der Benutzeroberfläche verursacht wurde. Die Systemanalyse ist nun auch vollständig offline lauffähig.

## v2.7.3
- **Verdoppelte Regelgeschwindigkeit für mittlere Lastabweichungen**: Der minimale Regler-Verstärkungsfaktor `ki_min` wurde von `0.15` auf `0.30` angehoben (und `ki_max` auf `0.60`), während die Skalierung `ki_error_scale` von `600` auf `400` verkleinert wurde. Dies verdoppelt die Regelgeschwindigkeit bei anhaltenden mittleren Netzabweichungen (z. B. 70W bis 300W Bezug/Einspeisung) und verkürzt die Ausregelzeit von vormals fast 2 Minuten auf unter 40 Sekunden, während Kleinstabweichungen weiterhin ruhig ausgeregelt werden.

## v2.7.2
- **Lademaximum bis 94 % SOC erhöht**: Der Puffer für das Erkennen einer vollen Batterie wurde von 3 % auf 1 % (also 94 % SOC bei 95 % Limit) reduziert. Dadurch können die Speicher länger über das AC-Netz geladen werden.
- **Dynamischer Anti-Windup-Schutz**: Die Begrenzung der internen Regler-Akkumulation (Integrator) wurde direkt mit dem neuen 94-%-Ladelimit synchronisiert. Sobald die Batterien voll sind und keine AC-Ladung mehr aufnehmen, friert der Regler bei `0 W` ein. Dadurch wird jegliche Verzögerung beim Übergang zum Entladen (z. B. beim plötzlichen Einschalten von Großverbrauchern) eliminiert.
