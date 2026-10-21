# Del 1 – SSH-oppsett via konsollkabel med Python

`ssh_oppsett.py` kobler seg til en Cisco-router eller -switch over konsollkabelen og setter opp det som trengs for å nå enheten med SSH:

- hostname og domenenavn
- lokal bruker med `privilege 15` og enable secret
- RSA-nøkler (2048 bit) og SSH versjon 2
- VTY-linjer som bare tar imot SSH (`login local`, `transport input ssh`)
- management-IP: på et fysisk interface (router) eller en VLAN-SVI med default gateway (switch)

Etter dette kan enheten konfigureres videre med Ansible over nettverket.

## Gjenbrukbart: ingenting er hardkodet

Scriptet spør om alle verdier når det kjører. Det samme scriptet ble brukt på alle fem enhetene, selv om de er tre forskjellige modeller. Passord leses med `getpass`, så de vises ikke på skjermen og havner aldri i koden eller i Git.

Koden er delt i funksjoner etter ansvar:

| Funksjon | Ansvar |
|---|---|
| `vent_paa_prompt()` | Leser fra serieporten til enheten viser en prompt (`#`, `>` eller `:`) |
| `send()` | Sender én kommando, venter på svar, svarer `yes` på `[yes/no]` og sier fra om `% Invalid input` |
| `til_privileged_exec()` | Kommer seg til `#`-prompten uansett hvor enheten står: hopper over oppsettsveiviseren, kjører `enable`, går ut av config-modus |
| `felles_kommandoer()` / `router_kommandoer()` / `switch_kommandoer()` | Bygger lista med IOS-kommandoer. Vil man endre hva som settes opp, er det bare her |
| `hent_verdier()` | Spør brukeren om alle verdiene |

Scriptet venter på prompt etter hver kommando. Konsollen går på 9600 baud, og sendes alt på én gang, mister enheten kommandoer.

## Slik kobler du opp mot en enhet

### Det du trenger

- Windows-PC med Python 3 (`py --version`)
- pyserial: `py -m pip install pyserial`
- Konsollkabel (RJ45 til USB / DB9) i **CONSOLE**-porten på enheten

### Finn COM-porten

**Win + X** → **Enhetsbehandling** → **Porter (COM og LPT)**. Der står for eksempel `COM1` eller `COM3`. Dra ut kabelen og sett den i igjen, så ser du hvilken port som forsvinner og kommer tilbake.

Scriptet må kjøres i **Windows (PowerShell)**, ikke i WSL/Ubuntu. Det er bare Windows som ser COM-portene.

### Nullstill enheten først (hvis den har gammel konfig)

I PuTTY (Serial, COM-porten, 9600):
```
enable
write erase
delete flash:vlan.dat      ← bare switcher
reload                     ← svar "no" på "Save?"
```
Svar `no` på «initial configuration dialog» etter oppstart, og **lukk PuTTY** før du kjører scriptet.

### Kjør scriptet

```powershell
cd \\wsl.localhost\Ubuntu\home\joakim\nk2-ak2\python
py ssh_oppsett.py
```

Scriptet viser alle kommandoene, med passordene skjult, før noe sendes. Svarer du `n`, avbrytes det uten at noe sendes. Det er nyttig for å sjekke verdiene først.

### Verdiene jeg brukte for STUD2

Domene `stud2.lab`, brukernavn `joakim` og maske `255.255.255.0` på alle.

| Rekkefølge | Enhet | Type | Hostname | Management-IP | Interface / VLAN | Gateway | Trunk-port |
|---|---|---|---|---|---|---|---|
| 1 | 3650 | `s` | STUD2-MLS | 10.2.0.5 | VLAN 100 | 10.2.0.1 | – |
| 2 | 2901 | `r` | STUD2-R1 | 10.2.0.2 | GigabitEthernet0/0 | – | – |
| 3 | 2901 | `r` | STUD2-R2 | 10.2.0.3 | GigabitEthernet0/0 | – | – |
| 4 | 2960 | `s` | STUD2-SW1 | 192.168.99.11 | VLAN 99 | 192.168.99.1 | FastEthernet0/1 |
| 5 | Catalyst 1000 | `s` | STUD2-SW2 | 192.168.99.12 | VLAN 99 | 192.168.99.1 | GigabitEthernet1/0/1 |

Rekkefølgen er valgt fordi PC-en når routerne via 3650, og switchene via routerne.

**Ekstra steg på 3650:** Portene mot PC-en og routerne må legges i VLAN 100 for hånd, rett etter scriptet:
```
interface range GigabitEthernet1/0/1 - 3
 switchport mode access
 switchport access vlan 100
 no shutdown
```

### Test SSH fra PC-en

1. Nettverkskabel fra PC-en til port 1 (Gi1/0/1) på 3650.
2. Statisk IP på PC-en: **Win + R** → `ncpa.cpl` → IPv4 → `10.2.0.10` / `255.255.255.0` / gateway `10.2.0.1`.
3. Test:
   ```powershell
   ping 10.2.0.5
   ssh joakim@10.2.0.5
   ```

**Routerne (2901) trenger ekstra SSH-flagg.** De kjører eldre IOS som bare støtter SHA-1-baserte algoritmer, og dem har moderne SSH-klienter slått av. `ssh joakim@10.2.0.2` gir derfor `Unable to negotiate`. Bruk den lange varianten for R1 og R2:
```powershell
ssh -oKexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group1-sha1 -oHostKeyAlgorithms=+ssh-rsa -oCiphers=+aes128-cbc,aes256-cbc,3des-cbc joakim@10.2.0.2
```
For å slippe å skrive dette hver gang, kan flaggene legges i `~/.ssh/config` (se [feilsøking](#problemer-jeg-møtte-og-hvordan-de-ble-løst)). Da virker vanlig `ssh joakim@10.2.0.2`. 3650 og switchene har nyere IOS og trenger ikke dette.

Switchene i VLAN 99 (192.168.99.x) kan først nås med SSH når routerne router VLAN 99. Det setter Ansible opp i Del 2.

## Problemer jeg møtte, og hvordan de ble løst

| Problem | Årsak | Løsning |
|---|---|---|
| Switchen hadde Vlan11–14, Loopback0 og en routet port med IP | Gammel konfig fra andre klasser | `write erase` + `delete flash:vlan.dat` + `reload` |
| Havnet i spørsmål om «management interface» | Svarte `yes` på oppsettsveiviseren etter reload | Ctrl + C, eller velg `0` til slutt. Scriptet svarer selv `no` |
| `could not open port '1'` | Skrev bare tallet | Skriv hele navnet: `COM1` |
| `PermissionError ... Access is denied` | PuTTY hadde COM-porten åpen | Lukk PuTTY. Bare ett program kan bruke porten om gangen |
| Fant ikke «gigabit-portene» på 3650, bare tomme hull | Hullene er SFP-spor (Gi1/1/1–4) | Gi1/0/1–24 er de vanlige RJ45-portene foran |
| `Connection refused` mot 3650 | `%IP-4-DUPADDR`: PC-en hadde samme IP som switchen (10.2.0.5) | Ga PC-en 10.2.0.10 |
| `unable to negotiate` mot 2901 | Gammel IOS støtter bare SHA-1-baserte SSH-algoritmer | Slo på eldre algoritmer i `~/.ssh/config` på PC-en (se under) |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | Enheten fikk ny RSA-nøkkel etter nullstilling | `ssh-keygen -R 10.2.0.5` fjerner den gamle nøkkelen |
| Catalyst 1000 hadde andre portnavn enn i diagrammet | C1000 bruker `GigabitEthernet1/0/x`, ikke `FastEthernet0/x` | Sjekk alltid med `show ip interface brief` |

SSH-konfig på Windows for de eldre routerne (`%USERPROFILE%\.ssh\config`). Lag den med `notepad $HOME\.ssh\config` i PowerShell, og pass på at Notisblokk ikke legger til `.txt`:
```
Host 10.2.0.2 10.2.0.3
    KexAlgorithms +diffie-hellman-group14-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group1-sha1
    HostKeyAlgorithms +ssh-rsa
    Ciphers +aes128-cbc,aes256-cbc,3des-cbc
```
