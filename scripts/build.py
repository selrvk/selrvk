"""Builds every SVG on the profile README: a fake desktop OS.

    desktop.svg    menubar, design window drawing my name, terminal, sticky note
    dock-*.svg     the nav, sliced so each app icon is its own link
    apps.svg       Finder-style "Applications" window of the tools I use
    activity.svg   Activity Monitor: 3D contribution skyline, streaks, repos, languages
    statusbar.svg  footer

Setup (run from this scripts/ folder):
    npm pack @fontsource/bricolage-grotesque@5 @fontsource/jetbrains-mono@5 @fontsource/caveat@5 simple-icons@16
    for f in *.tgz; do mkdir -p "${f%.tgz}" && tar xzf "$f" -C "${f%.tgz}" --strip-components=1; done
    pip install fonttools brotli skia-pathops
    python build.py            # writes to ../assets

GITHUB_TOKEN is optional: with it, contributions come from the GraphQL API,
without it they are read from the public contribution calendar.

Fonts are subset to the exact characters each SVG uses and embedded as base64,
so everything renders identically inside GitHub's <img> sandbox (which blocks
all external requests)."""
import base64, datetime as dt, glob, html, io, json, math, os, re, urllib.request
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.pens.basePen import BasePen

# ---------- config ----------
USER = os.environ.get("PROFILE_USER", "selrvk")
NAME = "Charles"
SURNAME = "Alcantara"
SITE = "charlesalcantara.com"
EMAIL = "charles.a7cantara@gmail.com"
LINKEDIN = "https://linkedin.com/in/charles-alcantara"
TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime.now(TZ)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets")
CACHE = os.path.join(HERE, "data.json")
os.makedirs(OUT, exist_ok=True)


def pkg(name):
    hits = sorted(glob.glob(f"{HERE}/{name}-[0-9]*/"))
    if not hits:
        raise SystemExit(f"missing {name}: see setup notes at the top of build.py")
    return hits[-1]


BRICO = pkg("fontsource-bricolage-grotesque") + "files/bricolage-grotesque-latin-{}-normal.woff2"
MONO = pkg("fontsource-jetbrains-mono") + "files/jetbrains-mono-latin-{}-normal.woff2"
CAVEAT = pkg("fontsource-caveat") + "files/caveat-latin-{}-normal.woff2"
ICONS = pkg("simple-icons") + "icons/{}.svg"

# key -> (file, css fallback). Each key is its own font-family, so weights never get synthesized.
FONTS = {
    "B5": (BRICO.format(500), "system-ui,sans-serif"),
    "B6": (BRICO.format(600), "system-ui,sans-serif"),
    "B8": (BRICO.format(800), "system-ui,sans-serif"),
    "M4": (MONO.format(400), "ui-monospace,monospace"),
    "M7": (MONO.format(700), "ui-monospace,monospace"),
    "C6": (CAVEAT.format(600), "cursive"),
}

# palette
BG0, WIN, TB, LINE, PANEL, CANVAS = "#0A0A10", "#16161D", "#1D1D25", "#2A2A35", "#18181F", "#101016"
INK, MUTED, DIM = "#F2F0EB", "#8E8E9A", "#5C5C6A"
PURPLE, BLUE, GREEN = "#9747FF", "#0D99FF", "#28C840"
LIGHTS = ("#FF5F57", "#FEBC2E", "#28C840")
LANG_COLORS = {
    "TypeScript": "#3178C6", "JavaScript": "#F1E05A", "HTML": "#E34C26", "CSS": "#663399",
    "Java": "#B07219", "Python": "#3572A5", "C": "#A8B9CC", "C++": "#F34B7D", "PHP": "#4F5D95",
    "GDScript": "#478CBF", "Kotlin": "#A97BFF", "Swift": "#F05138", "Dart": "#00B4AB", "Vue": "#41B883",
}


# ---------- fonts ----------
_tt = {}


def tt(key):
    if key not in _tt:
        _tt[key] = TTFont(FONTS[key][0])
    return _tt[key]


def measure(key, s, size):
    f = tt(key); cm = f.getBestCmap(); hm = f["hmtx"]
    return sum(hm[cm.get(ord(c), cm[32])][0] for c in s) * size / f["head"].unitsPerEm


class Doc:
    """Collects the characters each font draws, so @font-face can be subset to exactly those."""

    def __init__(self, W, H, label):
        self.W, self.H, self.label = W, H, label
        self.used, self.css, self.defs, self.body = {}, [], [], []

    def t(self, key, s, x, y, size, fill=INK, anchor=None, cls=None, style=None, extra=""):
        self.used.setdefault(key, set()).update(s)
        a = f' text-anchor="{anchor}"' if anchor else ""
        c = f' class="{cls}"' if cls else ""
        st = f' style="{style}"' if style else ""
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{key},{FONTS[key][1]}" font-size="{size}" '
                f'fill="{fill}"{a}{c}{st}{extra}>{html.escape(s)}</text>')

    def spans(self, key, parts, x, y, size, cls=None, style=None):
        """one text run with differently coloured pieces"""
        out = []
        for s, fill in parts:
            self.used.setdefault(key, set()).update(s)
            out.append(f'<tspan fill="{fill}">{html.escape(s)}</tspan>')
        c = f' class="{cls}"' if cls else ""
        st = f' style="{style}"' if style else ""
        return (f'<text xml:space="preserve" x="{x:.1f}" y="{y:.1f}" font-family="{key},{FONTS[key][1]}" '
                f'font-size="{size}"{c}{st}>{"".join(out)}</text>')

    def add(self, *parts):
        self.body.extend(parts)

    def render(self):
        faces = []
        for key, chars in sorted(self.used.items()):
            opts = subset.Options(); opts.flavor = "woff2"; opts.layout_features = ["kern", "liga"]
            f = TTFont(FONTS[key][0])
            s = subset.Subsetter(opts); s.populate(text="".join(chars) + " "); s.subset(f)
            buf = io.BytesIO(); f.save(buf)
            faces.append(f"@font-face{{font-family:'{key}';src:url(data:font/woff2;base64,"
                         f"{base64.b64encode(buf.getvalue()).decode()}) format('woff2')}}")
        return "\n".join([
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.W} {self.H}" width="{self.W}" '
            f'height="{self.H}" role="img" aria-label="{html.escape(self.label)}">',
            f"<style>{''.join(faces)}{''.join(self.css)}</style>",
            f"<defs>{''.join(self.defs)}</defs>",
            *self.body, "</svg>"])


REDUCED = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
POP = (".pop{transform-box:fill-box;transform-origin:50% 60%;animation:pop .55s cubic-bezier(.2,.9,.25,1.15) both}"
       "@keyframes pop{from{opacity:0;transform:translateY(14px) scale(.96)}to{opacity:1;transform:none}}"
       ".rise{animation:rise .7s cubic-bezier(.2,.7,.2,1) both}"
       "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
       ".on{animation:on 0s linear both}@keyframes on{from{opacity:0}to{opacity:1}}")


def d(t):
    return f"animation-delay:{t:.2f}s"


# ---------- shared chrome ----------
def rtop(x, y, w, h, r):
    """rect with only the top corners rounded"""
    return (f"M{x} {y + h}V{y + r}A{r} {r} 0 0 1 {x + r} {y}H{x + w - r}A{r} {r} 0 0 1 {x + w} {y + r}V{y + h}Z")


def window(doc, x, y, w, h, title, tb=38, r=12, shadow=True, title_key="B6"):
    o = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{WIN}"'
         + (' filter="url(#shadow)"' if shadow else "") + "/>",
         f'<path d="{rtop(x, y, w, tb, r)}" fill="{TB}"/>',
         f'<line x1="{x}" x2="{x + w}" y1="{y + tb + .5}" y2="{y + tb + .5}" stroke="{LINE}"/>']
    for i, c in enumerate(LIGHTS):
        o.append(f'<circle cx="{x + 20 + i * 20}" cy="{y + tb / 2}" r="6" fill="{c}"/>')
    if title:
        o.append(doc.t(title_key, title, x + w / 2, y + tb / 2 + 4.5, 13, MUTED, "middle"))
    o.append(f'<rect x="{x + .5}" y="{y + .5}" width="{w - 1}" height="{h - 1}" rx="{r}" fill="none" '
             f'stroke="#FFFFFF" stroke-opacity=".09"/>')
    return "".join(o)


SHADOW = ('<filter id="shadow" x="-20%" y="-20%" width="140%" height="160%">'
          '<feDropShadow dx="0" dy="18" stdDeviation="22" flood-color="#000" flood-opacity=".55"/></filter>')


def cursor(doc, label, color):
    """multiplayer cursor, tip at 0,0"""
    w = measure("B6", label, 13) + 16
    return (f'<path d="M0 0 L0 20 L5.5 15 L9.6 23.8 L12.8 22.3 L8.8 13.7 L15.6 13.7 Z" fill="{color}" '
            f'stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/>'
            f'<rect x="14" y="22" width="{w:.0f}" height="22" rx="6" fill="{color}"/>'
            + doc.t("B6", label, 22, 37, 13, "#fff"))


# ---------- glyph outline -> cubic segments (vector edit view) ----------
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
    from fontTools.pens.qu2cuPen import Qu2CuPen
    f = TTFont(path); cm = f.getBestCmap()
    removeOverlaps(f, [cm[ord(c)] for c in set(text)])
    gs = f.getGlyphSet()
    k = size / f["head"].unitsPerEm
    tf = lambda p: (x0 + p[0] * k, baseline - p[1] * k)
    glyphs, x = [], 0
    for ch in text:
        g = gs[cm[ord(ch)]]; pen = CubicPen(gs)
        g.draw(Qu2CuPen(pen, max_err=1.5, all_cubic=True))
        glyphs.append(dict(d=" ".join(pen.d), x=x,
                           anchors=[tf((a[0] + x, a[1])) for a in pen.anchors],
                           handles=[(tf((a[0] + x, a[1])), tf((b[0] + x, b[1]))) for a, b in pen.handles]))
        x += g.width
    return glyphs, k, x * k


# ---------- data ----------
def get(url, data=None):
    hdr = {"User-Agent": f"{USER}-profile-build"}
    if "api.github.com" in url:
        hdr["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            hdr["Authorization"] = "bearer " + os.environ["GITHUB_TOKEN"]
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def fetch_contributions():
    if os.environ.get("GITHUB_TOKEN"):
        q = ("query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{"
             "weeks{contributionDays{date contributionCount}}}}}}")
        res = json.loads(get("https://api.github.com/graphql",
                             json.dumps({"query": q, "variables": {"l": USER}}).encode()))
        weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    page = get(f"https://github.com/users/{USER}/contributions")
    dates = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', page))
    tips = dict(re.findall(r'<tool-tip[^>]*for="([^"]+)"[^>]*>\s*(No|\d+) contribution', page))
    return {day: 0 if tips.get(cid, "No") == "No" else int(tips[cid]) for day, cid in dates.items()}


def fetch_repos():
    repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner&sort=pushed"))
    return [dict(name=r["name"], lang=r["language"], size=r["size"], pushed=r["pushed_at"], id=r["id"])
            for r in repos if not r["fork"] and r["name"].lower() != USER.lower()]


def load_data():
    try:
        data = dict(contrib=fetch_contributions(), repos=fetch_repos())
        json.dump(data, open(CACHE, "w"))
    except Exception as e:  # offline or rate limited: fall back to the last good fetch
        print("fetch failed, using cache:", e)
        data = json.load(open(CACHE))
    return data


# ---------- desktop (hero) ----------
# The hero is built from pieces so the same desktop can be laid out landscape (desktop.svg)
# and portrait for phones (desktop-m.svg).
def hero_css(doc, s):
    """s scales how far the wallpaper glows and the idle cursor travel"""
    def tr(x, y):
        return f"translate({x * s:.0f}px,{y * s:.0f}px)"
    doc.css.append(POP + f"""
    .stroke{{fill:none;stroke:{BLUE};stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2s cubic-bezier(.65,0,.35,1) both}}
    .fill{{fill:{INK};animation:fade .6s ease-out both}}
    .pts{{animation:fade .4s ease-out both}}
    .hdl line{{stroke:{BLUE};stroke-width:1;opacity:.55}}
    .hdl circle{{fill:{CANVAS};stroke:{BLUE};stroke-width:1}}
    .anc{{fill:{CANVAS};stroke:{BLUE};stroke-width:1.2}}
    .settle{{animation:out .7s ease-in-out 4.1s both}}
    .sel{{animation:fade .12s linear 3.85s both}}
    .rowsel{{animation:fade .12s linear 3.85s both}}
    .press{{transform-box:fill-box;transform-origin:0 0;animation:press .22s ease-in-out 3.75s}}
    .drop{{transform-box:fill-box;transform-origin:50% 0;animation:drop .8s cubic-bezier(.3,1.4,.4,1) both}}
    .blink{{animation:blink 1.05s steps(1) infinite}}
    .d1{{animation:d1 26s ease-in-out infinite alternate}}
    .d2{{animation:d2 31s ease-in-out infinite alternate}}
    .d3{{animation:d3 23s ease-in-out infinite alternate}}
    @keyframes d1{{to{{transform:{tr(110, -80)}}}}}
    @keyframes d2{{to{{transform:{tr(-130, 70)}}}}}
    @keyframes d3{{to{{transform:{tr(-90, -60)}}}}}
    .wander{{animation:wander 16s ease-in-out 5.2s infinite}}
    @keyframes wander{{0%,100%{{transform:none}}14%,30%{{transform:{tr(-150, -78)}}}
      44%,60%{{transform:{tr(-270, 70)}}}74%,86%{{transform:{tr(-60, 60)}}}}}
    .float{{animation:float 7s ease-in-out 8s infinite}}
    @keyframes float{{0%,100%{{transform:none}}35%{{transform:translate(-16px,10px)}}65%{{transform:translate(8px,-6px)}}}}
    .dot{{animation:dot 1.3s ease-in-out infinite}}
    @keyframes dot{{0%,60%,100%{{transform:none;opacity:.35}}30%{{transform:translateY(-3px);opacity:1}}}}
    .ping{{transform-box:fill-box;transform-origin:center;animation:ping 2.2s ease-out infinite}}
    @keyframes ping{{from{{opacity:.7;transform:scale(1)}}to{{opacity:0;transform:scale(3.2)}}}}
    .spark{{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.6s cubic-bezier(.65,0,.35,1) 5s both}}
    @keyframes draw{{to{{stroke-dashoffset:0}}}}
    @keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
    @keyframes out{{to{{opacity:0}}}}
    @keyframes press{{50%{{transform:scale(.86)}}}}
    @keyframes drop{{from{{opacity:0;transform:translateY(-40px) rotate(-8deg)}}to{{opacity:1;transform:none}}}}
    @keyframes blink{{50%{{opacity:0}}}}
    """)


def wallpaper(doc, orbs):
    """opens the screen group; the caller closes it"""
    W, H = doc.W, doc.H
    colors = [(PURPLE, .55), (BLUE, .45), ("#FF7262", .28)]
    for i, ((cx, cy, r), (c, op)) in enumerate(zip(orbs, colors), 1):
        doc.defs.append(f'<radialGradient id="o{i}" cx="{cx}" cy="{cy}" r="{r}" gradientUnits="userSpaceOnUse">'
                        f'<stop offset="0" stop-color="{c}" stop-opacity="{op}"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    doc.defs += [
        SHADOW,
        '<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" '
        'numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .5 0"/></filter>',
        '<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#2A2A34"/></pattern>',
        f'<linearGradient id="spark" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="{BLUE}" stop-opacity=".35"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></linearGradient>',
        '<linearGradient id="note" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#FFE98A"/><stop offset="1" stop-color="#FFD84D"/></linearGradient>',
        f'<clipPath id="screen"><rect width="{W}" height="{H}" rx="16"/></clipPath>',
    ]
    doc.add('<g clip-path="url(#screen)">',
            f'<rect width="{W}" height="{H}" fill="{BG0}"/>',
            *(f'<rect class="d{i}" x="-240" y="-240" width="{W + 480}" height="{H + 480}" fill="url(#o{i})"/>' for i in (1, 2, 3)),
            f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity=".07"/>')


def menubar(doc, menus):
    W, mb = doc.W, 28
    doc.add(f'<rect width="{W}" height="{mb}" fill="#0E0E14" fill-opacity=".72"/>',
            f'<line x1="0" x2="{W}" y1="{mb - .5}" y2="{mb - .5}" stroke="#fff" stroke-opacity=".07"/>',
            f'<path d="M22 7.5l6.5 6.5-6.5 6.5-6.5-6.5z" fill="{PURPLE}"/>',
            doc.t("B8", USER, 38, 19, 13.5))
    x = 38 + measure("B8", USER, 13.5) + 22
    for m in menus:
        doc.add(doc.t("B5", m, x, 19, 13.5, "#D6D4CF"))
        x += measure("B5", m, 13.5) + 20
    date = NOW.strftime("%a %-d %b")
    rx = W - 18
    doc.add(doc.t("B6", date, rx, 19, 13.5, INK, "end"))
    rx -= measure("B6", date, 13.5) + 16
    if len(menus) > 3:
        doc.add(doc.t("M4", "GMT+8", rx, 18.5, 12, MUTED, "end"))
        rx -= measure("M4", "GMT+8", 12) + 18
    # battery + wifi
    doc.add(f'<rect x="{rx - 24}" y="9" width="22" height="11" rx="3" fill="none" stroke="{INK}" stroke-opacity=".8"/>'
            f'<rect x="{rx - 22}" y="11" width="15" height="7" rx="1.5" fill="{INK}"/>'
            f'<rect x="{rx - 1.5}" y="12.5" width="2" height="4" rx="1" fill="{INK}" fill-opacity=".8"/>')
    wx = rx - 44
    doc.add(f'<g fill="none" stroke="{INK}" stroke-width="1.7" stroke-linecap="round">'
            f'<path d="M{wx - 8} 12.5a11.5 11.5 0 0 1 16 0"/><path d="M{wx - 5} 15.5a7 7 0 0 1 10 0"/></g>'
            f'<circle cx="{wx}" cy="19" r="1.7" fill="{INK}"/>')


def design_window(doc, dx, dy, dw, panel, fh=None, tb=38, surname=46, role=17, edited=True):
    """the design file: my name drawn as a vector, selected by a collaborator. Returns where that cursor lands."""
    by = dy + tb + 1
    cx0 = dx + panel + (1 if panel else 0)
    fx, fy = cx0 + (20 if panel else 16), by + 32
    fw = dx + dw - fx - (20 if panel else 16)
    B8 = FONTS["B8"][0]
    x0 = fx + 28
    unit = glyph_run(NAME, B8, 100, 0, 0)[2] / 100
    size = (fw - 60) / unit
    base = fy + 36 + size * .74
    glyphs, k, _ = glyph_run(NAME, B8, size, x0, base)
    pts = [p for g in glyphs for p in g["anchors"]] + [p for g in glyphs for h in g["handles"] for p in h]
    bx0, bx1 = min(p[0] for p in pts) - 8, max(p[0] for p in pts) + 8
    by0, by1 = min(p[1] for p in pts) - 8, max(p[1] for p in pts) + 8
    sur_y = by1 + surname * 1.52
    role_parts = [("Full stack developer ", INK), ("& visual designer", MUTED)]
    role = min(role, (fw - 60) / measure("B5", "".join(s for s, _ in role_parts), 1))
    role_y = sur_y + role * 1.9
    if fh is None:
        fh = round(role_y - fy + 74)
    dh = fy + fh + 20 - dy

    doc.add(f'<g class="pop" style="{d(.15)}">', window(doc, dx, dy, dw, dh, None, tb))
    title = [(f"{NAME.lower()}.fig", INK)] + ([("  —  Edited", MUTED)] if edited else [])
    doc.add(doc.spans("B6", title, dx + dw / 2 - measure("B6", "".join(s for s, _ in title), 13) / 2, dy + tb / 2 + 4.5, 13))
    # avatars + share
    sx, ay = dx + dw - 16 - 58, dy + tb / 2
    doc.add(f'<rect x="{sx}" y="{ay - 11}" width="58" height="22" rx="6" fill="{BLUE}"/>',
            doc.t("B6", "Share", sx + 29, ay + 4, 12.5, "#fff", "middle"),
            f'<circle cx="{sx - 18}" cy="{ay}" r="11" fill="{BLUE}" stroke="{TB}" stroke-width="2"/>',
            doc.t("B8", "Y", sx - 18, ay + 4.5, 12, "#fff", "middle"),
            f'<circle cx="{sx - 36}" cy="{ay}" r="11" fill="{PURPLE}" stroke="{TB}" stroke-width="2"/>',
            doc.t("B8", "C", sx - 36, ay + 4.5, 12, "#fff", "middle"))
    # panel and canvas are clipped to the window so its rounded corners survive
    doc.defs.append(f'<clipPath id="dwin"><rect x="{dx}" y="{dy}" width="{dw}" height="{dh}" rx="12"/></clipPath>')
    doc.add('<g clip-path="url(#dwin)">')
    if panel:
        doc.add(f'<rect x="{dx}" y="{by}" width="{panel}" height="{dh - tb - 1}" fill="{PANEL}"/>',
                f'<line x1="{dx + panel + .5}" x2="{dx + panel + .5}" y1="{by}" y2="{dy + dh}" stroke="{LINE}"/>',
                doc.t("B8", "Layers", dx + 14, by + 24, 12.5),
                doc.t("B5", "Assets", dx + 70, by + 24, 12.5, DIM))
        rows = [("#", "hello", 0), ("pen", NAME, 1), ("T", SURNAME, 1), ("T", "Full stack developer", 1),
                ("comp", f"cursor / {USER}", 1)]
        for i, (ic, label, ind) in enumerate(rows):
            ry = by + 50 + i * 26
            if label == NAME:
                doc.add(f'<rect class="rowsel" x="{dx}" y="{ry - 17}" width="{panel}" height="26" fill="{BLUE}" fill-opacity=".22"/>')
            ix = dx + 14 + ind * 14
            if ic == "#":
                doc.add(doc.t("M4", "#", ix, ry, 12.5, MUTED))
            elif ic == "T":
                doc.add(doc.t("B8", "T", ix + 1, ry, 12.5, MUTED))
            elif ic == "pen":
                doc.add(f'<path d="M{ix} {ry}l2-6 6-6 3 3-6 6z" fill="none" stroke="{MUTED}" stroke-width="1.3" stroke-linejoin="round"/>')
            else:
                doc.add(f'<path d="M{ix + 5} {ry - 10}l5 5-5 5-5-5z" fill="{PURPLE}"/>')
            name = label if measure("B5", label, 12.5) < panel - (ix - dx) - 26 else label[:12] + "…"
            doc.add(doc.t("B5", name, ix + 18, ry, 12.5, INK if ind else "#D6D4CF"))
    # canvas
    doc.add(f'<rect x="{cx0}" y="{by}" width="{dx + dw - cx0}" height="{dy + dh - by}" fill="{CANVAS}"/>',
            f'<rect x="{cx0}" y="{by}" width="{dx + dw - cx0}" height="{dy + dh - by}" fill="url(#dots)"/>')
    doc.add("</g>", f'<rect x="{dx + .5}" y="{dy + .5}" width="{dw - 1}" height="{dh - 1}" rx="12" fill="none" '
                    f'stroke="#FFFFFF" stroke-opacity=".09"/>')
    doc.add(doc.t("B5", "hello", fx, fy - 8, 12, MUTED),
            doc.t("M4", f"{fw:.0f} × {fh}", fx + fw, fy - 8, 11, DIM, "end"),
            f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="#1A1A21" stroke="{LINE}"/>',
            "</g>")

    # the name, drawn as a vector
    t0 = .7
    for i, g in enumerate(glyphs):
        tr = f'transform="translate({x0 + g["x"] * k:.2f} {base:.2f}) scale({k:.5f} {-k:.5f})"'
        doc.add(f'<path class="fill" style="{d(2.75 + i * .05)}" {tr} d="{g["d"]}"/>')
    for i, g in enumerate(glyphs):
        tr = f'transform="translate({x0 + g["x"] * k:.2f} {base:.2f}) scale({k:.5f} {-k:.5f})"'
        doc.add(f'<path class="stroke" pathLength="1" stroke-width="{1.4 / k:.2f}" style="{d(t0 + i * .12)}" '
                f'{tr} d="{g["d"]}"/>')
    doc.add('<g class="settle">')
    for i, g in enumerate(glyphs):
        doc.add(f'<g class="pts" style="{d(t0 + .3 + i * .12)}"><g class="hdl">')
        for a, b in g["handles"]:
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 3:
                continue
            doc.add(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>'
                    f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="2"/>')
        doc.add("</g>")
        for a in g["anchors"]:
            doc.add(f'<rect class="anc" x="{a[0] - 2.5:.1f}" y="{a[1] - 2.5:.1f}" width="5" height="5"/>')
        doc.add("</g>")
    doc.add("</g>")
    # selection
    doc.add('<g class="sel">',
            f'<rect x="{bx0:.1f}" y="{by0:.1f}" width="{bx1 - bx0:.1f}" height="{by1 - by0:.1f}" fill="none" stroke="{BLUE}" stroke-width="1.4"/>')
    for hx in (bx0, bx1):
        for hy in (by0, by1):
            doc.add(f'<rect x="{hx - 4:.1f}" y="{hy - 4:.1f}" width="8" height="8" fill="#fff" stroke="{BLUE}" stroke-width="1.4"/>')
    dim = f"{bx1 - bx0:.0f} × {by1 - by0:.0f}"
    pw = measure("M4", dim, 11.5) + 14
    doc.add(f'<rect x="{(bx0 + bx1) / 2 - pw / 2:.1f}" y="{by1 + 9:.1f}" width="{pw:.1f}" height="19" rx="4" fill="{BLUE}"/>',
            doc.t("M4", dim, (bx0 + bx1) / 2, by1 + 22.5, 11.5, "#fff", "middle"), "</g>")
    # the rest of the frame
    doc.add(f'<g class="rise" style="{d(4.2)}">', doc.t("B8", SURNAME, x0 + 2, sur_y, surname, INK), "</g>",
            f'<g class="rise" style="{d(4.4)}">', doc.spans("B5", role_parts, x0 + 3, role_y, round(role, 1)), "</g>")
    # comment pin
    px_, py_ = x0 + 2, fy + fh - 34
    doc.add(f'<g class="pop" style="{d(5.1)}">',
            f'<path d="M{px_} {py_ + 26}V{py_ + 13}a13 13 0 1 1 13 13z" fill="{PURPLE}"/>',
            doc.t("B8", "C", px_ + 13, py_ + 17.5, 12, "#fff", "middle"),
            f'<rect x="{px_ + 34}" y="{py_}" width="{measure("B5", "ship it.", 13.5) + 22:.0f}" height="26" rx="8" fill="{TB}" stroke="{LINE}"/>',
            doc.t("B5", "ship it.", px_ + 45, py_ + 17.5, 13.5), "</g>")
    # ...and "you" typing a reply, forever
    rx_ = px_ + 34 + measure("B5", "ship it.", 13.5) + 22 + 12
    doc.add(f'<g class="pop" style="{d(7.6)}">',
            f'<circle cx="{rx_ + 11}" cy="{py_ + 13}" r="11" fill="{BLUE}"/>',
            doc.t("B8", "Y", rx_ + 11, py_ + 17.5, 12, "#fff", "middle"),
            f'<rect x="{rx_ + 28}" y="{py_}" width="46" height="26" rx="8" fill="{TB}" stroke="{LINE}"/>')
    for i in range(3):
        doc.add(f'<circle class="dot" style="{d(i * .16)}" cx="{rx_ + 40 + i * 11}" cy="{py_ + 13}" r="2.6" fill="{INK}"/>')
    doc.add("</g>")
    return dict(cursor=(bx1 + 6, by1 + 8), bottom=dy + dh)


def sticky(doc, nx, ny, n):
    k = n / 214
    doc.add(f'<g class="drop" style="{d(2.3)}"><g transform="rotate(4 {nx + n / 2} {ny + n / 2})">',
            f'<path d="M{nx + 8 * k} {ny + n}h{n - 16 * k}l{6 * k} {8 * k}h{-n + 4 * k}z" fill="#000" opacity=".25"/>',
            f'<rect x="{nx}" y="{ny}" width="{n}" height="{n}" rx="3" fill="url(#note)"/>',
            f'<path d="M{nx + n - 30 * k} {ny + n}l{30 * k} {-30 * k}v{27 * k}a3 3 0 0 1 -3 3z" fill="#E8BF2C"/>',
            f'<rect x="{nx + n / 2 - 40 * k}" y="{ny - 11 * k}" width="{80 * k}" height="{24 * k}" fill="#fff" opacity=".45" '
            f'transform="rotate(-3 {nx + n / 2} {ny})"/>')
    for i, s in enumerate(["open to", "open source +", "system design", "collabs!"]):
        doc.add(doc.t("C6", s, nx + 20 * k, ny + (50 + i * 38) * k, round(32 * k, 1), "#2E2600"))
    uw = measure("C6", "collabs!", 32 * k)
    doc.add(f'<path d="M{nx + 18 * k} {ny + 172 * k}q{uw / 2} {7 * k} {uw + 6 * k} {-2 * k}" fill="none" stroke="#C0392B" '
            f'stroke-width="{max(2.4 * k, 1.8):.1f}" stroke-linecap="round"/>',
            doc.t("C6", "— c.", nx + n - 22 * k, ny + n - 16 * k, round(24 * k, 1), "#6B5A00", "end"), "</g></g>")


def widgets(doc, data, x, y, cal_w, spark_w, h=150, gap=12, r=22):
    """a calendar and the last 30 days of contributions, both redrawn daily"""
    doc.add(f'<g class="pop" style="{d(4.6)}">',
            f'<rect x="{x}" y="{y}" width="{cal_w}" height="{h}" rx="{r}" fill="#14141B" fill-opacity=".82" stroke="#fff" stroke-opacity=".09"/>',
            doc.t("B8", NOW.strftime("%A").upper(), x + 18, y + 30, 11.5, "#B98CFF"),
            doc.t("B8", str(NOW.day), x + 16, y + 94, 64, INK),
            doc.t("B5", NOW.strftime("%B"), x + 18, y + 118, 14, MUTED),
            doc.t("M4", "GMT+8", x + 18, y + 136, 10.5, DIM), "</g>")
    days = sorted((dt.date.fromisoformat(k), v) for k, v in data["contrib"].items())
    last = [v for k, v in days if k <= NOW.date()][-30:]
    sx = x + cal_w + gap
    sx0, sx1, sy0, sy1 = sx + 16, sx + spark_w - 18, y + 78, y + 130
    top = max(max(last), 1)
    pts = [(sx0 + (sx1 - sx0) * i / (len(last) - 1), sy1 - (sy1 - sy0) * v / top) for i, v in enumerate(last)]
    line = "M" + " L".join(f"{px:.1f} {py:.1f}" for px, py in pts)
    doc.add(f'<g class="pop" style="{d(4.75)}">',
            f'<rect x="{sx}" y="{y}" width="{spark_w}" height="{h}" rx="{r}" fill="#14141B" fill-opacity=".82" stroke="#fff" stroke-opacity=".09"/>',
            doc.t("B8", "Contributions", sx + 16, y + 30, 12.5, INK),
            doc.t("M4", "30 days", sx + spark_w - 16, y + 30, 10.5, DIM, "end"),
            doc.t("B8", str(sum(last)), sx + 16, y + 68, 30, INK),
            f'<path d="{line} L{sx1} {sy1 + 6} L{sx0} {sy1 + 6}Z" fill="url(#spark)"/>',
            f'<path class="spark" pathLength="1" d="{line}" fill="none" stroke="{BLUE}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
            f'<circle class="ping" cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="4" fill="{BLUE}"/>',
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="4" fill="{BLUE}" stroke="#14141B" stroke-width="2"/>',
            "</g>")


TERMINAL = [
    ("cmd", "whoami"),
    ("out", [(f"{NAME} {SURNAME}".lower(), INK), ("  dev + designer", MUTED)]),
    ("cmd", "cat now.md"),
    ("out", [("building  ", DIM), ("a React Native capstone app", INK)]),
    ("out", [("learning  ", DIM), ("PyTorch, TensorFlow, Cisco, UI/UX", INK)]),
    ("out", [("based in  ", DIM), ("the Philippines, GMT+8", INK)]),
    ("cmd", f"open {SITE}"),
    ("out", [("▸ ", BLUE), ("opening portfolio in a new tab", MUTED)]),
    ("prompt",),
]


def terminal_height(fs, lh, tb):
    return tb + fs * 1.8 + (len(TERMINAL) - 1) * lh + fs * 1.1


def terminal(doc, tx0, ty0, tw, fs, lh, tb):
    doc.add(f'<g class="pop" style="{d(1.0)}">',
            window(doc, tx0, ty0, tw, terminal_height(fs, lh, tb), f"{USER} — zsh", tb), "</g>")
    cw = fs * .6
    lx, y, t = tx0 + fs * 1.4, ty0 + tb + fs * 1.8, 1.6
    prompt = [("~", BLUE), (" % ", DIM)]
    plen = sum(len(s) for s, _ in prompt)
    cid = 0
    for step in TERMINAL:
        if step[0] == "cmd":
            cmd = step[1]; cid += 1
            doc.add(doc.spans("M4", prompt, lx, y, fs, "on", d(t)))
            t += .3
            x = lx + plen * cw
            dur = .06 * len(cmd)
            widths = ";".join(f"{i * cw:.1f}" for i in list(range(len(cmd) + 1)) + [len(cmd) + 1])
            doc.defs.append(f'<clipPath id="c{cid}"><rect x="{x:.1f}" y="{y - fs:.1f}" height="{lh}" width="0">'
                            f'<animate attributeName="width" values="{widths}" calcMode="discrete" begin="{t:.2f}s" '
                            f'dur="{dur:.2f}s" fill="freeze"/></rect></clipPath>')
            doc.add(doc.t("M4", cmd, x, y, fs, INK, extra=f' clip-path="url(#c{cid})"'))
            xs = ";".join(f"{x + i * cw:.1f}" for i in list(range(len(cmd) + 1)) + [len(cmd)])
            doc.add(f'<rect x="{x:.1f}" y="{y - fs + 2:.1f}" width="{cw:.1f}" height="{fs + 4}" fill="{BLUE}" opacity="0">'
                    f'<set attributeName="opacity" to=".85" begin="{t - .3:.2f}s"/>'
                    f'<animate attributeName="x" values="{xs}" calcMode="discrete" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
                    f'<set attributeName="opacity" to="0" begin="{t + dur + .2:.2f}s"/></rect>')
            t += dur + .35
        elif step[0] == "out":
            doc.add(doc.spans("M4", step[1], lx, y, fs, "on", d(t)))
            t += .1
        else:
            t += .25
            doc.add(doc.spans("M4", prompt, lx, y, fs, "on", d(t)),
                    f'<g class="on" style="{d(t)}"><rect class="blink" x="{lx + plen * cw:.1f}" y="{y - fs + 2:.1f}" '
                    f'width="{cw:.1f}" height="{fs + 4}" fill="{BLUE}"/></g>')
        y += lh


def cursors(doc, sel, you):
    """the collaborator who made the selection, then wanders; and 'you', who drifts in and hovers"""
    W, H = doc.W, doc.H
    (tx, ty), (ux, uy) = sel, you
    doc.css.append(f".cur{{transform:translate({W + 60}px,{H + 40}px);animation:glide 1s cubic-bezier(.3,.7,.2,1) 2.75s forwards}}"
                   f"@keyframes glide{{to{{transform:translate({tx:.0f}px,{ty:.0f}px)}}}}"
                   f".you{{transform:translate({W + 40}px,{uy + 120}px);animation:you 1.4s cubic-bezier(.3,.7,.2,1) 6.4s forwards}}"
                   f"@keyframes you{{to{{transform:translate({ux:.0f}px,{uy:.0f}px)}}}}"
                   f"@media (prefers-reduced-motion:reduce){{.cur{{transform:translate({tx:.0f}px,{ty:.0f}px)}}"
                   f".you{{transform:translate({ux:.0f}px,{uy:.0f}px)}}.stroke{{stroke-dashoffset:0}}.settle{{opacity:0}}}}")
    doc.add(f'<g class="cur"><g class="wander"><g class="press">{cursor(doc, USER, PURPLE)}</g></g></g>',
            f'<g class="you"><g class="float">{cursor(doc, "you", BLUE)}</g></g>')


def screen_end(doc):
    doc.add("</g>", f'<rect x=".5" y=".5" width="{doc.W - 1}" height="{doc.H - 1}" rx="16" fill="none" stroke="#fff" stroke-opacity=".1"/>')
    doc.css.append(REDUCED)
    return doc.render()


HERO_ALT = (f"{NAME} {SURNAME}, full stack developer and visual designer. "
            "A desktop with a design file of my name, a terminal, a sticky note and widgets.")


def desktop(data):
    doc = Doc(1000, 660, HERO_ALT)
    hero_css(doc, 1)
    wallpaper(doc, [(200, 560, 560), (900, 80, 520), (720, 700, 300)])
    menubar(doc, ("File", "Edit", "View", "Build", "Draw", "Window", "Help"))
    sel = design_window(doc, 24, 48, 648, panel=144, fh=330)["cursor"]
    sticky(doc, 722, 70, 214)
    widgets(doc, data, 24, 490, 150, 234)
    terminal(doc, 436, 372, 540, fs=15.5, lh=24.5, tb=34)
    cursors(doc, sel, (900, 300))
    return screen_end(doc)


def desktop_mobile(data):
    """portrait layout for phones: everything stacked, type sized to stay readable at ~300px wide"""
    W = 400
    fs, lh, ttb = 13, 21, 30
    # lay out top to bottom, then size the screen to fit
    probe = Doc(W, 1, "")
    dw_bottom = design_window(probe, 12, 40, W - 24, panel=0, surname=36, role=15, edited=False)["bottom"]
    ty0 = dw_bottom + 34
    wy = ty0 + terminal_height(fs, lh, ttb) + 14
    H = round(wy + 150 + 12)

    doc = Doc(W, H, HERO_ALT)
    hero_css(doc, .45)
    wallpaper(doc, [(60, H - 140, 520), (W - 40, 60, 420), (W - 70, H + 20, 260)])
    menubar(doc, ("File", "Edit", "View"))
    sel = design_window(doc, 12, 40, W - 24, panel=0, surname=36, role=15, edited=False)["cursor"]
    terminal(doc, 12, ty0, W - 24, fs=fs, lh=lh, tb=ttb)
    sticky(doc, W - 150, dw_bottom - 58, 126)
    widgets(doc, data, 12, wy, 140, W - 24 - 140 - 12)
    cursors(doc, sel, (W - 84, wy + 62))  # 'you' ends up hovering the sparkline
    return screen_end(doc)


# ---------- icons ----------
def simple_icon(slug):
    svg = open(ICONS.format(slug)).read()
    return re.search(r' d="([^"]+)"', svg).group(1)


_si = []


def si_hex(slug):
    if not _si:
        data = json.load(open(pkg("simple-icons") + "data/simple-icons.json"))
        _si.extend(data if isinstance(data, list) else data["icons"])
    for ic in _si:
        if ic.get("slug") == slug or re.sub(r"[^a-z0-9]", "", ic["title"].lower()) == slug:
            return "#" + ic["hex"]
    return INK


def lum(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return .2126 * r + .7152 * g + .0722 * b


FIGMA = ('<path d="M-5 -15h5v10h-5a5 5 0 0 1 0-10z" fill="#F24E1E"/><path d="M0 -15h5a5 5 0 0 1 0 10h-5z" fill="#FF7262"/>'
         '<path d="M-5 -5h5v10h-5a5 5 0 0 1 0-10z" fill="#A259FF"/><circle cx="5" cy="0" r="5" fill="#1ABCFE"/>'
         '<path d="M-5 5h5v5a5 5 0 1 1 -5-5z" fill="#0ACF83"/>')
ADOBE = {"xd": ("Xd", "#FF61F6", "#470137"), "ps": ("Ps", "#31A8FF", "#001E36"), "ai": ("Ai", "#FF9A00", "#330000")}
LINKEDIN_IN = ('<path d="M-9 -3.5h4v13h-4zM-7 -10.5a2.3 2.3 0 1 1 0 4.6a2.3 2.3 0 1 1 0-4.6zM-2.5 -3.5h3.8v1.8'
               'c.6-1.1 2-2.1 4-2.1 4.1 0 4.9 2.7 4.9 6.2v7.2h-4v-6.4c0-1.5 0-3.5-2.2-3.5s-2.5 1.7-2.5 3.4v6.5h-4z" fill="#fff"/>')


def tool_tile(doc, cx, cy, size, slug):
    """app icon centred on cx, cy"""
    r = size * .26
    x, y = cx - size / 2, cy - size / 2
    if slug == "figma":
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" fill="#1E1E1E" stroke="#fff" stroke-opacity=".1"/>'
                f'<g transform="translate({cx} {cy}) scale({size / 42:.3f})">{FIGMA}</g>')
    if slug in ADOBE:
        s, fg, bg = ADOBE[slug]
        return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" fill="{bg}" stroke="{fg}" stroke-opacity=".5" stroke-width="1.5"/>'
                + doc.t("B8", s, cx, cy + size * .17, size * .46, fg, "middle"))
    col = si_hex(slug)
    dark = lum(col) < .22
    fill = "#23232B" if dark else col
    glyph = INK if dark else col
    g = size * .56
    return (f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" fill="{fill}" fill-opacity="{1 if dark else .14}"/>'
            f'<rect x="{x + .5}" y="{y + .5}" width="{size - 1}" height="{size - 1}" rx="{r}" fill="none" '
            f'stroke="{"#fff" if dark else col}" stroke-opacity="{.1 if dark else .35}"/>'
            f'<path transform="translate({cx - g / 2:.2f} {cy - g / 2:.2f}) scale({g / 24:.4f})" d="{simple_icon(slug)}" fill="{glyph}"/>')


# ---------- dock ----------
DOCK = [("site", "Portfolio", f"https://{SITE}"), ("mail", "Email", f"mailto:{EMAIL}"),
        ("in", "LinkedIn", LINKEDIN), ("gh", "Repos", f"https://github.com/{USER}?tab=repositories")]
DOCK_SLOT, DOCK_CAP, DOCK_H = 96, 22, 118


def dock_art(doc, kind, cx, cy, s):
    x, y, r = cx - s / 2, cy - s / 2, s * .24
    if kind == "site":
        return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{r}" fill="url(#gsite)"/>'
                f'<g fill="none" stroke="#fff" stroke-width="2.6"><circle cx="{cx}" cy="{cy}" r="{s * .28}"/>'
                f'<ellipse cx="{cx}" cy="{cy}" rx="{s * .12}" ry="{s * .28}"/><path d="M{cx - s * .28} {cy}h{s * .56}"/></g>')
    if kind == "mail":
        w, h = s * .56, s * .4
        return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{r}" fill="url(#gmail)"/>'
                f'<rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="4" fill="#fff"/>'
                f'<path d="M{cx - w / 2 + 2} {cy - h / 2 + 3}L{cx} {cy + 2}L{cx + w / 2 - 2} {cy - h / 2 + 3}" fill="none" '
                f'stroke="#3B82F6" stroke-width="2.6" stroke-linejoin="round"/>')
    if kind == "in":
        return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{r}" fill="#0A66C2"/>'
                f'<g transform="translate({cx + 1} {cy}) scale({s / 34:.3f})">{LINKEDIN_IN}</g>')
    g = s * .58
    return (f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{r}" fill="#24292F" stroke="#fff" stroke-opacity=".14"/>'
            f'<path transform="translate({cx - g / 2:.2f} {cy - g / 2:.2f}) scale({g / 24:.4f})" d="{simple_icon("github")}" fill="#fff"/>')


def dock(mobile=False):
    """The whole dock is drawn once in shared coordinates; each slice is the same art under a different viewBox,
    so the pieces line up seamlessly when placed side by side. Slices keep the same widths on phones (the README
    sets them), so the phone version drops the labels and lets each icon fill its slot instead."""
    n = len(DOCK)
    DW = DOCK_CAP * 2 + DOCK_SLOT * n
    H, shelf, tile, ty, hop = (100, (4, 92), 76, 48, 8) if mobile else (DOCK_H, (14, DOCK_H - 16), 58, 52, 14)
    files = []
    for i, (kind, label, _) in enumerate(DOCK):
        x0 = 0 if i == 0 else DOCK_CAP + i * DOCK_SLOT
        x1 = DW if i == n - 1 else DOCK_CAP + (i + 1) * DOCK_SLOT
        doc = Doc(x1 - x0, H, label)
        doc.defs += [
            f'<linearGradient id="gsite" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>',
            '<linearGradient id="gmail" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5AC8FA"/><stop offset="1" stop-color="#1E6FF0"/></linearGradient>',
            f'<linearGradient id="shelf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2A2A34"/><stop offset="1" stop-color="#17171E"/></linearGradient>']
        doc.css.append(".nudge{animation:nudge 12s ease-in-out 4s infinite}"
                       f"@keyframes nudge{{0%,10%,100%{{transform:none}}2.5%{{transform:translateY(-{hop}px)}}"
                       f"5%{{transform:none}}7%{{transform:translateY(-{hop / 2:.0f}px)}}}}"
                       ".hop{animation:hop .9s cubic-bezier(.3,1.6,.5,1) both}"
                       "@keyframes hop{0%{opacity:0;transform:translateY(22px)}100%{opacity:1;transform:none}}" + REDUCED)
        sy, sh = shelf
        body = [f'<svg x="0" y="0" width="{x1 - x0}" height="{H}" viewBox="{x0} 0 {x1 - x0} {H}">',
                f'<rect x="1" y="{sy}" width="{DW - 2}" height="{sh}" rx="26" fill="url(#shelf)"/>',
                f'<rect x="1.5" y="{sy + .5}" width="{DW - 3}" height="{sh - 1}" rx="25.5" fill="none" stroke="#fff" stroke-opacity=".12"/>',
                f'<path d="M26 {sy + 1.5}H{DW - 26}" stroke="#fff" stroke-opacity=".18"/>']
        for j, (k2, l2, _) in enumerate(DOCK):
            cx = DOCK_CAP + j * DOCK_SLOT + DOCK_SLOT / 2
            art = dock_art(doc, k2, cx, ty, tile)
            if j == 0:
                art = f'<g class="nudge">{art}</g>'
            body.append(f'<g class="hop" style="{d(.15 + j * .09)}">' + art + "</g>")
            if not mobile:
                body.append(doc.t("B6", l2, cx, 99, 12.5, "#D6D4CF", "middle"))
            if j == 0:
                body.append(f'<circle cx="{cx}" cy="{91 if mobile else 108}" r="{3 if mobile else 2.2}" fill="{INK}"/>')
        body.append("</svg>")
        doc.add(*body)
        files.append((f"dock-{i + 1}{'-m' if mobile else ''}.svg", doc.render(), (x1 - x0) / 10))
    return files


# ---------- applications (tools) ----------
TOOLS = [
    ("Frontend", [("React", "react"), ("Next.js", "nextdotjs"), ("TypeScript", "typescript"), ("Angular", "angular"),
                  ("Vue", "vuedotjs"), ("Svelte", "svelte"), ("Tailwind", "tailwindcss"), ("Bootstrap", "bootstrap")]),
    ("Backend", [("Node.js", "nodedotjs"), ("Express", "express"), ("FastAPI", "fastapi"), ("Django", "django"),
                 ("Spring", "spring"), ("PHP", "php")]),
    ("Languages", [("JavaScript", "javascript"), ("Python", "python"), ("Java", "openjdk"), ("Kotlin", "kotlin"),
                   ("Swift", "swift"), ("Dart", "dart"), ("C", "c"), ("C++", "cplusplus")]),
    ("Data & AI", [("PyTorch", "pytorch"), ("TensorFlow", "tensorflow"), ("PostgreSQL", "postgresql"),
                   ("MongoDB", "mongodb"), ("MySQL", "mysql"), ("Firebase", "firebase"), ("SQLite", "sqlite")]),
    ("Design & Ops", [("Figma", "figma"), ("Adobe XD", "xd"), ("Photoshop", "ps"), ("Illustrator", "ai"),
                      ("Docker", "docker"), ("Git", "git"), ("Linux", "linux"), ("Jenkins", "jenkins")]),
]


def discrete(attr, events, T, begin):
    """SMIL loop that jumps between values at the given times, forever"""
    return (f'<animate attributeName="{attr}" values="{";".join(f"{v:g}" for _, v in events)}" '
            f'keyTimes="{";".join(f"{t / T:.4f}" for t, _ in events)}" calcMode="discrete" '
            f'dur="{T}s" begin="{begin}s" repeatCount="indefinite"/>')


SEARCHES = ["React", "FastAPI", "Python", "PyTorch", "Figma"]


def apps(mobile=False):
    """desktop: Finder with a sidebar and one row of 8 per category. mobile: no sidebar, 4 per row."""
    if mobile:
        W, tb, side, cols, tile, c0, lab, row_h, sw = 400, 48, 0, 4, 52, 58, 44, 88, 128
    else:
        W, tb, side, cols, tile, c0, lab, row_h, sw = 1000, 52, 210, 8, 56, 64, 48, 96, 190
    sec = [c0 + lab + 16 + (math.ceil(len(t) / cols) - 1) * row_h for _, t in TOOLS]
    H = tb + 20 + sum(sec) + 34
    total = sum(len(t) for _, t in TOOLS)
    doc = Doc(W, H, "Applications: the tools I work with. " +
              ". ".join(f"{c}: {', '.join(n for n, _ in t)}" for c, t in TOOLS))
    doc.css.append(POP + REDUCED +
                   ".bob{animation:bob 44s ease-in-out infinite}"
                   "@keyframes bob{0%,5%,100%{transform:none}1.3%{transform:translateY(-9px)}"
                   "2.6%{transform:none}3.6%{transform:translateY(-3px)}}"
                   ".caret{animation:blink 1.05s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
                   "@media (prefers-reduced-motion:reduce){.typing{display:none}}")
    doc.add(window(doc, 0, 0, W, H, None, tb, 14, False))
    # the search box keeps looking things up; each hit lights up in the grid (and the sidebar, when there is one)
    SEG, T, BEGIN = 4, 4 * len(SEARCHES), 2.5
    cats = {label: i for i, (_, tools) in enumerate(TOOLS) for label, _ in tools}
    hits = []  # (label, typed_at, cleared_at)
    caret = [(0, 0)]
    clips = []
    for i, q in enumerate(SEARCHES):
        t0, w = i * SEG, []
        text = q.lower()
        for k in range(1, len(text) + 1):
            w.append((t0 + .35 + k * .11, measure("B5", text[:k], 13)))
        typed = w[-1][0]
        for k in range(len(text) - 1, -1, -1):
            w.append((t0 + 3.1 + (len(text) - k) * .04, measure("B5", text[:k], 13)))
        hits.append((q, typed, t0 + 3.1))
        clips.append([(0, 0)] + w)
        caret += w
    # toolbar
    cy_ = tb / 2
    if mobile:
        doc.add(doc.t("B8", "Applications", 84, cy_ + 5.5, 15))
    else:
        doc.add(f'<path d="M100 {cy_ - 6}l-6 6 6 6M122 {cy_ - 6}l6 6-6 6" fill="none" stroke="{MUTED}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
                doc.t("B8", "Applications", 150, cy_ + 5.5, 15))
    sx, sy = W - (16 if mobile else 20) - sw, cy_ - 13
    doc.add(f'<rect x="{sx}" y="{sy}" width="{sw}" height="26" rx="7" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".06"/>',
            f'<circle cx="{sx + 18}" cy="{cy_ - 1}" r="5" fill="none" stroke="{MUTED}" stroke-width="1.6"/>'
            f'<path d="M{sx + 22} {cy_ + 3}l4 4" stroke="{MUTED}" stroke-width="1.6" stroke-linecap="round"/>',
            '<g class="typing">')
    for i, q in enumerate(SEARCHES):
        doc.defs.append(f'<clipPath id="q{i}"><rect x="{sx + 32}" y="{sy + 1}" height="24" width="0">'
                        f'{discrete("width", clips[i], T, BEGIN)}</rect></clipPath>')
        doc.add(doc.t("B5", q.lower(), sx + 32, cy_ + 4.5, 13, INK, extra=f' clip-path="url(#q{i})"'))
    doc.add(f'<rect class="caret" x="{sx + 33}" y="{cy_ - 8}" width="1.6" height="15" fill="{BLUE}">'
            f'{discrete("x", [(t, sx + 33 + v) for t, v in caret], T, BEGIN)}</rect></g>')
    if not mobile:
        vx = sx - 96
        doc.add(f'<rect x="{vx}" y="{sy}" width="80" height="26" rx="7" fill="#fff" fill-opacity=".06"/>'
                f'<rect x="{vx + 3}" y="{sy + 3}" width="36" height="20" rx="5" fill="#fff" fill-opacity=".12"/>')
        for gx in (0, 7):
            for gy in (0, 7):
                doc.add(f'<rect x="{vx + 15 + gx}" y="{sy + 6 + gy}" width="5" height="5" rx="1" fill="{INK}"/>')
        for ly in (7, 12, 17):
            doc.add(f'<rect x="{vx + 52}" y="{sy + ly}" width="16" height="2" rx="1" fill="{MUTED}"/>')
    # sidebar
    if side:
        doc.add(f'<rect x="0" y="{tb + 1}" width="{side}" height="{H - tb - 1}" fill="{PANEL}"/>',
                f'<line x1="{side + .5}" x2="{side + .5}" y1="{tb + 1}" y2="{H}" stroke="{LINE}"/>',
                doc.t("B6", "Favorites", 18, tb + 32, 11.5, DIM))
        for i, (cat, tools) in enumerate(TOOLS):
            yy = tb + 60 + i * 30
            if i == 0:
                ys = [(0, yy - 19)] + [(k * SEG, tb + 60 + cats[q] * 30 - 19) for k, q in enumerate(SEARCHES)]
                doc.add(f'<rect x="8" y="{yy - 19}" width="{side - 16}" height="28" rx="7" fill="#fff" fill-opacity=".08">'
                        f'{discrete("y", ys, T, BEGIN)}</rect>')
            doc.add(f'<rect x="20" y="{yy - 11}" width="14" height="11" rx="2" fill="none" stroke="{BLUE}" stroke-width="1.5"/>'
                    f'<path d="M20 {yy - 8}h14" stroke="{BLUE}" stroke-width="1.5"/>',
                    doc.t("B5", cat, 44, yy, 13.5, INK),
                    doc.t("M4", str(len(tools)), side - 20, yy, 12, DIM, "end"))
        ly = tb + 60 + len(TOOLS) * 30 + 26
        doc.add(doc.t("B6", "Locations", 18, ly, 11.5, DIM))
        for i, s in enumerate([SITE, f"github / {USER}"]):
            yy = ly + 28 + i * 30
            doc.add(f'<circle cx="27" cy="{yy - 5}" r="6.5" fill="none" stroke="{MUTED}" stroke-width="1.5"/>',
                    doc.t("B5", s, 44, yy, 13.5, "#D6D4CF"))
    # grid
    gx0, gx1 = side + (16 if mobile else 24), W - (16 if mobile else 24)
    col = (gx1 - gx0) / cols
    n, pos, y0 = 0, {}, tb + 20
    for i, (cat, tools) in enumerate(TOOLS):
        tw = measure("B8", cat, 15)
        doc.add(doc.t("B8", cat, gx0, y0 + 16, 15),
                doc.t("M4", f"{len(tools)} apps", gx0 + tw + 10, y0 + 16, 11.5, DIM),
                f'<line x1="{gx0 + tw + 10 + measure("M4", f"{len(tools)} apps", 11.5) + 12:.1f}" x2="{gx1}" '
                f'y1="{y0 + 12}" y2="{y0 + 12}" stroke="{LINE}"/>')
        for j, (label, slug) in enumerate(tools):
            cx = gx0 + col * (j % cols) + col / 2
            cy = y0 + c0 + (j // cols) * row_h
            pos[label] = (cx, cy)
            # every icon hops once in a while, one at a time, like apps launching
            hop = 3 + (n * 11 % total) * 44 / total
            doc.add(f'<g class="pop" style="{d(.2 + n * .035)}"><g class="bob" style="{d(hop)}">',
                    tool_tile(doc, cx, cy, tile, slug), "</g>",
                    doc.t("B5", label, cx, cy + lab, 12.5, "#D6D4CF", "middle"), "</g>")
            n += 1
        y0 += sec[i]
    ring = tile + 12
    for q, on, off in hits:
        cx, cy = pos[q]
        doc.add(f'<rect x="{cx - ring / 2}" y="{cy - ring / 2}" width="{ring}" height="{ring}" rx="{ring * .28:.0f}" fill="{BLUE}" fill-opacity=".1" '
                f'stroke="{BLUE}" stroke-width="2" opacity="0" class="typing">{discrete("opacity", [(0, 0), (on, 1), (off, 0)], T, BEGIN)}</rect>')
    # status bar
    doc.add(f'<line x1="{side + 1}" x2="{W}" y1="{H - 30.5}" y2="{H - 30.5}" stroke="{LINE}"/>',
            doc.t("B5", f"{total} items, still collecting", (side + W) / 2, H - 11, 12, DIM, "middle"))
    return doc.render()


# ---------- activity monitor (contributions) ----------
def streaks(days):
    counts = [c for _, c in days]
    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)
    cur, i = 0, len(counts) - 1
    if counts and counts[-1] == 0:
        i -= 1  # today not counted yet
    while i >= 0 and counts[i]:
        cur += 1; i -= 1
    return cur, longest


def ago(iso):
    t = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    s = (NOW - t).total_seconds()
    if s < 3600: return f"{max(1, int(s // 60))}m ago"
    if s < 86400: return f"{int(s // 3600)}h ago"
    if s < 86400 * 60: return f"{int(s // 86400)}d ago"
    return f"{int(s // (86400 * 30))}mo ago"


def shade(hexc, f):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02X%02X%02X" % (int(r * f), int(g * f), int(b * f))


def activity(data, mobile=False):
    """desktop: skyline across the top, four stat tiles, process table beside languages.
    mobile: the same pieces stacked, with the table cut down to name, language and last push."""
    days = sorted((dt.date.fromisoformat(k), v) for k, v in data["contrib"].items())
    days = [(k, v) for k, v in days if k <= NOW.date()]
    total = sum(v for _, v in days)
    cur, longest = streaks(days)
    by_wd = [0] * 7
    for k, v in days:
        by_wd[k.weekday()] += v
    busiest = max(range(7), key=lambda i: by_wd[i])
    best_day, best = max(days, key=lambda kv: kv[1])
    active = sum(1 for _, v in days if v)
    peak = max(best, 1)
    repos = [r for r in data["repos"] if r["lang"]][:6]
    langs = {}
    for r in data["repos"]:
        if r["lang"]:
            langs[r["lang"]] = langs.get(r["lang"], 0) + 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top = ranked[:5]
    if len(ranked) > 5:
        top.append(("Other", sum(v for _, v in ranked[5:])))
    nlang = sum(v for _, v in top)

    if mobile:
        W, tb, sky_h = 400, 44, 312
        # stats (2 rows) + repo list + languages (3 legend rows) + footer, stacked under the skyline
        H = tb + sky_h + 12 + 2 * 84 - 10 + 20 + 34 + len(repos) * 32 + 22 + 72 + 2 * 25 + 18 + 30
        WV, DV, O, hmax = (6.1, -1.55), (4.3, 2.4), (23.3, 300), 105
        glint = (-120, 90, 640)
    else:
        W, H, tb, sky_h = 1000, 862, 48, 392
        WV, DV, O, hmax = (14.2, -3.6), (9.5, 5.2), (90, 402), 150
        glint = (-260, 200, 1500)
    k = 1 if not mobile else .65  # scale for small marks: beacon, labels
    doc = Doc(W, H, f"Activity monitor: {total} contributions in the last year, "
                    f"busiest on {dt.date(2024, 1, 1 + busiest).strftime('%A')}s, longest streak {longest} days, best day {best} contributions.")
    bar_w = (W - 32) if mobile else 314
    doc.css.append(POP + REDUCED +
                   ".glint{animation:glint 9s ease-in-out 3s infinite}"
                   f"@keyframes glint{{0%{{transform:none}}40%,100%{{transform:translateX({glint[2]}px)}}}}"
                   ".shim{animation:shim 7s ease-in-out 4s infinite}"
                   f"@keyframes shim{{0%{{transform:none}}35%,100%{{transform:translateX({bar_w + 100}px)}}}}"
                   ".ping{transform-box:fill-box;transform-origin:center;animation:ping 2.2s ease-out infinite}"
                   "@keyframes ping{from{opacity:.8;transform:scale(1)}to{opacity:0;transform:scale(3)}}")
    doc.defs.append('<linearGradient id="sheen" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                    '<stop offset=".5" stop-color="#fff" stop-opacity=".3"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')
    doc.defs.append('<linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#15141F"/>'
                    f'<stop offset="1" stop-color="{WIN}"/></linearGradient>'
                    f'<radialGradient id="glow" cx="{W * .72:.0f}" cy="{tb + sky_h * .45:.0f}" r="{W * .42:.0f}" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{PURPLE}" stop-opacity=".16"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>')
    doc.add(window(doc, 0, 0, W, H, None, tb, 14, False))
    doc.add(doc.spans("B6", [("Activity Monitor", INK), (("   last 12 months" if mobile else f"   {USER} · last 12 months"), MUTED)],
                      82 if mobile else 92, tb / 2 + 5, 13.5))
    if not mobile:
        tabs = ["Contributions", "Repos", "Languages"]
        tx = W - 20 - sum(measure("B6", s, 12.5) + 26 for s in tabs)
        doc.add(f'<rect x="{tx - 3}" y="11" width="{W - 20 - tx + 6:.1f}" height="26" rx="7" fill="#fff" fill-opacity=".06"/>')
        for i, s in enumerate(tabs):
            w = measure("B6", s, 12.5) + 26
            if i == 0:
                doc.add(f'<rect x="{tx}" y="14" width="{w:.1f}" height="20" rx="5" fill="#fff" fill-opacity=".13"/>')
            doc.add(doc.t("B6", s, tx + w / 2, 28.5, 12.5, INK if i == 0 else MUTED, "middle"))
            tx += w
    doc.add(f'<rect x="1" y="{tb + 1}" width="{W - 2}" height="{sky_h}" fill="url(#sky)"/>',
            f'<rect x="1" y="{tb + 1}" width="{W - 2}" height="{sky_h}" fill="url(#glow)"/>')

    # isometric skyline: week axis runs up-right, weekday axis down-right
    P = lambda w, dd: (O[0] + w * WV[0] + dd * DV[0], O[1] + w * WV[1] + dd * DV[1])
    start = days[0][0] - dt.timedelta(days=(days[0][0].weekday() + 1) % 7)
    grid = {}
    for day, c in days:
        off = (day - start).days
        grid[(off // 7, off % 7)] = (day, c)
    weeks = max(w for w, _ in grid) + 1
    ramp = ["#4A2C8C", "#7B3FE4", "#5A6CFF", "#0D99FF"]
    nz = sorted(c for _, c in days if c)
    cuts = [nz[int(len(nz) * q)] for q in (.25, .5, .75)] if nz else [1, 1, 1]
    cells = sorted(grid, key=lambda wd: (wd[1] - wd[0], wd[0]))
    poly = lambda pts: "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"
    up = lambda p, hh: (p[0], p[1] - hh)
    height = lambda c: 0 if not c else hmax * (.04 + math.sqrt(c / peak))
    lit = []  # every bar face, so a light can sweep across the skyline later
    for (w, dd) in cells:
        day, c = grid[(w, dd)]
        A, B, C, D = P(w, dd), P(w + 1, dd), P(w + 1, dd + 1), P(w, dd + 1)
        if not c:
            doc.add(f'<path d="{poly([A, B, C, D])}" fill="#23222D" stroke="#15141C" stroke-width="{.8 * k:.2f}"/>')
            continue
        lvl = sum(c > q for q in cuts)
        h = height(c)
        faces = [([A, D, up(D, h), up(A, h)], [A, D, D, A], .62),
                 ([D, C, up(C, h), up(D, h)], [D, C, C, D], .45),
                 ([up(A, h), up(B, h), up(C, h), up(D, h)], [A, B, C, D], 1)]
        begin = .3 + w * .022
        for full, flat, f in faces:
            lit.append(poly(full))
            col = shade(ramp[lvl], f)
            doc.add(f'<path d="{poly(full)}" fill="{col}" stroke="#0B0A12" stroke-opacity=".55" stroke-width="{.7 * k:.2f}" stroke-linejoin="round">'
                    f'<animate attributeName="d" values="{poly(flat)};{poly(full)}" dur=".7s" begin="{begin:.2f}s" '
                    f'calcMode="spline" keySplines=".2 .8 .3 1" fill="freeze"/></path>')
    # idle: a light sweeps across the bars every few seconds
    doc.defs.append(f'<clipPath id="lit"><path d="{"".join(lit)}"/></clipPath>')
    doc.add(f'<g clip-path="url(#lit)"><g class="glint"><rect x="{glint[0]}" y="{tb}" width="{glint[1]}" height="{sky_h}" '
            f'fill="url(#sheen)" transform="skewX(-20)"/></g></g>')
    # and a beacon on today
    tw_, td_ = max(grid, key=lambda wd: grid[wd][0])
    corners = [P(tw_, td_), P(tw_ + 1, td_), P(tw_ + 1, td_ + 1), P(tw_, td_ + 1)]
    bx_ = sum(p[0] for p in corners) / 4
    by_ = sum(p[1] for p in corners) / 4 - height(grid[(tw_, td_)][1])
    doc.add(f'<ellipse class="ping" cx="{bx_:.1f}" cy="{by_:.1f}" rx="{7 * k:.1f}" ry="{3.8 * k:.1f}" fill="none" stroke="{GREEN}" stroke-width="1.5"/>',
            f'<ellipse cx="{bx_:.1f}" cy="{by_:.1f}" rx="{4.5 * k:.1f}" ry="{2.6 * k:.1f}" fill="{GREEN}"/>',
            f'<path d="M{bx_:.1f} {by_ - 4 * k:.1f}V{by_ - 26 * k:.1f}" stroke="{GREEN}" stroke-opacity=".6"/>',
            doc.t("M4", "today", bx_ + 5, by_ - 20 * k, 10.5, GREEN)
            if bx_ + 5 + measure("M4", "today", 10.5) < W - 10 else
            doc.t("M4", "today", bx_ - 5, by_ - 20 * k, 10.5, GREEN, "end"))
    # month labels along the front edge
    ang = math.degrees(math.atan2(WV[1], WV[0]))
    last = None
    for w in range(weeks):
        day = grid.get((w, 0), grid.get((w, 6)))
        if not day:
            continue
        m = day[0].month
        nxt = grid.get((w + (3 if mobile else 2), 0))
        if m != last and w < weeks - 1 and not (nxt and nxt[0].month != m):
            x, y = P(w + .2, 7)
            ox, oy = (3, 14) if mobile else (4, 18)
            doc.add(doc.t("M4", day[0].strftime("%b"), x + ox, y + oy, 10 if mobile else 11, DIM,
                          extra=f' transform="rotate({ang:.1f} {x + ox:.1f} {y + oy:.1f})"'))
        last = m
    # headline
    hx, hy, hs = (20, tb + 56, 48) if mobile else (40, tb + 86, 68)
    doc.add(f'<g class="rise" style="{d(.2)}">', doc.t("B8", f"{total:,}", hx, hy, hs, INK), "</g>",
            f'<g class="rise" style="{d(.35)}">',
            doc.t("B5", "contributions in the last year", hx + 3, hy + hs * .44, 14 if mobile else 16, MUTED), "</g>")
    # legend
    lx, ly = W - (18 if mobile else 40), tb + sky_h - 20
    doc.add(doc.t("M4", "more", lx, ly, 11, DIM, "end"))
    lx -= measure("M4", "more", 11) + 8
    for col in reversed(["#23222D"] + ramp):
        lx -= 13
        doc.add(f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" rx="2.5" fill="{col}"/>')
    doc.add(doc.t("M4", "less", lx - 8, ly, 11, DIM, "end"))

    # stat tiles: one row of four, or two by two
    stats = [("busiest day of week", dt.date(2024, 1, 1 + busiest).strftime("%a"), f"{by_wd[busiest]} total"),
             ("longest streak", f"{longest}", "day" if longest == 1 else "days"),
             ("best day", f"{best}", best_day.strftime("on %b %-d")),
             ("active days", f"{active}", f"of {len(days)}")]
    per_row, gap, th, vs = (2, 10, 74, 28) if mobile else (4, 12, 84, 34)
    pad = 12 if mobile else 20
    sy = tb + sky_h + (12 if mobile else 14)
    cw_ = (W - 2 * pad - (per_row - 1) * gap) / per_row
    for i, (lbl, v, sub) in enumerate(stats):
        x = pad + (i % per_row) * (cw_ + gap)
        y = sy + (i // per_row) * (th + gap)
        doc.add(f'<g class="pop" style="{d(.6 + i * .08)}">',
                f'<rect x="{x:.1f}" y="{y}" width="{cw_:.1f}" height="{th}" rx="10" fill="#fff" fill-opacity=".035" stroke="#fff" stroke-opacity=".07"/>',
                doc.t("M4", lbl.upper(), x + 14, y + (20 if mobile else 24), 9.5 if mobile else 10.5, DIM),
                doc.t("B8", v, x + 14, y + th - (18 if mobile else 20), vs, INK),
                doc.t("B5", sub, x + 20 + measure("B8", v, vs), y + th - (18 if mobile else 20), 12.5 if mobile else 14, MUTED), "</g>")
    sy_end = sy + (len(stats) // per_row) * (th + gap) - gap

    # processes = recently pushed repos
    py0 = sy_end + (20 if mobile else 24)
    doc.add(f'<line x1="0" x2="{W}" y1="{py0 - 12.5}" y2="{py0 - 12.5}" stroke="{LINE}"/>')
    if mobile:
        doc.add(doc.t("B8", "Recently pushed", 16, py0 + 20, 14), doc.t("M4", "last push", W - 18, py0 + 20, 11, DIM, "end"))
        rx0, rw, ry0 = 8, W - 16, py0 + 34
    else:
        cols = [("PID", 24), ("Process", 88), ("Language", 318), ("Size", 488), ("Last push", 606)]
        doc.add(f'<rect x="12" y="{py0}" width="616" height="30" rx="6" fill="#fff" fill-opacity=".04"/>')
        for label, x in cols:
            doc.add(doc.t("B6", label, x, py0 + 20, 12, MUTED, "end" if label in ("Size", "Last push") else None))
        rx0, rw, ry0 = 12, 616, py0 + 36
    for i, r in enumerate(repos):
        y = ry0 + i * 32
        if i == 0:
            doc.add(f'<rect x="{rx0}" y="{y}" width="{rw}" height="30" rx="6" fill="{BLUE}" fill-opacity=".25"/>',
                    f'<circle class="ping" cx="{rx0 + rw - 11}" cy="{y + 15}" r="3.2" fill="{GREEN}"/>'
                    f'<circle cx="{rx0 + rw - 11}" cy="{y + 15}" r="3.2" fill="{GREEN}"/>')
        elif i % 2 == 0:
            doc.add(f'<rect x="{rx0}" y="{y}" width="{rw}" height="30" rx="6" fill="#fff" fill-opacity=".02"/>')
        lang = r["lang"]
        when = ago(r["pushed"])
        if mobile:
            name = r["name"] if measure("B6", r["name"], 13.5) < 170 else r["name"][:16] + "…"
            doc.add(doc.t("B6", name, 20, y + 20, 13.5, INK),
                    f'<circle cx="212" cy="{y + 15}" r="4" fill="{LANG_COLORS.get(lang, MUTED)}"/>',
                    doc.t("B5", lang, 222, y + 19.5, 12.5, "#D6D4CF"),
                    doc.t("M4", when, W - 30, y + 19.5, 12, INK if i == 0 else MUTED, "end"))
        else:
            size = f'{r["size"] / 1024:.1f} MB' if r["size"] >= 1024 else f'{r["size"]} KB'
            name = r["name"] if measure("B6", r["name"], 14) < 210 else r["name"][:20] + "…"
            doc.add(doc.t("M4", str(r["id"] % 100000), 24, y + 20, 12.5, DIM),
                    doc.t("B6", name, 88, y + 20, 14, INK),
                    f'<circle cx="323" cy="{y + 15}" r="4.5" fill="{LANG_COLORS.get(lang, MUTED)}"/>',
                    doc.t("B5", lang, 334, y + 20, 13.5, "#D6D4CF"),
                    doc.t("M4", size, 488, y + 20, 12.5, MUTED, "end"),
                    doc.t("M4", when, 606, y + 20, 12.5, INK if i == 0 else MUTED, "end"))

    # languages by repo: beside the table, or under it
    if mobile:
        ly0 = ry0 + len(repos) * 32 + 22
        doc.add(f'<line x1="0" x2="{W}" y1="{ly0 - 12.5}" y2="{ly0 - 12.5}" stroke="{LINE}"/>')
        lx0, lx1 = 16, W - 16
    else:
        ly0 = py0
        doc.add(f'<line x1="640.5" x2="640.5" y1="{py0 - 12}" y2="{H - 30}" stroke="{LINE}"/>')
        lx0, lx1 = 662, W - 24
    doc.add(doc.t("B8", "Languages", lx0, ly0 + 20, 15 if not mobile else 14), doc.t("M4", "by repo", lx1, ly0 + 20, 11, DIM, "end"))
    x = lx0
    doc.defs.append(f'<clipPath id="bar"><rect x="{lx0}" y="{ly0 + 34}" width="{lx1 - lx0}" height="10" rx="5"/></clipPath>')
    doc.add('<g clip-path="url(#bar)">')
    for lang, v in top:
        w = (lx1 - lx0) * v / nlang
        doc.add(f'<rect x="{x:.1f}" y="{ly0 + 34}" width="{max(w - 2, 1):.1f}" height="10" fill="{LANG_COLORS.get(lang, DIM)}"/>')
        x += w
    doc.add(f'<rect class="shim" x="{lx0 - 90}" y="{ly0 + 34}" width="80" height="10" fill="url(#sheen)"/>', "</g>")
    for i, (lang, v) in enumerate(top):
        if mobile:  # two columns of three
            half = (lx1 - lx0 - 24) / 2
            cx_, y = lx0 + (i // 3) * (half + 24), ly0 + 72 + (i % 3) * 25
            right = cx_ + half
        else:
            cx_, y, right = lx0, ly0 + 76 + i * 29, lx1
        doc.add(f'<circle cx="{cx_ + 5}" cy="{y - 4.5}" r="4.5" fill="{LANG_COLORS.get(lang, DIM)}"/>',
                doc.t("B5", lang, cx_ + 18, y, 13 if mobile else 13.5, "#D6D4CF"),
                doc.t("M4", f"{100 * v / nlang:.0f}%", right, y, 12 if mobile else 12.5, MUTED, "end"))

    foot = (f"{len(data['repos'])} repos · refreshed daily · {NOW.strftime('%-d %b %Y')}" if mobile else
            f"{len(data['repos'])} repos · refreshed daily at 00:00 GMT+8 · last refresh {NOW.strftime('%-d %b %Y')}")
    doc.add(f'<line x1="0" x2="{W}" y1="{H - 30.5}" y2="{H - 30.5}" stroke="{LINE}"/>',
            doc.t("B5", foot, W / 2, H - 11, 12, DIM, "middle"))
    return doc.render()


# ---------- status bar ----------
def statusbar(mobile=False):
    W, H = (400, 44) if mobile else (1000, 48)
    doc = Doc(W, H, "Every graphic on this page is an SVG drawn by scripts/build.py")
    doc.css.append(".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2s ease-out infinite}"
                   "@keyframes pulse{from{opacity:.6;transform:scale(1)}to{opacity:0;transform:scale(3)}}" + REDUCED)
    cy = H / 2
    doc.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{H / 2}" fill="{WIN}" stroke="#fff" stroke-opacity=".1"/>',
            f'<circle class="pulse" cx="24" cy="{cy}" r="4.5" fill="{GREEN}"/><circle cx="24" cy="{cy}" r="4.5" fill="{GREEN}"/>',
            doc.t("B6", "all systems nominal", 40, cy + 5, 13.5, INK))
    if mobile:
        doc.add(doc.t("M4", "scripts/build.py", W - 20, cy + 4.5, 12, BLUE, "end"))
    else:
        doc.add(doc.spans("M4", [("every pixel here is an SVG drawn by ", MUTED), ("scripts/build.py", BLUE)],
                          W / 2 - measure("M4", "every pixel here is an SVG drawn by scripts/build.py", 12.5) / 2 + 40, cy + 4.5, 12.5),
                doc.t("M4", f"built {NOW.strftime('%-d %b %Y')}", W - 24, cy + 4.5, 12.5, DIM, "end"))
    return doc.render()


if __name__ == "__main__":
    data = load_data()
    out = {"desktop.svg": desktop(data), "desktop-m.svg": desktop_mobile(data),
           "apps.svg": apps(), "apps-m.svg": apps(mobile=True),
           "activity.svg": activity(data), "activity-m.svg": activity(data, mobile=True),
           "statusbar.svg": statusbar(), "statusbar-m.svg": statusbar(mobile=True)}
    for fn, svg, pct in dock() + dock(mobile=True):
        out[fn] = svg
        print(f"{fn} width={pct:.1f}%")
    for fn, svg in out.items():
        open(os.path.join(OUT, fn), "w").write(svg)
        print(fn, len(svg) // 1024, "KB")
