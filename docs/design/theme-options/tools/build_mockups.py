"""Build the three Circuit White theme mockups (SPEC 14.3.4 step 1).

    python docs/design/theme-options/tools/build_mockups.py

Writes docs/design/theme-options/option-{a,b,c}/index.html + style.css.
Every file is self-contained (no network, no fonts, no external images).
Screens are fixed at 1440x900 so the decorative trace overlay can be placed on
exact pixels.
"""

from __future__ import annotations

import pathlib

import pixels as px

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# option definitions
# ---------------------------------------------------------------------------

OPTIONS = {
    "a": {
        "title": "Option A - Silk",
        "tokens": {
            "--cs-board": "#F4FAFC",
            "--cs-panel": "#FFFFFF",
            "--cs-pad": "#E6F7FB",
            "--cs-trace": "#19C3E6",
            "--cs-trace-soft": "#BFEFF9",
            "--cs-trace-deep": "#0A8FB3",
            "--cs-ink": "#0B2A3A",
            "--cs-ink-soft": "#4A6878",
            "--cs-warn": "#E8A317",
            "--cs-error": "#E5484D",
            "--cs-agent": "#7C5CFF",
            "--cs-canvas-surround": "#DCE6EA",
            "--cs-checker-a": "#FFFFFF",
            "--cs-checker-b": "#E3E8EB",
        },
        "layout": dict(P=6, g=6, pal_w=212, tool_w=40, agent_w=316, menu_h=28, ctx_h=36,
                       tl_h=184, status_h=24),
        "notch": 7, "bw": 1, "refdes": False, "palette": "grid", "cell_w": 30, "row_h": 22,
        "zoom": 16,
    },
    "b": {
        "title": "Option B - Schematic",
        "tokens": {
            "--cs-board": "#FFFFFF",
            "--cs-panel": "#FFFFFF",
            "--cs-pad": "#EDF8FB",
            "--cs-trace": "#19C3E6",
            "--cs-trace-soft": "#CDEFF7",
            "--cs-trace-deep": "#077A99",
            "--cs-ink": "#0B2A3A",
            "--cs-ink-soft": "#45606F",
            "--cs-warn": "#E8A317",
            "--cs-error": "#D9434A",
            "--cs-agent": "#6B4CF0",
            "--cs-canvas-surround": "#E1E7EA",
            "--cs-checker-a": "#FFFFFF",
            "--cs-checker-b": "#E4E9EC",
            "--cs-grid": "#B3E2EE",
        },
        "layout": dict(P=12, g=12, pal_w=236, tool_w=36, agent_w=318, menu_h=24, ctx_h=30,
                       tl_h=156, status_h=40),
        "notch": 9, "bw": 1, "refdes": True, "palette": "list", "cell_w": 24, "row_h": 19,
        "zoom": 16,
    },
    "c": {
        "title": "Option C - Solder Mask",
        "tokens": {
            "--cs-board": "#DDF3F8",
            "--cs-panel": "#FFFFFF",
            "--cs-pad": "#EAF8FB",
            "--cs-trace": "#19C3E6",
            "--cs-trace-soft": "#BFEFF9",
            "--cs-trace-deep": "#0A86A8",
            "--cs-ink": "#0B2A3A",
            "--cs-ink-soft": "#43606E",
            "--cs-warn": "#E8A317",
            "--cs-error": "#E5484D",
            "--cs-agent": "#7C5CFF",
            "--cs-canvas-surround": "#D5DEE2",
            "--cs-checker-a": "#FFFFFF",
            "--cs-checker-b": "#E1E7EA",
            "--cs-mask-trace": "#93D2E3",
            "--cs-pad-shade": "#B9DDE6",
        },
        "layout": dict(P=10, g=10, pal_w=216, tool_w=52, agent_w=318, menu_h=30, ctx_h=40,
                       tl_h=190, status_h=26),
        "notch": 10, "bw": 2, "refdes": False, "palette": "grid", "cell_w": 32, "row_h": 22,
        "zoom": 16, "tool_scale": 2,
    },
}

# ---------------------------------------------------------------------------
# shared CSS
# ---------------------------------------------------------------------------

BASE_CSS = r"""
/* ---- shared structure (identical in all three options) ---- */
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1440px;height:900px;overflow:hidden;background:var(--cs-board)}
body{font-family:var(--font-ui);font-size:var(--fs);line-height:1.25;color:var(--cs-ink)}
svg{display:block;shape-rendering:crispEdges;flex:none}
.sprite{image-rendering:pixelated}
button{font:inherit;color:inherit;background:none;border:0;cursor:default}
ul{list-style:none}
code,.mono{font-family:var(--font-mono);font-size:var(--fs-s)}
.ico{--ic1:var(--icon-line);--ic2:var(--icon-accent);--ic3:var(--icon-light);--ic4:var(--cs-panel)}
.app{position:relative;width:1440px;height:900px;display:grid;background:var(--app-bg)}
.traces{position:absolute;left:0;top:0;z-index:0;pointer-events:none}
.app>*:not(.traces){position:relative;z-index:1;min-width:0;min-height:0}
.silk{color:var(--silk);flex:none}
.soft{color:var(--cs-ink-soft)}
.via{--ic1:var(--via-ring);--ic3:var(--via-hole)}

/* panels = IC packages with a notched corner */
.panel{background:var(--cs-panel);border:var(--bw) solid var(--panel-line);display:flex;flex-direction:column;
  --notch-out:var(--cs-board);--notch-line:var(--panel-line);--halo:var(--cs-board)}
.panel.active{--panel-line:var(--panel-line-on);--halo:var(--panel-halo);box-shadow:0 0 0 1px var(--panel-halo)}
.panel>.notch{position:absolute;left:calc(-1 * var(--bw) - 1px);top:calc(-1 * var(--bw) - 1px);z-index:3}
.ph{display:flex;align-items:center;gap:6px;height:var(--ph-h);padding:0 8px 0 calc(var(--notch) + 4px);
  border-bottom:1px solid var(--sep);flex:none;background:var(--ph-bg)}
.ph .grow{flex:1}
.ph .meta{color:var(--cs-ink-soft);font-size:var(--fs-s)}

/* pads */
.pad{display:inline-flex;align-items:center;justify-content:center;gap:4px;background:var(--cs-pad);
  border:var(--pad-bw) solid var(--pad-line);clip-path:var(--chamfer);height:var(--pad-h);padding:0 6px;
  color:var(--cs-ink);white-space:nowrap}
.pad.on{background:var(--pad-on-bg);border-color:var(--cs-trace-deep);color:var(--cs-ink)}
.pad.on .ico{--ic2:var(--cs-trace-deep)}
.pad.icon-only{width:var(--pad-h);padding:0}
.seg{display:inline-flex;gap:2px}

/* menu bar */
.menubar{display:flex;align-items:center;gap:2px;padding:0 10px;background:var(--menu-bg);border-bottom:1px solid var(--menu-line)}
.brand{display:flex;align-items:center;gap:6px;margin-right:12px}
.brand .ico{--ic1:var(--cs-ink);--ic2:var(--cs-trace);--ic3:var(--cs-panel)}
.brand-name{font-weight:700;letter-spacing:.02em}
.menus{display:flex;gap:2px}
.menus span{padding:3px 8px}
.menus span.open{background:var(--cs-pad);box-shadow:inset 0 -2px 0 var(--cs-trace-deep)}
.menu-right{margin-left:auto;display:flex;align-items:center;gap:12px;color:var(--cs-ink-soft);font-size:var(--fs-s)}
.conn{display:flex;align-items:center;gap:4px;color:var(--cs-ink)}
.conn .ico{--ic1:var(--cs-ink);--ic3:var(--cs-agent)}

/* context bar */
.ctxbar{display:flex;align-items:center;gap:14px;padding:0 10px;background:var(--ctx-bg);border-bottom:1px solid var(--menu-line)}
.ctx-tool{display:flex;align-items:center;gap:6px}
.ctx-tool .ico{--ic2:var(--cs-trace-deep)}
.vsep{width:1px;align-self:stretch;margin:6px 0;background:var(--sep)}
.fld{display:flex;align-items:center;gap:6px}
.fld>.lbl{color:var(--cs-ink-soft);font-size:var(--fs-s)}
.val{background:var(--cs-panel);min-width:44px;font-family:var(--font-mono);font-size:var(--fs-s)}
.chk{display:flex;align-items:center;gap:6px}
.box{width:14px;height:14px;border:1px solid var(--cs-ink-soft);background:var(--cs-panel);display:grid;place-items:center}
.box.on{border-color:var(--cs-trace-deep);background:var(--pad-on-bg)}
.box .ico{--ic1:var(--cs-ink)}
.ctx-right{margin-left:auto;display:flex;gap:6px;align-items:center}

/* palette */
.fgbg{display:flex;align-items:center;gap:10px;padding:8px 10px;border-bottom:1px solid var(--sep)}
.fgbg .stack{position:relative;width:46px;height:40px;flex:none}
.fgbg .sw{position:absolute;width:28px;height:28px;border:1px solid var(--cs-ink)}
.fgbg .sw.bg{right:0;bottom:0}
.fgbg .sw.fg{left:0;top:0;box-shadow:0 0 0 1px var(--cs-panel)}
.fgbg dl{display:grid;grid-template-columns:auto 1fr;gap:1px 6px;font-size:var(--fs-s);flex:1}
.fgbg dt{color:var(--cs-ink-soft)}
.checker{background-color:var(--cs-checker-a);
  background-image:linear-gradient(90deg,transparent 4px,var(--cs-checker-a) 4px),linear-gradient(var(--cs-checker-b) 4px,var(--cs-checker-a) 4px);
  background-size:8px 8px}
.swatches{padding:8px 10px}
.swatches.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}
.sw-cell{display:flex;flex-direction:column;gap:2px}
.sw-chip{height:24px;border:1px solid var(--swatch-line);position:relative}
.sw-cell .idx{font-family:var(--font-mono);font-size:var(--fs-s);color:var(--cs-ink-soft);display:flex;justify-content:space-between}
.sw-cell.fg .sw-chip,.sw-row.fg .sw-chip{outline:2px solid var(--cs-trace-deep);outline-offset:1px}
.sw-cell.bg .sw-chip,.sw-row.bg .sw-chip{outline:1px solid var(--cs-ink);outline-offset:1px}
.sw-chip .tag{position:absolute;right:-1px;bottom:-1px}
.sw-cell .idx .u{opacity:1}
.tag{font-family:var(--font-mono);font-size:10px;line-height:12px;padding:0 3px;background:var(--cs-ink);color:var(--cs-panel)}
.tag.ghost{background:var(--cs-panel);color:var(--cs-ink);box-shadow:inset 0 0 0 1px var(--cs-ink)}
.swatches.list{display:flex;flex-direction:column}
.sw-row{display:grid;grid-template-columns:18px 26px 1fr 54px 26px;align-items:center;gap:5px;height:var(--row-h);padding:0 4px;font-size:var(--fs-s)}
.sw-row .sw-chip{height:13px}
.sw-row .sw-chip .tag{font-size:9px;line-height:10px;padding:0 2px;right:-4px;bottom:-3px}
.sw-row .idx{font-family:var(--font-mono);color:var(--cs-ink-soft);text-align:right}
.sw-row .hex{font-family:var(--font-mono);color:var(--cs-ink-soft)}
.sw-row .use{font-family:var(--font-mono);color:var(--cs-ink-soft);min-width:34px;text-align:right}
.sw-row.fg,.sw-row.bg{background:var(--cs-pad)}
.editor{padding:8px 10px;border-top:1px solid var(--sep);margin-top:auto;display:flex;flex-direction:column;gap:6px}
.editor .row{display:flex;align-items:center;gap:6px;font-size:var(--fs-s)}
.editor .row .k{width:14px;color:var(--cs-ink-soft);font-family:var(--font-mono)}
.bar{flex:1;height:10px;background:var(--cs-pad);border:1px solid var(--cs-ink-soft);position:relative}
.bar i{position:absolute;left:0;top:0;bottom:0;background:var(--bar-fill)}
.bar b{position:absolute;top:-3px;width:4px;height:14px;background:var(--cs-ink);margin-left:-2px}
.editor .num{width:28px;text-align:right;font-family:var(--font-mono)}
.hexin{font-family:var(--font-mono);background:var(--cs-panel);justify-content:flex-start;flex:1}
.pal-actions{display:flex;gap:4px;flex-wrap:wrap;padding:8px 10px;border-top:1px solid var(--sep)}

/* document */
.doc{display:flex;flex-direction:column}
.doc-tabs{display:flex;align-items:flex-end;gap:2px;height:var(--tab-h);padding:0 6px 0 calc(var(--notch) + 4px);border-bottom:1px solid var(--sep);background:var(--ph-bg);flex:none}
.dtab{display:flex;align-items:center;gap:6px;height:calc(var(--tab-h) - 4px);padding:0 8px;background:var(--cs-pad);border:1px solid var(--sep);border-bottom:0}
.dtab.on{background:var(--cs-panel);box-shadow:inset 0 2px 0 var(--cs-trace-deep);font-weight:600;height:calc(var(--tab-h) - 2px);margin-bottom:-1px}
.dtab .ico{--ic1:var(--cs-ink-soft)}
.dtab .dot{font-size:var(--fs-s);color:var(--cs-ink-soft)}
.canvas-wrap{flex:1;position:relative;background:var(--cs-canvas-surround);display:grid;place-items:center;overflow:hidden}
.canvas-frame{position:relative;box-shadow:0 0 0 1px var(--canvas-edge)}
.diff-box{position:absolute;border:1px solid var(--cs-agent);box-shadow:0 0 0 1px var(--cs-panel),inset 0 0 0 1px var(--cs-panel)}
.diff-tag{position:absolute;left:-2px;top:-22px;display:flex;align-items:center;gap:4px;height:18px;padding:0 5px 0 2px;
  background:var(--cs-panel);border:1px solid var(--cs-agent);font-size:var(--fs-s);white-space:nowrap}
.diff-tag .ico{--ic1:var(--cs-ink);--ic3:var(--cs-agent)}
.cv-chip{position:absolute;display:flex;align-items:center;gap:6px;padding:2px 6px;background:var(--cs-panel);border:1px solid var(--swatch-line);font-size:var(--fs-s)}

/* toolbar */
.toolbar{display:flex;flex-direction:column;align-items:center;gap:3px;padding:calc(var(--notch) + 4px) 0 6px}
.toolbar .grp{display:flex;flex-direction:column;gap:3px;padding:3px 0;border-bottom:1px solid var(--sep)}
.toolbar .grp:last-child{border-bottom:0}
.tool{position:relative;width:var(--tool-btn);height:var(--tool-btn);display:grid;place-items:center;background:transparent;border:var(--pad-bw) solid transparent;clip-path:var(--chamfer)}
.tool .ico{--ic1:var(--cs-ink);--ic2:var(--cs-ink-soft);--ic3:var(--cs-pad)}
.tool.on{background:var(--pad-on-bg);border-color:var(--cs-trace-deep)}
.tool.on .ico{--ic2:var(--cs-trace-deep);--ic3:var(--cs-panel)}
.tool .key{position:absolute;right:1px;bottom:0;font-family:var(--font-mono);font-size:9px;line-height:10px;color:var(--cs-ink-soft)}
.tooltip{position:absolute;right:calc(100% + 8px);top:50%;transform:translateY(-50%);display:flex;align-items:center;gap:8px;
  background:var(--cs-ink);color:var(--cs-panel);padding:3px 8px;font-size:var(--fs-s);white-space:nowrap;z-index:5}
.tooltip kbd{font-family:var(--font-mono);border:1px solid var(--cs-panel);padding:0 3px}

/* agent panel */
.atabs{display:flex;gap:0;border-bottom:1px solid var(--sep);flex:none;padding:0 6px;height:var(--tab-h);align-items:flex-end}
.atab{display:flex;align-items:center;gap:5px;height:calc(var(--tab-h) - 4px);padding:0 9px;color:var(--cs-ink);border:1px solid transparent;border-bottom:0}
.atab .ico{--ic1:var(--cs-ink)}
.atab.on{background:var(--cs-panel);border-color:var(--sep);box-shadow:inset 0 2px 0 var(--cs-trace-deep);font-weight:600;margin-bottom:-1px;height:calc(var(--tab-h) - 2px)}
.badge{display:inline-flex;align-items:center;gap:2px;font-family:var(--font-mono);font-size:var(--fs-s)}
.badge .ico{--ic1:var(--cs-ink);--ic2:var(--cs-warn)}
.acts{flex:1;overflow:hidden;display:flex;flex-direction:column}
.act{padding:7px 10px 7px 12px;border-bottom:1px solid var(--sep);display:flex;flex-direction:column;gap:3px;position:relative}
.act.sel{background:var(--act-sel-bg)}
.act.sel::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--cs-trace-deep)}
.act-head{display:flex;align-items:center;gap:8px}
.rev{font-family:var(--font-mono);font-size:var(--fs-s);font-weight:700;min-width:24px}
.actor{display:flex;align-items:center;gap:4px;font-size:var(--fs-s)}
.actor.agent .ico{--ic1:var(--cs-ink);--ic3:var(--cs-agent)}
.actor.human .ico{--ic1:var(--cs-ink);--ic3:var(--cs-pad)}
.when{margin-left:auto;font-size:var(--fs-s);color:var(--cs-ink-soft)}
.act-label{font-weight:600}
.act-meta{display:flex;gap:8px;align-items:center;font-size:var(--fs-s);color:var(--cs-ink-soft)}
.op{background:var(--cs-pad);color:var(--cs-ink);padding:0 4px;border:1px solid var(--sep)}
.act-btns{display:flex;gap:4px;margin-top:3px}
.act-btns .ico{--ic1:var(--cs-ink)}
.vsum{flex:none;border-top:1px solid var(--sep);padding:8px 10px;display:flex;flex-direction:column;gap:5px;background:var(--ph-bg)}
.vsum .line{display:flex;align-items:center;gap:6px;font-size:var(--fs-s)}
.vsum .ok .ico{--ic1:var(--cs-ink)}
.vsum .warn .ico{--ic1:var(--cs-ink);--ic2:var(--cs-warn)}

/* timeline */
.tl-head{display:flex;align-items:center;gap:8px}
.transport{display:flex;gap:2px}
.transport .ico{--ic1:var(--cs-ink);--ic2:var(--cs-ink-soft)}
.transport .pad.on .ico{--ic2:var(--cs-trace-deep)}
.legend{display:flex;gap:12px;align-items:center;font-size:var(--fs-s);color:var(--cs-ink-soft)}
.legend span{display:flex;align-items:center;gap:5px;position:relative}
.legend{--cell-w:20px}
.legend .lk{padding-left:11px}
.tl-body{flex:1;display:grid;grid-template-columns:var(--layer-w) 1fr;overflow:hidden}
.layers{border-right:1px solid var(--sep)}
.lrow,.frow{height:var(--row-h);display:flex;align-items:center;border-bottom:1px solid var(--sep-weak)}
.lrow{gap:6px;padding:0 8px;font-size:var(--fs)}
.lrow .ico{--ic1:var(--cs-ink);--ic3:var(--cs-pad)}
.lrow .lname{flex:1}
.lrow .op100{font-family:var(--font-mono);font-size:var(--fs-s);color:var(--cs-ink-soft)}
.lrow.sel{background:var(--act-sel-bg);box-shadow:inset 3px 0 0 var(--cs-trace-deep);font-weight:600}
.lrow.hidden .lname{color:var(--cs-ink-soft);font-style:italic}
.lrow.head,.frow.head{font-size:var(--fs-s);color:var(--cs-ink-soft)}
.frames{position:relative}
.fcell{width:var(--cell-w);height:100%;flex:none;display:grid;place-items:center;border-right:1px solid var(--sep-weak);position:relative}
.frow.head .fcell{font-family:var(--font-mono);flex-direction:column;line-height:1}
.frow.head .fcell.cur{background:var(--cs-ink);color:var(--cs-panel);font-weight:700}
.col-cur{position:absolute;top:0;bottom:0;background:var(--cur-col);pointer-events:none}
.tagrow{position:relative}
.tagspan{position:absolute;top:3px;bottom:3px;display:flex;align-items:center;gap:6px;padding:0 6px;border:1px solid var(--cs-trace-deep);background:var(--cs-pad);
  font-size:var(--fs-s);white-space:nowrap;overflow:hidden}
.tagspan b{font-weight:700}
.cel{display:block}
.cel.e{width:2px;height:2px;background:var(--cs-ink-soft)}
.cel.f{width:9px;height:9px;background:var(--cs-ink)}
.cel.l{width:9px;height:9px;background:var(--cs-panel);border:2px solid var(--cs-ink)}
.cel.l::after{content:"";position:absolute;right:calc(50% + 5px);top:calc(50% - 1px);width:calc(var(--cell-w) - 9px);height:2px;background:var(--cs-ink)}
.fcell.selcel{box-shadow:inset 0 0 0 2px var(--cs-trace-deep)}

/* status bar */
.status{display:flex;align-items:stretch;background:var(--status-bg);border-top:1px solid var(--menu-line);font-size:var(--fs-s)}
.status>div{display:flex;align-items:center;gap:6px;padding:0 10px;border-right:1px solid var(--sep)}
.status .k{color:var(--cs-ink-soft)}
.status .mono{font-size:var(--fs-s)}
.status .sw{width:12px;height:12px;border:1px solid var(--cs-ink)}
.status .ico{--ic1:var(--cs-ink);--ic2:var(--cs-warn)}
.status .push{margin-left:auto;border-left:1px solid var(--sep)}
.status .valid{font-weight:600}

/* motion: signal along the trace to the Activity tab (3 frames, 300 ms) */
.signal path{opacity:0}
.signal path:nth-child(1){animation:sig1 300ms steps(1,end) 1}
.signal path:nth-child(2){animation:sig2 300ms steps(1,end) 1}
.signal path:nth-child(3){animation:sig3 300ms steps(1,end) 1}
@keyframes sig1{0%{opacity:1}33.4%{opacity:0}}
@keyframes sig2{0%{opacity:0}33.4%{opacity:1}66.7%{opacity:0}}
@keyframes sig3{0%{opacity:0}66.7%{opacity:1}100%{opacity:0}}
@media (prefers-reduced-motion: reduce){.signal path{animation:none!important;opacity:0}}
"""

THEME_CSS = {
    # ---------------------------------------------------------------- A
    "a": r"""
/* Option A - Silk: the initial tokens, quiet white board, 1px cyan traces */
:root{
  --font-ui:"Segoe UI","Yu Gothic UI","Meiryo",system-ui,sans-serif;
  --font-mono:"Cascadia Mono","Consolas",monospace;
  --fs:13px;--fs-s:12px;
  --app-bg:var(--cs-board);
  --panel-line:var(--cs-trace);--panel-line-on:var(--cs-trace-deep);--panel-halo:var(--cs-trace-soft);
  --sep:var(--cs-trace-soft);--sep-weak:#E3F5FA;
  --ph-bg:var(--cs-panel);--ph-h:26px;--tab-h:30px;
  --silk:var(--cs-ink-soft);
  --pad-line:var(--cs-trace-soft);--pad-bw:1px;--pad-h:24px;--pad-on-bg:#D2F1F8;
  --chamfer:polygon(1px 0,calc(100% - 1px) 0,calc(100% - 1px) 1px,100% 1px,100% calc(100% - 1px),calc(100% - 1px) calc(100% - 1px),calc(100% - 1px) 100%,1px 100%,1px calc(100% - 1px),0 calc(100% - 1px),0 1px,1px 1px);
  --icon-line:var(--cs-ink);--icon-accent:var(--cs-trace-deep);--icon-light:var(--cs-pad);
  --menu-bg:var(--cs-panel);--ctx-bg:var(--cs-board);--menu-line:var(--cs-trace-soft);--status-bg:var(--cs-panel);
  --swatch-line:#9DB2BC;--bar-fill:var(--cs-trace-soft);
  --act-sel-bg:#EAF8FC;--cur-col:#EAF8FC;--canvas-edge:#9DB2BC;
  --via-ring:var(--cs-trace);--via-hole:var(--cs-board);
  --tool-btn:30px;--layer-w:232px;
}
/* header = a labelled net: silk label, then a 1px trace ending in a square via */
.ph .grow{height:1px;background:var(--cs-trace);margin:0 8px 0 4px;position:relative}
.ph .grow::after{content:"";position:absolute;right:-2px;top:-2px;width:5px;height:5px;border:1px solid var(--cs-trace);background:var(--cs-panel)}
.panel.active .ph .silk{color:var(--cs-ink)}
""",
    # ---------------------------------------------------------------- B
    "b": r"""
/* Option B - Schematic: fab-drawing precision, deep-copper lines, reference designators, dense */
:root{
  --font-ui:"Segoe UI","Yu Gothic UI","Meiryo",system-ui,sans-serif;
  --font-mono:"Cascadia Mono","Consolas",monospace;
  --fs:12px;--fs-s:11px;
  --app-bg:var(--cs-board);
  --panel-line:var(--cs-trace-deep);--panel-line-on:var(--cs-trace-deep);--panel-halo:var(--cs-trace);
  --sep:var(--cs-trace-soft);--sep-weak:#E6F6FA;
  --ph-bg:var(--cs-panel);--ph-h:22px;--tab-h:25px;
  --silk:var(--cs-ink);
  --pad-line:#9CCFDC;--pad-bw:1px;--pad-h:20px;--pad-on-bg:#CFF0F8;
  --chamfer:polygon(1px 0,calc(100% - 1px) 0,calc(100% - 1px) 1px,100% 1px,100% calc(100% - 1px),calc(100% - 1px) calc(100% - 1px),calc(100% - 1px) 100%,1px 100%,1px calc(100% - 1px),0 calc(100% - 1px),0 1px,1px 1px);
  --icon-line:var(--cs-ink);--icon-accent:var(--cs-trace-deep);--icon-light:var(--cs-pad);
  --menu-bg:var(--cs-panel);--ctx-bg:var(--cs-panel);--menu-line:var(--cs-trace-deep);--status-bg:var(--cs-pad);
  --swatch-line:#8FA6B1;--bar-fill:var(--cs-trace-soft);
  --act-sel-bg:#E5F6FB;--cur-col:#E9F7FB;--canvas-edge:var(--cs-ink-soft);
  --via-ring:var(--cs-trace-deep);--via-hole:var(--cs-panel);
  --tool-btn:28px;--layer-w:220px;
}
/* drafting dot grid on the board: 1px dot every 8px, hard stops only */
.app{background-color:var(--cs-board);
  background-image:linear-gradient(90deg,transparent 1px,var(--cs-board) 1px),linear-gradient(var(--cs-grid) 1px,var(--cs-board) 1px);
  background-size:8px 8px;background-position:3px 3px}
.ph{gap:8px}
/* silk-screen printed on the board, outside the component (reference designator + name) */
.gutter-label{position:absolute;left:calc(var(--notch) + 2px);top:-11px;display:flex;align-items:center;gap:4px;color:var(--cs-ink);z-index:4}
.refdes{display:block;background:var(--cs-ink);color:var(--cs-panel);padding:1px 2px}
.refdes .silk{color:var(--cs-panel)}
.gutter-label>.silk{color:var(--cs-ink)}
.toolbar .gutter-label{left:2px}
.toolbar .gutter-label>.silk{display:none}
/* underline tabs */
.atab,.dtab{background:transparent;border:0;box-shadow:none}
.atab.on,.dtab.on{background:transparent;border:0;box-shadow:inset 0 -2px 0 var(--cs-trace-deep);margin-bottom:0}
.atabs,.doc-tabs{background:var(--cs-panel)}
.doc-tabs{padding-left:10px}
/* title block status bar */
.titleblock{border:1px solid var(--cs-trace-deep);margin:0 12px 6px;background:var(--cs-panel)}
.titleblock .tb{flex-direction:column;align-items:flex-start;justify-content:center;gap:3px;padding:0 10px;border-right:1px solid var(--cs-trace-deep)}
.titleblock .tb:last-child{border-right:0}
.titleblock .tb>.silk{color:var(--cs-ink-soft)}
.titleblock .v{display:flex;align-items:center;gap:5px;line-height:1}
.titleblock .push{margin-left:auto;border-left:1px solid var(--cs-trace-deep)}
.panel.active{box-shadow:0 0 0 1px var(--cs-trace)}
.panel.active>.ph{box-shadow:inset 0 2px 0 var(--cs-trace)}
/* rulers / dimension lines around the canvas */
.dim{position:absolute;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:var(--fs-s);color:var(--cs-ink)}
.dim.h{height:9px;border-left:1px solid var(--cs-ink-soft);border-right:1px solid var(--cs-ink-soft)}
.dim.h::before{content:"";position:absolute;left:0;right:0;top:4px;height:1px;background:var(--cs-ink-soft)}
.dim.v{width:9px;border-top:1px solid var(--cs-ink-soft);border-bottom:1px solid var(--cs-ink-soft)}
.dim.v::before{content:"";position:absolute;top:0;bottom:0;left:4px;width:1px;background:var(--cs-ink-soft)}
.dim span{position:relative;background:var(--cs-canvas-surround);padding:0 4px}
.dim.v span{writing-mode:vertical-rl;padding:4px 0}
.ticks{position:absolute;background-image:linear-gradient(90deg,var(--cs-ink-soft) 1px,transparent 1px);background-size:16px 4px;background-repeat:repeat-x}
.ticks.v{background-image:linear-gradient(var(--cs-ink-soft) 1px,transparent 1px);background-size:4px 16px;background-repeat:repeat-y}
.lrow.sel{box-shadow:inset 2px 0 0 var(--cs-trace-deep)}
""",
    # ---------------------------------------------------------------- C
    "c": r"""
/* Option C - Solder Mask: pale cyan mask, routed 2px traces, chunky chips with pins */
:root{
  --font-ui:"Segoe UI","Yu Gothic UI","Meiryo",system-ui,sans-serif;
  --font-mono:"Cascadia Mono","Consolas",monospace;
  --fs:13px;--fs-s:12px;
  --app-bg:var(--cs-board);
  --panel-line:var(--cs-trace);--panel-line-on:var(--cs-trace-deep);--panel-halo:var(--cs-panel);
  --sep:var(--cs-trace-soft);--sep-weak:#E2F5F9;
  --ph-bg:var(--cs-panel);--ph-h:28px;--tab-h:32px;
  --silk:var(--cs-ink);
  --pad-line:var(--cs-pad-shade);--pad-bw:2px;--pad-h:26px;--pad-on-bg:#CDEFF7;
  --chamfer:polygon(2px 0,calc(100% - 2px) 0,calc(100% - 2px) 1px,calc(100% - 1px) 1px,calc(100% - 1px) 2px,100% 2px,100% calc(100% - 2px),calc(100% - 1px) calc(100% - 2px),calc(100% - 1px) calc(100% - 1px),calc(100% - 2px) calc(100% - 1px),calc(100% - 2px) 100%,2px 100%,2px calc(100% - 1px),1px calc(100% - 1px),1px calc(100% - 2px),0 calc(100% - 2px),0 2px,1px 2px,1px 1px,2px 1px);
  --icon-line:var(--cs-ink);--icon-accent:var(--cs-trace-deep);--icon-light:var(--cs-pad);
  --menu-bg:var(--cs-panel);--ctx-bg:var(--cs-panel);--menu-line:var(--cs-trace);--status-bg:var(--cs-panel);
  --swatch-line:#97ADB8;--bar-fill:var(--cs-trace-soft);
  --act-sel-bg:#E6F7FB;--cur-col:#E9F8FB;--canvas-edge:#97ADB8;
  --via-ring:var(--cs-trace);--via-hole:var(--cs-board);
  --tool-btn:34px;--layer-w:236px;
}
/* chunky pads: 2px bottom/right edge reads as a raised pixel key (flat colours only) */
.pad{border-color:var(--cs-pad) var(--cs-pad-shade) var(--cs-pad-shade) var(--cs-pad)}
.pad.on{border-color:var(--cs-trace-deep)}
.menubar,.ctxbar,.status{border-color:var(--cs-trace)}
.ctxbar{border-bottom:2px solid var(--cs-trace)}
.menubar{border-bottom:0}
.status{border-top:2px solid var(--cs-trace)}
/* DIP pins along both sides of the tool chip */
.pins{position:absolute;left:calc(-1 * var(--bw) - 5px);width:4px;top:24px;bottom:24px;
  background-image:linear-gradient(var(--cs-trace-deep) 4px,transparent 4px);background-size:4px 12px;background-repeat:repeat-y;z-index:0}
.pins.bottom{left:auto;right:calc(-1 * var(--bw) - 5px)}
/* chip marking: header strips are filled; the powered (active) chip is solid cyan with ink text */
.ph{background:var(--cs-trace-soft);border-bottom:2px solid var(--panel-line)}
.panel.active>.ph{background:var(--cs-trace);border-bottom-color:var(--cs-trace-deep)}
.panel.active>.ph .meta{color:var(--cs-ink)}
.panel.active>.ph .via{--via-hole:var(--cs-trace);--via-ring:var(--cs-ink)}
.ph .via{--via-hole:var(--cs-trace-soft);--via-ring:var(--cs-trace-deep)}
.atabs{background:var(--cs-panel);gap:3px;padding-top:4px}
.atab{background:var(--cs-pad);border:2px solid var(--cs-pad-shade);border-bottom:0;padding:0 7px}
.atab.on{background:var(--cs-panel);border-color:var(--cs-trace-deep);box-shadow:none}
.dtab{border:2px solid var(--cs-pad-shade);border-bottom:0}
.dtab.on{border-color:var(--cs-trace-deep);box-shadow:none}
.doc-tabs{background:var(--cs-trace-soft);border-bottom:2px solid var(--panel-line)}
.silkplate{display:flex;align-items:center;gap:5px}

.tool{border-color:transparent}
.tool.on{border-color:var(--cs-trace-deep)}
""",
}


# ---------------------------------------------------------------------------
# HTML pieces
# ---------------------------------------------------------------------------

I = px.icon


def refdes_label(refdes: str, text: str) -> str:
    return f'<div class="gutter-label"><span class="refdes">{px.silk(refdes)}</span>{px.silk(text)}</div>'


def silk_label(cfg, refdes: str, text: str) -> str:
    if cfg["refdes"]:
        return refdes_label(refdes, text)
    if cfg["key"] == "c":
        return f'<span class="silkplate">{px.via()}{px.silk(text)}</span>'
    return f'{px.via(big=False)}{px.silk(text)}'


def panel_open(cfg, cls: str, style: str, active=False, pins=False) -> str:
    a = " active" if active else ""
    pin_html = ""
    if pins:
        pin_html = '<i class="pins"></i><i class="pins bottom"></i>'
    return (f'<section class="panel {cls}{a}" style="{style}">{pin_html}'
            f'{px.notch_svg(cfg["notch"], cfg["bw"])}')


def menubar(cfg):
    menus = "".join(f'<span{" class=open" if m == "" else ""}>{m}</span>'
                    for m in ["File", "Edit", "Sprite", "Layer", "Frame", "Select", "View", "Agent", "Help"])
    return f"""<header class="menubar" style="grid-area:menu">
  <div class="brand">{I("chip", label="CyberSprite")}<span class="brand-name">CyberSprite</span></div>
  <nav class="menus">{menus}</nav>
  <div class="menu-right"><span>~/art/hero_walk.csprite</span>
    <span class="conn">{I("agent")}MCP: agent:claude-code connected</span></div>
</header>"""


def ctxbar(cfg):
    return f"""<div class="ctxbar" style="grid-area:ctx">
  <div class="ctx-tool">{I("pencil")}{px.silk("PENCIL")}</div>
  <div class="vsep"></div>
  <div class="fld"><span class="lbl">Brush size</span>
    <div class="seg"><button class="pad icon-only">{I("minus", label="smaller")}</button><span class="pad val">1 px</span><button class="pad icon-only">{I("plus", label="larger")}</button></div></div>
  <div class="fld"><span class="lbl">Shape</span>
    <div class="seg"><button class="pad on">{I("brush-square")}Square</button><button class="pad">{I("brush-round")}Round</button></div></div>
  <label class="chk"><span class="box on">{I("check")}</span>Pixel perfect</label>
  <div class="vsep"></div>
  <div class="fld"><span class="lbl">Ink</span><span class="pad">FG #7</span></div>
  <div class="ctx-right">
    <button class="pad on">{I("grid")}Grid</button>
    <button class="pad on">{I("onion")}Onion skin</button>
    <span class="pad val">1600%</span>
  </div>
</div>"""


USAGE = px.sprite_usage()


def swatch_bg(idx):
    col = px.PALETTE[idx][0]
    if col is None:
        return 'class="sw-chip checker"'
    return f'class="sw-chip" style="background:{col}"'


def palette_panel(cfg, style):
    fg, bg = 7, 0
    out = [panel_open(cfg, "palette", style)]
    out.append(f'<div class="ph">{silk_label(cfg, "U1", "PALETTE")}<span class="grow"></span>'
               f'<span class="meta">17 / 256</span><button class="pad icon-only" title="Freeze palette (off)">{I("unlock", label="palette not frozen")}</button></div>')
    out.append(f"""<div class="fgbg">
  <div class="stack"><span class="sw bg checker"></span><span class="sw fg" style="background:{px.PALETTE[fg][0]}"></span></div>
  <dl><dt>FG</dt><dd><b>#{fg}</b> trace-cyan</dd><dt>BG</dt><dd><b>#{bg}</b> transparent</dd></dl>
  <button class="pad icon-only" title="Swap (X)">{I("swap", label="swap")}</button>
</div>""")
    if cfg["palette"] == "grid":
        cells = []
        for i, (col, name) in enumerate(px.PALETTE):
            cls = " fg" if i == fg else (" bg" if i == bg else "")
            tag = '<span class="tag">FG</span>' if i == fg else ('<span class="tag ghost">BG</span>' if i == bg else "")
            cells.append(f'<div class="sw-cell{cls}"><span {swatch_bg(i)}>{tag}</span>'
                         f'<span class="idx"><span>{i:02d}</span></span></div>')
        out.append(f'<div class="swatches grid">{"".join(cells)}</div>')
    else:
        rows = []
        for i, (col, name) in enumerate(px.PALETTE):
            cls = " fg" if i == fg else (" bg" if i == bg else "")
            tag = '<span class="tag">FG</span>' if i == fg else ('<span class="tag ghost">BG</span>' if i == bg else "")
            hexs = (col or "#00000000")[1:]
            rows.append(f'<div class="sw-row{cls}"><span class="idx">{i}</span><span {swatch_bg(i)}>{tag}</span>'
                        f'<span>{name}</span><span class="hex">{hexs}</span><span class="use">{USAGE.get(i, 0)}</span></div>')
        out.append(f'<div class="swatches list">{"".join(rows)}</div>')
    r, g, b = 0x22, 0xB4, 0xD8
    bars = "".join(
        f'<div class="row"><span class="k">{k}</span><span class="bar"><i style="width:{v * 100 // 255}%"></i>'
        f'<b style="left:{v * 100 // 255}%"></b></span><span class="num">{v}</span></div>'
        for k, v in (("R", r), ("G", g), ("B", b)))
    out.append(f"""<div class="editor">
  <div class="row"><span class="k">#</span><span class="pad hexin">22B4D8</span><span class="soft">used {USAGE.get(fg, 0)} px</span></div>
  {bars}
</div>
<div class="pal-actions"><button class="pad">{I("plus")}Add</button><button class="pad">{I("minus")}Remove</button><button class="pad">Load</button><button class="pad">Save</button></div>
</section>""")
    return "".join(out)


def doc_panel(cfg, style, doc_w, main_h):
    zoom = cfg["zoom"]
    spr = px.sprite_svg(zoom)
    # the latest agent commit (r13) touched the helmet highlight: canvas px (6..25, 5..8)
    bx, by, bw_, bh = 6 * zoom, 5 * zoom, 20 * zoom, 4 * zoom
    extra = ""
    if cfg["key"] == "b":
        size = 32 * zoom
        extra = (f'<div class="dim h" style="left:0;top:-22px;width:{size}px"><span>32 px</span></div>'
                 f'<div class="dim v" style="left:-22px;top:0;height:{size}px"><span>32 px</span></div>'
                 f'<div class="ticks" style="left:0;top:-6px;width:{size + 1}px;height:4px"></div>'
                 f'<div class="ticks v" style="left:-6px;top:0;height:{size + 1}px;width:4px"></div>')
    return f"""{panel_open(cfg, "doc", style)}
<div class="doc-tabs">
  {refdes_label("U2", "CANVAS") if cfg["refdes"] else ""}<div class="dtab on">hero_walk.csprite <span class="dot">r13</span>{I("close", label="close")}</div>
  <div class="dtab">ui_icons.csprite {I("close", label="close")}</div>
</div>
<div class="canvas-wrap">
  <div class="canvas-frame">{spr}
    <div class="diff-box" style="left:{bx - 1}px;top:{by - 1}px;width:{bw_ + 2}px;height:{bh + 2}px">
      <span class="diff-tag">{I("agent")}r13 · 42 px changed</span></div>{extra}
  </div>
  <div class="cv-chip" style="left:10px;bottom:10px">frame <b>2</b> · layer <b>body</b> · walk</div>
  <div class="cv-chip" style="right:10px;bottom:10px">{I("grid")}grid 1 px · 16×</div>
</div>
</section>"""


TOOLS = [
    [("pencil", "Pencil", "B"), ("eraser", "Eraser", "E")],
    [("line", "Line", "L"), ("rect", "Rectangle", "U"), ("ellipse", "Ellipse", "⇧U")],
    [("fill", "Fill", "G"), ("eyedropper", "Eyedropper", "I")],
    [("select", "Rectangle select", "M"), ("move", "Move", "V")],
    [("hand", "Hand", "Space"), ("zoom", "Zoom", "Z")],
]


def toolbar(cfg, style):
    groups = []
    for grp in TOOLS:
        btns = []
        for name, label, key in grp:
            on = " on" if name == "pencil" else ""
            tip = ""
            if name == "fill":
                tip = f'<span class="tooltip">{label}<kbd>{key}</kbd></span>'
            size = 16 * cfg.get("tool_scale", 1)
            btns.append(f'<button class="tool{on}" title="{label} ({key})">{I(name, size=size, label=label)}{tip}</button>')
        groups.append(f'<div class="grp">{"".join(btns)}</div>')
    lab = refdes_label("U3", "TOOLS") if cfg["refdes"] else ""
    return f"""{panel_open(cfg, "toolbar", style, pins=cfg["key"] == "c")}{lab}{"".join(groups)}</section>"""


ACTIVITY = [
    ("r13", "agent", "agent:claude-code", "just now", "Shade helmet highlight", "draw_pixels", "f0–f3", "42 px", True),
    ("r12", "human", "gui", "2 min", "Fix left eye pixel", "stroke", "f2", "3 px", False),
    ("r11", "agent", "agent:claude-code", "4 min", "Add walk tag", "add_tag", "tag walk", "0–5", False),
    ("r10", "agent", "agent:claude-code", "4 min", "Outline pass, all frames", "outline", "f0–f5", "118 px", False),
]


def agent_panel(cfg, style):
    rows = []
    for rev, kind, who, when, label, op, frames, n, sel in ACTIVITY:
        btns = ""
        if sel:
            btns = (f'<div class="act-btns"><button class="pad">{I("diff")}Show diff</button>'
                    f'<button class="pad">{I("revert")}Revert to here</button></div>')
        rows.append(f"""<li class="act{" sel" if sel else ""}">
  <div class="act-head"><span class="rev">{rev}</span><span class="actor {kind}">{I(kind, label=kind)}{who}</span><span class="when">{when}</span></div>
  <div class="act-label">{label}</div>
  <div class="act-meta"><code class="op">{op}</code><span>{frames}</span><span>{n}</span></div>{btns}
</li>""")
    return f"""{panel_open(cfg, "agent", style, active=True)}
<div class="ph">{silk_label(cfg, "U4", "AGENT")}<span class="grow"></span><span class="meta">auto-follow on</span></div>
<div class="atabs">
  <div class="atab on">Activity</div>
  <div class="atab">Validate <span class="badge">{I("warn", label="warning")}1</span></div>
  <div class="atab">{I("diff")}Diff</div>
  <div class="atab">{I("source")}Sources</div>
</div>
<ul class="acts">{"".join(rows)}</ul>
<div class="vsum">
  <div class="line ok">{I("check", label="ok")}<b>Validate: ok</b><span class="soft">0 errors · 1 warning · 2 info</span></div>
  <div class="line warn">{I("warn", label="warning")}<code>Q-PIX-01</code><span>3 orphan pixels in frame 3 (limit 2)</span></div>
</div>
</section>"""


LAYERS = [
    ("fx", False, False, "EEEEFEEEEE"),
    ("outline", True, False, "FFFFFFFLLL"),
    ("body", True, False, "FFFFFFFLLL"),
    ("shade", True, False, "FFLLFFFLLL"),
    ("bg", True, True, "FLLLLLLLLL"),
]


def timeline(cfg, style):
    cw = cfg["cell_w"]
    nfr = 10
    cur = 2
    lrows = [f'<div class="lrow head">Tags</div>',
             f'<div class="lrow head"><span class="lname">Layers</span><span>opacity</span></div>']
    frows = []
    # tag band
    tags = (f'<div class="tagspan" style="left:1px;width:{6 * cw - 3}px"><b>walk</b><span>forward · loop</span></div>'
            f'<div class="tagspan" style="left:{6 * cw + 1}px;width:{4 * cw - 3}px"><b>idle</b><span>ping-pong</span></div>')
    frows.append(f'<div class="frow tagrow">{tags}</div>')
    heads = "".join(f'<div class="fcell{" cur" if i == cur else ""}">{i}<small style="font-size:9px">100</small></div>' for i in range(nfr))
    frows.append(f'<div class="frow head">{heads}</div>')
    for name, vis, lock, states in LAYERS:
        sel = name == "body"
        cls = " sel" if sel else ""
        cls += "" if vis else " hidden"
        eye = I("eye", label="visible") if vis else I("eye-off", label="hidden")
        lk = I("lock", label="locked") if lock else I("unlock", label="unlocked")
        lrows.append(f'<div class="lrow{cls}">{eye}{lk}<span class="lname">{name}</span><span class="op100">{"100" if name != "shade" else "100"}</span></div>')
        cells = []
        for i, s in enumerate(states):
            sc = " selcel" if (sel and i == cur) else ""
            cells.append(f'<div class="fcell{sc}"><i class="cel {s.lower()}"></i></div>')
        frows.append(f'<div class="frow">{"".join(cells)}</div>')
    col = f'<div class="col-cur" style="left:{cur * cw}px;width:{cw}px"></div>'
    legend = (f'<div class="legend"><span><i class="cel f"></i>cel</span>'
              f'<span class="lk"><i class="cel l" style="position:relative"></i>linked</span>'
              f'<span><i class="cel e"></i>empty</span></div>')
    return f"""{panel_open(cfg, "timeline", style)}
<div class="ph tl-head">{silk_label(cfg, "J1", "TIMELINE")}
  <div class="transport">
    <button class="pad icon-only">{I("first", label="first frame")}</button>
    <button class="pad icon-only">{I("prev", label="previous frame")}</button>
    <button class="pad icon-only">{I("play", label="play")}</button>
    <button class="pad icon-only">{I("next", label="next frame")}</button>
    <button class="pad icon-only">{I("last", label="last frame")}</button>
  </div>
  <span class="pad val">2 / 10</span><span class="pad val">100 ms</span>
  <button class="pad on">{I("loop")}Tag: walk</button>
  <button class="pad on">{I("onion")}Onion ±1</button>
  <span class="grow"></span>{legend}
</div>
<div class="tl-body">
  <div class="layers">{"".join(lrows)}</div>
  <div class="frames">{col}{"".join(frows)}</div>
</div>
</section>"""


def statusbar(cfg):
    if cfg["key"] == "b":
        def cell(label, value, cls=""):
            return f'<div class="tb{cls}">{px.silk(label)}<span class="v">{value}</span></div>'
        return f"""<footer class="status titleblock" style="grid-area:status">
  {cell("CURSOR", '<span class="mono">x 14 · y 11</span>')}
  {cell("INDEX", '<span class="sw" style="background:#22B4D8"></span><span class="mono">#7 22B4D8</span>')}
  {cell("SIZE", '<span class="mono">32×32</span>')}
  {cell("SCALE", '<span class="mono">16:1</span>')}
  {cell("REV", '<span class="mono">r13</span><span class="soft">saved</span>')}
  {cell("CHECK", f'{I("check", label="valid")}<b>Valid</b>{I("warn", label="warning")}1 warning')}
  {cell("DRAWN BY", f'{I("agent")}agent:claude-code', " push")}
  {cell("SHEET", '<b>hero_walk</b><span class="soft">frame 2 / 10</span>')}
</footer>"""
    return f"""<footer class="status" style="grid-area:status">
  <div><span class="k">x</span><span class="mono">14</span><span class="k">y</span><span class="mono">11</span></div>
  <div><span class="sw" style="background:#22B4D8"></span><span class="mono">#7</span><span class="mono soft">22B4D8</span></div>
  <div><span class="k">size</span><span class="mono">32×32</span></div>
  <div><span class="k">zoom</span><span class="mono">1600%</span></div>
  <div><span class="k">revision</span><span class="mono">r13</span><span class="soft">saved</span></div>
  <div class="valid">{I("check", label="valid")}Valid</div>
  <div>{I("warn", label="warning")}1 warning</div>
  <div class="push">{I("agent")}agent:claude-code · last commit r13</div>
</footer>"""


# ---------------------------------------------------------------------------
# decorative traces (board layer under the panels)
# ---------------------------------------------------------------------------


def traces_svg(cfg, geo) -> str:
    k = cfg["key"]
    layers: list[tuple[str, set]] = []
    sig: list[set] = []
    P, g = geo["P"], geo["g"]
    y_top_gap = geo["y_main"] - g // 2 - (1 if g >= 6 else 0)
    vias = []

    if k == "a":
        # one signal trace in the gap above the main row: canvas -> Activity tab
        x0 = geo["x_doc"] + 24
        x1 = geo["x_agent"] + 44
        y = y_top_gap
        layers.append(("var(--cs-trace)", px.trace_pixels([(x0, y), (x1, y)])))
        vias += [(x0 - 2, y - 2), (x1 - 2, y - 2)]
        third = (x1 - x0) // 3
        for i in range(3):
            sig.append(px.trace_pixels([(x0 + i * third, y), (x0 + (i + 1) * third, y)]))
        # a quiet return trace under the timeline
        y2 = geo["y_status"] - g // 2 - 1
        layers.append(("var(--cs-trace-soft)", px.trace_pixels([(P + 30, y2), (geo["x_doc"] + 300, y2)])))
        vias += [(P + 28, y2 - 2), (geo["x_doc"] + 298, y2 - 2)]
    elif k == "b":
        x = geo["x_agent"] - 6
        y_tab = geo["y_main"] + 22 + 12
        y0 = geo["y_main"] + 300
        pts = [(x, y0), (x, y_tab + 4), (x + 4, y_tab), (geo["x_agent"] - 1, y_tab)]
        layers.append(("var(--cs-trace)", px.trace_pixels(pts)))
        vias.append((x - 2, y0))
        sig.append(px.trace_pixels([(x, y0), (x, y0 - 90)]))
        sig.append(px.trace_pixels([(x, y0 - 90), (x, y0 - 180)]))
        sig.append(px.trace_pixels([(x, y0 - 180), (x, y_tab + 4), (x + 4, y_tab), (geo["x_agent"] - 1, y_tab)]))
    else:
        lane_a = lambda base: base + 2  # noqa: E731
        lane_b = lambda base: base + 6  # noqa: E731
        y_g1 = geo["y_main"] - g      # gap between ctx bar and main row
        y_g2 = geo["y_tl"] - g        # gap between main and timeline
        y_g3 = geo["y_status"] - g    # gap between timeline and status
        x_g1 = geo["x_doc"] - g       # palette | doc
        x_g2 = geo["x_tool"] - g      # doc | tools
        x_g3 = geo["x_agent"] - g     # tools | agent
        mt = "var(--cs-mask-trace)"
        # signal path: doc -> agent with a 45-degree lane change
        x0, x1 = geo["x_doc"] + 30, geo["x_agent"] + 46
        pts = [(x0, lane_b(y_g1)), (x0 + 200, lane_b(y_g1)), (x0 + 204, lane_a(y_g1)), (x1, lane_a(y_g1))]
        layers.append(("var(--cs-trace)", px.trace_pixels(pts, 2)))
        vias += [(x0 - 2, lane_b(y_g1) - 1), (x1 - 2, lane_a(y_g1) - 1)]
        seg = [(x0, lane_b(y_g1)), (x0 + 200, lane_b(y_g1))]
        sig.append(px.trace_pixels(seg, 2))
        sig.append(px.trace_pixels([(x0 + 200, lane_b(y_g1)), (x0 + 204, lane_a(y_g1)), (x0 + 420, lane_a(y_g1))], 2))
        sig.append(px.trace_pixels([(x0 + 420, lane_a(y_g1)), (x1, lane_a(y_g1))], 2))
        # vertical buses in the column gaps
        for xg in (x_g1,):
            ys, ye = geo["y_main"] + 40, geo["y_tl"] - g - 30
            layers.append((mt, px.trace_pixels([(xg + 4, ys), (xg + 4, ye)], 2)))
            vias += [(xg + 3, ys - 4), (xg + 3, ye + 1)]
        # horizontal buses with lane changes
        for yg, xs, xe, jog in ((y_g2, P + 40, geo["x_agent"] - 40, P + 420), (y_g3, P + 60, 1440 - P - 80, 900)):
            pts = [(xs, lane_a(yg)), (jog, lane_a(yg)), (jog + 4, lane_b(yg)), (xe, lane_b(yg))]
            layers.append((mt, px.trace_pixels(pts, 2)))
            vias += [(xs - 4, lane_a(yg) - 1), (xe + 1, lane_b(yg) - 1)]
        # second parallel bus under the agent column
        pts = [(geo["x_agent"] + 20, lane_b(y_g2)), (1440 - P - 30, lane_b(y_g2))]
        layers.append((mt, px.trace_pixels(pts, 2)))
        vias += [(geo["x_agent"] + 16, lane_b(y_g2) - 1), (1440 - P - 29, lane_b(y_g2) - 1)]

    parts = []
    for color, pxs in layers:
        parts.append(f'<path style="fill:{color}" d="{px.runs_path(pxs)}"/>')
    for vx, vy in vias:
        ring = {(vx + x, vy + y) for x, y in [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (1, 4), (2, 4), (3, 4)]}
        hole = {(vx + x, vy + y) for x in (1, 2, 3) for y in (1, 2, 3)}
        parts.append(f'<path style="fill:var(--via-ring)" d="{px.runs_path(ring)}"/>')
        parts.append(f'<path style="fill:var(--via-hole)" d="{px.runs_path(hole)}"/>')
    sig_html = "".join(f'<path style="fill:var(--cs-trace-deep)" d="{px.runs_path(s)}"/>' for s in sig)
    return (f'<svg class="traces" width="1440" height="900" aria-hidden="true">{"".join(parts)}'
            f'<g class="signal">{sig_html}</g></svg>')


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------


def geometry(cfg):
    L = cfg["layout"]
    P, g = L["P"], L["g"]
    doc_w = 1440 - 2 * P - L["pal_w"] - L["tool_w"] - L["agent_w"] - 3 * g
    main_h = 900 - L["menu_h"] - L["ctx_h"] - L["tl_h"] - L["status_h"] - 3 * g
    x_doc = P + L["pal_w"] + g
    x_tool = x_doc + doc_w + g
    x_agent = x_tool + L["tool_w"] + g
    y_main = L["menu_h"] + L["ctx_h"] + g
    y_tl = y_main + main_h + g
    y_status = y_tl + L["tl_h"] + g
    return dict(L, doc_w=doc_w, main_h=main_h, x_doc=x_doc, x_tool=x_tool, x_agent=x_agent,
                y_main=y_main, y_tl=y_tl, y_status=y_status)


def build(key: str):
    cfg = dict(OPTIONS[key], key=key)
    geo = geometry(cfg)
    L = cfg["layout"]
    cols = f'{L["P"]}px {L["pal_w"]}px {L["g"]}px {geo["doc_w"]}px {L["g"]}px {L["tool_w"]}px {L["g"]}px {L["agent_w"]}px {L["P"]}px'
    rows = f'{L["menu_h"]}px {L["ctx_h"]}px {L["g"]}px {geo["main_h"]}px {L["g"]}px {L["tl_h"]}px {L["g"]}px {L["status_h"]}px'
    areas = ('"menu menu menu menu menu menu menu menu menu" "ctx ctx ctx ctx ctx ctx ctx ctx ctx" '
             '". . . . . . . . ." ". pal . doc . tool . agent ." ". . . . . . . . ." '
             '". tl tl tl tl tl tl tl ." ". . . . . . . . ." "status status status status status status status status status"')
    tokens = "\n".join(f"  {k}:{v};" for k, v in cfg["tokens"].items())
    css = (f"/* {cfg['title']} - generated by tools/build_mockups.py; tokens first */\n"
           f":root{{\n{tokens}\n  --bw:{cfg['bw']}px;--notch:{cfg['notch']}px;--cell-w:{cfg['cell_w']}px;--row-h:{cfg['row_h']}px;\n}}\n"
           + BASE_CSS + THEME_CSS[key]
           + f".app{{grid-template-columns:{cols};grid-template-rows:{rows};grid-template-areas:{areas}}}\n")
    body = "\n".join([
        menubar(cfg),
        ctxbar(cfg),
        palette_panel(cfg, "grid-area:pal"),
        doc_panel(cfg, "grid-area:doc", geo["doc_w"], geo["main_h"]),
        toolbar(cfg, "grid-area:tool"),
        agent_panel(cfg, "grid-area:agent"),
        timeline(cfg, "grid-area:tl"),
        statusbar(cfg),
    ])
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CyberSprite - Circuit White - {cfg['title']}</title>
<meta name="viewport" content="width=1440">
<link rel="stylesheet" href="style.css">
</head>
<body>
{px.icon_defs()}
<div class="app">
{traces_svg(cfg, geo)}
{body}
</div>
</body>
</html>
"""
    out = ROOT / f"option-{key}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (out / "style.css").write_text(css.lstrip(), encoding="utf-8", newline="\n")
    print("wrote", out)


if __name__ == "__main__":
    for k in OPTIONS:
        build(k)
