"""Builds every SVG asset for the profile README.

Setup (run from this scripts/ folder):
    npm pack @fontsource/bricolage-grotesque @fontsource/jetbrains-mono
    for f in *.tgz; do tar xzf $f && mv package ${f%.tgz}; done
    pip install fonttools brotli skia-pathops
    python build.py            # writes to ../assets

Fonts are subset and embedded as base64 so the SVGs render identically
inside GitHub's <img> sandbox (which blocks all external requests)."""
import base64, io, os, html, glob
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.pens.basePen import BasePen

# ---------- config ----------
NAME_GLYPHS = "Charles"
HANDLE = "selrvk"
SITE = "charlesalcantara.com"
EMAIL = "charles.a7cantara@gmail.com"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
os.makedirs(OUT, exist_ok=True)

HERE = os.path.dirname(os.path.abspath(__file__))
FS = glob.glob(HERE + "/fontsource-bricolage-grotesque-*/files")[0] + "/bricolage-grotesque-latin-{}-normal.woff2"
FM = glob.glob(HERE + "/fontsource-jetbrains-mono-*/files")[0] + "/jetbrains-mono-latin-{}-normal.woff2"
ASCII = "".join(chr(c) for c in range(32, 127)) + "×—’·▸"

THEMES = {
    "dark": dict(canvas="#1E1E1E", dot="#3A3A3A", ink="#F2F0EB", muted="#8E8E93",
                 frame="#2C2C2C", frameline="#3D3D3D", label="#8E8E93",
                 sel="#0D99FF", comp="#9747FF", handle_fill="#1E1E1E"),
    "light": dict(canvas="#F5F5F5", dot="#D9D9D9", ink="#1A1A1A", muted="#6B6B70",
                  frame="#FFFFFF", frameline="#E3E3E3", label="#7A7A7F",
                  sel="#0D99FF", comp="#9747FF", handle_fill="#FFFFFF"),
}


def font_face(path, family, weight, text=ASCII):
    opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga"]
    f = TTFont(path)
    s = subset.Subsetter(opts); s.populate(text=text); s.subset(f)
    buf = io.BytesIO(); f.flavor = "woff2"; f.save(buf)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")


# ---------- glyph outline -> cubic segments (Figma-style vector edit view) ----------
class CubicPen(BasePen):
    def __init__(self, gs):
        super().__init__(gs); self.d = []; self.anchors = []; self.handles = []
    def _moveTo(self, p): self.d.append(f"M{p[0]:.1f} {p[1]:.1f}"); self.anchors.append(p)
    def _lineTo(self, p): self.d.append(f"L{p[0]:.1f} {p[1]:.1f}"); self.anchors.append(p)
    def _curveToOne(self, c1, c2, p):
        p0 = self._getCurrentPoint()
        self.d.append(f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p[0]:.1f} {p[1]:.1f}")
        self.handles += [(p0, c1), (p, c2)]; self.anchors.append(p)
    def _qCurveToOne(self, q, p):
        p0 = self._getCurrentPoint()
        c1 = (p0[0] + 2 / 3 * (q[0] - p0[0]), p0[1] + 2 / 3 * (q[1] - p0[1]))
        c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
        self._curveToOne(c1, c2, p)
    def _closePath(self): self.d.append("Z")


def glyph_run(text, path, size, x0, baseline):
    from fontTools.ttLib.removeOverlaps import removeOverlaps
    f = TTFont(path); cm = f.getBestCmap()
    removeOverlaps(f, [cm[ord(c)] for c in set(text)])
    gs = f.getGlyphSet()
    k = size / f["head"].unitsPerEm
    tf = lambda p: (x0 + p[0] * k, baseline - p[1] * k)
    glyphs, x = [], 0
    for ch in text:
        g = gs[cm[ord(ch)]]; pen = CubicPen(gs)
        from fontTools.pens.qu2cuPen import Qu2CuPen
        g.draw(Qu2CuPen(pen, max_err=1.5, all_cubic=True))
        # transform pen output
        d = " ".join(pen.d)
        anchors = [tf((a[0] + x, a[1])) for a in pen.anchors]
        handles = [(tf((a[0] + x, a[1])), tf((b[0] + x, b[1]))) for a, b in pen.handles]
        glyphs.append(dict(d=d, x=x, anchors=anchors, handles=handles))
        x += g.width
    return glyphs, k


def hero(theme):
    t = THEMES[theme]
    W, H = 1200, 500
    size, x0, base = 232, 112, 262
    bold = FS.format(800)
    glyphs, k = glyph_run(NAME_GLYPHS, bold, size, x0, base)
    f = TTFont(bold); gs = f.getGlyphSet(); cm = f.getBestCmap()
    # tight bbox of drawn glyphs
    xs = [a[0] for g in glyphs for a in g["anchors"]] + [p[0] for g in glyphs for h in g["handles"] for p in h]
    ys = [a[1] for g in glyphs for a in g["anchors"]] + [p[1] for g in glyphs for h in g["handles"] for p in h]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    pad = 10; bx0 -= pad; by0 -= pad; bx1 += pad; by1 += pad
    bw, bh = bx1 - bx0, by1 - by0

    css = [font_face(FS.format(500), "Brico", 500), font_face(FM.format(500), "Mono", 500)]
    css.append(f"""
    .lbl{{font-family:'Mono',ui-monospace,monospace;font-size:13px;fill:{t['label']}}}
    .sub{{font-family:'Brico',system-ui,sans-serif;font-weight:500;font-size:30px;fill:{t['ink']};letter-spacing:-.2px}}
    .sub2{{font-family:'Brico',system-ui,sans-serif;font-weight:500;font-size:30px;fill:{t['muted']};letter-spacing:-.2px}}
    .stroke{{fill:none;stroke:{t['sel']};stroke-dasharray:1;stroke-dashoffset:1;
             animation:draw 2.2s cubic-bezier(.65,0,.35,1) forwards}}
    .fill{{fill:{t['ink']};opacity:0;animation:fadein .7s ease-out 2.1s forwards}}
    .pts{{opacity:0;animation:pts .5s ease-out forwards}}
    .hdl line{{stroke:{t['sel']};stroke-width:1;opacity:.55}}
    .hdl circle{{fill:{t['handle_fill']};stroke:{t['sel']};stroke-width:1}}
    .anc{{fill:{t['handle_fill']};stroke:{t['sel']};stroke-width:1.2}}
    .settle{{animation:settle .8s ease-in-out 3.6s forwards}}
    .selbox{{opacity:0;animation:fadein .15s linear 3.35s forwards}}
    .cursor{{transform:translate(1240px,560px);animation:glide 1.1s cubic-bezier(.3,.7,.2,1) 2.3s forwards}}
    .press{{transform-box:fill-box;transform-origin:0 0;animation:press .25s ease-in-out 3.3s}}
    .copy{{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) 3.7s forwards}}
    @keyframes draw{{to{{stroke-dashoffset:0}}}}
    @keyframes fadein{{to{{opacity:1}}}}
    @keyframes pts{{to{{opacity:1}}}}
    @keyframes settle{{to{{opacity:0}}}}
    @keyframes glide{{to{{transform:translate({bx1 + 16:.0f}px,{by1 + 20:.0f}px)}}}}
    @keyframes press{{50%{{transform:scale(.86)}}}}
    @keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
    @media (prefers-reduced-motion:reduce){{
      *{{animation:none!important}} .stroke{{stroke-dashoffset:0}} .fill,.selbox,.copy,.pts{{opacity:1}}
      .settle{{opacity:0}} .cursor{{transform:translate({bx1 + 16:.0f}px,{by1 + 20:.0f}px)}} }}
    """)

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
         f'aria-label="Charles Alcantara, full stack developer and visual designer">',
         f"<style>{''.join(css)}</style>",
         f'<defs><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
         f'<circle cx="1" cy="1" r="1" fill="{t["dot"]}"/></pattern></defs>',
         f'<rect width="{W}" height="{H}" rx="14" fill="{t["canvas"]}"/>',
         f'<rect width="{W}" height="{H}" rx="14" fill="url(#dots)"/>']
    # frame
    fx, fy, fw, fh = 56, 48, W - 112, H - 96
    o.append(f'<text class="lbl" x="{fx}" y="{fy - 12}">{HANDLE} / profile</text>')
    o.append(f'<text class="lbl" x="{fx + fw}" y="{fy - 12}" text-anchor="end">{fw} × {fh}</text>')
    o.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="{t["frame"]}" stroke="{t["frameline"]}"/>')

    # glyph layers: fill (below), outline stroke, handles + anchors
    for i, g in enumerate(glyphs):
        tr = f'transform="translate({x0 + g["x"] * k:.2f} {base}) scale({k:.5f} {-k:.5f})"'
        o.append(f'<path class="fill" style="animation-delay:{2.1 + i * .05:.2f}s" {tr} d="{g["d"]}"/>')
    for i, g in enumerate(glyphs):
        tr = f'transform="translate({x0 + g["x"] * k:.2f} {base}) scale({k:.5f} {-k:.5f})"'
        o.append(f'<path class="stroke" pathLength="1" stroke-width="{1.5 / k:.2f}" '
                 f'style="animation-delay:{i * .12:.2f}s" {tr} d="{g["d"]}"/>')
    o.append('<g class="settle">')
    for i, g in enumerate(glyphs):
        delay = .35 + i * .12
        o.append(f'<g class="pts" style="animation-delay:{delay:.2f}s"><g class="hdl">')
        for a, b in g["handles"]:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 3: continue
            o.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>'
                     f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="2.4"/>')
        o.append("</g>")
        for a in g["anchors"]:
            o.append(f'<rect class="anc" x="{a[0] - 3:.1f}" y="{a[1] - 3:.1f}" width="6" height="6"/>')
        o.append("</g>")
    o.append("</g>")

    # selection box + handles + dimension pill
    o.append('<g class="selbox">')
    o.append(f'<rect x="{bx0:.1f}" y="{by0:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="none" stroke="{t["sel"]}" stroke-width="1.5"/>')
    for hx in (bx0, (bx0 + bx1) / 2, bx1):
        for hy in (by0, (by0 + by1) / 2, by1):
            if hx == (bx0 + bx1) / 2 and hy == (by0 + by1) / 2: continue
            o.append(f'<rect x="{hx - 4.5:.1f}" y="{hy - 4.5:.1f}" width="9" height="9" fill="#fff" stroke="{t["sel"]}" stroke-width="1.5"/>')
    dim = f"{bw:.0f} × {bh:.0f}"
    pw = len(dim) * 8.1 + 18
    cx = (bx0 + bx1) / 2
    o.append(f'<rect x="{cx - pw / 2:.1f}" y="{by1 + 10:.1f}" width="{pw:.1f}" height="22" rx="4" fill="{t["sel"]}"/>'
             f'<text x="{cx:.1f}" y="{by1 + 25.5:.1f}" text-anchor="middle" font-family="Mono,monospace" '
             f'font-size="13" fill="#fff">{dim}</text>')
    o.append("</g>")

    # copy
    o.append(f'<g class="copy"><text class="sub" x="{x0 + 4}" y="{by1 + 88:.0f}">Full stack developer and visual designer.</text>'
             f'<text class="sub2" x="{x0 + 4}" y="{by1 + 128:.0f}">I write the code and I draw the thing it becomes.</text></g>')

    # multiplayer cursor
    o.append(f'<g class="cursor"><g class="press">'
             f'<path d="M0 0 L0 22 L6 16.5 L10.5 26 L14 24.4 L9.6 15 L17 15 Z" fill="{t["comp"]}" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>'
             f'<rect x="16" y="24" width="{len(HANDLE) * 8.4 + 18:.0f}" height="24" rx="6" fill="{t["comp"]}"/>'
             f'<text x="25" y="40.5" font-family="Brico,system-ui,sans-serif" font-weight="500" font-size="14" fill="#fff">{HANDLE}</text>'
             f"</g></g>")
    o.append("</svg>")
    return "\n".join(o)


# ---------- terminal ----------
def terminal():
    W = 1200; fs = 21; cw = fs * .6; lh = 34; px = 44; top = 84
    P = [("charles@selrvk", "#9747FF"), (" ~ ", "#6E7681"), ("% ", "#6E7681")]
    script = [
        ("cmd", "whoami"),
        ("out", [("Charles Alcantara", "#F2F0EB"), (", full stack developer and visual designer", "#8B949E")]),
        ("gap",),
        ("cmd", "cat now.md"),
        ("out", [("  building  ", "#6E7681"), ("a React Native capstone app", "#F2F0EB")]),
        ("out", [("  learning  ", "#6E7681"), ("AI with PyTorch and TensorFlow, Cisco networking, UI/UX", "#F2F0EB")]),
        ("out", [("  open to   ", "#6E7681"), ("open source and system design collaborations", "#F2F0EB")]),
        ("out", [("  based in  ", "#6E7681"), ("the Philippines, GMT+8", "#F2F0EB")]),
        ("gap",),
        ("cmd", f"open https://{SITE}"),
        ("out", [("  ", ""), ("▸ ", "#0D99FF"), ("portfolio opened in a new tab", "#8B949E")]),
        ("gap",),
        ("prompt",),
    ]
    rows = sum(1 if s[0] != "gap" else .5 for s in script)
    H = int(top + rows * lh + 14)
    mono = [font_face(FM.format(w), "Mono", w) for w in (400, 700)]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Terminal: whoami and what Charles is working on now">',
         "<style>" + "".join(mono) +
         f".t{{font-family:'Mono',ui-monospace,monospace;font-size:{fs}px;white-space:pre}}"
         ".b{font-weight:700}"
         ".o{opacity:0;animation:on 0s linear forwards}"
         "@keyframes on{to{opacity:1}}"
         ".blink{animation:blink 1.05s steps(1) infinite}"
         "@keyframes blink{50%{opacity:0}}"
         "@media (prefers-reduced-motion:reduce){.o{animation:none;opacity:1}}"
         "</style>",
         '<defs><linearGradient id="bar" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#1F2329"/><stop offset="1" stop-color="#191C21"/></linearGradient></defs>',
         f'<rect width="{W}" height="{H}" rx="14" fill="#0F1115"/>',
         f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="#2A2F37"/>',
         f'<path d="M14 0.5H{W - 14}A13.5 13.5 0 0 1 {W - .5} 14V46H.5V14A13.5 13.5 0 0 1 14 .5Z" fill="url(#bar)"/>',
         f'<line x1="0" x2="{W}" y1="46" y2="46" stroke="#2A2F37"/>',
         '<circle cx="28" cy="23" r="6.5" fill="#FF5F57"/><circle cx="50" cy="23" r="6.5" fill="#FEBC2E"/><circle cx="72" cy="23" r="6.5" fill="#28C840"/>',
         f'<text x="{W / 2}" y="28" text-anchor="middle" font-family="Mono,monospace" font-size="13" fill="#8B949E">charles@selrvk: ~ — zsh</text>']
    t = 0.5; y = top; spd = .065; cid = 0
    plen = sum(len(s) for s, _ in P)

    def prompt_spans():
        return "".join(f'<tspan fill="{c}"{" class=\"b\"" if i == 0 else ""}>{html.escape(s)}</tspan>' for i, (s, c) in enumerate(P))

    for step in script:
        kind = step[0]
        if kind == "gap":
            y += lh / 2; continue
        if kind == "cmd":
            cmd = step[1]; cid += 1
            o.append(f'<text xml:space="preserve" class="t o" style="animation-delay:{t:.2f}s" x="{px}" y="{y}">{prompt_spans()}</text>')
            t += .35
            x = px + plen * cw
            vals = ";".join(f"{i * cw:.1f}" for i in list(range(len(cmd) + 1)) + [len(cmd) + 1])
            dur = spd * len(cmd)
            o.append(f'<clipPath id="c{cid}"><rect x="{x}" y="{y - fs}" height="{lh}" width="0">'
                     f'<animate attributeName="width" values="{vals}" calcMode="discrete" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                     f'</rect></clipPath>')
            o.append(f'<text xml:space="preserve" class="t" clip-path="url(#c{cid})" x="{x}" y="{y}" fill="#E6EDF3">{html.escape(cmd)}</text>')
            xs = ";".join(f"{x + i * cw:.1f}" for i in list(range(len(cmd) + 1)) + [len(cmd)])
            o.append(f'<rect x="{x}" y="{y - fs + 2}" width="{cw:.1f}" height="{fs + 5}" fill="#0D99FF" opacity="0">'
                     f'<set attributeName="opacity" to=".9" begin="{t - .3:.2f}s"/>'
                     f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                     f'<set attributeName="opacity" to="0" begin="{t + dur + .25:.2f}s"/></rect>')
            t += dur + .35; y += lh
        elif kind == "out":
            spans = "".join(f'<tspan fill="{c or "#E6EDF3"}">{html.escape(s)}</tspan>' for s, c in step[1])
            o.append(f'<text xml:space="preserve" class="t o" style="animation-delay:{t:.2f}s" x="{px}" y="{y}">{spans}</text>')
            t += .12; y += lh
        elif kind == "prompt":
            t += .3
            o.append(f'<text xml:space="preserve" class="t o" style="animation-delay:{t:.2f}s" x="{px}" y="{y}">{prompt_spans()}</text>')
            o.append(f'<g class="o" style="animation-delay:{t:.2f}s"><rect class="blink" x="{px + plen * cw}" y="{y - fs + 2}" width="{cw:.1f}" height="{fs + 5}" fill="#0D99FF"/></g>')
    o.append("</svg>")
    return "\n".join(o)


# ---------- link buttons (Figma component chips) ----------
ICONS = {
    # simple, original glyph drawings, 20x20 box
    "web": '<circle cx="10" cy="10" r="8" fill="none" stroke="{c}" stroke-width="1.6"/><ellipse cx="10" cy="10" rx="3.6" ry="8" fill="none" stroke="{c}" stroke-width="1.6"/><line x1="2" x2="18" y1="10" y2="10" stroke="{c}" stroke-width="1.6"/>',
    "mail": '<rect x="2" y="4" width="16" height="12" rx="2" fill="none" stroke="{c}" stroke-width="1.6"/><path d="M2.8 5.2 10 11l7.2-5.8" fill="none" stroke="{c}" stroke-width="1.6" stroke-linejoin="round"/>',
    "in": '<rect x="2" y="2" width="16" height="16" rx="3" fill="none" stroke="{c}" stroke-width="1.6"/><line x1="6.3" x2="6.3" y1="8.5" y2="14.5" stroke="{c}" stroke-width="1.8"/><circle cx="6.3" cy="5.7" r="1.1" fill="{c}"/><path d="M9.6 14.5V8.5M9.6 11.2c0-1.7 1-2.8 2.4-2.8s2.2 1 2.2 2.6v3.5" fill="none" stroke="{c}" stroke-width="1.8"/>',
    "gh": '<path d="M7.4 16.6c-3.6 1.1-3.6-1.8-5-2.2M12.6 18.4v-2.8c0-.8.1-1.4-.4-1.9 2.4-.3 4.9-1.2 4.9-5.3a4.1 4.1 0 0 0-1.1-2.9 3.8 3.8 0 0 0-.1-2.9s-.9-.3-3 1.1a10.3 10.3 0 0 0-5.4 0c-2.1-1.4-3-1.1-3-1.1a3.8 3.8 0 0 0-.1 2.9 4.1 4.1 0 0 0-1.1 2.9c0 4.1 2.5 5 4.9 5.3-.5.5-.5 1-.4 1.9v2.8" fill="none" stroke="{c}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>',
}


def chip(icon, text, theme):
    t = THEMES[theme]
    ff = font_face(FS.format(500), "Brico", 500, text=text)
    w = int(len(text) * 9.3 + 76)
    h = 52
    fg, bg, line = (t["ink"], t["frame"], t["frameline"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{html.escape(text)}">'
            f"<style>{ff}</style>"
            f'<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="10" fill="{bg}" stroke="{line}" stroke-width="1.5"/>'
                        f'<path d="M22 17l4.5 4.5-4.5 4.5-4.5-4.5z" fill="{t["comp"]}" transform="translate(0 4.5)"/>'
            f'<g transform="translate(38 16)">{ICONS[icon].format(c=fg)}</g>'
            f'<text x="68" y="32.5" font-family="Brico,system-ui,sans-serif" font-weight="500" font-size="17" fill="{fg}">{html.escape(text)}</text>'
            "</svg>")


if __name__ == "__main__":
    for th in THEMES:
        open(f"{OUT}/hero-{th}.svg", "w").write(hero(th))
        for icon, text, slug in [("web", SITE, "site"), ("mail", EMAIL, "email"),
                                 ("in", "LinkedIn", "linkedin"), ("gh", "GitHub", "github")]:
            open(f"{OUT}/chip-{slug}-{th}.svg", "w").write(chip(icon, text, th))
    open(f"{OUT}/terminal.svg", "w").write(terminal())
    for fn in sorted(os.listdir(OUT)):
        print(fn, os.path.getsize(f"{OUT}/{fn}") // 1024, "KB")
