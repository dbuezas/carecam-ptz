# CareCam Pro (Huiyun / YGTek / ZJ-TRAS) local control — spike result

Camera: YGTek AJL33PQ0866, Fullhan FH8626V100, fw YGT.AJL33PQ0866-v230511.1400.
Two lenses (wide 3.6mm = LenID 0, tele = LenID 1), pan/tilt (PTZMode 3). Lens
switch is a control command, not a separate RTSP stream.

## Confirmed working (tested against the real camera, login+read only)
- LOCAL login on TCP 16668 succeeds with NO cloud. Reply METHOD 3115 CODE 0.
- Auth = OwnerToken from the device's own groupcfg.db, sent verbatim as UserToken.
- Framing: 8-byte header = 23 24 | METHOD(hi,lo) | big-endian body length | EncType byte | 00.
- The 3114 login request is sent PLAINTEXT (header EncType byte = 0x30).
- The device reply (and further traffic) is AES-128-CBC, key = IV = first 16 ASCII
  bytes of the OwnerToken. Body is PKCS#7-padded.
- 3115 reply returns DID, CTEI, GID and a fresh session EncKey/EncLoad to use next.

## RTSP (video) — works today, independent of the above
- rtsp://admin:admin123456@192.168.178.107:8554/profile0 (main), /profile1, /profile2
  = same wide lens at different qualities. Factory default creds admin/admin123456.

## Not yet tested (needs user OK: first real movement)
- PTZ command wire form. Candidate: METHOD 3428, BODY
  {"PTZType":"0","PTZControl":"<dir>","Step":"<n>","Speed":"<n>"}, AES with session key.
  Also a modern IoT path (IoT type 1006). Direction enum + stop form unconfirmed.
- Lens switch (CurrentLenID 0/1) via ctrlDeviceFunc.

## Files
- tras_login2.py = working local login (plaintext 3114, decrypt 3115).
- tras_probe.py = framing-variant probe (found plaintext 3114).
