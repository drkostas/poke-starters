#!/usr/bin/env python3
import base64, pathlib

# Build the single-file app: inline fonts + maps + marker as data URIs.
# Runs relative to this file's directory (self-contained, portable).
SCRATCH = pathlib.Path(__file__).resolve().parent
FONTS = SCRATCH / "fonts"
MAPS = SCRATCH / "maps"

# 2x2 dark placeholder PNG (used when a real map asset isn't downloaded yet)
PLACEHOLDER = ("data:image/png;base64,"
  "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEklEQVR4nGNsaGhgwAKYGLAKAwAaGgIF"
  "yBS9GwAAAABJRU5ErkJggg==")

def datauri(path, mime):
    b = pathlib.Path(path).read_bytes()
    if not b:
        raise SystemExit(f"EMPTY FILE: {path}")
    return f"data:{mime};base64," + base64.b64encode(b).decode()

def sprite_map(dirname):
    d = SCRATCH / "sprites" / dirname
    out = {}
    for p in sorted(d.glob("*.png"), key=lambda x: int(x.stem)):
        out[int(p.stem)] = datauri(p, "image/png")
    # JS object literal
    return "{" + ",".join(f'{k}:"{v}"' for k, v in out.items()) + "}"

def map_uri(candidates):
    for name in candidates:
        p = MAPS / name
        if p.exists() and p.stat().st_size > 500:
            mime = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
            return datauri(p, mime), name
    return PLACEHOLDER, None

kanto, kn = map_uri(["kanto_frlg.png", "kanto_rby.png", "kanto.png"])
johto, jn = map_uri(["johto.png"])
hoenn, hn = map_uri(["hoenn.png"])
print("maps ->", {"kanto": kn, "johto": jn, "hoenn": hn})

html = (SCRATCH / "lab.template.html").read_text(encoding="utf-8")
repl = {
    "__MARKER__": datauri(MAPS / "gen3_marker.png", "image/png"),
    "__OAK__": datauri(MAPS / "prof_oak.png", "image/png"),
    "__TOUR__": (SCRATCH / "tour.json").read_text(encoding="utf-8").strip(),
    "__FONT_RAJD5__": datauri(FONTS / "rajdhani-500.woff2", "font/woff2"),
    "__FONT_RAJD7__": datauri(FONTS / "rajdhani-700.woff2", "font/woff2"),
    "__FONT_PRESS__": datauri(FONTS / "press-start.woff2", "font/woff2"),
}
for k, v in repl.items():
    html = html.replace(k, v)

leftover = [t for t in repl if t in html]
if leftover:
    raise SystemExit(f"LEFTOVER TOKENS: {leftover}")

# wrap so the STANDALONE-served file (server.py) has a real root: doctype exits quirks mode,
# lang satisfies WCAG 3.1.1. The template stays a fragment (an Artifact-publish path would inject its own skeleton).
html = '<!doctype html>\n<html lang="en">\n' + html + '\n</html>\n'
out = SCRATCH / "lab.built.html"
out.write_text(html, encoding="utf-8")
print(f"OK wrote {out} ({len(html)//1024} KB)")
