#!/usr/bin/env python3
"""
Build the Ariel estimate as a self-contained HTML page (single source of
truth for both the web link and the final PDF). Data comes from
build_estimate.py; images are embedded as base64. Run weasyprint on the
output to produce the PDF.
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


def before_cell(lead, body, img):
    src = b64(img) if img else None
    inner = (f'<div class="baphoto" style="background-image:url({src})"></div>' if src
             else '<div class="baphoto after"><span class="aftxt">FINISHED DESIGN</span>'
                  '<span class="afsub">photo to be added</span></div>')
    tag = "BEFORE"
    return inner, lead, body, tag


def ba_cell(lead, body, img, tag):
    src = b64(img) if img else None
    if src:
        ph = f'<div class="baphoto" style="background-image:url({src})"></div>'
    else:
        ph = ('<div class="baphoto after"><span class="aftxt">FINISHED DESIGN</span>'
              '<span class="afsub">photo to be added</span></div>')
    return (f'<div class="bacell"><div class="tag">{tag}</div>{ph}'
            f'<div class="cap"><b>{esc(lead)}</b><br>{esc(body)}</div></div>')


def ba_pair(pair):
    (bl, bb, bi), (al, ab, ai) = pair
    return (f'<div class="bapair">{ba_cell(bl, bb, bi, "BEFORE")}'
            f'{ba_cell(al, ab, ai, "AFTER")}</div>')


# ---------------------------------------------------------------- chrome
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


# ---------------------------------------------------------------- pages
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
  <div class="cov-bottom">
    <div class="goldband"></div>
    <div class="lower">
      <div class="cocompany">{esc(E.COMPANY['name']).upper()}</div>
      <div class="cotag">{esc(E.COMPANY['tagline'])}</div>
      <div class="covscope">
        <span>2,720 SQ FT PAVERS</span><span class="dot">·</span>
        <span>1,230 SQ FT ARTIFICIAL TURF</span><span class="dot">·</span>
        <span>PALMS &amp; GRAVEL PREP</span>
      </div>
      <div class="dcols">{cols}</div>
      <div class="cofoot">
        <span>{esc(E.COMPANY['license'])} &nbsp;·&nbsp; {esc(E.COMPANY['phone'])} &nbsp;·&nbsp; {esc(E.COMPANY['web'])}</span>
        <span>{esc(E.COMPANY['address'])}</span>
      </div>
    </div>
  </div>
</section>"""


def overview():
    lead, body = E.FINISHED["intro"]
    stats = "".join(
        f'<div class="stat {"hi" if l.lower().startswith("total") else ""}">'
        f'<div class="snum">{esc(v)}</div><div class="slab"><b>{esc(u)}</b> · {esc(l)}</div></div>'
        for v, u, l in E.MEASURE)
    mats = "".join(f'<div class="matrow"><b>{n}</b><span>{d}</span></div>'
                   for n, d in E.MATERIALS)
    return f"""
<section class="page">{page_head("01","PROJECT OVERVIEW")}
  <h2>Project Overview</h2><div class="rule"></div>
  <div class="ibox gold"><b class="ititle navy">{esc(lead)}</b><p>{esc(body)}</p></div>
  <div class="stats big">{stats}</div>
  <div class="grid2 ov">
    <div class="ibox plain"><b class="ititle">WHAT WE'RE BUILDING</b>
      <ul>
        <li><b>2,720 sq ft pavers</b> &nbsp;·&nbsp; Angelus, Sandstone Copper</li>
        <li><b>1,230 sq ft turf</b> &nbsp;·&nbsp; Marathon synthetic grass</li>
        <li>Palm planting prep &amp; decorative gravel</li>
        <li>Concrete / paver borders and accent lighting tie-in</li>
      </ul></div>
    <div class="ibox plain"><b class="ititle">MATERIALS &amp; SELECTIONS</b>
      <div class="mats">{mats}</div></div>
  </div>
  <div class="ibox navy wide"><b class="ititle">THE FINISHED LOOK</b>
    <p>Warm Sandstone Copper pavers wrap the pool and run clean to the house, a full Marathon
    turf lawn stays green year-round, and a row of palms with uplighting and white gravel
    frames the yard. Every surface sits on a compacted, draining base so it stays flat for years.</p></div>
  {page_foot(2)}
</section>"""


def included():
    rows = "".join(
        f'<tr class="{"alt" if i%2==0 else ""}"><td class="num">{esc(n)}</td>'
        f'<td class="phase">{esc(p)}</td><td class="desc">{esc(d)}</td></tr>'
        for i, (n, p, d) in enumerate(E.SCOPE_ROWS))
    return f"""
<section class="page">{page_head("02","SCOPE OF WORK")}
  <h2>What's Included</h2><div class="rule"></div>
  <p class="lead">This is the full job. Everything below is bundled into the price on page 6.
     Labor, equipment, debris haul-off, and on-site management are included.</p>
  <table class="scope"><thead><tr><th>#</th><th>PHASE</th><th>WORK INCLUDED</th></tr></thead>
    <tbody>{rows}</tbody></table>
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
  <div class="ibox gold wide"><b class="ititle">CLIENT-SUPPLIED</b>
    <p>Palm trees (date palms) are purchased by the client. We prepare the planting
    infrastructure and install the decorative gravel around them.</p></div>
  {page_foot(3)}
</section>"""


def before_after_page(pairs, page_no, with_intro):
    intro = f'<p class="lead">{esc(E.BEFORE_AFTER["intro"])}</p>' if with_intro else \
            '<p class="lead">More angles of the yard, each shown today next to the finished design.</p>'
    body = "".join(ba_pair(p) for p in pairs)
    return f"""
<section class="page">{page_head("03","SITE TODAY VS. FINISHED")}
  <h2>Before &amp; After</h2><div class="rule"></div>
  {intro}
  {body}
  {page_foot(page_no)}
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
<section class="page">{page_head("04","INVESTMENT")}
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
  <div class="cfoot"><span>{esc(E.COMPANY['name'])} &nbsp;·&nbsp; {esc(E.COMPANY['license'])} &nbsp;·&nbsp; {esc(E.COMPANY['phone'])}</span><span>Page 7 of 7</span></div>
</section>"""


CSS = """
:root{--navy:#1B2A5B;--gold:#B0894A;--cream:#FAF6EE;--cream2:#F6F1E6;
--grey:#5b6573;--greyl:#9AA1AC;--ink:#1F2733;--line:#E3E6EB;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:#5b6472;font-family:Arial,Helvetica,sans-serif;color:var(--ink);
-webkit-print-color-adjust:exact;print-color-adjust:exact}
.page{position:relative;width:8.5in;height:11in;background:#fff;margin:18px auto;
padding:50px 64px 74px;box-shadow:0 6px 24px rgba(0,0,0,.3);overflow:hidden}
@media print{body{background:#fff}.page{margin:0;box-shadow:none}}
@page{size:letter;margin:0}
h2{color:var(--navy);font-size:32px;margin-top:10px}
h3{color:var(--navy);font-size:16px;margin:20px 0 3px}
.eyebrow{font-weight:bold;font-size:9px;letter-spacing:2.4px}
.eyebrow.gold{color:var(--gold)}.eyebrow.grey{color:var(--greyl)}
.center{text-align:center}
.rule{width:50px;height:2px;background:var(--gold);margin:11px 0 6px}
.rule.center{margin:11px auto}
.lead{color:var(--grey);font-size:12.5px;line-height:1.5;margin:10px 0 14px}
.topbar{position:absolute;top:0;left:0;right:0;height:11px;background:var(--navy)}
.topgold{position:absolute;top:11px;left:0;right:0;height:3px;background:var(--gold)}
.rhead{display:flex;justify-content:space-between;align-items:center;margin:8px 0 20px}
.rco{color:var(--navy);font-weight:bold;font-size:12px}
.rcli{color:var(--greyl);font-size:12px}
.cfoot{position:absolute;bottom:36px;left:64px;right:64px;display:flex;justify-content:space-between;
border-top:1px solid var(--line);padding-top:9px;color:var(--greyl);font-size:9.5px}
/* info boxes */
.ibox{background:var(--cream);border-left:4px solid var(--gold);border-radius:4px;
padding:14px 18px;margin:12px 0}
.ibox.navy{border-left-color:var(--navy)}
.ibox.plain{border-left-color:var(--gold)}
.ibox.wide{margin-top:14px}
.ititle{color:var(--gold);font-size:11px;letter-spacing:.6px;display:block;margin-bottom:7px}
.ititle.navy{color:var(--navy);font-size:15px}
.ibox p{font-size:12px;line-height:1.55}
.ibox ul{margin-left:18px;font-size:12px;line-height:1.7}
.big{font-size:19px;font-weight:bold;margin:2px 0 7px}.navy{color:var(--navy)}
/* stats */
.stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin:16px 0}
.stats.big .stat{padding:18px 12px}
.stat{background:var(--cream);border-radius:8px;padding:14px;text-align:center}
.stat.hi{background:var(--navy)}
.snum{font-size:26px;font-weight:bold;color:var(--navy)}.stat.hi .snum{color:#fff}
.slab{font-size:9.5px;color:var(--grey);margin-top:4px}.slab b{color:var(--gold)}
.stat.hi .slab{color:#C9CFE0}
/* overview */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:6px}
.grid2.ov{margin-top:14px}
.matrow{margin-bottom:7px;font-size:11.5px;line-height:1.4}
.matrow b{color:var(--navy);display:block}
.matrow span{color:var(--grey)}
/* scope table */
table{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}
.scope th,.sched th{background:var(--navy);color:#fff;font-size:8.5px;text-align:left;padding:7px 9px;letter-spacing:.5px}
.scope td{padding:10px 9px;vertical-align:top;border-bottom:1px solid var(--line)}
.scope tr.alt td{background:#F7F8FA}
.num{color:var(--gold);font-weight:bold;font-size:14px;width:36px}
.phase{color:var(--navy);font-weight:bold;width:155px}
.desc{color:var(--ink);font-size:11px;line-height:1.45}
/* before/after */
.bapair{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-bottom:13px}
.bacell .tag{font-size:8px;font-weight:bold;letter-spacing:2.5px;color:var(--greyl);margin-bottom:5px}
.baphoto{height:1.95in;border-radius:7px;background-size:cover;background-position:center;
background-color:#EEF1F5}
.baphoto.after{display:flex;flex-direction:column;align-items:center;justify-content:center;
background:var(--cream);border:1px solid #E6DEC9}
.aftxt{color:var(--gold);font-weight:bold;font-size:12px;letter-spacing:1.5px}
.afsub{color:var(--greyl);font-size:9px;margin-top:5px}
.cap{font-size:11px;color:var(--grey);margin-top:7px;line-height:1.4}
.cap b{color:var(--ink)}
/* pricing */
.banner{background:var(--navy);border-radius:8px;text-align:center;padding:16px;margin:12px 0}
.beyebrow{color:var(--gold);font-size:9px;letter-spacing:2px;font-weight:bold}
.btotal{color:#fff;font-size:36px;font-weight:bold;margin:3px 0}
.bnote{color:#AEB6CC;font-size:10.5px}
.sched td{padding:7px 9px;border-bottom:1px solid var(--line);font-size:12px}
.sched tr.alt td{background:#F7F8FA}
.sched .amt{text-align:right;color:var(--navy);font-weight:bold}
.sched .pct{text-align:right;color:var(--grey);width:56px}
.sched tr.total td{background:var(--cream2);color:var(--navy);font-weight:bold;border:none}
th.amt{text-align:right}th.pct{text-align:right}
.optband{background:var(--cream);border-radius:8px;padding:14px 18px;margin:14px 0}
.oblab{color:var(--gold);font-size:9px;font-weight:bold;letter-spacing:1px;margin-bottom:9px}
.opts{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.opt{border-left:1px solid #E6DEC9;padding-left:14px}
.opt:first-child{border-left:none;padding-left:0}
.oprice{font-size:23px;font-weight:bold;color:var(--navy)}
.oname{font-size:11.5px;font-weight:bold;color:var(--ink);margin-top:3px}
.osub{font-size:10px;color:var(--grey)}.osub.rec{color:var(--gold);font-weight:bold}
/* cover */
.cover{background:var(--navy);padding:0;position:relative}
.card{background:#fff;border-radius:14px;width:6.4in;margin:1.5in auto 0;padding:34px 30px 38px;text-align:center;color:var(--ink)}
.logo{width:1.45in;height:auto;margin:0 auto 8px}
.ctitle{color:var(--navy);font-size:42px;margin:8px 0 2px}
.csub{color:var(--gold);font-style:italic;font-size:14px}
.cname{font-size:22px;font-weight:bold;margin:8px 0 5px}
.caddr{color:var(--grey);font-size:12.5px;line-height:1.55}
.cphone{color:var(--greyl);font-size:11px;margin-top:7px}
.cov-bottom{background:var(--navy);position:absolute;bottom:0;left:0;right:0}
.goldband{height:3px;background:var(--gold)}
.lower{padding:30px 0.9in 36px;color:#fff}
.cocompany{font-weight:bold;font-size:15px;letter-spacing:.5px}
.cotag{color:#AEB6CC;font-size:11px;margin-top:7px}
.covscope{display:flex;gap:14px;align-items:center;margin:22px 0 8px;color:var(--gold);
font-size:10px;font-weight:bold;letter-spacing:1.5px}
.covscope .dot{color:#5b6aa0}
.dcols{display:flex;gap:1.1in;margin:26px 0 30px}
.dlab{color:var(--gold);font-size:9px;font-weight:bold;letter-spacing:1px}
.dval{color:#fff;font-size:13px;margin-top:6px}
.cofoot{position:static;display:flex;justify-content:space-between;border-top:1px solid #33406B;
padding-top:12px;color:#AEB6CC;font-size:9.5px}
/* thanks */
.thanks{text-align:center}
.tlogo{width:1.3in;margin-top:34px}
.tbig{color:var(--navy);font-size:32px;margin:8px 0 2px}
.tgrid{text-align:left;margin-top:34px}
.disc{color:var(--greyl);font-style:italic;font-size:11.5px;margin-top:30px;max-width:6in;margin-left:auto;margin-right:auto;line-height:1.55}
"""

pages = (cover() + overview() + included()
         + before_after_page(E.BEFORE_AFTER["pairs"][:3], 4, True)
         + before_after_page(E.BEFORE_AFTER["pairs"][3:], 5, False)
         + pricing() + thanks())

HTMLDOC = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(E.COMPANY['name'])} | {esc(E.CLIENT['name'])} Estimate</title>
<style>{CSS}</style></head><body>
{pages}
</body></html>"""


def build():
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(HTMLDOC)
    print("wrote", OUT, f"({os.path.getsize(OUT)//1024} KB)")


if __name__ == "__main__":
    build()
