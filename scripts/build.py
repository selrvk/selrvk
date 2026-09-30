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
def desktop():
    W, H = 1000, 660
    doc = Doc(W, H, f"{NAME} {SURNAME}, full stack developer and visual designer. "
                    "A desktop with a design file of my name, a terminal and a sticky note.")
    doc.defs += [
        SHADOW,
        f'<radialGradient id="o1" cx="200" cy="560" r="560" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{PURPLE}" stop-opacity=".55"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="o2" cx="900" cy="80" r="520" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{BLUE}" stop-opacity=".45"/><stop offset="1" stop-color="{BLUE}" stop-opacity="0"/></radialGradient>',
        '<radialGradient id="o3" cx="720" cy="700" r="300" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="#FF7262" stop-opacity=".28"/><stop offset="1" stop-color="#FF7262" stop-opacity="0"/></radialGradient>',
        '<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".9" '
        'numOctaves="2" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .5 0"/></filter>',
        '<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#2A2A34"/></pattern>',
        f'<linearGradient id="grad" x1="0" x2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>',
        '<linearGradient id="note" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#FFE98A"/><stop offset="1" stop-color="#FFD84D"/></linearGradient>',
        f'<clipPath id="screen"><rect width="{W}" height="{H}" rx="16"/></clipPath>',
    ]

    # --- wallpaper
    doc.add('<g clip-path="url(#screen)">',
            f'<rect width="{W}" height="{H}" fill="{BG0}"/>',
            f'<rect width="{W}" height="{H}" fill="url(#o1)"/><rect width="{W}" height="{H}" fill="url(#o2)"/>',
            f'<rect width="{W}" height="{H}" fill="url(#o3)"/>',
            f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity=".07"/>')

    # --- menubar
    mb = 28
    doc.add(f'<rect width="{W}" height="{mb}" fill="#0E0E14" fill-opacity=".72"/>',
            f'<line x1="0" x2="{W}" y1="{mb - .5}" y2="{mb - .5}" stroke="#fff" stroke-opacity=".07"/>',
            f'<path d="M22 7.5l6.5 6.5-6.5 6.5-6.5-6.5z" fill="{PURPLE}"/>',
            doc.t("B8", USER, 38, 19, 13.5))
    x = 38 + measure("B8", USER, 13.5) + 22
    for m in ("File", "Edit", "View", "Build", "Draw", "Window", "Help"):
        doc.add(doc.t("B5", m, x, 19, 13.5, "#D6D4CF"))
        x += measure("B5", m, 13.5) + 20
    date = NOW.strftime("%a %-d %b")
    rx = W - 18
    doc.add(doc.t("B6", date, rx, 19, 13.5, INK, "end"))
    rx -= measure("B6", date, 13.5) + 16
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
    @keyframes draw{{to{{stroke-dashoffset:0}}}}
    @keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
    @keyframes out{{to{{opacity:0}}}}
    @keyframes press{{50%{{transform:scale(.86)}}}}
    @keyframes drop{{from{{opacity:0;transform:translateY(-40px) rotate(-8deg)}}to{{opacity:1;transform:none}}}}
    @keyframes blink{{50%{{opacity:0}}}}
    """)

    # --- design window
    dx, dy, dw, dh, tb = 24, 48, 648, 424, 38
    panel = 144
    doc.add(f'<g class="pop" style="{d(.15)}">', window(doc, dx, dy, dw, dh, None, tb))
    doc.add(doc.spans("B6", [(f"{NAME.lower()}.fig", INK), ("  —  Edited", MUTED)],
                      dx + dw / 2 - measure("B6", f"{NAME.lower()}.fig  —  Edited", 13) / 2, dy + 23.5, 13))
    # avatars + share
    sx = dx + dw - 16 - 58
    doc.add(f'<rect x="{sx}" y="{dy + 8}" width="58" height="22" rx="6" fill="{BLUE}"/>',
            doc.t("B6", "Share", sx + 29, dy + 23, 12.5, "#fff", "middle"),
            f'<circle cx="{sx - 18}" cy="{dy + 19}" r="11" fill="{BLUE}" stroke="{TB}" stroke-width="2"/>',
            doc.t("B8", "Y", sx - 18, dy + 23.5, 12, "#fff", "middle"),
            f'<circle cx="{sx - 36}" cy="{dy + 19}" r="11" fill="{PURPLE}" stroke="{TB}" stroke-width="2"/>',
            doc.t("B8", "C", sx - 36, dy + 23.5, 12, "#fff", "middle"))
    by = dy + tb + 1
    # layers panel
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
    cx0 = dx + panel + 1
    doc.add(f'<rect x="{cx0}" y="{by}" width="{dx + dw - cx0}" height="{dh - tb - 1}" fill="{CANVAS}"/>',
            f'<rect x="{cx0}" y="{by}" width="{dx + dw - cx0}" height="{dh - tb - 1}" fill="url(#dots)"/>')
    fx, fy, fw, fh = cx0 + 20, by + 32, dx + dw - cx0 - 40, 330
    doc.add(doc.t("B5", "hello", fx, fy - 8, 12, MUTED),
            doc.t("M4", f"{fw} × {fh}", fx + fw, fy - 8, 11, DIM, "end"),
            f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" fill="#1A1A21" stroke="{LINE}"/>',
            "</g>")

    # the name, drawn as a vector
    B8 = FONTS["B8"][0]
    x0 = fx + 28
    unit = glyph_run(NAME, B8, 100, 0, 0)[2] / 100
    size = (fw - 60) / unit
    base = fy + 36 + size * .74
    glyphs, k, _ = glyph_run(NAME, B8, size, x0, base)
    pts = [p for g in glyphs for p in g["anchors"]] + [p for g in glyphs for h in g["handles"] for p in h]
    bx0, bx1 = min(p[0] for p in pts) - 8, max(p[0] for p in pts) + 8
    by0, by1 = min(p[1] for p in pts) - 8, max(p[1] for p in pts) + 8
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
    doc.add(f'<g class="rise" style="{d(4.2)}">', doc.t("B8", SURNAME, x0 + 2, by1 + 70, 46, INK), "</g>",
            f'<g class="rise" style="{d(4.4)}">',
            doc.spans("B5", [("Full stack developer ", INK), ("& visual designer", MUTED)], x0 + 3, by1 + 102, 17),
            "</g>")
    # comment pin
    px_, py_ = x0 + 2, fy + fh - 34
    doc.add(f'<g class="pop" style="{d(5.1)}">',
            f'<path d="M{px_} {py_ + 26}V{py_ + 13}a13 13 0 1 1 13 13z" fill="{PURPLE}"/>',
            doc.t("B8", "C", px_ + 13, py_ + 17.5, 12, "#fff", "middle"),
            f'<rect x="{px_ + 34}" y="{py_}" width="{measure("B5", "ship it.", 13.5) + 22:.0f}" height="26" rx="8" fill="{TB}" stroke="{LINE}"/>',
            doc.t("B5", "ship it.", px_ + 45, py_ + 17.5, 13.5), "</g>")
    # the multiplayer cursor that "made" the selection
    tx, ty = bx1 + 6, by1 + 8
    doc.css.append(f".cur{{transform:translate(1060px,700px);animation:glide 1s cubic-bezier(.3,.7,.2,1) 2.75s forwards}}"
                   f"@keyframes glide{{to{{transform:translate({tx:.0f}px,{ty:.0f}px)}}}}"
                   f"@media (prefers-reduced-motion:reduce){{.cur{{transform:translate({tx:.0f}px,{ty:.0f}px)}}"
                   ".stroke{stroke-dashoffset:0}.settle{opacity:0}}")

    # --- sticky note
    nx, ny, nw, nh = 722, 70, 214, 214
    doc.add(f'<g class="drop" style="{d(2.3)}"><g transform="rotate(4 {nx + nw / 2} {ny + nh / 2})">',
            f'<path d="M{nx + 8} {ny + nh}h{nw - 16}l6 8h{-nw + 4}z" fill="#000" opacity=".25"/>',
            f'<rect x="{nx}" y="{ny}" width="{nw}" height="{nh}" rx="3" fill="url(#note)"/>',
            f'<path d="M{nx + nw - 30} {ny + nh}l30 -30v27a3 3 0 0 1 -3 3z" fill="#E8BF2C"/>',
            f'<rect x="{nx + nw / 2 - 40}" y="{ny - 11}" width="80" height="24" fill="#fff" opacity=".45" transform="rotate(-3 {nx + nw / 2} {ny})"/>')
    for i, (s, size) in enumerate([("open to", 32), ("open source +", 32), ("system design", 32), ("collabs!", 32)]):
        doc.add(doc.t("C6", s, nx + 20, ny + 50 + i * 38, size, "#2E2600"))
    uw = measure("C6", "collabs!", 32)
    doc.add(f'<path d="M{nx + 18} {ny + 172}q{uw / 2} 7 {uw + 6} -2" fill="none" stroke="#C0392B" stroke-width="2.4" stroke-linecap="round"/>',
            doc.t("C6", "— c.", nx + nw - 22, ny + nh - 16, 24, "#6B5A00", "end"), "</g></g>")

    # --- wallpaper type
    doc.add(f'<g class="rise" style="{d(4.7)}">', doc.t("B8", "I write the code", 32, 532, 31), "</g>",
            f'<g class="rise" style="{d(4.85)}">', doc.t("B8", "and I draw the thing", 32, 570, 31), "</g>",
            f'<g class="rise" style="{d(5.0)}">', doc.t("B8", "it becomes.", 32, 608, 31, "url(#grad)"), "</g>",
            f'<g class="rise" style="{d(5.3)}">', doc.t("M4", f"{SITE}  ↗", 33, 640, 12, MUTED), "</g>")

    # --- terminal
    tx0, ty0, tw, th, ttb = 436, 372, 540, 272, 34
    doc.add(f'<g class="pop" style="{d(1.0)}">', window(doc, tx0, ty0, tw, th, f"{USER} — zsh", ttb), "</g>")
    fs, lh, cw = 15.5, 24.5, 15.5 * .6
    lx, y, t = tx0 + 22, ty0 + ttb + 28, 1.6
    prompt = [("~", BLUE), (" % ", DIM)]
    plen = sum(len(s) for s, _ in prompt)
    script = [
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
    cid = 0
    for step in script:
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

    # --- cursors on top of everything
    doc.add(f'<g class="cur"><g class="press">{cursor(doc, USER, PURPLE)}</g></g>')
    doc.css.append(".you{transform:translate(1040px,420px);animation:you 1.4s cubic-bezier(.3,.7,.2,1) 6.4s forwards}"
                   "@keyframes you{to{transform:translate(900px,300px)}}"
                   "@media (prefers-reduced-motion:reduce){.you{transform:translate(900px,300px)}}")
    doc.add(f'<g class="you">{cursor(doc, "you", BLUE)}</g>')

    doc.add("</g>",
            f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="16" fill="none" stroke="#fff" stroke-opacity=".1"/>')
    doc.css.append(REDUCED)
    return doc.render()


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


def dock():
    """The whole dock is drawn once in shared coordinates; each slice is the same art under a different viewBox,
    so the pieces line up seamlessly when placed side by side."""
    n = len(DOCK)
    DW = DOCK_CAP * 2 + DOCK_SLOT * n
    files = []
    for i, (kind, label, _) in enumerate(DOCK):
        x0 = 0 if i == 0 else DOCK_CAP + i * DOCK_SLOT
        x1 = DW if i == n - 1 else DOCK_CAP + (i + 1) * DOCK_SLOT
        doc = Doc(x1 - x0, DOCK_H, label)
        doc.defs += [
            f'<linearGradient id="gsite" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{BLUE}"/></linearGradient>',
            '<linearGradient id="gmail" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5AC8FA"/><stop offset="1" stop-color="#1E6FF0"/></linearGradient>',
            f'<linearGradient id="shelf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2A2A34"/><stop offset="1" stop-color="#17171E"/></linearGradient>']
        doc.css.append(".hop{animation:hop .9s cubic-bezier(.3,1.6,.5,1) both}"
                       "@keyframes hop{0%{opacity:0;transform:translateY(22px)}100%{opacity:1;transform:none}}" + REDUCED)
        body = [f'<svg x="0" y="0" width="{x1 - x0}" height="{DOCK_H}" viewBox="{x0} 0 {x1 - x0} {DOCK_H}">',
                f'<rect x="1" y="14" width="{DW - 2}" height="{DOCK_H - 16}" rx="26" fill="url(#shelf)"/>',
                f'<rect x="1.5" y="14.5" width="{DW - 3}" height="{DOCK_H - 17}" rx="25.5" fill="none" stroke="#fff" stroke-opacity=".12"/>',
                f'<path d="M26 15.5H{DW - 26}" stroke="#fff" stroke-opacity=".18"/>']
        for j, (k2, l2, _) in enumerate(DOCK):
            cx = DOCK_CAP + j * DOCK_SLOT + DOCK_SLOT / 2
            body.append(f'<g class="hop" style="{d(.15 + j * .09)}">' + dock_art(doc, k2, cx, 52, 58) + "</g>")
            body.append(doc.t("B6", l2, cx, 99, 12.5, "#D6D4CF", "middle"))
            if j == 0:
                body.append(f'<circle cx="{cx}" cy="108" r="2.2" fill="{INK}"/>')
        body.append("</svg>")
        doc.add(*body)
        files.append((f"dock-{i + 1}.svg", doc.render(), (x1 - x0) / 10))
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


def apps():
    W, tb, side, sec = 1000, 52, 210, 128
    H = tb + 20 + sec * len(TOOLS) + 34
    total = sum(len(t) for _, t in TOOLS)
    doc = Doc(W, H, "Applications: the tools I work with. " +
              ". ".join(f"{c}: {', '.join(n for n, _ in t)}" for c, t in TOOLS))
    doc.css.append(POP + REDUCED)
    doc.add(window(doc, 0, 0, W, H, None, tb, 14, False))
    # toolbar
    doc.add(f'<path d="M100 20l-6 6 6 6M122 20l6 6-6 6" fill="none" stroke="{MUTED}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
            doc.t("B8", "Applications", 150, 31.5, 15))
    sx = W - 20 - 190
    doc.add(f'<rect x="{sx}" y="13" width="190" height="26" rx="7" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".06"/>',
            f'<circle cx="{sx + 18}" cy="25" r="5" fill="none" stroke="{MUTED}" stroke-width="1.6"/>'
            f'<path d="M{sx + 22} 29l4 4" stroke="{MUTED}" stroke-width="1.6" stroke-linecap="round"/>',
            doc.t("B5", "Search tools", sx + 32, 30.5, 13, DIM))
    vx = sx - 96
    doc.add(f'<rect x="{vx}" y="13" width="80" height="26" rx="7" fill="#fff" fill-opacity=".06"/>'
            f'<rect x="{vx + 3}" y="16" width="36" height="20" rx="5" fill="#fff" fill-opacity=".12"/>')
    for gx in (0, 7):
        for gy in (0, 7):
            doc.add(f'<rect x="{vx + 15 + gx}" y="{19 + gy}" width="5" height="5" rx="1" fill="{INK}"/>')
    for ly in (20, 25, 30):
        doc.add(f'<rect x="{vx + 52}" y="{ly}" width="16" height="2" rx="1" fill="{MUTED}"/>')
    # sidebar
    doc.add(f'<rect x="0" y="{tb + 1}" width="{side}" height="{H - tb - 1}" fill="{PANEL}"/>',
            f'<line x1="{side + .5}" x2="{side + .5}" y1="{tb + 1}" y2="{H}" stroke="{LINE}"/>',
            doc.t("B6", "Favorites", 18, tb + 32, 11.5, DIM))
    for i, (cat, tools) in enumerate(TOOLS):
        yy = tb + 60 + i * 30
        if i == 0:
            doc.add(f'<rect x="8" y="{yy - 19}" width="{side - 16}" height="28" rx="7" fill="#fff" fill-opacity=".08"/>')
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
    gx0, gx1 = side + 24, W - 24
    col = (gx1 - gx0) / 8
    n = 0
    for i, (cat, tools) in enumerate(TOOLS):
        y0 = tb + 20 + i * sec
        tw = measure("B8", cat, 15)
        doc.add(doc.t("B8", cat, gx0, y0 + 16, 15),
                doc.t("M4", f"{len(tools)} apps", gx0 + tw + 10, y0 + 16, 11.5, DIM),
                f'<line x1="{gx0 + tw + 10 + measure("M4", f"{len(tools)} apps", 11.5) + 12:.1f}" x2="{gx1}" '
                f'y1="{y0 + 12}" y2="{y0 + 12}" stroke="{LINE}"/>')
        for j, (label, slug) in enumerate(tools):
            cx = gx0 + col * j + col / 2
            doc.add(f'<g class="pop" style="{d(.2 + n * .035)}">', tool_tile(doc, cx, y0 + 64, 56, slug),
                    doc.t("B5", label, cx, y0 + 112, 12.5, "#D6D4CF", "middle"), "</g>")
            n += 1
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


def activity(data):
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

    W, H = 1000, 862
    doc = Doc(W, H, f"Activity monitor: {total} contributions in the last year, "
                    f"busiest on {dt.date(2024, 1, 1 + busiest).strftime('%A')}s, longest streak {longest} days, best day {best} contributions.")
    doc.css.append(POP + REDUCED)
    doc.defs.append('<linearGradient id="sky" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#15141F"/>'
                    f'<stop offset="1" stop-color="{WIN}"/></linearGradient>'
                    f'<radialGradient id="glow" cx="720" cy="220" r="420" gradientUnits="userSpaceOnUse">'
                    f'<stop offset="0" stop-color="{PURPLE}" stop-opacity=".16"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>')
    tb = 48
    doc.add(window(doc, 0, 0, W, H, None, tb, 14, False))
    doc.add(doc.spans("B6", [("Activity Monitor", INK), (f"   {USER} · last 12 months", MUTED)], 92, 29, 13.5))
    tabs = ["Contributions", "Repos", "Languages"]
    tx = W - 20 - sum(measure("B6", s, 12.5) + 26 for s in tabs)
    doc.add(f'<rect x="{tx - 3}" y="11" width="{W - 20 - tx + 6:.1f}" height="26" rx="7" fill="#fff" fill-opacity=".06"/>')
    for i, s in enumerate(tabs):
        w = measure("B6", s, 12.5) + 26
        if i == 0:
            doc.add(f'<rect x="{tx}" y="14" width="{w:.1f}" height="20" rx="5" fill="#fff" fill-opacity=".13"/>')
        doc.add(doc.t("B6", s, tx + w / 2, 28.5, 12.5, INK if i == 0 else MUTED, "middle"))
        tx += w
    doc.add(f'<rect x="1" y="{tb + 1}" width="{W - 2}" height="392" fill="url(#sky)"/>',
            f'<rect x="1" y="{tb + 1}" width="{W - 2}" height="392" fill="url(#glow)"/>')

    # isometric skyline: week axis runs up-right, weekday axis down-right
    WV, DV = (14.2, -3.6), (9.5, 5.2)
    O = (90, 402)
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
    for (w, dd) in cells:
        day, c = grid[(w, dd)]
        A, B, C, D = P(w, dd), P(w + 1, dd), P(w + 1, dd + 1), P(w, dd + 1)
        poly = lambda pts: "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + "Z"
        if not c:
            doc.add(f'<path d="{poly([A, B, C, D])}" fill="#23222D" stroke="#15141C" stroke-width=".8"/>')
            continue
        lvl = sum(c > q for q in cuts)
        h = 6 + 150 * math.sqrt(c / peak)
        up = lambda p, hh: (p[0], p[1] - hh)
        faces = [([A, D, up(D, h), up(A, h)], [A, D, D, A], .62),
                 ([D, C, up(C, h), up(D, h)], [D, C, C, D], .45),
                 ([up(A, h), up(B, h), up(C, h), up(D, h)], [A, B, C, D], 1)]
        begin = .3 + w * .022
        for full, flat, f in faces:
            col = shade(ramp[lvl], f)
            doc.add(f'<path d="{poly(full)}" fill="{col}" stroke="#0B0A12" stroke-opacity=".55" stroke-width=".7" stroke-linejoin="round">'
                    f'<animate attributeName="d" values="{poly(flat)};{poly(full)}" dur=".7s" begin="{begin:.2f}s" '
                    f'calcMode="spline" keySplines=".2 .8 .3 1" fill="freeze"/></path>')
    # month labels along the front edge
    ang = math.degrees(math.atan2(WV[1], WV[0]))
    last = None
    for w in range(weeks):
        day = grid.get((w, 0), grid.get((w, 6)))
        if not day:
            continue
        m = day[0].month
        nxt = grid.get((w + 2, 0))
        if m != last and w < weeks - 1 and not (nxt and nxt[0].month != m):
            x, y = P(w + .2, 7)
            doc.add(doc.t("M4", day[0].strftime("%b"), x + 4, y + 18, 11, DIM,
                          extra=f' transform="rotate({ang:.1f} {x + 4:.1f} {y + 18:.1f})"'))
        last = m
    # headline
    doc.add(f'<g class="rise" style="{d(.2)}">', doc.t("B8", f"{total:,}", 40, tb + 86, 68, INK), "</g>",
            f'<g class="rise" style="{d(.35)}">', doc.t("B5", "contributions in the last year", 43, tb + 116, 16, MUTED), "</g>")
    # legend
    lx, ly = W - 40, tb + 372
    doc.add(doc.t("M4", "more", lx, ly, 11, DIM, "end"))
    lx -= measure("M4", "more", 11) + 8
    for col in reversed(["#23222D"] + ramp):
        lx -= 13
        doc.add(f'<rect x="{lx}" y="{ly - 10}" width="11" height="11" rx="2.5" fill="{col}"/>')
    doc.add(doc.t("M4", "less", lx - 8, ly, 11, DIM, "end"))

    # stat tiles
    sy = tb + 406
    stats = [("busiest day of week", dt.date(2024, 1, 1 + busiest).strftime("%a"), f"{by_wd[busiest]} total"),
             ("longest streak", f"{longest}", "day" if longest == 1 else "days"),
             ("best day", f"{best}", best_day.strftime("on %b %-d")),
             ("active days", f"{active}", f"of {len(days)}")]
    cw_ = (W - 40 - 3 * 12) / 4
    for i, (k, v, sub) in enumerate(stats):
        x = 20 + i * (cw_ + 12)
        doc.add(f'<g class="pop" style="{d(.6 + i * .08)}">',
                f'<rect x="{x:.1f}" y="{sy}" width="{cw_:.1f}" height="84" rx="10" fill="#fff" fill-opacity=".035" stroke="#fff" stroke-opacity=".07"/>',
                doc.t("M4", k.upper(), x + 16, sy + 24, 10.5, DIM),
                doc.t("B8", v, x + 16, sy + 64, 34, INK),
                doc.t("B5", sub, x + 22 + measure("B8", v, 34), sy + 64, 14, MUTED), "</g>")

    # processes = recently pushed repos
    py0 = sy + 108
    doc.add(f'<line x1="0" x2="{W}" y1="{py0 - 12.5}" y2="{py0 - 12.5}" stroke="{LINE}"/>')
    cols = [("PID", 24, "M4"), ("Process", 88, "B6"), ("Language", 318, "B5"), ("Size", 488, "M4"), ("Last push", 606, "M4")]
    doc.add(f'<rect x="12" y="{py0}" width="{616}" height="30" rx="6" fill="#fff" fill-opacity=".04"/>')
    for label, x, _ in cols:
        doc.add(doc.t("B6", label, x if label not in ("Size", "Last push") else x, py0 + 20, 12, MUTED,
                      "end" if label in ("Size", "Last push") else None))
    for i, r in enumerate([r for r in data["repos"] if r["lang"]][:6]):
        y = py0 + 36 + i * 32
        if i == 0:
            doc.add(f'<rect x="12" y="{y}" width="616" height="30" rx="6" fill="{BLUE}" fill-opacity=".25"/>')
        elif i % 2 == 0:
            doc.add(f'<rect x="12" y="{y}" width="616" height="30" rx="6" fill="#fff" fill-opacity=".02"/>')
        lang = r["lang"] or "—"
        size = f'{r["size"] / 1024:.1f} MB' if r["size"] >= 1024 else f'{r["size"]} KB'
        name = r["name"] if measure("B6", r["name"], 14) < 210 else r["name"][:20] + "…"
        doc.add(doc.t("M4", str(r["id"] % 100000), 24, y + 20, 12.5, DIM),
                doc.t("B6", name, 88, y + 20, 14, INK),
                f'<circle cx="{323}" cy="{y + 15}" r="4.5" fill="{LANG_COLORS.get(lang, MUTED)}"/>',
                doc.t("B5", lang, 334, y + 20, 13.5, "#D6D4CF"),
                doc.t("M4", size, 488, y + 20, 12.5, MUTED, "end"),
                doc.t("M4", ago(r["pushed"]), 606, y + 20, 12.5, INK if i == 0 else MUTED, "end"))
    doc.add(f'<line x1="{640.5}" x2="{640.5}" y1="{py0 - 12}" y2="{H - 30}" stroke="{LINE}"/>')

    # languages by repo
    langs = {}
    for r in data["repos"]:
        if r["lang"]:
            langs[r["lang"]] = langs.get(r["lang"], 0) + 1
    ranked = sorted(langs.items(), key=lambda kv: -kv[1])
    top = ranked[:5]
    if len(ranked) > 5:
        top.append(("Other", sum(v for _, v in ranked[5:])))
    n = sum(v for _, v in top)
    lx0, lx1 = 662, W - 24
    doc.add(doc.t("B8", "Languages", lx0, py0 + 20, 15), doc.t("M4", "by repo", lx1, py0 + 20, 11, DIM, "end"))
    x = lx0
    doc.defs.append(f'<clipPath id="bar"><rect x="{lx0}" y="{py0 + 38}" width="{lx1 - lx0}" height="10" rx="5"/></clipPath>')
    doc.add('<g clip-path="url(#bar)">')
    for lang, v in top:
        w = (lx1 - lx0) * v / n
        doc.add(f'<rect x="{x:.1f}" y="{py0 + 38}" width="{max(w - 2, 1):.1f}" height="10" fill="{LANG_COLORS.get(lang, DIM)}"/>')
        x += w
    doc.add("</g>")
    for i, (lang, v) in enumerate(top):
        y = py0 + 80 + i * 29
        doc.add(f'<circle cx="{lx0 + 5}" cy="{y - 4.5}" r="4.5" fill="{LANG_COLORS.get(lang, DIM)}"/>',
                doc.t("B5", lang, lx0 + 18, y, 13.5, "#D6D4CF"),
                doc.t("M4", f"{100 * v / n:.0f}%", lx1, y, 12.5, MUTED, "end"))

    doc.add(f'<line x1="0" x2="{W}" y1="{H - 30.5}" y2="{H - 30.5}" stroke="{LINE}"/>',
            doc.t("B5", f"{len(data['repos'])} repos · refreshed daily at 00:00 GMT+8 · last refresh "
                         f"{NOW.strftime('%-d %b %Y')}", W / 2, H - 11, 12, DIM, "middle"))
    return doc.render()


# ---------- status bar ----------
def statusbar():
    W, H = 1000, 48
    doc = Doc(W, H, "Every graphic on this page is an SVG drawn by scripts/build.py")
    doc.css.append(".pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2s ease-out infinite}"
                   "@keyframes pulse{from{opacity:.6;transform:scale(1)}to{opacity:0;transform:scale(3)}}" + REDUCED)
    doc.add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="{H / 2}" fill="{WIN}" stroke="#fff" stroke-opacity=".1"/>',
            f'<circle class="pulse" cx="26" cy="24" r="4.5" fill="{GREEN}"/><circle cx="26" cy="24" r="4.5" fill="{GREEN}"/>',
            doc.t("B6", "all systems nominal", 42, 29, 13.5, INK),
            doc.spans("M4", [("every pixel here is an SVG drawn by ", MUTED), ("scripts/build.py", BLUE)],
                      W / 2 - measure("M4", "every pixel here is an SVG drawn by scripts/build.py", 12.5) / 2 + 40, 28.5, 12.5),
            doc.t("M4", f"built {NOW.strftime('%-d %b %Y')}", W - 24, 28.5, 12.5, DIM, "end"))
    return doc.render()


if __name__ == "__main__":
    data = load_data()
    out = {"desktop.svg": desktop(), "apps.svg": apps(), "activity.svg": activity(data), "statusbar.svg": statusbar()}
    for fn, svg, pct in dock():
        out[fn] = svg
        print(f"{fn} width={pct:.1f}%")
    for fn, svg in out.items():
        open(os.path.join(OUT, fn), "w").write(svg)
        print(fn, len(svg) // 1024, "KB")
