#!/usr/bin/env python3
"""
render_instance.py — deterministically render a room artefact from its Bingley
template. This is the ONLY supported way to build a Prospecting artefact. Never
hand-write the HTML: the desk shell must come from the template verbatim.

It replaces the contents of the template's
  <script type="application/json" id="room-data">...</script>
block with your DATA JSON and writes the instance. Everything else (the Bingley
desk shell, SVG chrome, render logic) is copied byte-for-byte.

Usage:
  python3 render_instance.py --template <template.html> --data <data.json> --out <instance.html>
  # or pipe the data:
  cat data.json | python3 render_instance.py --template <template.html> --out <instance.html>

Exits non-zero with a clear message if the template or the data block is missing,
or if the data isn't valid JSON — so a bad run fails loudly instead of silently
falling back to improvised HTML.
"""
import argparse, json, math, re, sys, os


def _sanitize(o):
    """Replace non-finite floats (NaN / Infinity / -Infinity) with None ANYWHERE in the DATA.
    Python's json.dumps emits these as bare `NaN`/`Infinity` tokens — invalid JSON that the
    browser's strict JSON.parse rejects, which would blank the whole artefact. One flaky number
    from a research step (e.g. a bad score) must never sink the render; it becomes null instead."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_sanitize(v) for v in o]
    return o

BLOCK_RE = re.compile(
    r'(<script\s+type="application/json"\s+id="room-data">)(.*?)(</script>)',
    re.DOTALL)


def render(template_html, data_obj):
    if not BLOCK_RE.search(template_html):
        raise SystemExit("ERROR: no <script id=\"room-data\"> block in template — "
                         "is this the right Bingley room template?")
    payload = json.dumps(_sanitize(data_obj), ensure_ascii=False, allow_nan=False)
    # guard against breaking out of the script block
    # Escape EVERY "<" (valid only inside JSON strings, where all of ours live) so no case/spacing
    # variant of a close-tag can break out of the script block.
    payload = payload.replace("<", "\\u003c")
    return BLOCK_RE.sub(lambda m: m.group(1) + payload + m.group(3),
                        template_html, count=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--data", help="path to data JSON; omit to read stdin")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    if not os.path.isfile(a.template):
        raise SystemExit(f"ERROR: template not found: {a.template}")
    with open(a.template, encoding="utf-8") as f:
        tpl = f.read()

    raw = open(a.data, encoding="utf-8").read() if a.data else sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"ERROR: --data is not valid JSON: {e}")

    out = render(tpl, data)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(out)

    # sanity: confirm the shell survived and data went in
    checks = {"bingley shell": 'id="stage"' in out or 'id="scp-shell"' in out,
              "data injected": '"companies"' in out or '"rows"' in out,
              "template marker": "TEMPLATE_VERSION" in out}
    bad = [k for k, v in checks.items() if not v]
    if bad:
        raise SystemExit("ERROR: instance failed sanity check: " + ", ".join(bad))
    print(f"OK wrote {a.out} ({len(out)} bytes); shell intact, data injected.")


if __name__ == "__main__":
    main()
