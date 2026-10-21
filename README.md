# NK2 Arbeidskrav 2 – Automatisering av Cisco-utstyr (STUD2)

Repoet automatiserer oppsettet av STUD2-siden av racket i to trinn:

| Del | Verktøy | Hva det gjør | Dokumentasjon |
|---|---|---|---|
| 1 | Python + pyserial over konsollkabel | Gir hver enhet hostname, bruker, SSH og management-IP | [python/README.md](python/README.md) |
| 2 | Ansible (`cisco.ios`) over SSH | VLAN-er, trunker, router-on-a-stick, HSRP, DHCP og EtherChannel | [ansible/README.md](ansible/README.md) |

```
  Del 1: Python (konsoll)              Del 2: Ansible (SSH)
 ┌──────────────────────────┐        ┌──────────────────────────────────┐
 │ hostname, bruker, RSA,   │  SSH   │ subinterfaces + HSRP, VLAN-er,   │
 │ SSH v2, management-IP    │ ─────► │ trunker, access-porter, DHCP,    │
 │ (fabrikkny enhet)        │  oppe  │ EtherChannel mot STUD1           │
 └──────────────────────────┘        └──────────────────────────────────┘
```

Python gjør enhetene nåbare, og Ansible tar over derfra. Hvorfor det må deles slik, står i [ansible/README.md](ansible/README.md#hva-kan-ikke-ansible-gjøre-oppgave-24).

## Utstyr (STUD2)

| Hostname | Modell | Rolle | Management-IP |
|---|---|---|---|
| STUD2-MLS | Catalyst 3650-24PS | Samler PC og routere i admin-nettet | 10.2.0.5 |
| STUD2-R1 | Cisco 2901 | Router-on-a-stick, HSRP aktiv, DHCP | 10.2.0.2 |
| STUD2-R2 | Cisco 2901 | Router-on-a-stick, HSRP standby, DHCP | 10.2.0.3 |
| STUD2-SW1 | Catalyst 2960-24TT | Kobler routerne til resten av nettet | 192.168.99.11 |
| STUD2-SW2 | Catalyst 1000 | Klient-PC-er og EtherChannel mot STUD1 | 192.168.99.12 |

## Rask start

1. Sett opp SSH på hver enhet med `python/ssh_oppsett.py` (se [python/README.md](python/README.md)).
2. Konfigurer resten med Ansible fra `ansible/`-mappa:
   ```bash
   ansible-playbook site.yml --ask-vault-pass
   ```
