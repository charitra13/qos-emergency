"""Report generation: Markdown, CSV and a self-contained HTML page with inline SVG charts."""
import html
from .protocol import CLASS_NAMES

COLORS = {"fifo": "#9aa5b1", "pq": "#e07a5f", "wfq": "#3d85c6", "drr": "#6aa84f", "eps": "#8e44ad"}
LABELS = {"fifo": "FIFO", "pq": "Strict PQ", "wfq": "WFQ", "drr": "DRR", "eps": "EPS (proposed)"}
CLASS_ORDER = ["emergency", "voice", "video", "best_effort"]


def _e(s):
    return html.escape(str(s))


def svg_grouped_bar(title, cats, series, ylabel, w=760, h=330, log=False):
    import math
    ml, mr, mt, mb = 60, 20, 40, 60
    pw, ph = w - ml - mr, h - mt - mb
    vals = [v for s in series.values() for v in s]
    vmax = max(vals + [1e-9])
    if log:
        lo, hi = 0.1, max(10.0, 10 ** math.ceil(math.log10(vmax)))
        f = lambda v: (math.log10(max(v, lo)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        ticks = [lo * 10 ** i for i in range(int(round(math.log10(hi / lo))) + 1)]
    else:
        hi = vmax * 1.1
        f = lambda v: v / hi
        ticks = [hi * i / 5 for i in range(6)]
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;font-family:sans-serif;font-size:11px">' % (w, h, w),
         '<text x="%d" y="22" font-size="14" font-weight="bold">%s</text>' % (ml, _e(title))]
    for t in ticks:
        y = mt + ph * (1 - f(t))
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#ddd"/>' % (ml, y, w - mr, y))
        o.append('<text x="%d" y="%.1f" text-anchor="end">%s</text>' % (ml - 5, y + 4, ("%.4g" % t)))
    o.append('<text x="14" y="%d" transform="rotate(-90 14 %d)" text-anchor="middle">%s</text>' % (mt + ph // 2, mt + ph // 2, _e(ylabel)))
    n, k = len(cats), len(series)
    gw = pw / n
    bw = gw * 0.8 / k
    for ci, c in enumerate(cats):
        gx = ml + ci * gw
        o.append('<text x="%.1f" y="%d" text-anchor="middle">%s</text>' % (gx + gw / 2, h - mb + 16, _e(c)))
        for si, (name, vs) in enumerate(series.items()):
            v = vs[ci]
            bh = max(0.0, ph * f(v))
            x = gx + gw * 0.1 + si * bw
            o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"><title>%s %s: %.2f</title></rect>' %
                     (x, mt + ph - bh, bw, bh, COLORS.get(name, "#555"), _e(LABELS.get(name, name)), _e(c), v))
    lx = ml
    for name in series:
        o.append('<rect x="%d" y="%d" width="10" height="10" fill="%s"/><text x="%d" y="%d">%s</text>' %
                 (lx, h - 22, COLORS.get(name, "#555"), lx + 14, h - 13, _e(LABELS.get(name, name))))
        lx += 130
    o.append("</svg>")
    return "".join(o)


def svg_lines(title, series, xlabel, ylabel, w=760, h=330, log=False):
    import math
    ml, mr, mt, mb = 60, 20, 40, 60
    pw, ph = w - ml - mr, h - mt - mb
    pts = [p for s in series.values() for p in s]
    if not pts:
        return ""
    xmin, xmax = min(p[0] for p in pts), max(p[0] for p in pts)
    ymax = max(max(p[1] for p in pts), 1e-9)
    if log:
        lo, hi = 1.0, 10 ** math.ceil(math.log10(max(ymax, 10)))
        fy = lambda v: (math.log10(max(v, lo)) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))
        yt = [10 ** i for i in range(int(math.log10(hi)) + 1)]
    else:
        hi = ymax * 1.1
        fy = lambda v: v / hi
        yt = [hi * i / 5 for i in range(6)]
    fx = lambda v: (v - xmin) / (xmax - xmin or 1)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;font-family:sans-serif;font-size:11px">' % (w, h, w),
         '<text x="%d" y="22" font-size="14" font-weight="bold">%s</text>' % (ml, _e(title))]
    for t in yt:
        y = mt + ph * (1 - fy(t))
        o.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#ddd"/><text x="%d" y="%.1f" text-anchor="end">%s</text>' %
                 (ml, y, w - mr, y, ml - 5, y + 4, "%.4g" % t))
    for i in range(6):
        xv = xmin + (xmax - xmin) * i / 5
        o.append('<text x="%.1f" y="%d" text-anchor="middle">%.4g</text>' % (ml + pw * fx(xv), h - mb + 16, xv))
    o.append('<text x="%d" y="%d" text-anchor="middle">%s</text>' % (ml + pw // 2, h - mb + 34, _e(xlabel)))
    o.append('<text x="14" y="%d" transform="rotate(-90 14 %d)" text-anchor="middle">%s</text>' % (mt + ph // 2, mt + ph // 2, _e(ylabel)))
    lx = ml
    for name, s in series.items():
        d = " ".join("%s%.1f,%.1f" % ("M" if i == 0 else "L", ml + pw * fx(x), mt + ph * (1 - fy(y))) for i, (x, y) in enumerate(s))
        o.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, COLORS.get(name, "#555")))
        o.append('<rect x="%d" y="%d" width="10" height="10" fill="%s"/><text x="%d" y="%d">%s</text>' %
                 (lx, h - 22, COLORS.get(name, "#555"), lx + 14, h - 13, _e(LABELS.get(name, name))))
        lx += 130
    o.append("</svg>")
    return "".join(o)


def scenario_table_md(res):
    lines = ["### %s" % res["title"], "", res["desc"], "",
             "| Scheduler | Class | Sent | Loss % | Delay avg ms | p99 ms | Jitter ms | Thr kbps | SLA |",
             "|---|---|---:|---:|---:|---:|---:|---:|:--:|"]
    for s, run in res["runs"].items():
        for c in CLASS_ORDER:
            m, v = run["summary"][c], run["sla"][c]
            sla = "-" if c == "best_effort" else ("PASS" if v["pass"] else "FAIL")
            lines.append("| %s | %s | %d | %.2f | %.1f | %.1f | %.1f | %.0f | %s |" %
                         (LABELS.get(s, s), c, m["sent"], m["loss_pct"], m["delay_avg_ms"],
                          m["delay_p99_ms"], m["jitter_ms"], m["throughput_kbps"], sla))
    if any("recovery_ms" in r for r in res["runs"].values()):
        lines += ["", "Recovery time (ms until emergency delay < 100 ms after failure ends): " +
                  ", ".join("%s=%.0f" % (LABELS.get(s, s), r["recovery_ms"]) for s, r in res["runs"].items() if "recovery_ms" in r)]
    return "\n".join(lines) + "\n"


def to_csv(all_results):
    rows = ["scenario,scheduler,class,sent,delivered,loss_pct,delay_avg_ms,delay_p50_ms,delay_p95_ms,delay_p99_ms,delay_max_ms,jitter_ms,offered_kbps,throughput_kbps,sla_pass"]
    for sid, res in all_results.items():
        for s, run in res["runs"].items():
            for c in CLASS_ORDER:
                m = run["summary"][c]
                rows.append("%s,%s,%s,%d,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.1f,%.1f,%s" % (
                    sid, s, c, m["sent"], m["delivered"], m["loss_pct"], m["delay_avg_ms"], m["delay_p50_ms"],
                    m["delay_p95_ms"], m["delay_p99_ms"], m["delay_max_ms"], m["jitter_ms"], m["offered_kbps"],
                    m["throughput_kbps"], "" if c == "best_effort" else run["sla"][c]["pass"]))
    return "\n".join(rows) + "\n"


def scenario_html(res):
    runs = res["runs"]
    out = ["<section><h2>%s</h2><p>%s</p>" % (_e(res["title"]), _e(res["desc"]))]
    out.append("<table><tr><th>Scheduler</th>" + "".join("<th>%s</th>" % c for c in CLASS_ORDER[:3]) + "<th>Recovery</th></tr>")
    for s, run in runs.items():
        cells = ""
        for c in CLASS_ORDER[:3]:
            v = run["sla"][c]
            tip = "; ".join(v["violations"]) or "meets SLA"
            cells += '<td class="%s" title="%s">%s</td>' % ("ok" if v["pass"] else "bad", _e(tip), "PASS" if v["pass"] else "FAIL")
        out.append("<tr><td>%s</td>%s<td>%s</td></tr>" % (_e(LABELS.get(s, s)), cells,
                   ("%.0f ms" % run["recovery_ms"]) if "recovery_ms" in run else "-"))
    out.append("</table>")
    cats = CLASS_ORDER
    out.append(svg_grouped_bar("99th percentile one-way delay (ms, log scale)", cats,
               {s: [r["summary"][c]["delay_p99_ms"] for c in cats] for s, r in runs.items()}, "ms", log=True))
    out.append(svg_grouped_bar("Packet loss (%)", cats,
               {s: [r["summary"][c]["loss_pct"] for c in cats] for s, r in runs.items()}, "%"))
    out.append(svg_grouped_bar("Delivered throughput (kbit/s)", cats,
               {s: [r["summary"][c]["throughput_kbps"] for c in cats] for s, r in runs.items()}, "kbit/s"))
    out.append(svg_grouped_bar("Jitter (mean |delay variation|, ms)", cats,
               {s: [r["summary"][c]["jitter_ms"] for c in cats] for s, r in runs.items()}, "ms"))
    if "recovery_ms" in next(iter(runs.values())):
        out.append(svg_lines("Emergency one-way delay over time (ms, log)",
                   {s: [(t, max(d, 1.0)) for t, d in r["timeline"]["emergency"]] for s, r in runs.items()},
                   "arrival time (s)", "ms", log=True))
    out.append("</section>")
    return "".join(out)


def build_html(all_results, sweep=None, ablation=None, title="QoS-Aware Emergency Traffic Prioritization - Results"):
    css = ("body{font-family:sans-serif;max-width:900px;margin:20px auto;padding:0 12px;color:#222}"
           "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #ccc;padding:4px 10px;text-align:center}"
           "td.ok{background:#d9ead3}td.bad{background:#f4cccc}section{margin-bottom:40px}h2{border-bottom:2px solid #8e44ad}")
    o = ["<!doctype html><html><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body><h1>%s</h1>" % (_e(title), css, _e(title))]
    o.append("<p>SLA targets - emergency: p99 &le; 50 ms, loss &le; 0.1 %; voice: p99 &le; 150 ms, jitter &le; 30 ms, loss &le; 1 %; video: p99 &le; 300 ms, loss &le; 2 %.</p>")
    for res in all_results.values():
        o.append(scenario_html(res))
    if sweep:
        o.append("<section><h2>TC10 - Load sweep</h2><p>Emergency/voice p99 delay as bulk traffic grows from light load to heavy overload.</p>")
        loads = sweep["loads_kbps"]
        o.append(svg_lines("Emergency p99 delay vs. bulk load (ms, log)",
                 {s: list(zip(loads, [max(v, 1.0) for v in r["emergency_p99_ms"]])) for s, r in sweep["runs"].items()}, "bulk offered load (kbit/s)", "ms", log=True))
        o.append(svg_lines("Voice p99 delay vs. bulk load (ms, log)",
                 {s: list(zip(loads, [max(v, 1.0) for v in r["voice_p99_ms"]])) for s, r in sweep["runs"].items()}, "bulk offered load (kbit/s)", "ms", log=True))
        o.append(svg_lines("Best-effort throughput vs. bulk load (kbit/s)",
                 {s: list(zip(loads, r["be_throughput_kbps"])) for s, r in sweep["runs"].items()}, "bulk offered load (kbit/s)", "kbit/s"))
        o.append("</section>")
    if ablation:
        o.append("<section><h2>Classifier ablation (noisy markings)</h2><table><tr><th>Mode</th><th>Accuracy %</th><th>Cache-hit %</th><th>Emergency p99 ms</th><th>Emergency loss %</th></tr>")
        for m, v in ablation.items():
            o.append("<tr><td>%s</td><td>%.2f</td><td>%.2f</td><td>%.1f</td><td>%.2f</td></tr>" % (_e(m), v["accuracy_pct"], v["cache_hit_ratio_pct"], v["emergency_p99_ms"], v["emergency_loss_pct"]))
        o.append("</table></section>")
    o.append("</body></html>")
    return "".join(o)
