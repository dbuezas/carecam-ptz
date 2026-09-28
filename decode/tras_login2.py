# SPIKE: plaintext 3114 login, read + decrypt 3115 reply. No PTZ, no movement.
import glob, json, socket, struct, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
HOST = sys.argv[1]; PORT = 16668
UP = "/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/uploads"
grp = json.load(open(glob.glob(f"{UP}/**/groupcfg.db", recursive=True)[0]))
dev = json.load(open(glob.glob(f"{UP}/**/devcfg.db", recursive=True)[0]))
owner = grp["OwnerToken"]; key = owner[:16].encode()
def unpad(b): return b[:-b[-1]] if b and 1 <= b[-1] <= 16 else b
def readn(s, n):
    b = b""
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c: break
        b += c
    return b
def recv_msg(s):
    hdr = readn(s, 8)
    if len(hdr) < 8: return None
    method = f"{hdr[2]:02X}{hdr[3]:02X}"; enct = hdr[6]; blen = struct.unpack(">H", hdr[4:6])[0]
    body = readn(s, blen)
    if enct == 0x31:
        try: body = unpad(Cipher(algorithms.AES(key), modes.CBC(key)).decryptor().update(body))
        except Exception as e: return (method, enct, f"decrypt fail {e}", body[:16].hex())
    try: return (method, enct, json.loads(body.decode(errors="replace")))
    except Exception: return (method, enct, "non-json", body[:64].hex())

body = json.dumps({"METHOD":"3114","SEQID":"1","BODY":{"UserToken":owner,"OsType":"1","SDKVersion":dev.get("SdkVersion","50663936"),"EncType":"49","EncKey":key.decode(),"EncLoad":key.decode()}}).encode()
pkt = b"\x23\x24\x31\x14" + struct.pack(">H", len(body)) + b"\x30\x00" + body
s = socket.create_connection((HOST, PORT), timeout=6); s.settimeout(4)
s.sendall(pkt)
r = recv_msg(s)
print("reply:", json.dumps(r[2], ensure_ascii=False)[:400] if isinstance(r[2], dict) else r)
if isinstance(r[2], dict):
    code = r[2].get("CODE")
    print("METHOD", r[0], "CODE", code, "->", "SUCCESS: local login works, no cloud" if code == "0" else "rejected")
s.close()
