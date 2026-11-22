"""Naukari Pakki render service (runs OFF the quiz server). POST /render  (header X-NP-Signature = hex HMAC-SHA256 of the raw body with RENDER_SECRET)
 -> 200 application/pdf  (primary)  |  200 application/zip of PNG pages, header X-NP-Format: png  (fallback when PDF fails)  |  4xx/5xx JSON error.
GET /health. Concurrent requests are supported; at most MAX_JOBS Chrome processes run at once, others wait (queue), so memory stays bounded."""
import hashlib, hmac, io, json, os, shutil, tempfile, threading, time, zipfile
from flask import Flask, Response, jsonify, request
import render

SECRET = os.environ.get('RENDER_SECRET', '')
MAX_JOBS = int(os.environ.get('MAX_JOBS', '3'))
MAX_BODY = 2 * 1024 * 1024
TMP_ROOT = os.environ.get('RENDER_TMP', tempfile.gettempdir()) + '/np_render'
TTL = int(os.environ.get('FILE_TTL_SECONDS', '3600'))
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_BODY
sem = threading.BoundedSemaphore(MAX_JOBS)
os.makedirs(TMP_ROOT, exist_ok=True)

def cleanup_loop():
    while True:
        now = time.time()
        for n in os.listdir(TMP_ROOT):
            p = os.path.join(TMP_ROOT, n)
            try:
                if now - os.path.getmtime(p) > TTL:
                    shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            except OSError:
                pass
        time.sleep(300)
threading.Thread(target=cleanup_loop, daemon=True).start()

def authorised(raw):
    if not SECRET:
        return False                                   # never run open
    sig = request.headers.get('X-NP-Signature', '')
    return hmac.compare_digest(sig, hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest())

@app.get('/health')
def health():
    return jsonify(ok=True, chrome=bool(render.CHROME), busy=MAX_JOBS - sem._value)

@app.post('/render')
def do_render():
    raw = request.get_data()
    if not authorised(raw):
        return jsonify(error='unauthorised'), 401
    try:
        payload = json.loads(raw)
        if payload.get('kind') == 'match':
            job = tempfile.mkdtemp(dir=TMP_ROOT)
            try:
                with sem:
                    out = os.path.join(job, 'm.png')
                    try:
                        render.render_match_png(payload, out)
                    except Exception as e:
                        return jsonify(error='render failed: ' + str(e)[:200]), 500
                    return Response(open(out, 'rb').read(), mimetype='image/png', headers={'X-NP-Format': 'png1'})
            finally:
                shutil.rmtree(job, ignore_errors=True)
        items = payload.get('cards') if 'cards' in payload else payload.get('questions')
        assert isinstance(items, list) and 0 < len(items) <= 200
    except Exception:
        return jsonify(error='bad payload'), 400
    job = tempfile.mkdtemp(dir=TMP_ROOT)
    try:
        with sem:                                       # waits when MAX_JOBS renders are already running
            pdf = os.path.join(job, 'notes.pdf')
            try:
                render.render_pdf(payload, pdf)
                data = open(pdf, 'rb').read()
                return Response(data, mimetype='application/pdf', headers={'X-NP-Format': 'pdf'})
            except Exception as e:                      # PDF failed -> PNG pages with the same design
                try:
                    if not os.path.isfile(pdf):
                        raise
                    pngs = render.render_png(pdf, os.path.join(job, 'pg'))
                except Exception:
                    return jsonify(error='render failed: ' + str(e)[:200]), 500
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w') as z:
                    for i, f in enumerate(pngs, 1):
                        z.write(f, 'page_%02d.png' % i)
                return Response(buf.getvalue(), mimetype='application/zip', headers={'X-NP-Format': 'png'})
    finally:
        shutil.rmtree(job, ignore_errors=True)
