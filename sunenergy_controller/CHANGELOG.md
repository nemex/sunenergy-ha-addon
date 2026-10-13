# Changelog

## v3.5.2
- **Volle Akkus entladen gemeinsam**: Sobald bei vollen Akkus einer der beiden Speicher zu entladen beginnt, wird die Einspeisegrenze (IS) jetzt fuer beide freigegeben. Die Entladung wird dann wie gewohnt nach SOC aufgeteilt. Bisher wurde nur der Speicher freigegeben, der selbst schon entlud.
- **Anlass (13.10.)**: Von 16:52 bis 17:22 deckte Speicher L2 das Haus allein. Das Netz stand dabei auf 0 W, deshalb bekam Speicher L1 kein Signal und blieb bei IS 20-160 W haengen. Speicher L2 lag danach 5 % unter Speicher L1.
