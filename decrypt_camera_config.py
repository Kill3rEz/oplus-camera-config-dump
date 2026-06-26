#!/usr/bin/env python3
"""
Oplus Camera Config — offline manual decryptor
==============================================

Decrypts the encrypted APS / vendor-tag camera config files shipped in the
firmware (``/odm/etc/camera/config/``) **without** running the app or Frida.

This reimplements what ``decode()`` inside ``libOplusSecurity.so`` does, which
was recovered by reverse engineering that library:

  * Cipher:  AES-128 in **ECB** mode  (10 rounds; standard FIPS-197 S-boxes)
  * Key:     hard-coded 16-byte key embedded in the library (see KEY below)
  * Padding: PKCS#7  (the library zero-fills it after decrypting; we strip it)

On-disk container format of an encrypted config file:

    +--------------+-------------------------------+--------------+
    | 4-byte head  |  AES-128-ECB ciphertext       | 4-byte foot  |
    | 01 01 xx xx  |  (len = filesize - 8)         | yy yy yy ff  |
    +--------------+-------------------------------+--------------+

The first byte (0x01) matches ``getVersion()`` returning 1. Files that do not
start with the 01 01 magic are already plaintext (JSON / protobuf) and are
skipped.

Usage:
    python3 decrypt_camera_config.py <file-or-dir> [<file-or-dir> ...] [-o OUTDIR]
    python3 decrypt_camera_config.py re/fw_config -o re/decrypted

Intended for security research / reverse engineering on devices you own.
"""
import argparse
import os
import sys

from Crypto.Cipher import AES  # pip install pycryptodome

# 16-byte AES-128 key embedded in libOplusSecurity.so.
# Recovered from the runtime key schedule (round key 0) and verified to be the
# exact standard AES-128 expansion stored in the library's .bss.
KEY = bytes.fromhex("6f2170406c247525535e4326412a4d28")

MAGIC = b"\x01\x01"           # first 2 bytes of every encrypted file
HEADER_LEN = 4                # bytes before the ciphertext
FOOTER_LEN = 4                # bytes after the ciphertext


def is_encrypted(blob: bytes) -> bool:
    return blob[:2] == MAGIC


def strip_pkcs7(data: bytes) -> bytes:
    """Remove PKCS#7 padding; fall back to stripping trailing NULs."""
    if not data:
        return data
    n = data[-1]
    if 1 <= n <= 16 and data[-n:] == bytes([n]) * n:
        return data[:-n]
    return data.rstrip(b"\x00")


def decrypt_blob(blob: bytes) -> bytes:
    """Decrypt one in-memory encrypted config file -> plaintext bytes."""
    if not is_encrypted(blob):
        raise ValueError("not an encrypted oplus camera config (missing 01 01 magic)")
    ct = blob[HEADER_LEN:len(blob) - FOOTER_LEN]
    if len(ct) % 16 != 0:
        raise ValueError(f"ciphertext length {len(ct)} is not a multiple of 16")
    pt = AES.new(KEY, AES.MODE_ECB).decrypt(ct)
    return strip_pkcs7(pt)


def iter_inputs(paths):
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                fp = os.path.join(p, name)
                if os.path.isfile(fp):
                    yield fp
        else:
            yield p


def main():
    ap = argparse.ArgumentParser(description="Offline decryptor for Oplus encrypted camera config files.")
    ap.add_argument("paths", nargs="+", help="encrypted file(s) or directory containing them")
    ap.add_argument("-o", "--outdir", default=".", help="output directory (default: cwd)")
    ap.add_argument("--key", help="override AES-128 key (32 hex chars)")
    args = ap.parse_args()

    key = bytes.fromhex(args.key) if args.key else KEY
    if len(key) != 16:
        sys.exit("key must be 16 bytes (32 hex chars)")
    globals()["KEY"] = key
    os.makedirs(args.outdir, exist_ok=True)

    n_ok = n_skip = n_err = 0
    for fp in iter_inputs(args.paths):
        blob = open(fp, "rb").read()
        base = os.path.basename(fp)
        if not is_encrypted(blob):
            print(f"[skip] {base:46} (plaintext, not encrypted)")
            n_skip += 1
            continue
        try:
            pt = decrypt_blob(blob)
        except Exception as e:
            print(f"[ERR ] {base:46} {e}")
            n_err += 1
            continue
        out_name = base if base.endswith(".json") else base + ".json"
        out_path = os.path.join(args.outdir, out_name)
        with open(out_path, "wb") as f:
            f.write(pt)
        preview = pt[:48].decode("utf-8", "replace").replace("\n", " ")
        print(f"[ OK ] {base:46} {len(blob):>7}B enc -> {len(pt):>7}B  {preview!r}")
        n_ok += 1

    print(f"\ndecrypted={n_ok} skipped={n_skip} errors={n_err} -> {args.outdir}")


if __name__ == "__main__":
    main()
