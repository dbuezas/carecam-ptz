# CareCam Pro / Huiyun / YGTek (ZJ-TRAS "China Telecom SmartHome") — local protocol

Tested live against YGTek AJL33PQ0866 (Fullhan FH8626V100, fw YGT...-v230511.1400),
dual-lens (wide 3.6mm=lens0, tele=lens1), pan/tilt.

## Transport (CONFIRMED live)
- Command channel: TCP 16668. 8-byte header + body.
  header = 23 24 | METHOD_hi METHOD_lo | bodylen(big-endian, 2B) | EncType(0x30 plain / 0x31 AES) | 00
- Login req METHOD 3114 is sent PLAINTEXT (EncType 0x30). Everything else AES-128-CBC.
- AES key = IV = first 16 ASCII bytes of the OwnerToken (from the account/device binding).
  The 3115 reply returns a session EncKey/EncLoad; use first 16 bytes of each as key/iv after login.
- Auth = UserToken = the OwnerToken verbatim. NO CLOUD needed: the device validates it locally.
- Reply METHOD = request+1 (3114->3115, 3428->3429), field CODE "0" = success.
- Video is a SEPARATE media channel; simplest path is the firmware RTSP server:
  rtsp://admin:admin123456@<ip>:8554/profile0 (main) /profile1 /profile2 (same wide lens, 3 qualities).

## Confirmed commands (live)
- 3114/3115 login.
- 3428/3429 PTZ. BODY {"PTZType":"0","PTZControl":"1|2|3|4","Step":"8","Speed":"8"} (values are strings).
  Directions: 1=UP 2=DOWN 3=LEFT 4=RIGHT (only these; no diagonals, no zoom via PTZ).
  Stop: PTZControl "0" observed to stop movement live (CODE 0). The SDK also has a dedicated
  stopCtrlPtz command (Cmd_StopPtzOption) — prefer confirming its numeric code before shipping.

## Command SURFACE (names/params/enums HIGH confidence from decompiled Java;
## numeric METHOD codes NOT yet extracted except the two above — need Ghidra on libbusiness.so)
- PTZ presets: add/goto/rename/delete (Cmd_*PtzPresetPoint*), cruise add/del/start, watch point.
- Lens: switchCamLens(did,lensId) = Cmd_SwitchPeerCamLen (live active lens); setDefaultLensId persisted.
  lensId indexes lensList; wide=lower focal, tele=higher. curLensId read from CameraBean.
- Camera cfg setters: IR mode (IRModeEnum AUTO0/AUTO_NOLAMP1/FULLCOLOR2/NATURAL3/IR4),
  inversion/flip, mirror, OSD text+pos (OSDPositionEnum 0..4), OSD on/off, WDR, cam on/off,
  video params, audio params. HDR/antiflicker/privacy via setInIoTBuss JSON. Generic: ctrlDeviceFunc.
- Device: get/set zone&time, reboot, factory reset, name, volume, version/upgrade, TF info/format,
  network info + wifi list/set, play sound, alarm/timer policy, human count.
- Events: register listener (callback, no request); device pushes EventInfBean async;
  EventID 100000=motion, 100001=human. Enable/disable via setAlarmPolicy.
- Media (separate channel): openLiveStream/closeStream, getLiveStreamImage (JPEG snapshot),
  record calendar/list, openRecordStream/seek, downloads; talkback push.

## To finish the numeric-code table (safe, offline)
Load libbusiness.so (armeabi-v7a) in Ghidra; for each Cmd_*, read the 16-bit method constant it
passes into the request/header builder, and the iTrd_Json_AddItemToObject key strings for body
fields. DO NOT brute-force method codes against a live camera (space includes reboot/factory-reset).

## Onboarding for real users (not yet built)
The only per-user secret is the OwnerToken. To avoid manual config dumps, log into the ZJ/CareCam
cloud once (loginByEmail/Mobile -> token), fetch the device OwnerToken, then run fully local.

## CONFIRMED numeric METHOD codes (from libbusiness.so, family A = JSON, high byte 0x34)
| command | METHOD | body | status |
|---|---|---|---|
| login | 3114/3115 | UserToken,OsType,SDKVersion,EncType,EncKey,EncLoad | LIVE ✓ |
| PTZ move | 3428/3429 | PTZType"0", PTZControl 1=up 2=down 3=left 4=right, Step, Speed | LIVE ✓ |
| PTZ stop | 3428 | PTZType"0", PTZControl"0" (or PTZType"3") | LIVE ✓ |
| goto preset | 3428 | PTZType, PresetID | high conf |
| **lens switch** | **3450/3451** | **LenID (0=wide, 1=tele)** | LIVE ✓ |
| set default lens | 34b4 | AutoFlag, DefaultLenId | high conf |
| DANGER reboot | 3412 | ChannelID | AVOID |
| DANGER factory reset | 3416 | (empty) | AVOID |

Legacy CmdOld_* use a different binary channel (class 5, 1-byte cmd id) — not needed; the 34xx JSON family works live.
Full command surface (IR mode, OSD, WDR, inversion, presets, events, media) mapped in earlier notes; remaining 34xx codes readable with the same movs-low-byte + movs r3,0x34 pattern.

## Audio / speaker (decoded on paper; needs a live noise-making test to finish)
Two transports share TCP 16668, same 8-byte header (Tras_EncMsgHead). Demux on byte[2]:
- command/JSON: byte[2] = 0x30-0x37 (e.g. METHOD hi 0x34). Body AES per EncType byte.
- STREAM DATA: byte[2] = 0x50 ('P'), byte[3] = msgtype (0x13 live A/V, 0x12 sound-file). PLAINTEXT.

Stream data header: 23 24 | 50 | msgtype | BE len | 00 00 | BE channelID | BE blockCtr | raw bytes.
Audio = G.711 mu-law, 8000 Hz, mono, 160-byte (20ms) frames.

Easy TTS route (upload clip then play):
1. Open: JSON command BuildSoundFileReq, BODY {ChannelID, SoundName, FileSize}. METHOD unknown; probe
   showed 34A6/34A8/34AA/34AC are accepted (one is the sound-file open) - needs a live upload to confirm which.
2. Upload: raw file bytes in 0x50/0x12 packets (12-byte header above), blockCtr increments.
3. Play: METHOD 34A4 {CtrlType:"1", Name}. (confirmed)
Known sound cmds: list 34A0 {SoundType}, delete 34A2 {Name}, play 34A4, volume 34B0, audio param 342A.
Cloud TTS (needs internet): 5206 {Text, VoiceType}.

Remaining unknowns (need a live capture or noise-making trial): exact sound-file-open METHOD,
the clip container the device expects, blockCtr rule, whether open must be ACKed before data,
and pure-audio inner header size (14 vs 22 bytes) for real-time push.
Play-sound of an EXISTING clip (button "Play sound b1") is fully working via 34A4.
