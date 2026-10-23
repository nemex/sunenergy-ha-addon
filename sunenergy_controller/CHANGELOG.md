# Changelog

## v3.6.2
- **Morgen-PV im Sperrband wieder ans Haus, jetzt ohne Schwingen**: Ursache des Kreises aus v3.5.9/v3.6.0 gefunden (1-s-Daten 20.–23.10., ~3 000 Sollwert-Änderungen): Springt GS im Sperrband um 40 W oder mehr, drosselt der Speicher für ~5–14 s seine PV auf etwa Abgabe + 40 W, und der Akku lädt nicht mehr (85–100 % der Fälle). Kleinere Schritte verkraftet er (1–16 %), konstantes GS nie. Die erlaubte Abgabe aus der gedrosselten PV erzwang dann weitere große Sprünge.
- **GS im Sperrband nur noch in Schritten von höchstens 20 W pro Takt**, auch beim Einschalten.
- **Erlaubte Abgabe aus dem PV-Höchstwert der letzten 60 s**, damit ein kurzer Einbruch keinen großen Schritt nach unten erzwingt.
- **Erst ab 60 W möglicher Abgabe pro Speicher durchreichen.** Darunter frisst der Wechselrichter des Speichers (~40 W) zu viel, dann geht die PV zuerst in den Akku.
- **IS 2400, solange durchgereicht wird.**
- Digitaler Zwilling gegen v3.5.8 (Akku zuerst): 14 echte Herbsttage −1 008 Wh, Winterwoche −47 Wh, Sommerwochen −211 Wh.
