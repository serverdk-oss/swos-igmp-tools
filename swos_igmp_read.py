#!/usr/bin/env python3
"""
Read-only status tool for MikroTik SwOS switches (full SwOS, not Lite).

Built on top of the `mikrotik-swos` PyPI library (github.com/lanrat/python-mikrotik-swos),
which handles HTTP Digest auth + the SwOS JS-object wire format. This script adds two
things that library doesn't expose yet: the system-wide IGMP snooping/querier/fastleave/
version flags, and the live IGMP group-membership table (`!igmp.b`).

Field names (igmp, igmq, igfl, igve, addr/vlan/prts for !igmp.b) were extracted directly
from a real SwOS unit's shipped JS (webui_reference/CRS326-24S+2Q/index.html in the
python-mikrotik-swos repo), not guessed from hex dumps. Confirmed against SwOS 2.17/2.18.

READ-ONLY: only issues GET requests. No POST/write capability.

Usage: python3 swos_igmp_read.py <switch-ip> [username] [password]
       (defaults: username=admin, password="")
"""
import sys
import requests
from requests.auth import HTTPDigestAuth

from swos.core import parse_js_object, decode_port_mask, decode_ip_address_le
from swos import get_links, get_system_info


def fetch_raw(url, path, auth):
    r = requests.get(f"{url}/{path}", auth=auth, timeout=5)
    r.raise_for_status()
    return parse_js_object(r.text)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    ip = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else "admin"
    password = sys.argv[3] if len(sys.argv) > 3 else ""
    url = f"http://{ip}"
    auth = HTTPDigestAuth(username, password)

    sysinfo = get_system_info(url, username, password)
    print(f"=== {ip} — {sysinfo['identity'] or sysinfo['model']} ({sysinfo['model']}) ===")
    print(f"uptime: {sysinfo['uptime']}s | mac: {sysinfo['mac_address']} | fw: {sysinfo['version']}")

    raw_sys = fetch_raw(url, "sys.b", auth)
    igmp_on = bool(raw_sys.get("igmp"))
    igmq_on = bool(raw_sys.get("igmq"))
    igfl_on = bool(raw_sys.get("igfl"))
    igve = ["v2", "v3"][raw_sys.get("igve")] if raw_sys.get("igve") in (0, 1) else raw_sys.get("igve")
    print(f"\nIGMP Snooping: {'ON' if igmp_on else 'off'}")
    print(f"IGMP Querier:  {'ON' if igmq_on else 'off'}")
    print(f"IGMP Fast Leave: {'ON' if igfl_on else 'off'}")
    print(f"IGMP Version:  {igve}")

    try:
        groups = fetch_raw(url, "!igmp.b", auth)
        if isinstance(groups, dict):
            groups = [groups]
        port_count = len(get_links(url, username, password))
        print(f"\nIGMP group membership table ({len(groups)} entries):")
        print(f"{'Group Address':<18} {'VLAN':<6} Member Ports")
        for g in groups:
            addr = g.get("addr")
            vlan = g.get("vlan", "-")
            ports = decode_port_mask(g.get("prts", 0), port_count)
            addr_str = decode_ip_address_le(addr) if isinstance(addr, int) else str(addr)
            print(f"{addr_str:<18} {vlan!s:<6} {ports}")
    except Exception as e:
        print(f"\n(could not read live IGMP group table: {e})")

    print("\nPort link status:")
    for link in get_links(url, username, password):
        print(f"  {link}")


if __name__ == "__main__":
    main()
