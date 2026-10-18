#!/usr/bin/env python3
"""輪播圖上傳後台：貼圖片網址或選檔案上傳 -> 存進 images/ -> 自動推上 GitHub Pages"""
import os, re, hmac, hashlib, json, time, subprocess, ipaddress, socket, urllib.request, urllib.parse, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import cookies
from email.parser import BytesParser
from email.policy import HTTP

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "images")
PASS = open(os.path.expanduser("~/.banner-admin-pass")).read().strip()
TOKEN = hmac.new(PASS.encode(), b"banner-admin", hashlib.sha256).hexdigest()
MAX = 10 * 1024 * 1024
MAGIC = [(b"\xff\xd8\xff", ".jpg"), (b"\x89PNG\r\n\x1a\n", ".png"), (b"GIF8", ".gif")]

def ext_of(b):
    for m, e in MAGIC:
        if b.startswith(m): return e
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return ".webp"
    return None

def safe_url(u):
    p = urllib.parse.urlparse(u)
    if p.scheme not in ("http", "https") or not p.hostname: raise ValueError("只接受 http/https 網址")
    for ai in socket.getaddrinfo(p.hostname, None):
        ip = ipaddress.ip_address(ai[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("不允許內網位址")

class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def fetch(u):
    safe_url(u)
    op = urllib.request.build_opener(NoRedir)
    r = op.open(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)
    data = r.read(MAX + 1)
    if len(data) > MAX: raise ValueError("檔案超過 10MB")
    return data

def save(data, hint):
    e = ext_of(data)
    if not e: raise ValueError("不是支援的圖片格式(jpg/png/gif/webp)")
    base = re.sub(r"[^\w\-]", "_", os.path.splitext(os.path.basename(hint))[0])[:40] or "img"
    name = f"{time.strftime('%m%d%H%M%S')}_{base}{e}"
    open(os.path.join(IMG, name), "wb").write(data)
    return name

def publish():
    r = subprocess.run([os.path.join(ROOT, "update.sh")], capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip()

def page(msg="", cls=""):
    files = sorted(f for f in os.listdir(IMG) if ext_of(open(os.path.join(IMG, f), "rb").read(12)))
    items = "".join(
        f'<div class=it><img src="/img/{urllib.parse.quote(f)}"><span>{html.escape(f)}</span>'
        f'<form method=post action=/delete><input type=hidden name=f value="{html.escape(f)}"><button>刪除</button></form></div>'
        for f in files)
    m = f'<p class="msg {cls}">{html.escape(msg)}</p>' if msg else ""
    return f"""<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>輪播圖後台</title><style>
body{{font:15px system-ui;max-width:720px;margin:0 auto;padding:16px;background:#f5f5f5}}
section{{background:#fff;padding:14px;border-radius:8px;margin-bottom:14px}}
textarea{{width:100%;box-sizing:border-box;height:90px}}button{{padding:8px 16px;margin-top:8px}}
.it{{display:flex;align-items:center;gap:10px;margin:8px 0}}.it img{{width:120px;height:60px;object-fit:cover;border-radius:4px}}
.it span{{flex:1;word-break:break-all;font-size:13px}}.it button{{margin:0}}.msg{{padding:10px;border-radius:6px;background:#e8f0fe}}.err{{background:#fde8e8}}
</style><h2>輪播圖後台</h2>{m}
<section><b>貼圖片網址</b>(一行一個)<form method=post action=/add-url><textarea name=urls placeholder="https://.../banner.jpg"></textarea><button>加入</button></form></section>
<section><b>上傳檔案</b><form method=post action=/add-file enctype=multipart/form-data><input type=file name=files accept="image/*" multiple><br><button>上傳</button></form></section>
<section><b>目前圖片({len(files)})</b>{items}<p style="font-size:12px;color:#888">顯示順序依檔名排序;改動後約 1 分鐘生效。<a href="https://s258852s.github.io/banner-site/" target=_blank>預覽</a></p></section>"""

LOGIN = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>登入</title>
<form method=post action=/login style="max-width:300px;margin:80px auto;font:16px system-ui"><input type=password name=p placeholder=密碼 autofocus style="width:100%;padding:8px"><button style="margin-top:8px;padding:8px 16px">登入</button></form>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def authed(self):
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "t" in c and hmac.compare_digest(c["t"].value, TOKEN)
    def send(self, body, code=200, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b)))
        for k, v in extra: self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def redirect(self, to="/", extra=()):
        self.send_response(303); self.send_header("Location", to)
        for k, v in extra: self.send_header(k, v)
        self.end_headers()
    def do_GET(self):
        if not self.authed(): return self.send(LOGIN)
        if self.path.startswith("/img/"):
            f = os.path.basename(urllib.parse.unquote(self.path[5:])); p = os.path.join(IMG, f)
            if os.path.isfile(p): return self.send(open(p, "rb").read(), ctype="image/*")
            return self.send("404", 404)
        self.send(page())
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        if n > 60 * 1024 * 1024: return self.send("too large", 413)
        if self.path == "/login":
            p = urllib.parse.parse_qs(self.rfile.read(n).decode()).get("p", [""])[0]
            if hmac.compare_digest(p, PASS):
                return self.redirect(extra=[("Set-Cookie", f"t={TOKEN}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000")])
            time.sleep(1); return self.send(LOGIN, 401)
        if not self.authed(): return self.send(LOGIN, 401)
        ok, bad = [], []
        if self.path == "/add-url":
            urls = urllib.parse.parse_qs(self.rfile.read(n).decode()).get("urls", [""])[0].split()
            for u in urls:
                try: ok.append(save(fetch(u), urllib.parse.urlparse(u).path))
                except Exception as e: bad.append(f"{u[:60]}: {e}")
        elif self.path == "/add-file":
            raw = self.rfile.read(n)
            msgp = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw)
            for part in msgp.iter_parts():
                fn = part.get_filename()
                if not fn: continue
                try: ok.append(save(part.get_payload(decode=True)[:MAX + 1], fn))
                except Exception as e: bad.append(f"{fn}: {e}")
        elif self.path == "/delete":
            f = os.path.basename(urllib.parse.parse_qs(self.rfile.read(n).decode()).get("f", [""])[0]); p = os.path.join(IMG, f)
            if os.path.isfile(p): os.remove(p); ok.append(f)
        else: return self.send("404", 404)
        if ok: publish()
        msg = (f"完成 {len(ok)} 張。" if ok else "") + (" 失敗:" + "；".join(bad) if bad else "")
        self.send(page(msg or "沒有變動", "err" if bad else ""))

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8790), H).serve_forever()
