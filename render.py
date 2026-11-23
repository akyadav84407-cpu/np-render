"""Naukari Pakki study-notes renderer: JSON payload -> A4 PDF (primary) or PNG pages (fallback). HTML + headless Chrome (HarfBuzz shaping,
so Hindi conjuncts/matras are correct, text stays selectable). No PHP/GD involved; runs OFF the quiz server."""
import base64, html, os, shutil, subprocess, tempfile, glob

CHROME = os.environ.get('CHROME_BIN') or shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
HERE = os.path.dirname(os.path.abspath(__file__))
OPT = ['A', 'B', 'C', 'D']

def esc(s):
    return html.escape(str(s or ''), quote=False).replace('\n', '<br>')

def logo_uri(payload):
    b = payload.get('logo_b64')
    if b:
        return 'data:image/png;base64,' + b
    f = os.path.join(HERE, 'logo.png')
    if os.path.isfile(f):
        return 'data:image/png;base64,' + base64.b64encode(open(f, 'rb').read()).decode()
    return ''

CSS = """
@page { size: A4; margin: 14mm 12mm 16mm 12mm;
  @bottom-center { content: "Naukari Pakki  |  Page " counter(page) " of " counter(pages); font: 8pt 'Noto Sans','FreeSans',sans-serif; color:#0B2A6B; }
  @bottom-right { content: "naukaripakki.in"; font: 8pt 'Noto Sans','FreeSans',sans-serif; color:#6b7280; } }
* { box-sizing: border-box; }
body { font-family: 'Noto Sans','Noto Sans Devanagari','FreeSans','Mukta',sans-serif; font-size: 9.2pt; color:#111827; line-height:1.38; margin:0; }
.hdr { display:flex; align-items:center; background:#0B2A6B; color:#fff; padding:7px 12px; border-radius:6px; border-bottom:4px solid #FFD21F; }
.hdr img { width:44px; height:44px; background:#fff; border-radius:6px; padding:2px; margin-right:12px; }
.hdr .t { font-weight:700; font-size:15pt; } .hdr .s { font-size:9pt; color:#FFD21F; }
.meta { display:flex; justify-content:space-between; margin:6px 2px 8px; font-size:8.6pt; color:#0B2A6B; font-weight:600; }
.q { border:1px solid #cfd9ee; border-left:5px solid #0B2A6B; border-radius:5px; padding:6px 9px; margin:0 0 8px; break-inside:avoid; }
.q h3 { margin:0 0 3px; font-size:10pt; color:#0B2A6B; }
.q h3 span.n { background:#FFD21F; color:#0B2A6B; border-radius:10px; padding:0 7px; margin-right:6px; }
.hi { color:#1f2937; } .opts { margin:3px 0; display:grid; grid-template-columns:1fr 1fr; gap:1px 10px; font-size:8.8pt; }
.opts .c { color:#0E7A32; font-weight:700; }
.ans { background:#e8f6ec; border-radius:4px; padding:2px 6px; display:inline-block; font-weight:700; color:#0E7A32; margin:2px 0; }
.ex { margin-top:3px; font-size:8.8pt; } .ex b { color:#0B2A6B; }
.gk { background:#fff7d6; border-radius:4px; padding:3px 7px; margin-top:3px; font-size:8.6pt; }
.src { font-size:7.6pt; color:#6b7280; margin-top:2px; word-break:break-all; }
.pg { break-after:page; } .pg:last-child { break-after:auto; }
"""

def build_html(p):
    qs = p.get('questions', [])
    per = int(p.get('per_page') or 0) or max(1, len(p.get('questions', [])))   # 0 = natural flow, as many per page as fit
    lg = logo_uri(p)
    head = ('<div class="hdr">' + (f'<img src="{lg}">' if lg else '') +
            f'<div><div class="t">NAUKARI PAKKI</div><div class="s">{esc(p.get("title", "Detailed Study Notes"))}</div></div></div>'
            f'<div class="meta"><span>Subject / विषय: {esc(p.get("subject", ""))}</span><span>Date / दिनांक: {esc(p.get("date", ""))}</span>'
            f'<span>Questions: {len(qs)}</span></div>')
    pages = []
    for i in range(0, max(1, len(qs)), per):
        body = head if i == 0 else '<div class="meta"><span>NAUKARI PAKKI – ' + esc(p.get('title', '')) + '</span></div>'
        for q in qs[i:i + per]:
            opts = ''.join(
                f'<div class="{"c" if k == q.get("correct") else ""}">({OPT[j]}) {esc(q.get("opt_en", ["","","",""])[j])} / {esc(q.get("opt_hi", ["","","",""])[j])}</div>'
                for j, k in enumerate(OPT))
            body += (f'<div class="q"><h3><span class="n">Q{q.get("no")}</span>{esc(q.get("q_en"))}</h3>'
                     f'<div class="hi">{esc(q.get("q_hi"))}</div><div class="opts">{opts}</div>'
                     f'<div class="ans">✔ Answer / उत्तर: ({esc(q.get("correct"))})</div>'
                     f'<div class="ex"><b>Explanation:</b> {esc(q.get("expl_en"))}</div><div class="ex hi"><b>व्याख्या:</b> {esc(q.get("expl_hi"))}</div>')
            if q.get('notes_en') or q.get('notes_hi'):
                body += f'<div class="ex"><b>Current Affairs:</b> {esc(q.get("notes_en"))}</div><div class="ex hi"><b>करंट अफेयर्स:</b> {esc(q.get("notes_hi"))}</div>'
            if q.get('static_gk_en') or q.get('static_gk_hi'):
                body += f'<div class="gk"><b>Static GK / स्थैतिक सामान्य ज्ञान:</b> {esc(q.get("static_gk_en"))}<br>{esc(q.get("static_gk_hi"))}</div>'
            if q.get('source'):
                body += f'<div class="src">Source: {esc(q.get("source"))}</div>'
            body += '</div>'
        pages.append(f'<div class="pg">{body}</div>')
    return f'<!doctype html><html lang="hi"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'


TOPIC_CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin:0; padding:0; }
body { font-family: 'Noto Sans','Noto Sans Devanagari','FreeSans','Mukta',sans-serif; color:#111827; }
.page { width:210mm; height:297mm; padding:4mm 4mm 0; position:relative; break-after:page; overflow:hidden; background:#fff; }
.page:last-child { break-after:auto; }
.top { height:21mm; background:#0B2A6B; border-radius:3mm; display:flex; align-items:center; padding:0 4mm; color:#fff; border-bottom:1.2mm solid #FFD21F; }
.top img { width:15mm; height:15mm; background:#fff; border-radius:50%; padding:.6mm; margin-right:3mm; }
.top .brand { font-weight:800; font-size:19pt; color:#FFD21F; line-height:1; } .top .sub { font-size:6.6pt; color:#fff; margin-top:1mm; }
.top .mid { margin-left:auto; text-align:right; } .top .gs { font-weight:800; font-size:12.5pt; } .top .part { display:inline-block; background:#FFD21F; color:#0B2A6B; font-weight:800; border-radius:2mm; padding:0 3mm; margin-left:2mm; font-size:11pt; }
.top .pill { margin-top:1.2mm; background:#C8161D; border-radius:3mm; padding:.4mm 3mm; font-size:6.8pt; font-weight:700; display:inline-block; }
.grid { display:grid; grid-template-columns:repeat(3, 1fr); grid-template-rows:repeat(5, 1fr); gap:2mm; height:calc(297mm - 4mm - 21mm - 2mm - 13mm); margin-top:2mm; }
.card { border:.25mm solid #9db3d6; border-radius:2mm; overflow:hidden; display:flex; flex-direction:column; background:#fff; min-height:0; }
.card .hd { background:#0B2A6B; color:#fff; padding:.9mm 1.5mm .9mm 1mm; display:flex; align-items:center; min-height:9mm; flex:0 0 auto; }
.card .no { flex:0 0 auto; background:#FFD21F; color:#0B2A6B; font-weight:800; font-size:9.5pt; border-radius:1.6mm; padding:0 1.6mm; margin-right:1.4mm; line-height:1.35; }
.card .ht { font-weight:800; font-size:7.3pt; line-height:1.18; } .card .ht i { font-style:normal; font-weight:700; color:#FFE27A; display:block; font-size:6.7pt; }
.card .bd { padding:1.1mm 1.5mm; font-size:7.3pt; line-height:1.27; flex:1 1 auto; overflow:hidden; }
.card ul { list-style:none; margin:0; padding:0; } .card li { padding-left:2.4mm; position:relative; margin-bottom:.5mm; }
.card li:before { content:""; position:absolute; left:0; top:1.1mm; width:1.2mm; height:1.2mm; background:#C8861D; }
.card li b { color:#0B2A6B; }
.hl { background:#FFF1B8; border-radius:1mm; padding:.5mm 1.3mm; margin:.7mm 0; font-weight:600; }
table.t { width:100%; border-collapse:collapse; margin:.6mm 0; font-size:6.4pt; } table.t th { background:#FFE27A; color:#0B2A6B; border:.2mm solid #d7b53a; padding:.2mm .8mm; } table.t td { border:.2mm solid #cbd5e1; padding:.2mm .8mm; }
.ftr { position:absolute; left:4mm; right:4mm; bottom:3mm; height:8mm; background:#0B2A6B; color:#fff; border-radius:2mm; display:flex; align-items:center; justify-content:space-between; padding:0 4mm; font-size:6.4pt; font-weight:700; }
.ftr .b { color:#FFD21F; font-weight:800; font-size:9pt; }
.mq { border:.3mm solid #9db3d6; border-radius:2.5mm; margin:3mm 0; overflow:hidden; }
.mq .qh { background:#0B2A6B; color:#fff; padding:2mm 3mm; font-size:9.5pt; font-weight:800; display:flex; justify-content:space-between; }
.mq .qh span { background:#FFD21F; color:#0B2A6B; border-radius:2mm; padding:0 2.5mm; }
.mq .qb { padding:2.5mm 3mm; font-size:9pt; line-height:1.45; } .mq .qb .en { color:#374151; font-size:8.4pt; margin-top:1mm; }
.mq .ans { background:#FFF9DB; border-top:.3mm solid #FFD21F; padding:2.5mm 3mm; font-size:9pt; line-height:1.5; } .mq .ans b { color:#0B2A6B; }
.mnote { font-size:7.6pt; color:#6b7280; margin:1mm 0 0; }
"""
SHRINK_JS = """<script>
document.querySelectorAll('.card .bd').forEach(function(b){var fs=7.3;while(b.scrollHeight>b.clientHeight+1&&fs>4.9){fs-=0.15;b.style.fontSize=fs+'pt';}});
</script>"""

def _card(c, n):
    pts = ''.join(f'<li><b>{esc(p.get("k", ""))}</b>{": " if p.get("k") else ""}{esc(p.get("v", ""))}</li>' for p in c.get('points', []))
    hl = f'<div class="hl">{esc(c.get("highlight"))}</div>' if c.get('highlight') else ''
    tb = ''
    t = c.get('table')
    if t and t.get('head') and t.get('rows'):
        tb = '<table class="t"><tr>' + ''.join(f'<th>{esc(h)}</th>' for h in t['head']) + '</tr>' + \
             ''.join('<tr>' + ''.join(f'<td>{esc(x)}</td>' for x in r) + '</tr>' for r in t['rows']) + '</table>'
    return (f'<div class="card"><div class="hd"><span class="no">{n:02d}</span><div class="ht">{esc(c.get("heading_en"))}'
            f'<i>{esc(c.get("heading_hi"))}</i></div></div><div class="bd"><ul>{pts}</ul>{hl}{tb}</div></div>')

def build_topics_html(p):
    EN = p.get('lang') == 'en'
    LANGC = 'en' if EN else 'hi'
    cards = p.get('cards', [])
    lg = logo_uri(p)
    pages = []
    mains = [m for m in (p.get('mains') or []) if isinstance(m, dict) and m.get('q_hi') and m.get('a_hi')][:2]
    total = max(1, (len(cards) + 14) // 15) + (1 if mains else 0)
    card_pages = total - (1 if mains else 0)
    for pg in range(card_pages):
        chunk = cards[pg * 15:(pg + 1) * 15]
        body = ''.join(_card(c, pg * 15 + i + 1) for i, c in enumerate(chunk))
        body += ''.join('<div class="card" style="border-style:dashed;border-color:#e5e7eb"></div>' for _ in range(15 - len(chunk)))
        part = f'<span class="part">PART {pg + 1}</span>' if total > 1 else ''
        pages.append(
            f'<div class="page"><div class="top">' + (f'<img src="{lg}">' if lg else '') +
            f'<div><div class="brand">NAUKARI PAKKI</div><div class="sub">Exam Notes • Quick Revision • {"English" if EN else "Bilingual"}</div></div>'
            f'<div class="mid"><div class="gs">{esc(p.get("title", "GENERAL STUDIES | DETAILED STUDY NOTES"))}{part}</div>'
            f'<div class="pill">{esc(p.get("subject", ""))} • {esc(p.get("date", ""))}</div></div></div>'
            f'<div class="grid">{body}</div>'
            f'<div class="ftr"><span class="b">NAUKARI PAKKI</span><span>DETAILED STUDY NOTES &nbsp;|&nbsp; EXAM-ORIENTED LEARNING</span><span>Page {pg + 1} of {total}</span></div></div>')
    if mains:
        lg2 = (f'<img src="{lg}">' if lg else '')
        blocks = ''.join(
            f'<div class="mq"><div class="qh">Q{i + 1}. {"MAINS PRACTICE" if EN else "MAINS PRACTICE / मुख्य परीक्षा अभ्यास"}<span>{esc(m.get("marks", ""))} Marks • {esc(m.get("words", ""))} words</span></div>'
            f'<div class="qb"><b>{esc(m.get("q_hi"))}</b>' + (f'<div class="en">{esc(m.get("q_en"))}</div>' if m.get("q_en") else '') + '</div>'
            f'<div class="ans"><b>{"Model answer:" if EN else "Model answer / आदर्श उत्तर:"}</b><br>{esc(m.get("a_hi"))}</div></div>' for i, m in enumerate(mains))
        pages.append(
            f'<div class="page"><div class="top">{lg2}<div><div class="brand">NAUKARI PAKKI</div><div class="sub">Mains Answer Writing • BEO / PCS style</div></div>'
            f'<div class="mid"><div class="gs">MAINS PRACTICE</div><div class="pill">{esc(p.get("subject", ""))} • {esc(p.get("date", ""))}</div></div></div>'
            f'<div style="padding:2mm 3mm">{blocks}<p class="mnote">Questions are based on today\'s topics. Write the answer yourself first, then compare with the model answer.</p></div>'
            f'<div class="ftr"><span class="b">NAUKARI PAKKI</span><span>DETAILED STUDY NOTES &nbsp;|&nbsp; EXAM-ORIENTED LEARNING</span><span>Page {total} of {total}</span></div></div>')
    return f'<!doctype html><html lang="{LANGC}"><head><meta charset="utf-8"><style>{TOPIC_CSS}</style></head><body>{"".join(pages)}{SHRINK_JS}</body></html>'

def _run(cmd, timeout):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

def render_pdf(payload, out_pdf, timeout=90):
    if not CHROME:
        raise RuntimeError('Chrome/Chromium not installed')
    with tempfile.TemporaryDirectory() as d:
        h = os.path.join(d, 'n.html'); open(h, 'w', encoding='utf-8').write(build_topics_html(payload) if payload.get('cards') is not None else build_html(payload))
        r = _run([CHROME, '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', f'--user-data-dir={d}/prof',
                  '--no-pdf-header-footer', f'--print-to-pdf={out_pdf}', 'file://' + h], timeout)
    if not os.path.isfile(out_pdf) or os.path.getsize(out_pdf) < 1500:
        raise RuntimeError('pdf not produced: ' + r.stderr.decode('utf-8', 'ignore')[-300:])
    return out_pdf

def render_png(pdf, out_prefix, dpi=170):
    """PNG fallback: same design, rasterised from the PDF (one image per page)."""
    if not shutil.which('pdftoppm'):
        raise RuntimeError('pdftoppm missing')
    _run(['pdftoppm', '-png', '-r', str(dpi), pdf, out_prefix], 120)
    return sorted(glob.glob(out_prefix + '*.png'))
