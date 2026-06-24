#!/usr/bin/env python3
"""
OPC-UA browser for PLCNext (or any OPC-UA server).

Default: print the full device/variable tree.
--modbus: show only Modbus devices and their registers.

Usage:
  python3 opc_browse.py [url] [--user USER] [--password PASS]
  python3 opc_browse.py --modbus
  python3 opc_browse.py --depth 12
"""

import asyncio
import argparse
import sys
import socket
from pathlib import Path

APP_URI  = "urn:opc-browse:client"
CERT_DIR = Path.home() / ".config" / "opc_browse"
CERT_FILE = CERT_DIR / "client_cert.pem"
KEY_FILE  = CERT_DIR / "client_key.pem"

MODBUS_KEYWORDS = {
    "xHmi2152Heartbeat", "modbus", "mb", "coil",
    "holding", "register", "input_reg", "discrete",
}

try:
    from asyncua import Client, ua
    from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
    from cryptography.hazmat.primitives.serialization import Encoding
except ImportError:
    print("asyncua not installed. Run: pip install asyncua cryptography")
    sys.exit(1)


# ── certificate ──────────────────────────────────────────────────────────────

def ensure_cert():
    """Return (cert_path, key_path), generating and saving them if needed."""
    if CERT_FILE.exists() and KEY_FILE.exists():
        return CERT_FILE, KEY_FILE

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import Encoding
    import datetime

    print(f"Generating persistent client certificate in {CERT_DIR} ...")
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "opc_browse_client"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OpcBrowse"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(APP_URI),
                x509.DNSName(socket.gethostname()),
            ]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    CERT_FILE.write_bytes(cert.public_bytes(Encoding.PEM))
    KEY_FILE.write_bytes(key.private_bytes(
        Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    print(f"  Certificate : {CERT_FILE}")
    print(f"  Private key : {KEY_FILE}")
    print()
    print("  *** ACTION REQUIRED ***")
    print("  Copy the certificate to the PLCNext and trust it:")
    print(f"  1. scp {CERT_FILE} admin@10.240.240.31:/opt/plcnext/...")
    print("  2. In PLCnext Engineer: Security > OPC UA > Trusted Clients > Import")
    print("  (or set the server to accept all clients during testing)")
    print()

    return CERT_FILE, KEY_FILE


# ── full tree browser ─────────────────────────────────────────────────────────

TREE_CHARS = {"mid": "├─", "last": "└─", "pipe": "│ ", "space": "  "}

async def browse_tree(node, prefix="", depth=0, max_depth=8):
    try:
        children = await node.get_children()
    except Exception:
        return

    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        connector = TREE_CHARS["last"] if is_last else TREE_CHARS["mid"]
        child_prefix = prefix + (TREE_CHARS["space"] if is_last else TREE_CHARS["pipe"])

        try:
            name = (await child.read_browse_name()).Name
            node_class = await child.read_node_class()
            node_id = child.nodeid.to_string()

            if node_class == ua.NodeClass.Variable:
                try:
                    value = await child.read_value()
                except Exception:
                    value = "<unreadable>"
                print(f"{prefix}{connector} {name}  =  {value}  [{node_id}]")
            else:
                print(f"{prefix}{connector} [{node_class.name}] {name}  ({node_id})")
                if depth < max_depth:
                    await browse_tree(child, child_prefix, depth + 1, max_depth)

        except Exception as e:
            print(f"{prefix}{connector} <error: {e}>")


# ── modbus-only mode ──────────────────────────────────────────────────────────

def is_modbus_node(name: str) -> bool:
    low = name.lower()
    return any(kw in low for kw in MODBUS_KEYWORDS)


async def collect_registers(node) -> list:
    registers = []
    try:
        for child in await node.get_children():
            try:
                child_class = await child.read_node_class()
                child_name = (await child.read_browse_name()).Name
                child_id = child.nodeid.to_string()

                if child_class == ua.NodeClass.Variable:
                    try:
                        value = await child.read_value()
                    except Exception:
                        value = "<unreadable>"
                    registers.append({"name": child_name, "node_id": child_id, "value": value})
                elif child_class == ua.NodeClass.Object:
                    sub = await collect_registers(child)
                    for r in sub:
                        r["name"] = f"{child_name}/{r['name']}"
                    registers.extend(sub)
            except Exception:
                continue
    except Exception:
        pass
    return registers


async def find_modbus_devices(node, path="", depth=0, max_depth=10) -> list:
    devices = []
    if depth > max_depth:
        return devices
    try:
        children = await node.get_children()
    except Exception:
        return devices

    for child in children:
        try:
            child_class = await child.read_node_class()
            if child_class != ua.NodeClass.Object:
                continue
            child_name = (await child.read_browse_name()).Name
            child_path = f"{path}/{child_name}" if path else child_name
            child_id = child.nodeid.to_string()

            if is_modbus_node(child_name) or is_modbus_node(child_path):
                registers = await collect_registers(child)
                if registers:
                    devices.append({
                        "name": child_name,
                        "node_id": child_id,
                        "path": child_path,
                        "registers": registers,
                    })

            sub = await find_modbus_devices(child, child_path, depth + 1, max_depth)
            devices.extend(sub)
        except Exception:
            continue

    return devices


def print_modbus(devices: list):
    if not devices:
        print("\nNo Modbus devices found.")
        print("Tip: the PLC may have no variables exposed over OPC-UA yet,")
        print("     or device names don't match the keywords below.")
        print(f"     Keywords: {sorted(MODBUS_KEYWORDS)}")
        return

    for dev in devices:
        print(f"\n{'='*60}")
        print(f"  Device : {dev['name']}")
        print(f"  Path   : {dev['path']}")
        print(f"  Node ID: {dev['node_id']}")
        print(f"  {'─'*56}")
        if dev["registers"]:
            col_w = max(len(r["name"]) for r in dev["registers"])
            for reg in dev["registers"]:
                print(f"  {reg['name']:<{col_w}}  {reg['value']}  [{reg['node_id']}]")
        else:
            print("  (no registers)")

    print(f"\n{'='*60}")
    print(f"Total: {len(devices)} Modbus device(s) found.")


# ── connection + dispatch ─────────────────────────────────────────────────────

async def connect(url, username, password, no_security):
    client = Client(url=url)
    client.application_uri = APP_URI
    if username:
        client.set_user(username)
        client.set_password(password or "")

    if not no_security:
        cert_path, key_path = ensure_cert()
        await client.set_security(
            SecurityPolicyBasic256Sha256,
            certificate=str(cert_path),
            private_key=str(key_path),
            mode=ua.MessageSecurityMode.SignAndEncrypt,
        )
    return client


async def main(url, username, password, no_security, modbus_only, max_depth):
    print(f"Connecting to {url} ...")
    client = await connect(url, username, password, no_security)

    async with client:
        print("Connected.\n")
        objects = client.get_objects_node()

        if modbus_only:
            print("Scanning for Modbus devices ...\n")
            devices = await find_modbus_devices(objects)
            print_modbus(devices)
        else:
            print("Browsing full device tree ...\n")
            print(f"[Objects]  ({objects.nodeid.to_string()})")
            await browse_tree(objects, prefix="", depth=0, max_depth=max_depth)
            print("\nDone. Use --modbus to filter Modbus devices only.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Browse OPC-UA devices on a PLCNext (or any OPC-UA server)"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default="opc.tcp://10.240.240.31:4840",
        help="OPC-UA server URL (default: opc.tcp://10.240.240.31:4840)",
    )
    parser.add_argument("--user",        default="",   help="Username")
    parser.add_argument("--password",    default="",   help="Password")
    parser.add_argument("--no-security", action="store_true",
                        help="Skip certificate/security (try None policy)")
    parser.add_argument("--modbus",      action="store_true",
                        help="Show only Modbus devices and their registers")
    parser.add_argument("--depth",       type=int, default=8,
                        help="Max browse depth for full tree mode (default: 8)")
    args = parser.parse_args()

    asyncio.run(main(
        url=args.url,
        username=args.user,
        password=args.password,
        no_security=args.no_security,
        modbus_only=args.modbus,
        max_depth=args.depth,
    ))
