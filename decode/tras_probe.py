# SPIKE probe: try framing variants for the 3114 local login. Read-only (no PTZ).
import glob, json, socket, struct, sys, time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
HOST = sys.argv[1]; PORT = 16668
UP = "/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/uploads"
grp = json.load(open(glob.glob(f"{UP}/**/groupcfg.db", recursive=True)[0]))
owner = grp["OwnerToken"]; key = owner[:16].encode()
def pkcs7(b): n = 16 - (len(b) % 16) or 16; return b + bytes([n])*n
def enc(b, k): return Cipher(algorithms.AES(k), modes.CBC(k)).encryptor().update(pkcs7(b))
def peek(label, payload):
    try:
        s = socket.create_connection((HOST, PORT), timeout=5)
    except Exception as e:
        print(label, "connect fail", e); return
    s.settimeout(3)
    if payload: s.sendall(payload)
    time.sleep(0.3)
    try:
        r = s.recv(256)
        print(label, "->", "closed(empty)" if r == b"" else f"{len(r)}B {r[:24].hex()}")
    except socket.timeout:
        print(label, "-> (silence, held open)")
    except Exception as e:
        print(label, "->", type(e).__name__, e)
    s.close()

body = json.dumps({"METHOD":"3114","SEQID":"1","BODY":{"UserToken":owner,"OsType":"1","SDKVersion":"50663936","EncType":"49","EncKey":key.decode(),"EncLoad":key.decode()}}).encode()
peek("0 listen-only", b"")
ct = enc(body, key)
peek("1 hdr 2324+3114+htons(ct)+3100 enc", b"\x23\x24\x31\x14"+struct.pack(">H",len(ct))+b"\x31\x00"+ct)
peek("2 hdr enctype=30 plaintext", b"\x23\x24\x31\x14"+struct.pack(">H",len(body))+b"\x30\x00"+body)
peek("3 hdr len=htons(plain) but enc body", b"\x23\x24\x31\x14"+struct.pack(">H",len(body))+b"\x31\x00"+ct)
peek("4 magic 2423 order", b"\x24\x23\x31\x14"+struct.pack(">H",len(ct))+b"\x31\x00"+ct)
peek("5 little-endian len", b"\x23\x24\x31\x14"+struct.pack("<H",len(ct))+b"\x31\x00"+ct)
peek("6 raw plaintext json no header", body)
