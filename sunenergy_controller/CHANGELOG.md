# Changelog

## v2.7.5
- **Fehlerbehebung Lucide React Crash (Systemanalyse rendering fix)**: Die `Icon`-Komponente der Systemanalyse wurde neu strukturiert. Sie isoliert die DOM-manipulierende Funktion von Lucide (`createIcons()`) nun vollständig über einen React `useRef`-Container. Dies verhindert, dass Lucide direkt den von React kontrollierten Virtual DOM überschreibt, was zuvor zu einem fatalen React-Absturz (`NotFoundError: Failed to execute 'removeChild' on 'Node'`) und einer komplett leeren/weißen Seite führte.

## v2.7.4
- **Lokale Auslieferung von Frontend-Bibliotheken (Ingress CSP Fix)**: Alle externen Javascript-Bibliotheken (React, Recharts, Tailwind CSS, Lucide, Babel Standalone und HTML2Canvas) werden nun lokal aus dem Addon-Verzeichnis heraus ausgeliefert. Dies behebt die leere/weiße Seite bei der Systemanalyse im Home Assistant Ingress, welche durch die restriktive Content-Security-Policy (CSP) der Benutzeroberfläche verursacht wurde. Die Systemanalyse ist nun auch vollständig offline lauffähig.

## v2.7.3
- **Verdoppelte Regelgeschwindigkeit für mittlere Lastabweichungen**: Der minimale Regler-Verstärkungsfaktor `ki_min` wurde von `0.15` auf `0.30` angehoben (und `ki_max` auf `0.60`), während die Skalierung `ki_error_scale` von `600` auf `400` verkleinert wurde. Dies verdoppelt die Regelgeschwindigkeit bei anhaltenden mittleren Netzabweichungen (z. B. 70W bis 300W Bezug/Einspeisung) und verkürzt die Ausregelzeit von vormals fast 2 Minuten auf unter 40 Sekunden, während Kleinstabweichungen weiterhin ruhig ausgeregelt werden.
