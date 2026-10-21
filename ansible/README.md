# Del 2 – Konfigurasjon med Ansible

Ansible konfigurerer STUD2-oppsettet over SSH etter at enhetene har fått SSH med Python-scriptet i Del 1. Alle enhetene kjører IOS eller IOS-XE, så collection-en **`cisco.ios`** brukes for alle.

Hva som settes opp:

- **Routerne (R1 og R2):** router-on-a-stick med ett subinterface per VLAN, og HSRP slik at de deler én gateway (.1) i hvert nett
- **Switchene (SW1 og SW2):** VLAN-er, trunker med native VLAN 999, access-porter til PC-ene med PortFast
- **DHCP** på routerne for VLAN 10 og 20
- **EtherChannel (LACP)** på SW2, klar for å kobles mot STUD1

## Topologi og IP-plan

```
 MGMT-PC 10.2.0.10
      │ Gi1/0/1
 STUD2-MLS (3650) 10.2.0.5 ── VLAN 100 (admin-nett 10.2.0.0/24, gateway 10.2.0.1 = HSRP)
      │ Gi1/0/2                 │ Gi1/0/3
 STUD2-R1 Gi0/0 .2         STUD2-R2 Gi0/0 .3
 STUD2-R1 Gi0/1 (trunk)    STUD2-R2 Gi0/1 (trunk)
      │ Fa0/1                   │ Fa0/2
      └──── STUD2-SW1 (2960) 192.168.99.11 ────┘
                  │ Fa0/4 (trunk)
            STUD2-SW2 (C1000) 192.168.99.12
            │ Gi1/0/2        │ Gi1/0/3        ║ Gi1/0/4 + Gi1/0/5 (Po1, LACP)
          PC VLAN 20      PC VLAN 10        STUD1
```

| VLAN | Navn | Subnett | Gateway (HSRP) | R1 / R2 | DHCP R1 | DHCP R2 |
|---|---|---|---|---|---|---|
| 10 | VLAN10 | 192.168.10.0/24 | .1 | .2 / .3 | .100–.149 | .150–.199 |
| 20 | VLAN20 | 192.168.20.0/24 | .1 | .2 / .3 | .100–.149 | .150–.199 |
| 99 | MGMT | 192.168.99.0/24 | .1 | .2 / .3 | – | – |
| 100 | admin-nett | 10.2.0.0/24 | .1 | .2 / .3 | – | – |
| 999 | NATIVE_UNUSED | – | – | – | – | – |

HSRP-gruppenummeret er det samme som VLAN-ID-en (admin-nettet bruker gruppe 100). R1 har prioritet 110 og er aktiv, R2 har 90 og er standby.

## Struktur

```
ansible/
├── ansible.cfg                  ← peker på inventaret, slår av host key checking
├── requirements.txt             ← pip-pakker (med paramiko<4, se feilsøking)
├── site.yml                     ← kjører alle playbookene i riktig rekkefølge
├── inventory/
│   ├── hosts.yml                ← enhetene og gruppene (core, routers, access)
│   ├── group_vars/
│   │   ├── all/
│   │   │   ├── main.yml         ← hvordan Ansible kobler til (network_cli, paramiko)
│   │   │   ├── network.yml      ← ★ IP-planen: VLAN-er, nett, gateway
│   │   │   └── vault.yml        ← kryptert: brukernavn, passord, enable secret
│   │   ├── routers.yml          ← interface-navn som er likt på begge routerne
│   │   └── access.yml           ← native VLAN, standardverdier for switchene
│   └── host_vars/
│       ├── stud2-r1.yml         ← .2, HSRP-prioritet 110, DHCP .100–.149
│       ├── stud2-r2.yml         ← .3, HSRP-prioritet 90, DHCP .150–.199
│       ├── stud2-sw1.yml        ← trunk-porter
│       └── stud2-sw2.yml        ← trunk, access-porter, EtherChannel
└── playbooks/
    ├── routers.yml              ← subinterfaces + HSRP
    ├── switches.yml             ← VLAN-er, trunker, access-porter, EtherChannel
    └── dhcp.yml                 ← DHCP-pool per VLAN
```

**Prinsippet:** Playbookene inneholder ingen IP-adresser eller portnavn. Alt hentes fra variablene. `network.yml` fungerer som en variabelfil, omtrent som `terraform.tfvars`: IP-planen står ett sted, og playbookene bygger konfigurasjonen ut fra den.

## Installasjon (WSL / Ubuntu)

Ansible kjører ikke på Windows, så det installeres i WSL:
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip
python3 -m venv ~/ansible-venv
source ~/ansible-venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install cisco.ios ansible.netcommon ansible.utils
```

Passordene ligger i `inventory/group_vars/all/vault.yml`, kryptert med Ansible Vault. Den kan lages på nytt slik:
```bash
export EDITOR=nano
ansible-vault create inventory/group_vars/all/vault.yml
```
med innholdet:
```yaml
vault_user: joakim
vault_password: <SSH-passord>
vault_enable: <enable secret>
```
Fila er kryptert og kan derfor ligge trygt i et offentlig repo.

## Bruk

Alle kommandoer kjøres fra `ansible/`-mappa, fordi `ansible.cfg` bare leses fra mappa du står i.

```bash
cd ~/nk2-ak2/ansible

# Test at Ansible når enhetene
ansible core,routers -m cisco.ios.ios_command -a "commands='show version | include uptime'" --ask-vault-pass

# Konfigurer alt
ansible-playbook site.yml --ask-vault-pass

# Se hva som ville blitt endret, uten å endre noe
ansible-playbook site.yml --ask-vault-pass --check --diff

# Bare én del
ansible-playbook playbooks/dhcp.yml --ask-vault-pass
```

`site.yml` kjører i denne rekkefølgen:
1. **routers.yml**: Må være først. Switchene i VLAN 99 nås bare gjennom routernes subinterface `.99`.
2. **switches.yml**: Kjører med `serial: 1`, slik at SW1 blir ferdig før SW2. SW2 nås bare gjennom SW1 Fa0/4, som ikke er trunk før SW1 er konfigurert.
3. **dhcp.yml**

Hver playbook lagrer konfigurasjonen med `save_when: modified`, altså bare hvis noe faktisk er endret.

### Idempotens

Playbookene kan kjøres så mange ganger man vil. Andre gang er alt grønt `ok`, fordi Ansible bare sender det som mangler:

```
PLAY RECAP
stud2-r1   : ok=7   changed=0   unreachable=0   failed=0
stud2-r2   : ok=7   changed=0   unreachable=0   failed=0
stud2-sw1  : ok=5   changed=0   unreachable=0   failed=0   skipped=8
stud2-sw2  : ok=13  changed=0   unreachable=0   failed=0
```
SW1 har `skipped`, fordi den ikke har access-porter eller EtherChannel. Listene er tomme, så de taskene hoppes over.

### Verifisering

```bash
ansible routers -m cisco.ios.ios_command -a "commands='show standby brief'" --ask-vault-pass
ansible routers -m cisco.ios.ios_command -a "commands='show ip dhcp binding'" --ask-vault-pass
ansible access -m cisco.ios.ios_command -a "commands='show interfaces trunk'" --ask-vault-pass
ansible stud2-sw2 -m cisco.ios.ios_command -a "commands='show etherchannel summary'" --ask-vault-pass
```

Testet resultat:
- R1 er Active og R2 Standby i alle HSRP-gruppene.
- En PC på SW2 Gi1/0/3 fikk 192.168.10.150 og en PC på Gi1/0/2 fikk 192.168.20.151, med gateway .1.
- Begge adressene ble delt ut fra R2s område. Det er den routeren som svarer først som deler ut, og fordi områdene ikke overlapper, kan de aldri gi bort samme adresse.

## Vedlikehold og utvidelse

| Jeg vil … | Endre | Kjør |
|---|---|---|
| Legge til et VLAN | Nytt element i `vlans:` i `network.yml` (`dhcp: true/false`) | `site.yml` |
| Flytte en PC til et annet VLAN | `vlan:` under porten i `host_vars/stud2-sw2.yml` | `playbooks/switches.yml` |
| Legge til en access-port | Nytt element i `access_ports:` i switchens `host_vars` | `playbooks/switches.yml` |
| Bytte aktiv HSRP-router | `hsrp_priority` i `host_vars/stud2-r*.yml` | `playbooks/routers.yml` |
| Endre DHCP-område | `dhcp_first` / `dhcp_last` i `host_vars/stud2-r*.yml` | `playbooks/dhcp.yml` |
| Legge til en port i EtherChannel | Ny port under `members:` i `host_vars/stud2-sw2.yml` | `playbooks/switches.yml` |
| Legge til en ny switch | Legg den under `access` i `hosts.yml`, lag `host_vars/<navn>.yml` og kjør Python-scriptet på den først | `playbooks/switches.yml` |

Et nytt VLAN får automatisk subinterface og HSRP på routerne, blir opprettet og tillatt på trunkene, og får DHCP-pool hvis `dhcp: true`. Ingen playbook må endres.

## EtherChannel mot STUD1

SW2 har Port-channel 1 klar på **Gi1/0/4 + Gi1/0/5**. For at STUD1 skal kunne koble seg til, må STUD1 sette opp:

| Innstilling | Verdi |
|---|---|
| Protokoll | LACP (`channel-group X mode active` eller `passive`) |
| Modus | trunk |
| Native VLAN | 999 |
| Tillatte VLAN-er | 10, 20 |
| VTP | transparent (så VLAN-databasene ikke overskriver hverandre) |

VLAN 99 og 100 går ikke over EtherChannel. Management holdes på STUD2-siden.

Uten kabel viser `show etherchannel summary` `Po1(SD)` med portene `(D)`. Når STUD1 er koblet til med riktig oppsett, blir det `Po1(SU)` med portene `(P)`.

## Hva kan ikke Ansible gjøre? (oppgave 2.4)

Ansible (`network_cli`) trenger en fungerende SSH-tilkobling til enheten. Alt som må skje *før* SSH virker, eller som bryter tilkoblingen Ansible står på, kan ikke gjøres med Ansible:

1. **Førstegangsoppsett.** En nullstilt enhet har ingen IP, ingen bruker og ingen RSA-nøkler. Dette må gjøres over konsollkabel. Derfor brukes Python-scriptet (pyserial) i Del 1.
2. **Oppsettsveiviseren, `write erase` og `reload`** til fabrikkoppsett skjer på konsollen.
3. **Portene på 3650 i VLAN 100.** Ansible når 3650 *gjennom* disse portene, så de måtte settes opp før Ansible kunne koble til. De ble satt for hånd på konsollen.
4. **Endringer som kutter Ansibles egen tilkobling**, som å endre management-IP-en Ansible er koblet til.

**Slik henger Python og Ansible sammen:** Python-scriptet gjør hver enhet nåbar med SSH. Ansible tar over derfra og bygger resten av nettverket. IP-adressene som skrives inn i scriptet er de samme som står i `inventory/hosts.yml`, så de to delene utgjør én flyt:

```
fabrikkny enhet ──► ssh_oppsett.py (konsoll) ──► SSH oppe ──► ansible-playbook site.yml ──► ferdig nettverk
```

## Problemer jeg møtte, og hvordan de ble løst

| Problem | Årsak | Løsning |
|---|---|---|
| `ansible-galaxy: The term is not recognized` | Kjørte kommandoen i PowerShell | Ansible finnes bare i WSL/Ubuntu |
| `ansible-vault: command not found` på ny PC | Python-miljøet var ikke aktivert eller installert | `source ~/ansible-venv/bin/activate` (eller installer) |
| `Incompatible ssh peer (no acceptable kex algorithm)` mot 2901 | paramiko 4 har fjernet SHA-1-nøkkelutvekslingen som gammel IOS bruker | `pip install "paramiko>=3.4,<4"`, låst i `requirements.txt` |
| `'host_index' is undefined` | Mappa het `hosts_vars` i stedet for `host_vars` | Ansible krever nøyaktig navnet `host_vars` |
| `No inventory was parsed` | Kjørte fra `~/nk2-ak2` i stedet for `~/nk2-ak2/ansible` | `ansible.cfg` leses bare fra mappa du står i |
| `YAML parsing failed` | `cat > ... <<'EOF'`, `EOF` og språknavnet `yaml` ble limt inn i filene | Slettet linjene. `--syntax-check` fanger slike feil (men leser ikke `host_vars`) |
| Routernes Gi0/1 sto som `down/down` | Dårlig kabel | `down/down` = fysisk feil, `administratively down` = `shutdown` |
| PC-en nådde ikke 192.168.99.x selv om routerne gjorde det | Lab-PC-en har to nettverkskort, og Windows sendte trafikken ut skolenettet | `route add 192.168.0.0 mask 255.255.0.0 10.2.0.1` (som administrator) |
| PortFast-tasken på SW2 ble `changed` hver gang | C1000 skriver `spanning-tree portfast edge` i running-config | Kommandoen som variabel (`portfast_command`) per enhet. `ios_config` sammenligner tekst med running-config |
| `git push` ble avvist (`fetch first`) | GitHub hadde commits fra en annen PC | `git pull --rebase` og så `git push` |
