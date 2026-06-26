# oplus-camera-config-dump

> [Frida](https://frida.re/) based tool that hooks the decryption routine inside `libOplusSecurity.so` and dumps the decrypted APS camera configuration files to disk as soon as the native function returns.

**Tested on:** Custom ROMs running the OPlus camera port built against blob version `CPH2653_16.0.7.201(EX01)` — see the [dodge-camera-port](https://github.com/dodge-camera-port) project (experimental OPlus camera port for OnePlus 13, developed in collaboration with other cool guys).

**Should also work on:** OxygenOS `CPH2653_16.0.7.201(EX01)` — untested.

---

## What is this?

The stock OnePlus/OPPO camera app ships with an **Advanced Photography System (APS)** — a closed, encrypted pipeline that governs every aspect of how the camera sensor behaves: which computational photography algorithms fire, under what conditions, with what parameters, for every shoot mode from a basic JPEG to AI Night, Bokeh, or 4K video.

All of this logic lives in **binary-encrypted config files** on-device. The app decrypts them at runtime using a proprietary security library (`libOplusSecurity.so`), loads them into memory, and never exposes the plaintext anywhere on the filesystem.

**This tool hooks into that process.** It works by:

1. Waiting for `libOplusSecurity.so` to be loaded into the process memory.
2. Hooking the decryption function at a given offset.
3. On `onLeave`, reading the returned pointer + the length captured on `onEnter`, and shipping those raw bytes back to the Python host process over Frida's `send()`/data channel.
4. Saving each dump as `decrypted_config_<address>.json` in the current working directory.

---

## What files can you extract?

Each dump corresponds to a distinct layer of the APS camera configuration. Here is exactly what each type contains:

### APS Pipeline Config (`aps_capture_configs`)

The master enable/disable matrix for every capture and preview algorithm, per shooting mode.

Exposes:
- **APS version** and operating mode (full pipeline / capture-only / preview-only)
- Per-mode algorithm enable flags for all 55+ algos:
  `mfnr`, `hdr`, `raw_hdr`, `turbo_hdr`, `supernight`, `superphoto`, `bokeh`, `fusion`, `yuvsr`, `ai_sr`, `ai_deblur`, `ice_ainr`, `darksight`, `aimoon`, `facebase_retouch`, `face_beauty`, `face_restore`, `watermark`, `opxwatermark`, `pf`, `deflicker`, `cfr`, `hybridraw`, `super_raw`, `supersensor`, `scportrait`, `portrait_supernight`, `video_blur`, `tilt_shift`, `filter`, `filter_microscope`, `document_rectify`, `text_enhance`, `super_text`, `rotate_mirror`, `rectify`, `mask_refine`, `merge_hdr`, `couple_hdr`, `basic_tone`, `blurless`, `portraitrepair`, `raw2yuv`, `sw_png_encode`, `single_blur`, `single_portrait`, `face_info`, `face_rectify`, `pic_best`, `upscale` and more
- Shooting modes covered: `common`, `night`, `portrait`, `xpan`, `panorama`, `macro`, `microscope`, `microscopeVideo`, `professional`, `idPhoto`, `sticker`, `superText`, `longExposure`, `aiHighPixel`, `groupshot`, `commonVideo`, `fastVideo`, `slowVideo`, `4kVideo`, `superEISVideo`, `superEISProVideo`, `liveHDR`, `thirdParty`, `commonSatHal`, `commonVideoSatHal` and dummy/minimal modes

### Multi-Algo Decision Tree (`multiAlgo`)

The **brain of the capture pipeline** — a full conditional decision tree that selects which algorithm chain runs for each shot.

Exposes:
- **Prerequisites evaluation** — conditions evaluated before capture begins:
  `PREREQUISITES_NORMAL`, `PREREQUISITES_QUADCFA`, `PREREQUISITES_TURBO_HDR`, `PREREQUISITES_VIDEO`, `PREREQUISITES_FLASH`, `PREREQUISITES_BOKEH`, `PREREQUISITES_FRONT_BOKEH`, `PREREQUISITES_MFNR_CHDR`, `PREREQUISITES_HYBRIDRAW`, `PREREQUISITES_TIMELAPSE_PRO`
- **Capture mode matching** — full enum of `APS_CAPMODE_*` values:
  `REAR_NORMAL`, `REAR_NIGHT`, `REAR_BOKEH`, `FRONT_NORMAL`, `FRONT_NIGHT`, `FRONT_BOKEH`, `VIDEO`, `FAST_VIDEO`, `SLOW_VIDEO`, `PROFESSIONAL`, `XPAN`, `MACRO`, `MICROSCOPE`, `STICKER`, `LONGEXPOSURE`, `AI_HIGH_PIXEL`, `HIGH_PIC_SIZE`, `ID_PHOTO`, `SUPER_TEXT`, `TIMELAPSE_PRO`
- **Algorithm selection logic** — branching plans (`plan`, `planCondition`, `planResult`, `defaultResult`) that determine which `APS_ALGO_*` chain executes:
  `MFNR`, `TURBO_HDR`, `HYBRIDRAW`, `BOKEH`, `SINGLE_PORTRAIT`, `FACEBEAUTY`, `FACERESTORE`, `AIMOON`, `UPSCALE`, `WATERMARK`, `CFR`, `RAW2YUV`, `SUPER_RAW`, `STARMODE`, `TILT_SHIFT`, `TEXT_ENHANCE`, `DOCUMENT_RECTIFY` and more
- **ALGO_PARAM blocks** — per-algorithm parameter bundles (frame counts, memory caps, HDR variant flags, MFNR exposure settings)
- Conditional operators: `eq`, `not_eq`, `and`, `or`, nested logic trees

### Vendor Tags (`VendorTag` / `com.oplus.*`)

Raw Camera2 API vendor tag values — the **low-level tuning parameters** baked into the camera HAL.

Exposes:
- **SAT (Seamless Zoom) configuration**: zoom range per lens (`ultrawide 0.6×–1.0×`, `main 1.0×–3.0×`, `tele 3.0×–120.0×`), transition thresholds, switch ratios
- **Sensor geometry**: full-res and crop-mode resolutions for all physical sensors, aspect ratios, active array sizes
- **MFNR / HDR triggers**: lux index thresholds, exposure decision flags, low-battery fallback modes
- **Capture defer / burst config**: buffer counts, latency flags, pipeline depth
- **ISP tuning constants**: tone curve IDs, profile hue/saturation map IDs, color correction references
- **Feature capability flags**: which HAL features are enabled at compile-time for this device

### APS Schema / Keyword Dictionary (`jsonKeyword`, `conditionParams`)

The **schema definition file** for the APS config toolchain (version 2.4).

Exposes:
- Full list of reserved JSON keywords used by the APS config compiler
- `conditionParams`: every parameter name that can appear in a conditional expression, with its full valid `valueRange` — includes `specificProcessFlag`, `captureMode`, `flashMode`, `zoomRatio`, `motionCapture`, `luxIndex`, `sceneType` and all their valid enum values (e.g. `SPECIFIC_ALGO_MTK_HDRV4`, `SPECIFIC_ALGO_MTK_MFNR_HDRV5_F6`, `APS_ALGO_DCG_FUSION`, `APS_ALGO_AI_DE_HAZY`, `APS_ALGO_AI_RECTIFY`, ...)
- Acts as the **ground truth** for what values are legal in condition trees

---

## ⚠️ Disclaimer

This tool is published for **security research, reverse engineering and educational purposes only**. Only use it on devices you own or are explicitly authorized to test. You are solely responsible for complying with the applicable laws, terms of service, and software licenses in your jurisdiction. The author provides no warranty and assumes no liability for misuse.

---

## Requirements

- A **rooted physical OnePlus / OPPO device** with `com.oplus.camera` installed.
- `frida-server` on the device, with:
  - the **same CPU architecture** as the device (`arm64`)
  - a **version matching** the `frida` Python package installed on your computer (mismatched versions are the #1 cause of connection errors)
- USB debugging enabled, with the device connected and authorized (`adb devices` must list it as `device`, not `unauthorized`).
- Python 3.8+ on the host machine.
- The target app installed on the device (`com.oplus.camera` by default).

---

## Installation (host machine)

```bash
git clone https://github.com/Kill3rEz/oplus-camera-config-dump.git
cd oplus-camera-config-dump
pip install -r requirements.txt
```

---

## Setting up frida-server on the device

1. Check the Frida version just installed:
   ```bash
   pip show frida | grep Version
   ```
2. Download the **matching** `frida-server-<version>-android-arm64` build from the [official Frida releases page](https://github.com/frida/frida/releases) (e.g. `frida-server-<version>-android-arm64.xz`), then decompress it.
3. Push it to the device and make it executable:
   ```bash
   adb push frida-server-<version>-android-arm64 /data/local/tmp/frida-server
   adb shell "chmod 755 /data/local/tmp/frida-server"
   ```
4. Run it as root (it must stay running in the foreground or be backgrounded with `&`/`nohup`):
   ```bash
   adb shell "su -c '/data/local/tmp/frida-server &'"
   ```
5. Verify it's reachable from the host:
   ```bash
   frida-ps -U
   ```
   If this lists running processes on the device, you're good to go.

---

## Usage

> ⚠️ **Important: clear the app's data before every run.**
> If the app has already decrypted its configuration in a previous session, it will likely reuse a cached/already-decrypted copy instead of calling the decryption routine again — in that case the hook will simply never fire and you'll see no dumps at all. Force a fresh decryption by wiping the app's data right before launching the script:
> ```bash
> adb shell pm clear com.oplus.camera
> ```
> (or manually: Settings → Apps → Camera → Storage & cache → Clear storage).
> Do this every time you want to capture a new dump, not just the first time.

With `frida-server` running on the device, the phone connected via USB, and the app's data freshly cleared:

```bash
python3 camera_decrypt_dump.py
```

The script will:
1. Spawn `com.oplus.camera` (suspended) on the device.
2. Attach Frida and load the hooking script.
3. Resume the app.

Once the app is running, interact with the camera normally (open it, switch modes, etc.) until you see `[+] DUMP COMPLETE!` messages in the terminal — each one means a `decrypted_config_<address>.json` file was written to your current directory.

Press **Enter** in the terminal when you're done to exit cleanly.

### Optional arguments

```bash
python3 camera_decrypt_dump.py \
    --package com.oplus.camera \
    --lib libOplusSecurity.so \
    --offset 0x51c4
```

| Argument    | Default               | Description                                   |
|-------------|-----------------------|-----------------------------------------------|
| `--package` | `com.oplus.camera`    | Target app package name                       |
| `--lib`     | `libOplusSecurity.so` | Native library containing the target function |
| `--offset`  | `0x51c4`              | Offset of the decrypt function inside the lib |

---

## Output format

All dumps are saved as `.json` files. They may contain:
- **Null-byte padding** at the end (memory alignment artifact) — strip with `sed 's/\x00//g'` or the included parser
- **Embedded control characters** in multi-value numeric fields — handled automatically by the parser script

Run the included `parse_dump.py` to sanitize and pretty-print any dump:

```bash
python3 parse_dump.py decrypted_config_0xb400007cafea6b00.json
```

The output filenames embed the RAM address of the buffer at the time of the dump — these are virtual addresses from the target process's address space and vary per run.

---

## Notes & limitations

- **Stale/cached app data is the #1 reason "nothing happens."** Always run `adb shell pm clear <package>` right before launching the script, otherwise the app may skip decryption entirely and reuse data from the previous run.
- The offset `0x51c4` was located through static analysis on a specific firmware/app build. **It is very likely to differ across device models, ROM versions, and app updates.** If the hook never fires, re-locate the function (e.g. with Ghidra/IDA) for your specific binary and pass the new value via `--offset`.
- The function signature assumed here is `decrypt(ctx, length, ...) -> outputPtr`, i.e. the input length is read from the second argument (`args[1]`) and the decrypted buffer address is the return value. Other builds may use a different calling convention, requiring changes to the hook logic.
- Dumped files may contain proprietary/internal data from the target app — handle and share them responsibly.

---

## Troubleshooting

- **`frida.ServerNotRunningError`** — `frida-server` isn't running on the device, or `adb` isn't forwarding correctly. Re-check the setup steps above.
- **Version mismatch errors** — make sure the `frida-server` build on the device exactly matches the `frida` pip package version on the host.
- **Hook never triggers** — the library/offset may not match your device's build; verify with `frida-ps -U` that the app is running and use `frida-trace` or static analysis to confirm the library is loaded and the offset is correct.

---

## Related searches

`oplus camera APS config extract` · `OnePlus camera config decrypt` · `com.oplus.camera config dump` · `APS_ALGO config OnePlus` · `oplus vendor tag dump` · `OnePlus 13 camera algorithm config`

---

## License

This project is licensed under the [PolyForm Noncommercial License 1.0.0](LICENSE.txt).

In short: you're free to use, study, modify and share this code for any **noncommercial** purpose (personal projects, research, education, hobby use, etc.). Any **commercial use requires the copyright holder's explicit permission** — open an issue or contact the author first.
