#!/usr/bin/env python3
"""Generate the profile Hero: C++ source beside its x86-64 assembly, joined by colored ribbons.

Writes ../assets/hero-light.svg and ../assets/hero-dark.svg. Each SVG embeds the subset of
Victor Mono it uses (an SVG shown as an <img> can't load web fonts), so it renders the same
wherever GitHub shows it.

    pip install -r requirements.txt
    python build.py

Motion: the build plays once on load, then each band lights up in turn and a pulse runs the
jmp loop, forever. The un-animated state is always the finished picture, so visitors who ask
for reduced motion see a still image.
"""
import base64
import io
import math
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"
ASSETS = HERE.parent / "assets"

TITLE = "Shuojiang Liu, compiled"
ALT = ("C++ source beside its x86-64 assembly and machine code, each line joined to its output "
       "by a colored ribbon. latency_ns() returns 0; run() loops learn<C, Cpp, Linux>() forever; "
       "a struct holds New York and Georgia Tech.")

# GitHub's own page colors, so the Hero sits on the page instead of on a card.
PAGE = {
    "light": dict(fg="#1f2328", muted="#59636e", rule="#d1d9e0", line_no="#b6bec7"),
    "dark": dict(fg="#f0f6fc", muted="#9198a1", rule="#3d444d", line_no="#4d5560"),
}


def oklch(L, C, h):
    """OKLCH to an sRGB hex string (gamut-clipped)."""
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    rgb = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )

    def encode(x):
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055

    return "#%02x%02x%02x" % tuple(round(encode(v) * 255) for v in rgb)


# ------------------------------------------------------------------ fonts

FAMILY = "Victor Mono"


class Face:
    def __init__(self, file, weight, style="normal"):
        self.path = FONTS / file
        self.weight, self.style = weight, style
        tt = TTFont(self.path)
        self.advance = tt["hmtx"][tt.getBestCmap()[ord("0")]][0] / tt["head"].unitsPerEm

    def woff2_base64(self, chars):
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = []      # no ligatures or alternates: code must look as typed
        options.notdef_outline = True
        subsetter = subset.Subsetter(options)
        subsetter.populate(text="".join(sorted(chars)))
        tt = TTFont(self.path, recalcTimestamp=False)   # keep output byte-identical across runs
        subsetter.subset(tt)
        buf = io.BytesIO()
        tt.save(buf)
        return base64.b64encode(buf.getvalue()).decode()


CODE = Face("victor-mono-latin-500-normal.woff2", 500)
KEYWORD = Face("victor-mono-latin-600-italic.woff2", 600, "italic")    # cursive, C++ source only
COMMENT = Face("victor-mono-latin-500-italic.woff2", 500, "italic")
STRONG = Face("victor-mono-latin-700-normal.woff2", 700)


# ------------------------------------------------------------------ content

# Token roles: code, kw (C++ keyword, cursive), op (assembly mnemonic, upright), str, muted,
# comment, strong.
SOURCE = [
    [("#include ", "kw"), ("<cstdint>", "str")],
    [],
    [("struct ", "kw"), ("C; ", "code"), ("struct ", "kw"), ("Cpp; ", "code"), ("struct ", "kw"),
     ("Linux;", "code")],
    [("template ", "kw"), ("<", "muted"), ("class", "kw"), ("...> ", "muted"), ("void ", "kw"),
     ("learn();", "code")],
    [],
    [("std::uint64_t ", "code"), ("latency_ns", "strong"), ("() {", "code")],
    [("    ", "code"), ("return ", "kw"), ("0;  ", "code"), ("// aspirational", "comment")],
    [("}", "code")],
    [],
    [("[[noreturn]] ", "muted"), ("void ", "kw"), ("run", "strong"), ("() {", "code")],
    [("    ", "code"), ("for ", "kw"), ("(;;) learn<C, Cpp, Linux>();", "code")],
    [("}", "code")],
    [],
    [("struct ", "kw"), ("engineer", "strong"), (" {", "code")],
    [("    ", "code"), ("const char", "kw"), ("* city   = ", "code"), ('"New York"', "str"),
     (";", "code")],
    [("    ", "code"), ("const char", "kw"), ("* school = ", "code"), ('"Georgia Tech"', "str"),
     (";", "code")],
    [("} me;", "code")],
]

# clang -O3 output for SOURCE: (kind, machine code, mnemonic or label, operands).
# If the source changes, recompute the bytes: eb f9 jumps back 7, over the 5-byte call and itself.
ASSEMBLY = [
    ("label", None, "latency_ns():", None),
    ("insn", "31 c0", "xor", "eax, eax"),
    ("insn", "c3", "ret", ""),
    ("label", None, "run():", None),
    ("insn", "50", "push", "rax"),
    ("local", None, ".LBB1_1:", None),
    ("insn", "e8 00 00 00 00", "call", "void learn<C, Cpp, Linux>()"),   # unlinked: rel32 still 0
    ("insn", "eb f9", "jmp", ".LBB1_1"),
    ("label", None, "me:", None),
    ("data", None, ".quad", ".L.str"),
    ("data", None, ".quad", ".L.str.1"),
    ("local", None, ".L.str:", None),
    ("data", None, ".asciz", '"New York"'),
    ("local", None, ".L.str.1:", None),
    ("data", None, ".asciz", '"Georgia Tech"'),
]

# One band per source construct: (hue, source lines, assembly lines), all 1-based.
BANDS = [
    (85, [6, 7, 8], [1, 2, 3]),             # latency_ns
    (20, [10, 11, 12], [4, 5, 6, 7, 8]),    # run
    (200, [15], [10, 12, 13]),              # city
    (265, [16], [11, 14, 15]),              # school
]
LOOP_LABEL, LOOP_JMP = 6, 8                 # assembly lines joined by the jump arrow


def assembly_tokens():
    machine_col, mnemonic_col = 15, 7
    lines = []
    for kind, code, a, b in ASSEMBLY:
        if kind == "label":
            lines.append([(a, "strong")])
        elif kind == "local":
            lines.append([(a, "muted")])
        else:
            lines.append([(f"{code or '':<{machine_col}}", "muted"), (f"{a:<{mnemonic_col}}", "op"),
                          (b, "str" if b.startswith('"') else "code")])
    return lines


# ------------------------------------------------------------------ svg

MOTION_CSS = (
    "@keyframes in{from{opacity:0}to{opacity:1}}"
    "@keyframes wipe{from{-webkit-clip-path:inset(0 100% 0 0);clip-path:inset(0 100% 0 0)}"
    "to{-webkit-clip-path:inset(0 0 0 0);clip-path:inset(0 0 0 0)}}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}.pulse{display:none}}"
)


def anim(name, duration, delay, easing="ease-out", iterations="1"):
    # fill-mode "both": hidden-at-start states exist only while the animation runs
    return f' style="animation:{name} {duration:.3f}s {easing} {delay:.3f}s {iterations} both"'


def tour_keyframes(n):
    """n groups take turns being lit; each holds for 1/n of the period, with a short crossfade."""
    s = 100.0 / n
    return (f"@keyframes tour{{0%{{opacity:0}}{s * 0.15:.2f}%{{opacity:1}}"
            f"{s * 0.92:.2f}%{{opacity:1}}{s * 1.08:.2f}%{{opacity:0}}100%{{opacity:0}}}}")


class Svg:
    def __init__(self):
        self.parts, self.used = [], {}

    def add(self, s):
        self.parts.append(s)

    def line(self, x, y, size, tokens, styles, extra=""):
        """One line of text; tokens are (text, role), styles map role -> (face, color)."""
        spans = []
        for text, role in tokens:
            if not text:
                continue
            face, color = styles[role]
            self.used.setdefault(face, set()).update(text)
            spans.append(f'<tspan font-weight="{face.weight}" font-style="{face.style}" '
                         f'fill="{color}">{escape(text)}</tspan>')
        return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}"{extra}>{"".join(spans)}</text>'

    def render(self, width, height, css):
        faces = "".join(
            f'@font-face{{font-family:"{FAMILY}";font-weight:{face.weight};font-style:{face.style};'
            f'src:url(data:font/woff2;base64,{face.woff2_base64(chars)}) format("woff2")}}'
            for face, chars in self.used.items())
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" xml:space="preserve" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(TITLE)}</title><desc id="desc">{escape(ALT)}</desc>'
            f'<style>{faces}text{{font-family:"{FAMILY}";white-space:pre}}{css}</style>\n'
            + "\n".join(self.parts) + "\n</svg>\n")


# ------------------------------------------------------------------ the Hero

def hero(theme):
    page, dark = PAGE[theme], theme == "dark"
    keyword = oklch(0.76, 0.12, 305) if dark else oklch(0.47, 0.17, 305)
    string = oklch(0.78, 0.11, 155) if dark else oklch(0.48, 0.12, 155)
    fg, muted = page["fg"], page["muted"]
    styles = {
        "code": (CODE, fg), "kw": (KEYWORD, keyword), "op": (CODE, keyword), "str": (CODE, string),
        "muted": (CODE, muted), "comment": (COMMENT, muted), "strong": (STRONG, fg),
        "line_no": (CODE, page["line_no"]),
    }
    asm = assembly_tokens()

    # --- geometry
    W, size, pitch = 880, 13, 21.0
    cw = CODE.advance * size
    LX0, LX1, GAP = 0.0, 360.0, 92.0          # source pane, then the gap the ribbons cross
    RX0, RX1 = LX1 + GAP, W                   # assembly pane
    AX = RX0 + 22.0                           # assembly text, after the jump-arrow gutter
    head, y0 = 16.0, 50.0
    baseline = pitch * 0.68
    widest_src = max(sum(len(t) for t, _ in line) for line in SOURCE) + 3.6
    widest_asm = max(sum(len(t) for t, _ in line) for line in asm)
    assert LX0 + widest_src * cw <= LX1 - 12, "source overflows its pane"
    assert AX + widest_asm * cw <= RX1 - 16, "assembly overflows its pane"

    def top(n):  # top edge of 1-based line n
        return y0 + (n - 1) * pitch

    # --- timing, in seconds: compile, then settle into the tour and the loop
    C0, STEP, RIBBON = 0.35, 0.3, 0.55

    def ribbon_at(k):
        return C0 + k * STEP

    def asm_at(k, j=0):
        return ribbon_at(k) + RIBBON * 0.7 + j * 0.05

    done = asm_at(len(BANDS) - 1, 3) + 0.3
    settle = done + 0.5
    SLOT = 2.2
    period = SLOT * len(BANDS)

    def band_of(n):
        """Band an assembly line appears with; unbanded lines go with the next banded line."""
        for k, (_, _, lines) in enumerate(BANDS):
            if n in lines:
                return k
        return band_of(n + 1)

    # --- bands and ribbons
    def src_rect(n):
        return f'x="{LX0:.1f}" y="{top(n):.2f}" width="{LX1 - LX0:.1f}" height="{pitch:.2f}"'

    def asm_rect(n):
        return f'x="{RX0:.1f}" y="{top(n):.2f}" width="{RX1 - RX0:.1f}" height="{pitch:.2f}"'

    def ribbons(src_lines, asm_lines):
        a, b = top(src_lines[0]), top(src_lines[-1]) + pitch
        blocks = [[asm_lines[0]]]
        for n in asm_lines[1:]:
            if n == blocks[-1][-1] + 1:
                blocks[-1].append(n)
            else:
                blocks.append([n])
        c = LX1 + GAP / 2
        paths = []
        for block in blocks:
            ta, tb = top(block[0]), top(block[-1]) + pitch
            paths.append(f"M{LX1:.1f},{a:.2f} C{c:.1f},{a:.2f} {c:.1f},{ta:.2f} {RX0:.1f},{ta:.2f} "
                         f"V{tb:.2f} C{c:.1f},{tb:.2f} {c:.1f},{b:.2f} {LX1:.1f},{b:.2f} Z")
        return paths

    svg = Svg()
    lit = []
    for k, (hue, src_lines, asm_lines) in enumerate(BANDS):
        calm = oklch(0.31, 0.05, hue) if dark else oklch(0.945, 0.04, hue)
        hot = oklch(0.42, 0.075, hue) if dark else oklch(0.885, 0.068, hue)
        paths = ribbons(src_lines, asm_lines)
        for n in src_lines:
            svg.add(f'<rect {src_rect(n)} fill="{calm}"{anim("in", 0.25, ribbon_at(k) - 0.15)}/>')
        for d in paths:
            svg.add(f'<path d="{d}" fill="{calm}" fill-opacity="0.85"'
                    f'{anim("wipe", RIBBON, ribbon_at(k), "cubic-bezier(.3,.6,.2,1)")}/>')
        for n in asm_lines:
            svg.add(f'<rect {asm_rect(n)} fill="{calm}"{anim("in", 0.25, asm_at(k))}/>')
        lit.append("".join([f'<rect {src_rect(n)} fill="{hot}"/>' for n in src_lines]
                           + [f'<path d="{d}" fill="{hot}"/>' for d in paths]
                           + [f'<rect {asm_rect(n)} fill="{hot}"/>' for n in asm_lines]))
    for k, group in enumerate(lit):  # the tour: base opacity 0, so the still image shows calm bands
        svg.add(f'<g opacity="0"{anim("tour", period, settle + k * SLOT, "linear", "infinite")}>'
                f'{group}</g>')

    # --- pane headers
    header = round(size * 0.96, 2)
    for x0, x1, label, note in ((LX0, LX1, "shuojiang.cpp", None), (RX0, RX1, "x86-64 clang", "-O3")):
        svg.add(svg.line(x0 + 2, head, header, [(label, "strong")], styles))
        if note:
            svg.add(svg.line(x1 - 2, head, header, [(note, "muted")], styles, ' text-anchor="end"'))
        svg.add(f'<line x1="{x0:.1f}" y1="{head + 12:.1f}" x2="{x1:.1f}" y2="{head + 12:.1f}" '
                f'stroke="{page["rule"]}" stroke-width="1"/>')

    # --- text
    for n, tokens in enumerate(SOURCE, 1):
        svg.add(svg.line(LX0 + 2.3 * cw, top(n) + baseline, size, [(f"{n:>2}", "line_no")], styles,
                         ' text-anchor="end"'))
        svg.add(svg.line(LX0 + 3.6 * cw, top(n) + baseline, size, tokens, styles))
    order = {}
    for n, tokens in enumerate(asm, 1):
        k = band_of(n)
        j = order[k] = order.get(k, -1) + 1
        svg.add(svg.line(AX, top(n) + baseline, size, tokens, styles, anim("in", 0.25, asm_at(k, j))))
    svg.add(svg.line(AX, top(len(SOURCE)) + baseline, size, [("Compiler returned: 0", "muted")],
                     styles, anim("in", 0.4, done)))

    # --- the jump arrow, and the pulse that runs it forever
    ya, yb = top(LOOP_LABEL) + pitch / 2, top(LOOP_JMP) + pitch / 2
    xg, xe = RX0 + 8.0, AX - 4.0
    arrow = f"M{xe:.2f},{yb:.2f} H{xg:.2f} V{ya:.2f} H{xe:.2f}"
    stroke = f'fill="none" stroke="{keyword}" stroke-width="1.3" stroke-linejoin="round"'
    svg.add(f'<g{anim("in", 0.3, asm_at(band_of(LOOP_JMP), 4))}><path d="{arrow}" {stroke}/>'
            f'<path d="M{xe - 4.5:.2f},{ya - 3.5:.2f} L{xe:.2f},{ya:.2f} L{xe - 4.5:.2f},{ya + 3.5:.2f}" '
            f'{stroke} stroke-linecap="round"/></g>')
    svg.add(f'<circle class="pulse" r="3.2" fill="{keyword}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{settle:.2f}s" fill="freeze"/>'
            f'<animateMotion dur="1.1s" begin="{settle:.2f}s" repeatCount="indefinite" '
            f'path="{arrow}"/></circle>')

    height = round(top(len(SOURCE)) + pitch + 4)
    return svg.render(W, height, MOTION_CSS + tour_keyframes(len(BANDS)))


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    for theme in ("light", "dark"):
        path = ASSETS / f"hero-{theme}.svg"
        path.write_text(hero(theme))
        print(f"wrote {path.relative_to(HERE.parent)} ({path.stat().st_size // 1024} KiB)")
