# Changelog

## v3.5.9
- **Morgen-PV geht zuerst ans Haus**: Im Entladesperr-Band (SOC 10–15 %) hielt das Add-on die Speicher bisher auf IS = 10 W. Die ganze Speicher-PV ging dann in den Akku, auch wenn das Haus gleichzeitig aus dem Netz zog. Jetzt reicht jeder Speicher dort so viel von seiner eigenen PV ans Haus durch, wie das Haus nach den Hoymiles noch braucht. Der Rest lädt weiter den Akku.
- **Kein Entladen im Sperrband**: Die Abgabe ist auf die eigene PV abzüglich 60 W begrenzt (Sollwert und Einspeisegrenze). Gerätetest 17.10. bei SOC 11 %: Der Speicher gibt seine PV ab und entlädt auch bei höherer Anforderung nicht.
- **Warum**: An Tagen, an denen die Akkus ohnehin voll werden, ist die direkt genutzte Morgen-PV reiner Gewinn (gemessen 200–350 Wh/Tag). An trüben Tagen blieb sie bisher im Sperrband unter 15 % eingesperrt, während das Haus abends aus dem Netz zog (17./18.10.).
