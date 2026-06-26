#!/usr/bin/env python3
"""
Oplus Camera Config Decrypt Dumper
===================================

A Frida-based dynamic instrumentation tool that hooks the decryption
routine inside libOplusSecurity.so (found in some Oplus / OnePlus / Oppo
camera app builds) and dumps the decrypted output buffer to disk as soon
as the function returns.

Intended for security research, reverse engineering and educational
purposes, on devices you own or are otherwise authorized to test.

Requirements:
    - A rooted Android device (or emulator) with frida-server running
    - frida-server architecture/version matching the device and the
      installed `frida` Python package (see README.md)
    - USB debugging enabled, device connected and authorized (adb devices)
    - Python packages: frida, frida-tools (see requirements.txt)

Usage:
    python3 camera_decrypt_dump.py
    python3 camera_decrypt_dump.py --package com.oplus.camera --lib libOplusSecurity.so --offset 0x51c4
"""

import argparse
import sys

import frida


DEFAULT_PACKAGE = "com.oplus.camera"
DEFAULT_LIB_NAME = "libOplusSecurity.so"
DEFAULT_OFFSET = "0x51c4"


def build_js_payload(lib_name: str, offset: str) -> str:
    """Builds the Frida JS payload that hooks the decrypt function."""
    return f"""
var libName = "{lib_name}";
var isHooked = false;

function hookDecrypt() {{
    if (isHooked) return;

    var targetModule = Process.findModuleByName(libName);
    if (!targetModule) return;

    isHooked = true;
    var baseAddr = targetModule.base;
    var targetAddr = baseAddr.add({offset});

    console.log("[+] " + libName + " loaded in memory at " + baseAddr);
    console.log("[*] Decryption function hooked ({offset}) -> " + targetAddr);

    Interceptor.attach(targetAddr, {{
        onEnter: function(args) {{
            // Store the length as a proper integer.
            this.inputLen = args[1].toInt32();
            console.log("\\n[*] Decryption call intercepted! -> Size: " + this.inputLen + " bytes");
        }},
        onLeave: function(retval) {{
            var outPtr = ptr(retval);
            var lengthToRead = parseInt(this.inputLen, 10);

            if (!outPtr.isNull() && lengthToRead > 0) {{
                console.log("[+] Decrypted buffer in memory at: " + outPtr);

                try {{
                    // Ask the pointer itself to read the memory region
                    // (avoids the TypeError some Memory.readByteArray calls hit).
                    var decryptedBuffer = outPtr.readByteArray(lengthToRead);

                    send({{
                        "action": "dump",
                        "address": outPtr.toString()
                    }}, decryptedBuffer);

                }} catch (e) {{
                    console.log("[-] Error while dumping memory: " + (e.stack || e));
                }}
            }}
        }}
    }});
}}

// Poll every 500ms until the library shows up in memory.
var checkTimer = setInterval(function() {{
    if (Process.findModuleByName(libName)) {{
        clearInterval(checkTimer);
        hookDecrypt();
    }}
}}, 500);

if (Process.findModuleByName(libName)) {{
    clearInterval(checkTimer);
    hookDecrypt();
}} else {{
    console.log("[*] Waiting silently for the app to load " + libName + "...");
}}
"""


def on_message(message, data):
    if message["type"] == "send":
        payload = message["payload"]
        if payload.get("action") == "dump" and data is not None:
            filename = f"decrypted_config_{payload['address']}.json"
            with open(filename, "wb") as f:
                f.write(data)
            print(f"[+] DUMP COMPLETE! Saved as: {filename}")

            try:
                preview = data[:70].decode("utf-8", errors="ignore")
                print(f"    Text preview: {preview}...\n")
            except Exception:
                pass

    elif message["type"] == "error":
        print(f"[-] Frida error: {message['stack']}")


def main():
    parser = argparse.ArgumentParser(
        description="Hook a decryption routine in a native library and dump the output buffer."
    )
    parser.add_argument("--package", default=DEFAULT_PACKAGE, help="Target app package name")
    parser.add_argument("--lib", default=DEFAULT_LIB_NAME, help="Target native library name")
    parser.add_argument(
        "--offset",
        default=DEFAULT_OFFSET,
        help="Offset (hex, e.g. 0x51c4) of the decrypt function inside the library",
    )
    args = parser.parse_args()

    js_code = build_js_payload(args.lib, args.offset)

    print("[*] Waiting for the device...")
    try:
        device = frida.get_usb_device()
        print(f"[*] Attaching to process '{args.package}'...")

        pid = device.spawn([args.package])
        session = device.attach(pid)

        script = session.create_script(js_code)
        script.on("message", on_message)
        script.load()

        device.resume(pid)

        print("[+] App launched! Now interact with the camera on the phone.")
        print("[*] Frida is listening silently. Press ENTER here to exit when done.\n")
        sys.stdin.read()

    except frida.ExecutableNotFoundError:
        print(f"[-] Error: app '{args.package}' was not found on the device.")
    except frida.ServerNotRunningError:
        print("[-] Error: frida-server is not running on the device. See README.md for setup steps.")
    except Exception as e:
        print(f"[-] Unexpected error: {e}")


if __name__ == "__main__":
    main()
