# CareCam PTZ (local, no cloud)

Home Assistant integration for **CareCam / Huiyun / YGTek** Wi‑Fi cameras — the
ones set up with the *CareCam Pro* / *Huiyun* apps (the "China Telecom SmartHome"
/ ZJ‑TRAS P2P SDK). It talks to the camera **directly on your LAN, without the
cloud**, using the same protocol the app uses.

> Reverse‑engineered from the app. Confirmed on a YGTek **AJL33PQ0866** (Fullhan
> FH8626V100, dual‑lens). Other models in this family are likely but untested —
> reports welcome.

## Features

- **Video** – two RTSP streams (main / sub), played by Home Assistant's native
  stream (fast to start).
- **PTZ** – up / down / left / right, with a configurable **step** and **speed**.
- **Lens** – switch wide ↔ tele on dual‑lens models.
- **Night vision** – auto / auto (no lamp) / full colour / natural / infrared.
- **Image** – orientation (flip / mirror), wide dynamic range.
- **Privacy** – camera on/off, microphone on/off.
- **Speaker** – volume, play stored sounds, and **TTS / audio playback**
  (`media_player`, works with `tts.speak`).
- **Name on video** (OSD text).
- **Sensors** – Wi‑Fi signal, SD card size / free / status.
- **Maintenance** – reboot and factory‑reset buttons (disabled by default).

Everything except video runs over the camera's local command channel; the
current settings are read back from the camera, so entity states are real.

## Not supported

- **Motion / person events** – this SDK delivers those via the vendor cloud, not
  locally, so a cloud‑free integration can't receive them.
- Presets, SD playback, anti‑flicker – not implemented.

## Install

1. Copy `custom_components/carecam` into your Home Assistant `config/custom_components/`
   (or add this repo to HACS as a custom repository), then restart Home Assistant.
2. **Settings → Devices & services → Add integration → CareCam.**
3. Enter the camera **host/IP** and its **owner token** (see below). RTSP
   username / password / port default to `admin` / `admin123456` / `8554`.

### Getting the owner token

Local login uses the camera's *owner token* — the credential the app receives
when the account is bound to the camera. You get it once from the app's own
**log / diagnostics export**:

1. In the **CareCam Pro** (Huiyun) app, open the device and trigger the log
   export / feedback‑with‑logs feature (it collects the device's config and
   logs into an archive you can share/save — e.g. a `log.tar.gz`).
2. Open the archive and find **`groupcfg.db`** (under `SDKFlashLog/ZJCONF/config/`).
   Despite the `.db` name it is plain **JSON**.
3. Copy the value of **`"OwnerToken"`** (a ~32‑character string). Paste it into
   the integration's *Owner token* field.

The same archive also confirms the camera's local IP and DID if you need them.

> Why manual: the token is normally issued by the vendor cloud at pairing time.
> There is no cloud‑free way to mint it, so it's extracted once. A future version
> could fetch it automatically via a one‑time cloud login.

## Notes

- Give the camera a fixed IP in your router so the address doesn't change.
- The RTSP server has a well‑known default password and the camera exposes
  telnet — keep it off the internet / on a guest network.

## License

MIT
