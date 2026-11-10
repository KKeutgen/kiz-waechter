#!/usr/bin/env python3
"""
K.I.Z "Nur fuer Frauen" 2027 Wien - re:sale-Waechter (Cloud-Version fuer GitHub Actions)
Prueft die offizielle re:sale-Seite etwa jede Minute und schickt bei freien Tickets
eine Push-Nachricht ueber ntfy aufs Handy.
"""

import datetime
import os
import random
import re
import time
import urllib.request

URL = "https://kiz-shop.com/en/events/k-i-z-nur-fuer-frauen-2027-stadthalle"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
LAUFZEIT_MINUTEN = float(os.environ.get("LAUFZEIT_MINUTEN", "350"))
INTERVALL = 60
ZUFALL = 15
ERINNERN_MINUTEN = 3

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
AUSVERKAUFT = {"soldout", "outofstock", "discontinued"}
NICHT_VERFUEGBAR = ["currently not available", "derzeit nicht verfügbar",
                    "zurzeit nicht verfügbar", "ausverkauft", "sold out"]


def log(msg):
    print(f"[{datetime.datetime.utcnow():%H:%M:%S} UTC] {msg}", flush=True)


def laden():
    req = urllib.request.Request(URL, headers={
        "User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="replace")


def status(html):
    werte = [w.lower() for w in re.findall(
        r'"availability"\s*:\s*"(?:https?://schema\.org/)?([A-Za-z]+)"', html)]
    if werte:
        return "VERFUEGBAR" if any(w not in AUSVERKAUFT for w in werte) else "AUSVERKAUFT"
    if any(t in html.lower() for t in NICHT_VERFUEGBAR):
        return "AUSVERKAUFT"
    return "UNKLAR"


def push(titel, text, dringend=True):
    if not NTFY_TOPIC:
        log("Kein NTFY_TOPIC gesetzt - Push uebersprungen")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=text.encode("utf-8"),
        headers={"Title": titel, "Priority": "urgent" if dringend else "default",
                 "Tags": "ticket,rotating_light" if dringend else "information_source",
                 "Click": URL})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"Push fehlgeschlagen: {e}")


def main():
    if os.environ.get("TESTLAUF") == "1":
        try:
            s = status(laden())
        except Exception as e:
            s = f"FEHLER ({e})"
        push("Test: K.I.Z-Waechter", f"Verbindung klappt. Seitenstatus: {s}", dringend=False)
        log(f"Testlauf, Status: {s}")
        return

    ende = time.time() + LAUFZEIT_MINUTEN * 60
    letzter, letzter_alarm, fehler = None, 0.0, 0
    while time.time() < ende:
        try:
            s = status(laden())
            fehler = 0
            log(s)
        except Exception as e:
            s, fehler = "FEHLER", fehler + 1
            log(f"Abruf fehlgeschlagen: {e}")
            if fehler == 15:
                push("K.I.Z-Waechter: Problem",
                     "Die Shop-Seite ist seit ca. 15 Minuten nicht erreichbar.", dringend=False)

        if s == "VERFUEGBAR" and (letzter != "VERFUEGBAR"
                                  or time.time() - letzter_alarm > ERINNERN_MINUTEN * 60):
            push("K.I.Z Ticket verfuegbar!",
                 "Auf der re:sale-Seite ist ein Ticket frei. Jetzt antippen und kaufen!")
            letzter_alarm = time.time()
        elif s == "UNKLAR" and letzter == "AUSVERKAUFT":
            push("K.I.Z-Waechter: Seite hat sich veraendert",
                 "Bitte kurz selbst nachsehen - evtl. gibt es Tickets.")

        if s != "FEHLER":
            letzter = s
        time.sleep(max(30, INTERVALL + random.uniform(-ZUFALL, ZUFALL)))


if __name__ == "__main__":
    main()
