"""Rebuild docs/index.html from the generator output.
Run from the src/ folder:  python tool_stand.py && python export_solids.py && python build_drawings.py
"""
import json, os
here = os.path.dirname(os.path.abspath(__file__))
tpl = open(os.path.join(here, "drawing_template.html"), encoding="utf-8").read()
geo = json.load(open(os.path.join(here, "build", "geometry.json")))
geo.pop("grid", None)
sol = open(os.path.join(here, "build", "solids.json")).read()
html = tpl.replace("/*GEO*/null", json.dumps(geo, separators=(",", ":"))).replace("/*SOL*/null", sol)
out = os.path.join(here, "..", "docs", "index.html")
# GitHub Pages needs a full document; the template is a body fragment
if not html.lstrip().lower().startswith("<!doctype"):
    html = "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n" + html.replace("</style>", "</style>\n</head><body>", 1) + "\n</body></html>\n"
open(out, "w", encoding="utf-8").write(html)
print("wrote", out)
