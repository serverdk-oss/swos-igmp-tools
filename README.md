# swos-tools

A read-only Python toolkit for querying **MikroTik SwOS** switches — the switches
that have *no SSH, no CLI, and no REST API*, only a JavaScript web UI talking to the
device over a proprietary binary format (`/sys.b`, `/link.b`, `/igmp.b`, ...).

This project fills that gap: it lets you read status, stats, and IGMP snooping/querier
state from a script instead of clicking through the web UI by hand.

## Credits

This project is built directly on top of **[python-mikrotik-swos](https://github.com/lanrat/python-mikrotik-swos)**
by lanrat and contributors ("SwOS Contributors"), MIT licensed. That library did the hard
part — reverse-engineering SwOS's Digest auth and binary wire format — and this repo
depends on it via pip rather than vendoring its source.

What this repo adds on top:
- `swos_igmp_read.py` — IGMP snooping/querier/fast-leave/version status and the live
  multicast group table, which the upstream library doesn't expose
- A compatibility catalog extending coverage checks across additional switch models
  (see the table below), using the reference web-UI JS the upstream repo already bundles
  for several real devices

If you're looking for the base functionality (port stats, VLANs, PoE, SFP, SNMP), that's
all upstream — go there first. This repo exists specifically for the IGMP gap.

## What's included

- **`mikrotik-swos`** (PyPI, [github.com/lanrat/python-mikrotik-swos](https://github.com/lanrat/python-mikrotik-swos))
  — an existing, actively maintained library this project builds on. It already handles:
  - HTTP **Digest** auth (not Basic — a plain `curl -u user:pass` will 401)
  - The SwOS binary wire format (`{key:val,...}` blobs, little-endian IPs, hex-encoded
    ASCII strings, port bitmasks)
  - Read functions: `get_system_info`, `get_links`, `get_vlans`, `get_poe`, `get_lag`,
    `get_hosts`, `get_sfp_info`, `get_snmp`
  - Write functions also exist upstream (`set_port_config`, `set_vlans`, etc.) but this
    project does not wire them into anything — treat any switch you point this at as
    read-only unless you deliberately reach for the upstream write calls yourself.

- **`swos_igmp_read.py`** — a small extension adding the one thing the upstream library
  doesn't expose: IGMP snooping/querier status and the live multicast group table.
  - From `sys.b`: `igmp` (snooping on/off), `igmq` (querier on/off), `igfl` (fast leave
    on/off), `igve` (IGMP version, `0` → v2, `1` → v3)
  - From `!igmp.b`: the live group-membership table — `addr` (multicast group, decoded
    from a little-endian-encoded IP), `vlan`, `prts` (bitmask of member ports)

  These field names were taken directly from a real SwOS unit's own shipped JavaScript
  (not guessed from raw hex) — see [Provenance](#provenance) below.

## Usage

```bash
python3 -m venv venv
venv/bin/pip install mikrotik-swos

venv/bin/python3 swos_igmp_read.py <switch-ip> [username] [password]
# username/password default to admin / "" (empty) if omitted
```

Example output:

```
IGMP Snooping: on
IGMP Querier:  on
Fast Leave:    on
IGMP Version:  v3

Active groups:
  239.1.0.5      vlan 1   ports: 17,24
  239.1.1.1      vlan 1   ports: 24
  239.255.255.250 vlan 1  ports: (none — SSDP, no downstream members)
```

Anything else the upstream library supports (port stats, VLANs, PoE, SFP info, SNMP
config) is available the normal way — see the `mikrotik-swos` PyPI docs.

## Tested / compatible models

| Model | Firmware family | IGMP fields (`igmp`/`igmq`/`igfl`/`igve`) | Group table (`!igmp.b`) | Base library (port/VLAN/PoE/etc.) | Confidence |
|---|---|---|---|---|---|
| CSS326-24G-2S+ | Full SwOS | present | present | works | **Live-tested** against real hardware, both status reads and the IGMP extension confirmed correct |
| CRS326-24S+2Q | Full SwOS | present, identical | present | works | Confirmed against the model's real shipped web-UI JS; not live-tested on physical hardware |
| CRS305-1G-4S+ | Full SwOS | present, identical | present | works | Same as above — JS-confirmed, not live-tested |
| CRS309-1G-8S+ | Full SwOS | present, identical | present | works | Same as above — JS-confirmed, not live-tested |
| CRS310-8G+2S+ | Full SwOS | present, identical | present | works | Same as above — JS-confirmed, not live-tested |
| CSS610-8G-2S+ | SwOS **Lite** | **absent** — this firmware line has no IGMP feature in the UI at all | absent | untested — Lite uses a different `.b` endpoint naming scheme not covered here | Known gap, see below |
| CSS610-8P-2S+ | SwOS **Lite** | absent (same as above) | absent | untested | Known gap, see below |

**Takeaway:** `swos_igmp_read.py` works across the entire full-SwOS / CRS3xx+CSS326
family — the IGMP feature set and field layout are identical on every full-SwOS model
checked so far. **SwOS Lite** (CSS610 and likely other budget/PoE-lite models) is a real,
confirmed gap: those devices simply don't expose an IGMP feature in their UI at all, so
this tool can't read something that isn't there. A Lite-specific pass (different field
scheme entirely, even for basic port/VLAN reads) would be a separate piece of work.

## Provenance — confirmed vs. guessed

Correctness matters more than speed here, so every field name/type above was checked
against a **real device's own shipped code**, not inferred from staring at hex dumps:

- Live devices: confirmed by capturing real HTTP responses and cross-checking against
  the decode logic.
- Non-live models: cross-checked against the `webui_reference/` folder in the upstream
  `python-mikrotik-swos` repo, which bundles the actual `index.html`/JS captured from
  real physical units for several models — the same ground truth a firmware-image
  extraction would produce, without needing to download and unpack a firmware image
  by hand.

If you add support for a new model, please note in a PR/issue whether it was confirmed
against live hardware or only against reference JS — that distinction is deliberately
preserved in the table above and should stay that way.

## Safety notes

- This tool only ever sends `GET` requests. It does not call any of the upstream
  library's write functions.
- SwOS devices with no password set (blank password on the `admin`/configured account)
  are common in small deployments — this tool doesn't change that, and doesn't store or
  transmit credentials anywhere beyond the single request to the switch you point it at.
- Don't run write operations against switches carrying production traffic without
  understanding exactly what you're changing — SwOS has no undo/rollback UI beyond
  re-entering the old values by hand.
