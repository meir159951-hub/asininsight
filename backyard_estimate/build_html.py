#!/usr/bin/env python3
"""
Build a self-contained HTML version of the Ariel estimate.
Reuses all data from build_estimate.py (single source of truth) and embeds
images as base64 so the page is one portable file. Print CSS makes each
section a US-Letter page, so the same HTML converts cleanly to a 7-page PDF.
"""
import os, base64, html
import build_estimate as E

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "estimate.html")


def b64(path):
    if not path or not os.path.exists(path):
        return None
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    mime = "image/png" if ext == "png" else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


LOGO = b64(E.LOGO)


def esc(s):
    return html.escape(str(s))


def photo_html(img, label, cls="ph"):
    src = b64(img) if img else None
    if src:
        return f'<div class="{cls} filled" style="background-image:url({src})"></div>'
    return (f'<div class="{cls} empty"><div class="phlabel">{esc(label)}</div>'
            f'<div class="phsub">photo pending</div></div>')


def cover():
    cols = "".join(
        f'<div class="dcol"><div class="dlab">{esc(l)}</div><div class="dval">{esc(v)}</div></div>'
        for l, v in [("DATE", E.DOC["date"]), ("ESTIMATE NO.", E.DOC["estimate_no"]),
                     ("VALID FOR", E.DOC["valid_for"])])
    return f"""
<section class="page cover">
  <div class="card">
    <img class="logo" src="{LOGO}" alt="Ariel">
    <div class="eyebrow gold center">PROJECT ESTIMATE</div>
    <h1 class="ctitle">{esc(E.DOC['project_title'])}</h1>
    <div class="csub">{esc(E.DOC['project_sub'])}</div>
    <div class="rule center"></div>
    <div class="eyebrow grey center">PREPARED FOR</div>
    <div class="cname">{esc(E.CLIENT['name'])}</div>
    <div class="caddr">{esc(E.CLIENT['addr1'])}<br>{esc(E.CLIENT['addr2'])}</div>
    <div class="cphone">{esc(E.CLIENT['phone'])}</div>
  </div>
  <div class="goldband"></div>
  <div class="lower">
    <div class="cocompany">{esc(E.COMPANY['name']).upper()}</div>
    <div class="cotag">{esc(E.COMPANY['tagline'])}</div>
    <div class="dcols">{cols}</div>
    <div class="cofoot">
      <span>{esc(E.COMPANY['license'])} &nbsp;·&nbsp; {esc(E.COMPANY['phone'])} &nbsp;·&nbsp; {esc(E.COMPANY['web'])}</span>
      <span>{esc(E.COMPANY['address'])}</span>
    </div>
  </div>
</section>"""


def page_head(num, label):
    return f"""
  <div class="topbar"></div><div class="topgold"></div>
  <div class="rhead">
    <span class="rco">{esc(E.COMPANY['name']).upper()}</span>
    <span class="rcli">{esc(E.CLIENT['residence'])} &nbsp;·&nbsp; Project Estimate</span>
  </div>
  <div class="eyebrow gold">{esc(num)} · {esc(label)}</div>"""


def page_foot(n):
    return f"""
  <div class="cfoot">
    <span>{esc(E.COMPANY['name'])} &nbsp;·&nbsp; {esc(E.COMPANY['license'])} &nbsp;·&nbsp; {esc(E.COMPANY['phone'])}</span>
    <span>Page {n} of 7</span>
  </div>"""


def finished():
    lead, body = E.FINISHED["intro"]
    stats = "".join(
        f'<div class="stat {"hi" if l.lower().startswith("total") else ""}">'
        f'<div class="snum">{esc(v)}</div><div class="slab"><b>{esc(u)}</b> · {esc(l)}</div></div>'
        for v, u, l in E.MEASURE)
    grid = "".join(
        f'<div class="gcell">{photo_html(img, lead2, "ph half")}'
        f'<div class="cap"><b>{esc(lead2)}</b><br>{esc(body2)}</div></div>'
        for lead2, body2, img in E.FINISHED["grid"])
    return f"""
<section class="page">{page_head("01","DESIGN DIRECTION")}
  <h2>Finished Look</h2><div class="rule"></div>
  <div class="ibox gold"><b class="ititle navy">{esc(lead)}</b><p>{esc(body)}</p></div>
  <div class="stats">{stats}</div>
  {photo_html(E.FINISHED['hero'], "FINISHED — HERO", "ph hero")}
  <div class="grid2">{grid}</div>
  {page_foot(2)}
</section>"""


def scope():
    rows = "".join(
        f'<tr class="{"alt" if i%2==0 else ""}"><td class="num">{esc(n)}</td>'
        f'<td class="phase">{esc(p)}</td><td class="desc">{esc(d)}</td></tr>'
        for i, (n, p, d) in enumerate(E.SCOPE_ROWS))
    mats = "<br>".join(f"<b>{n}:</b> {d}" for n, d in E.MATERIALS)
    return f"""
<section class="page">{page_head("02","SCOPE OF WORK")}
  <h2>What's Included</h2><div class="rule"></div>
  <p class="lead">Everything below is bundled into the price on page 6. Labor, equipment,
     debris haul-off, and on-site management are included.</p>
  <table class="scope"><thead><tr><th>#</th><th>PHASE</th><th>WORK INCLUDED</th></tr></thead>
    <tbody>{rows}</tbody></table>
  <div class="ibox gold"><b class="ititle">MATERIALS &amp; SELECTIONS</b><p>{mats}</p></div>
  <div class="grid2">
    <div class="ibox navy"><b class="ititle">HOW WE DO THE JOB</b>
      <ul><li>Compacted, draining aggregate base under everything.</li>
      <li>Proper slope so water runs off, never pools.</li>
      <li>Edges locked with borders so nothing shifts.</li>
      <li>Site cleaned and hauled off when we leave.</li></ul></div>
    <div class="ibox navy"><b class="ititle">LICENSED, INSURED, SPECIALIZED</b>
      <ul><li>CSLB License #1129259, Class B General Building.</li>
      <li>Outdoor renovation only: paving, fencing, hardscape.</li>
      <li>General liability and workers' comp on file.</li></ul></div>
  </div>
  {page_foot(3)}
</section>"""


def ba_pair(pair):
    out = ""
    for i, (lead, body, img) in enumerate(pair):
        tag = "BEFORE" if i == 0 else "AFTER"
        out += (f'<div class="gcell"><div class="tag">{tag}</div>'
                f'{photo_html(img, tag, "ph half")}'
                f'<div class="cap"><b>{esc(lead)}</b><br>{esc(body)}</div></div>')
    return f'<div class="grid2">{out}</div>'


def before_after():
    pairs = "".join(ba_pair(p) for p in E.BEFORE_AFTER["pairs"])
    nt, nb = E.BEFORE_AFTER["note"]
    return f"""
<section class="page">{page_head("03","SITE TODAY VS. FINISHED")}
  <h2>Before &amp; After</h2><div class="rule"></div>
  <p class="lead">{esc(E.BEFORE_AFTER['intro'])}</p>
  {pairs}
  <div class="ibox navy"><b class="ititle">{esc(nt).upper()}</b><p>{esc(nb)}</p></div>
  {page_foot(4)}
</section>"""


def angles():
    rows = "".join(ba_pair(r) for r in E.ANGLES["rows"])
    return f"""
<section class="page">{page_head("04","MORE ANGLES")}
  <h2>Side Yard, Right Side &amp; Corners</h2><div class="rule"></div>
  <p class="lead">{esc(E.ANGLES['intro'])}</p>
  {rows}
  {page_foot(5)}
</section>"""


def pricing():
    sched = "".join(
        f'<tr class="{"alt" if i%2==0 else ""}"><td class="num">{esc(n)}</td>'
        f'<td>{esc(m)}</td><td class="amt">{esc(a)}</td><td class="pct">{esc(p)}</td></tr>'
        for i, (n, m, a, p) in enumerate(E.PRICING["schedule"]))
    opts = "".join(
        f'<div class="opt"><div class="oprice">{esc(pr)}</div>'
        f'<div class="oname">{esc(nm)}</div>'
        f'<div class="osub {"rec" if "recommend" in sub.lower() else ""}">{esc(sub)}</div></div>'
        for nm, sub, pr in E.PRICING["options"])
    ni = "".join(f"<li>{n}</li>" for n in E.PRICING["not_included"])
    return f"""
<section class="page">{page_head("05","INVESTMENT")}
  <h2>Pricing &amp; Terms</h2><div class="rule"></div>
  <div class="banner"><div class="beyebrow">TOTAL PROJECT INVESTMENT</div>
    <div class="btotal">{esc(E.PRICING['total'])}</div>
    <div class="bnote">{esc(E.PRICING['total_note'])}</div></div>
  <h3>Payment Schedule</h3>
  <p class="lead">Structured per California CSLB rules. Down payment limited to $1,000 by law.
     Progress payments are tied to milestones on site.</p>
  <table class="sched"><thead><tr><th>#</th><th>MILESTONE</th><th class="amt">AMOUNT</th><th class="pct">%</th></tr></thead>
    <tbody>{sched}
    <tr class="total"><td></td><td>TOTAL</td><td class="amt">{esc(E.PRICING['total'])}</td><td class="pct">100%</td></tr>
    </tbody></table>
  <div class="optband"><div class="oblab">OPTIONAL SCOPES</div><div class="opts">{opts}</div></div>
  <div class="grid2">
    <div class="ibox gold"><b class="ititle">TIMELINE</b>
      <div class="big navy">{esc(E.PRICING['timeline_title'])}</div><p>{esc(E.PRICING['timeline_body'])}</p></div>
    <div class="ibox navy"><b class="ititle">NOT INCLUDED</b><ul>{ni}</ul></div>
  </div>
  {page_foot(6)}
</section>"""


def thanks():
    return f"""
<section class="page thanks">
  <div class="topbar"></div><div class="topgold"></div>
  <div class="rhead"><span class="rco">{esc(E.COMPANY['name']).upper()}</span>
    <span class="rcli">{esc(E.CLIENT['residence'])} &nbsp;·&nbsp; Project Estimate</span></div>
  <img class="logo tlogo" src="{LOGO}">
  <div class="eyebrow gold center">THANK YOU</div>
  <h1 class="tbig">We Look Forward to Working With You</h1>
  <div class="rule center"></div>
  <div class="grid2 tgrid">
    <div class="ibox gold"><b class="ititle">NEXT STEPS</b>
      <p>Call <b>{esc(E.DOC['pm_name'].split()[0])}</b> at <b>{esc(E.DOC['pm_phone'])}</b> with any
      questions or to move forward. We will schedule an in-person meeting to sign the formal
      contract, which includes the California Mechanics Lien Warning, the 3-day Right to Cancel
      notice, and full CSLB disclosures.</p></div>
    <div class="ibox navy"><b class="ititle">ABOUT ARIEL</b>
      <p>We hold a California CSLB <b>Class B General Building</b> license, but by choice we work
      only on outdoor projects: paving, fencing, outdoor kitchens, and hardscape. Specialization
      is what keeps our work tight and our timelines predictable.</p></div>
  </div>
  <p class="disc">This is an estimate, not a contract. Pricing valid {esc(E.DOC['valid_for'].lower())}
     from the cover date. A formal home-improvement contract supersedes this document upon signing.</p>
  {page_foot(7)}
</section>"""


CSS = """
:root{--navy:#1B2A5B;--gold:#B0894A;--cream:#FAF6EE;--cream2:#F6F1E6;
--grey:#6B7280;--greyl:#9AA1AC;--ink:#1F2733;--line:#E3E6EB;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#5b6472;font-family:Arial,Helvetica,sans-serif;color:var(--ink);
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{position:relative;width:8.5in;min-height:11in;background:#fff;margin:18px auto;
padding:46px 61px 70px;box-shadow:0 6px 24px rgba(0,0,0,.3);overflow:hidden}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;page-break-after:always}}
@page{size:letter;margin:0}
h2{color:var(--navy);font-size:30px;margin-top:8px}
h3{color:var(--navy);font-size:15px;margin:18px 0 2px}
.eyebrow{font-weight:bold;font-size:9px;letter-spacing:2.4px}
.eyebrow.gold{color:var(--gold)}.eyebrow.grey{color:var(--greyl)}
.center{text-align:center}
.rule{width:48px;height:2px;background:var(--gold);margin:10px 0 4px}
.rule.center{margin:10px auto}
.lead{color:var(--grey);font-size:12px;margin:8px 0 10px}
/* top chrome */
.topbar{position:absolute;top:0;left:0;right:0;height:10px;background:var(--navy)}
.topgold{position:absolute;top:10px;left:0;right:0;height:3px;background:var(--gold)}
.rhead{display:flex;justify-content:space-between;align-items:center;margin:6px 0 18px}
.rco{color:var(--navy);font-weight:bold;font-size:12px}
.rcli{color:var(--greyl);font-size:12px}
.cfoot{position:absolute;bottom:34px;left:61px;right:61px;display:flex;justify-content:space-between;
border-top:1px solid var(--line);padding-top:8px;color:var(--greyl);font-size:9.5px}
/* info boxes */
.ibox{background:var(--cream);border-left:4px solid var(--gold);border-radius:4px;
padding:12px 16px;margin:10px 0}
.ibox.navy{border-left-color:var(--navy)}
.ititle{color:var(--gold);font-size:11px;letter-spacing:.5px;display:block;margin-bottom:5px}
.ititle.navy{color:var(--navy);font-size:15px}
.ibox p{font-size:11px;line-height:1.5}
.ibox ul{margin-left:16px;font-size:11px;line-height:1.55}
.big{font-size:18px;font-weight:bold;margin:2px 0 6px}.navy{color:var(--navy)}
/* photos */
.ph{border-radius:6px;background-size:cover;background-position:center}
.ph.empty{border:1.5px dashed #C7CDD6;background:#EEF1F5;display:flex;flex-direction:column;
align-items:center;justify-content:center}
.phlabel{color:var(--greyl);font-weight:bold;font-size:11px}
.phsub{color:var(--greyl);font-size:9px;margin-top:3px}
.hero{width:100%;height:2.0in;margin:8px 0}
.half{height:1.5in}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:8px}
.gcell .cap{font-size:11px;color:var(--grey);margin-top:6px;line-height:1.4}
.gcell .cap b{color:var(--ink)}
.tag{font-size:8px;font-weight:bold;letter-spacing:2px;color:var(--greyl);margin-bottom:4px}
/* stats */
.stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:14px 0}
.stat{background:var(--cream);border-radius:6px;padding:12px;text-align:center}
.stat.hi{background:var(--navy)}
.snum{font-size:21px;font-weight:bold;color:var(--navy)}.stat.hi .snum{color:#fff}
.slab{font-size:9px;color:var(--grey);margin-top:3px}.slab b{color:var(--gold)}
.stat.hi .slab{color:#C9CFE0}
/* scope table */
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:11px}
.scope th,.sched th{background:var(--navy);color:#fff;font-size:8.5px;text-align:left;padding:6px 8px;letter-spacing:.5px}
.scope td{padding:9px 8px;vertical-align:top;border-bottom:1px solid var(--line)}
.scope tr.alt td{background:#F7F8FA}
.num{color:var(--gold);font-weight:bold;font-size:13px;width:34px}
.phase{color:var(--navy);font-weight:bold;width:150px}
.desc{color:var(--ink);font-size:10.5px;line-height:1.4}
/* pricing */
.banner{background:var(--navy);border-radius:8px;text-align:center;padding:14px;margin:10px 0}
.beyebrow{color:var(--gold);font-size:9px;letter-spacing:2px;font-weight:bold}
.btotal{color:#fff;font-size:34px;font-weight:bold;margin:2px 0}
.bnote{color:#AEB6CC;font-size:10px}
.sched td{padding:6px 8px;border-bottom:1px solid var(--line);font-size:11px}
.sched tr.alt td{background:#F7F8FA}
.sched .amt{text-align:right;color:var(--navy);font-weight:bold}
.sched .pct{text-align:right;color:var(--grey);width:54px}
.sched tr.total td{background:var(--cream2);color:var(--navy);font-weight:bold;border:none}
th.amt{text-align:right}th.pct{text-align:right}
.optband{background:var(--cream);border-radius:6px;padding:12px 16px;margin:12px 0}
.oblab{color:var(--gold);font-size:9px;font-weight:bold;letter-spacing:1px;margin-bottom:8px}
.opts{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.opt{border-left:1px solid #E6DEC9;padding-left:12px}
.opt:first-child{border-left:none;padding-left:0}
.oprice{font-size:21px;font-weight:bold;color:var(--navy)}
.oname{font-size:11px;font-weight:bold;color:var(--ink);margin-top:2px}
.osub{font-size:10px;color:var(--grey)}.osub.rec{color:var(--gold);font-weight:bold}
/* cover */
.cover{background:var(--navy);color:#fff;padding:0}
.card{background:#fff;border-radius:12px;margin:1.2in 0.9in 0;padding:26px 24px 30px;text-align:center;color:var(--ink)}
.logo{width:1.3in;height:auto;margin:0 auto 6px}
.ctitle{color:var(--navy);font-size:38px;margin:6px 0 2px}
.csub{color:var(--gold);font-style:italic;font-size:13px}
.cname{font-size:20px;font-weight:bold;margin:6px 0 4px}
.caddr{color:var(--grey);font-size:12px;line-height:1.5}
.cphone{color:var(--greyl);font-size:11px;margin-top:6px}
.goldband{height:3px;background:var(--gold);margin-top:34px}
.lower{padding:30px 0.9in 0}
.cocompany{font-weight:bold;font-size:14px;letter-spacing:.5px}
.cotag{color:#AEB6CC;font-size:11px;margin-top:6px}
.dcols{display:flex;gap:1.1in;margin:42px 0 60px}
.dlab{color:var(--gold);font-size:9px;font-weight:bold;letter-spacing:1px}
.dval{color:#fff;font-size:13px;margin-top:6px}
.cofoot{display:flex;justify-content:space-between;border-top:1px solid #33406B;
padding-top:10px;color:#AEB6CC;font-size:9.5px}
/* thanks */
.thanks{text-align:center}
.tlogo{width:1.2in;margin-top:24px}
.tbig{color:var(--navy);font-size:30px;margin:6px 0 2px}
.tgrid{text-align:left;margin-top:24px}
.disc{color:var(--greyl);font-style:italic;font-size:11px;margin-top:22px;max-width:6in;margin-left:auto;margin-right:auto}
"""

HTMLDOC = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(E.COMPANY['name'])} — {esc(E.CLIENT['name'])} Estimate</title>
<style>{CSS}</style></head><body>
{cover()}{finished()}{scope()}{before_after()}{angles()}{pricing()}{thanks()}
</body></html>"""


def build():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(HTMLDOC)
    print("wrote", OUT, f"({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    build()
