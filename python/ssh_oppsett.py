"""
ssh_oppsett.py - Setter opp SSH på en Cisco router eller switch via konsollkabel.
Alle verdier (hostname, IP, brukernavn, passord ...) spørres om når scriptet kjører,
så det samme scriptet kan brukes på alle enhetene.
"""
import getpass
import time

import serial


# ---------------------------------------------------------------------------
# Kommunikasjon med enheten
# ---------------------------------------------------------------------------
def vent_paa_prompt(ser, timeout=10):
    """Les fra enheten til den viser en prompt (#, > eller :) eller tiden går ut."""
    svar = ""
    start = time.time()
    while time.time() - start < timeout:
        svar += ser.read(ser.in_waiting or 1).decode(errors="ignore")
        if svar.rstrip().endswith(("#", ">", ":")):
            break
    return svar


def send(ser, kommando, timeout=10):
    """Send én kommando, vent på svar og si fra hvis IOS ikke godtok den."""
    ser.write((kommando + "\r").encode())
    svar = vent_paa_prompt(ser, timeout)
    print(svar, end="")

    # F.eks. "Do you really want to replace them? [yes/no]:" ved crypto key
    if svar.rstrip().endswith("[yes/no]:"):
        svar += send(ser, "yes", timeout)

    if "% Invalid" in svar or "% Incomplete" in svar:
        print(f"\n!!! IOS godtok ikke: {kommando}")
    return svar


def til_privileged_exec(ser):
    """Kom til Router#-prompten uansett hvor enheten står når vi kobler til."""
    ser.write(b"\r")
    for _ in range(15):
        svar = vent_paa_prompt(ser, timeout=5).rstrip()
        if "initial configuration dialog" in svar:
            ser.write(b"no\r")                      # hopp over oppsettsveiviseren
        elif svar.endswith("Password:"):
            pw = getpass.getpass("Enheten ber om eksisterende passord: ")
            ser.write((pw + "\r").encode())
        elif svar.endswith(")#"):
            ser.write(b"end\r")                     # står i config-modus
        elif svar.endswith("#"):
            return                                  # ferdig - vi er i privileged exec
        elif svar.endswith(">"):
            ser.write(b"enable\r")
        else:
            ser.write(b"\r")                        # f.eks. "Press RETURN to get started"
    raise SystemExit("Fikk ikke kontakt med enheten. Sjekk kabel og COM-port.")


# ---------------------------------------------------------------------------
# Hvilke kommandoer som skal sendes
# ---------------------------------------------------------------------------
def felles_kommandoer(v):
    """Likt for router og switch. hostname og domene MÅ komme før crypto key."""
    return [
        f"hostname {v['hostname']}",
        "no ip domain-lookup",
        f"ip domain-name {v['domene']}",
        f"username {v['brukernavn']} privilege 15 secret {v['passord']}",
        f"enable secret {v['enable']}",
        "service password-encryption",
        "crypto key generate rsa general-keys modulus 2048",
        "ip ssh version 2",
        f"line vty {v['vty']}",
        "login local",
        "transport input ssh",
        "exit",
    ]


def router_kommandoer(v):
    return [
        f"interface {v['interface']}",
        f"ip address {v['ip']} {v['maske']}",
        "no shutdown",
        "exit",
    ]


def switch_kommandoer(v):
    kommandoer = [
        f"vlan {v['vlan']}",
        "name MGMT",
        "exit",
        f"interface vlan {v['vlan']}",
        f"ip address {v['ip']} {v['maske']}",
        "no shutdown",
        "exit",
        f"ip default-gateway {v['gateway']}",
    ]
    if v["uplink"]:
        kommandoer += [f"interface {v['uplink']}", "switchport mode trunk", "exit"]
    return kommandoer


# ---------------------------------------------------------------------------
# Input fra bruker
# ---------------------------------------------------------------------------
def spør_passord(tekst):
    while True:
        p1 = getpass.getpass(f"{tekst}: ")
        if p1 and p1 == getpass.getpass("  Gjenta: "):
            return p1
        print("  Tomt eller ikke likt, prøv igjen.")


def hent_verdier():
    v = {}
    v["type"] = input("Router eller switch? (r/s): ").strip().lower()
    v["hostname"] = input("Hostname: ")
    v["domene"] = input("Domenenavn (f.eks. stud2.lab): ")
    v["brukernavn"] = input("Brukernavn for SSH: ")
    v["passord"] = spør_passord("Passord for SSH-brukeren")
    v["enable"] = spør_passord("Enable secret")
    v["ip"] = input("Management-IP: ")
    v["maske"] = input("Subnettmaske [255.255.255.0]: ") or "255.255.255.0"

    if v["type"] == "r":
        v["vty"] = "0 4"
        v["interface"] = input("Interface for IP [GigabitEthernet0/0]: ") or "GigabitEthernet0/0"
    else:
        v["vty"] = "0 15"
        v["vlan"] = input("Management-VLAN [99]: ") or "99"
        v["gateway"] = input("Default gateway: ")
        v["uplink"] = input("Trunk-port mot router (tom = ingen): ")
    return v


# ---------------------------------------------------------------------------
# Hovedprogram
# ---------------------------------------------------------------------------
def main():
    v = hent_verdier()
    kommandoer = felles_kommandoer(v)
    kommandoer += router_kommandoer(v) if v["type"] == "r" else switch_kommandoer(v)

    print("\nDisse kommandoene sendes (passord skjult):")
    for k in kommandoer:
        print("  " + k.replace(v["passord"], "****").replace(v["enable"], "****"))

    if input("\nSende til enheten? (j/n): ").lower() != "j":
        print("Avbrutt - ingenting sendt.")
        return

    port = input("COM-port COM1: ")
    with serial.Serial(port, baudrate=9600, timeout=1) as ser:
        til_privileged_exec(ser)
        send(ser, "terminal length 0")
        send(ser, "configure terminal")
        for k in kommandoer:
            # RSA-nøkler kan ta lang tid å generere
            send(ser, k, timeout=90 if k.startswith("crypto") else 10)
        send(ser, "end")
        send(ser, "write memory", timeout=30)
        send(ser, "show ip ssh")

    print(f"\n\nFerdig! Test fra PC-en:  ssh {v['brukernavn']}@{v['ip']}")


if __name__ == "__main__":
    main()