# SPIKE: login, then pan LEFT ~1.5s and STOP. User is watching the camera.
import glob, json, socket, struct, sys, time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
HOST = sys.argv[1]; PORT = 16668
DIR = sys.argv[2] if len(sys.argv) > 2 else "3"   # 1=up 2=down 3=left 4=right
METHOD = sys.argv[3] if len(sys.argv) > 3 else "3428"
UP = "/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/uploads"
grp = json.load(open(glob.glob(f"{UP}/**/groupcfg.db", recursive=True)[0]))
dev = json.load(open(glob.glob(f"{UP}/**/devcfg.db", recursive=True)[0]))
owner = grp["OwnerToken"]; k0 = owner[:16].encode()
def pkcs7(b): n = 16 - (len(b) % 16) or 16; return b + bytes([n])*n
def unpad(b): return b[:-b[-1]] if b and 1 <= b[-1] <= 16 else b
def enc(b, key, iv): return Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor().update(pkcs7(b))
def dec(b, key, iv):
    try: return unpad(Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor().update(b))
    except Exception: return None
def readn(s, n):
    b=b""
    while len(b)<n:
        c=s.recv(n-len(b))
        if not c: break
        b+=c
    return b
def send(s, method, body, key, iv, plaintext=False):
    j = json.dumps({"METHOD":method,"SEQID":str(int(time.time())%100000),"BODY":body}).encode()
    payload = j if plaintext else enc(j, key, iv)
    et = 0x30 if plaintext else 0x31
    s.sendall(b"\x23\x24"+bytes([int(method[:2],16),int(method[2:],16)])+struct.pack(">H",len(payload))+bytes([et,0])+payload)
def recv(s, key, iv):
    h = readn(s,8)
    if len(h)<8: return None
    m=f"{h[2]:02X}{h[3]:02X}"; et=h[6]; bl=struct.unpack(">H",h[4:6])[0]; b=readn(s,bl)
    if et==0x31:
        for kk,ii in [(key,iv),(k0,k0)]:
            d=dec(b,kk,ii)
            if d and (d[:1] in (b"{",b"[")): b=d; break
    try: return (m, json.loads(b.decode(errors="replace")))
    except Exception: return (m, b[:60].hex())

s = socket.create_connection((HOST,PORT),timeout=6); s.settimeout(4)
send(s, "3114", {"UserToken":owner,"OsType":"1","SDKVersion":dev.get("SdkVersion","50663936"),"EncType":"49","EncKey":k0.decode(),"EncLoad":k0.decode()}, k0, k0, plaintext=True)
m, r = recv(s, k0, k0)
print("login", m, r.get("CODE") if isinstance(r,dict) else r)
sk = r["BODY"]["EncKey"].encode(); sv = r["BODY"]["EncLoad"].encode()
# pick a 16-byte key/iv for session (try device key[:16] + iv, fallback owner[:16])
key = sk[:16]; iv = sv[:16]
ptz = {"PTZType":"0","PTZControl":DIR,"Step":"8","Speed":"8"}
print(f"-> PTZ start method={METHOD} dir={DIR} (watch camera)")
send(s, METHOD, ptz, key, iv)
try: print("   reply", recv(s, key, iv))
except socket.timeout: print("   (no reply)")
time.sleep(1.5)
stop = {"PTZType":"0","PTZControl":"0","Step":"8","Speed":"8"}
send(s, METHOD, stop, key, iv)
try: print("   stop reply", recv(s, key, iv))
except socket.timeout: print("   (no stop reply)")
s.close()
