# SPIKE (login + read status only; sends NO movement command).
# Tests whether a CareCam/ZJ-TRAS camera accepts a LOCAL login using the
# OwnerToken from its own exported groupcfg.db, with no cloud.
import glob, json, socket, struct, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HOST, PORT = sys.argv[1], 16668
UP = "/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/uploads"
grp = json.load(open(glob.glob(f"{UP}/**/groupcfg.db", recursive=True)[0]))
dev = json.load(open(glob.glob(f"{UP}/**/devcfg.db", recursive=True)[0]))
owner = grp["OwnerToken"]

def mask(s):
    return s[:4] + "…" + s[-2:] if s and len(s) > 6 else "…"

def pkcs7(b):
    n = 16 - (len(b) % 16) or 16
    return b + bytes([n]) * n

def unpad(b):
    return b[:-b[-1]] if b and 1 <= b[-1] <= 16 else b

def frame(method, body, key, iv):
    j = json.dumps({"METHOD": method, "SEQID": "1", "BODY": body}).encode()
    ct = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor().update(pkcs7(j))
    hi, lo = int(method[:2], 16), int(method[2:], 16)
    hdr = b"\x23\x24" + bytes([hi, lo]) + struct.pack(">H", len(ct)) + bytes([0x31, 0x00])
    return hdr + ct

def recv_msg(sock, key, iv):
    hdr = b""
    while len(hdr) < 8:
        c = sock.recv(8 - len(hdr))
        if not c: return None, None, "closed"
        hdr += c
    method = f"{hdr[2]:02X}{hdr[3]:02X}"
    blen = struct.unpack(">H", hdr[4:6])[0]
    body = b""
    while len(body) < blen:
        c = sock.recv(blen - len(body))
        if not c: break
        body += c
    try:
        pt = unpad(Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor().update(body))
        return method, json.loads(pt.decode(errors="replace")), None
    except Exception as e:
        return method, None, f"decrypt/parse failed: {e} raw={body[:32].hex()}"

CANDIDATES = [
    ("OwnerToken[:16]", owner[:16].encode(), owner[:16].encode()),
    ("EncKey/EncLv", grp["EncKey"].encode(), grp["EncLv"].encode()),
]
print(f"host {HOST}:{PORT}  owner={mask(owner)}  grpid={grp['grpid']}")
for name, key, iv in CANDIDATES:
    if len(key) != 16 or len(iv) != 16:
        print(f"[{name}] skip: key/iv not 16 bytes"); continue
    try:
        s = socket.create_connection((HOST, PORT), timeout=6)
    except Exception as e:
        print("connect failed:", e); break
    body = {"UserToken": owner, "OsType": "1", "SDKVersion": dev.get("SdkVersion", "50663936"),
            "EncType": "49", "EncKey": key.decode(), "EncLoad": iv.decode()}
    s.sendall(frame("3114", body, key, iv))
    method, msg, err = recv_msg(s, key, iv)
    s.close()
    if err:
        print(f"[{name}] reply method={method} -> {err}")
    else:
        code = msg.get("CODE")
        print(f"[{name}] reply method={method} CODE={code} -> {'SUCCESS' if code=='0' else 'rejected'}  body={json.dumps(msg.get('BODY',{}))[:120]}")
        if code == "0":
            print(">>> LOCAL LOGIN WORKS, no cloud. <<<")
            break
