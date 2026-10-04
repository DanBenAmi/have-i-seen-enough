/* Have I Seen Enough? — page behaviour and charts.
   Charts are plain SVG drawn at the container's width; every colour comes from
   CSS classes that read the theme tokens, so theme switches need no re-render. */
(function () {
  "use strict";

  /* ------------------------------------------------------------------ data */
  // All values are copied from the paper (tables and figure data files).

  // Table: core representation results (Qwen3-VL-8B).
  var CORE = [
    { src: "HD-EPIC", dag: true, geom: "composite", label: "cue present", units: "520 prefixes", shuffle: 0.524, conf: 0.845, vis: 0.500, ready: 0.985, lo: 0.965, hi: 0.999 },
    { src: "HD-EPIC", dag: true, geom: "matched pair", label: "availability", units: "4,800 windows", shuffle: 0.495, conf: 0.636, vis: 0.495, ready: 0.827, lo: 0.812, hi: 0.840 },
    { src: "NExT-GQA", dag: false, geom: "crossed quad", label: "containment", units: "1,208 quads", shuffle: 0.498, conf: 0.588, vis: 0.500, ready: 0.727, lo: 0.710, hi: 0.745 },
    { src: "NExT-GQA", dag: false, geom: "prefix", label: "onset", units: "5,580 windows", shuffle: 0.502, conf: 0.580, vis: 0.544, ready: 0.733, lo: 0.715, hi: 0.749 },
    { src: "ST-Evidence", dag: false, geom: "prefix", label: "onset", units: "6,546 windows", shuffle: 0.484, conf: 0.589, vis: 0.552, ready: 0.722, lo: 0.706, hi: 0.739 },
    { src: "ST-Evidence-Gen", dag: false, geom: "prefix", label: "onset", units: "4,346 prefixes", shuffle: 0.578, conf: 0.622, vis: 0.651, ready: 0.827, lo: 0.813, hi: 0.840 },
    { src: "Oops!", dag: true, geom: "short window", label: "containment", units: "1,204 windows", shuffle: 0.496, conf: 0.642, vis: 0.654, ready: 0.874, lo: 0.855, hi: 0.892 },
    { src: "ActivityNet", dag: true, geom: "containment window", label: "containment", units: "2,390 windows", shuffle: 0.493, conf: 0.579, vis: 0.517, ready: 0.764, lo: 0.742, hi: 0.787 },
    { src: "HERBench", dag: true, geom: "burst", label: "availability", units: "6,209 bursts", shuffle: 0.498, conf: 0.738, vis: 0.534, ready: 0.918, lo: 0.906, hi: 0.930 }
  ];

  /* --------------------------------------------------------------- helpers */
  var NS = "http://www.w3.org/2000/svg";

  function s(tag, attrs, parent) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, text, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function txt(parent, x, y, str, cls, anchor, extra) {
    var t = s("text", Object.assign({ x: x, y: y, class: cls || "", "text-anchor": anchor || "start" }, extra || {}), parent);
    t.textContent = str;
    return t;
  }
  function lin(d0, d1, r0, r1) {
    var f = function (v) { return r0 + (v - d0) / (d1 - d0) * (r1 - r0); };
    return f;
  }
  function f3(v) { return v.toFixed(3); }
  function ci(lo, hi, fmt) { return "[" + fmt(lo) + ", " + fmt(hi) + "]"; }
  function halo(t) { t.setAttribute("paint-order", "stroke"); t.setAttribute("stroke", "var(--surface)"); t.setAttribute("stroke-width", "4"); t.setAttribute("stroke-linejoin", "round"); return t; }

  // Marker glyphs
  function square(parent, x, y, size, cls) { return s("rect", { x: x - size / 2, y: y - size / 2, width: size, height: size, rx: 2, class: cls }, parent); }
  function diamond(parent, x, y, r, cls) { return s("path", { d: "M" + x + " " + (y - r) + "L" + (x + r) + " " + y + "L" + x + " " + (y + r) + "L" + (x - r) + " " + y + "Z", class: cls }, parent); }
  function cross(parent, x, y, r, cls) { return s("path", { d: "M" + (x - r) + " " + (y - r) + "L" + (x + r) + " " + (y + r) + "M" + (x + r) + " " + (y - r) + "L" + (x - r) + " " + (y + r), class: cls }, parent); }

  /* --------------------------------------------------------------- tooltip */
  function Tooltip(container) {
    var el = h("div", "tooltip", null, container);
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    return {
      show: function (build, x, y) {
        el.textContent = "";
        build(el);
        el.classList.add("show");
        var cw = container.clientWidth, tw = el.offsetWidth, th = el.offsetHeight;
        var left = x + 16;
        if (left + tw > cw) left = x - tw - 16;
        if (left < 0) left = Math.max(0, Math.min(cw - tw, x - tw / 2));
        var top = y - th / 2;
        if (top < -8) top = -8;
        el.style.left = left + "px";
        el.style.top = top + "px";
      },
      hide: function () { el.classList.remove("show"); }
    };
  }
  function ttTitle(el, t, sub) { h("div", "tt-title", t, el); if (sub) h("div", "tt-sub", sub, el); }
  function ttRow(el, color, value, name) {
    var r = h("div", "tt-row", null, el);
    var k = h("span", "tt-key", null, r);
    k.style.background = color || "transparent";
    h("span", "tt-val", value, r);
    h("span", "tt-name", name, r);
  }
  function localPoint(container, evt) {
    var b = container.getBoundingClientRect();
    return { x: evt.clientX - b.left, y: evt.clientY - b.top };
  }

  // Wire a hit element for pointer + keyboard. anchor() returns the {x,y} used on focus.
  function bindHover(node, container, tip, build, anchor, onState) {
    node.setAttribute("tabindex", "0");
    node.addEventListener("pointerenter", function (e) { var p = localPoint(container, e); tip.show(build, p.x, p.y); if (onState) onState(true); });
    node.addEventListener("pointermove", function (e) { var p = localPoint(container, e); tip.show(build, p.x, p.y); });
    node.addEventListener("pointerleave", function () { tip.hide(); if (onState) onState(false); });
    node.addEventListener("focus", function () { var a = anchor(); tip.show(build, a.x, a.y); if (onState) onState(true); });
    node.addEventListener("blur", function () { tip.hide(); if (onState) onState(false); });
  }

  /* ---------------------------------------------------------- table views */
  function buildTable(host, head, rows, numericFrom) {
    if (!host) return;
    host.textContent = "";
    var t = h("table", "data", null, host);
    var thead = h("thead", null, null, t), tr = h("tr", null, null, thead);
    head.forEach(function (c, i) { var th = h("th", i >= numericFrom ? "n" : null, c, tr); th.setAttribute("scope", "col"); });
    var tb = h("tbody", null, null, t);
    rows.forEach(function (r) {
      var row = h("tr", null, null, tb);
      r.forEach(function (c, i) { h("td", i >= numericFrom ? "n" : null, c, row); });
    });
  }

  /* ------------------------------------------------------------ renderers */
  var palette = { ready: "var(--accent)", conf: "var(--conf)", muted: "var(--muted)" };

  // 1. Core results dot plot -------------------------------------------------
  function renderCore(container) {
    var W = container.clientWidth;
    var narrow = W < 620;
    var labelW = narrow ? 0 : 236;
    var rowH = narrow ? 56 : 44;
    var top = 24, bottom = 50, right = 54, left = labelW + 8;
    var H = top + rowH * CORE.length + bottom;
    var x = lin(0.45, 1.0, left, W - right);

    container.textContent = "";
    var svg = s("svg", { width: W, height: H, viewBox: "0 0 " + W + " " + H }, container);
    var tip = Tooltip(container);

    var g = s("g", { class: "grid" }, svg);
    [0.5, 0.6, 0.7, 0.8, 0.9, 1.0].forEach(function (v) {
      s("line", { x1: x(v), x2: x(v), y1: top - 6, y2: H - bottom }, g);
      txt(svg, x(v), H - bottom + 20, v.toFixed(1), "tick", "middle");
    });
    s("line", { x1: x(0.5), x2: x(0.5), y1: top - 10, y2: H - bottom, class: "ref-strong" }, svg);
    txt(svg, x(0.5) + 5, top - 8, "chance", "annot", "start");
    txt(svg, (left + W - right) / 2, H - 8, "Held-out AUROC", "axis-title", "middle");

    var hits = s("g", null, svg);
    var marks = s("g", null, svg);

    CORE.forEach(function (d, i) {
      var y0 = top + i * rowH;
      var cy = narrow ? y0 + 38 : y0 + rowH / 2;
      var hit = s("rect", { x: 0, y: y0, width: W, height: rowH, rx: 6, class: "row-hit" }, hits);
      hit.setAttribute("aria-label", d.src + " " + d.geom + ": readiness " + f3(d.ready) + ", confidence " + f3(d.conf) + ", visual layer-0 " + f3(d.vis) + ", shuffle " + f3(d.shuffle));

      var name = d.src + (d.dag ? "†" : "");
      if (narrow) {
        var t1 = halo(txt(marks, 4, y0 + 17, name, "row-label", "start"));
        var t2 = s("tspan", { class: "row-sub", dx: 6 }, t1); t2.textContent = d.geom + " · " + d.label;
      } else {
        txt(marks, 4, cy - 4, name, "row-label", "start");
        txt(marks, 4, cy + 14, d.geom + " · " + d.label, "row-sub", "start");
      }

      var all = [d.shuffle, d.conf, d.vis, d.ready];
      s("line", { x1: x(Math.min.apply(null, all)), x2: x(d.ready), y1: cy, y2: cy, class: "span" }, marks);
      s("line", { x1: x(d.lo), x2: x(d.hi), y1: cy, y2: cy, class: "ci-ready" }, marks);
      cross(marks, x(d.shuffle), cy, 4, "m-cross");
      diamond(marks, x(d.vis), cy, 6, "m-gray");
      square(marks, x(d.conf), cy, 10, "m-conf");
      s("circle", { cx: x(d.ready), cy: cy, r: 6, class: "m-ready" }, marks);
      txt(marks, x(d.hi) + 7, cy + 4, f3(d.ready), "value", "start");

      bindHover(hit, container, tip, function (el) {
        ttTitle(el, name + " · " + d.geom, d.label + " labels · " + d.units);
        ttRow(el, palette.ready, f3(d.ready) + " " + ci(d.lo, d.hi, f3), "readiness");
        ttRow(el, palette.conf, f3(d.conf), "confidence");
        ttRow(el, palette.muted, f3(d.vis), "visual layer-0");
        ttRow(el, palette.muted, f3(d.shuffle), "shuffle control");
      }, function () { return { x: x(d.ready), y: cy }; });
    });

    buildTable(document.querySelector('[data-table="core"]'),
      ["Source", "Geometry", "Label", "Units", "Shuffle", "Confidence", "Visual L0", "Readiness", "95% CI"],
      CORE.map(function (d) { return [d.src + (d.dag ? "†" : ""), d.geom, d.label, d.units, f3(d.shuffle), f3(d.conf), f3(d.vis), f3(d.ready), ci(d.lo, d.hi, f3)]; }), 4);
  }

  /* ------------------------------------------------------- mount + resize */
  function mount(id, render) {
    var el = document.getElementById(id);
    if (!el) return;
    var lastW = -1, raf = 0;
    function draw() {
      var w = el.clientWidth;
      if (w === lastW || w === 0) return;
      lastW = w;
      render(el);
    }
    draw();
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); }).observe(el);
    } else {
      window.addEventListener("resize", function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(draw); });
    }
  }

  /* ------------------------------------------------------------- page UI */
  function themeUI() {
    var btn = document.getElementById("theme-toggle");
    if (!btn) return;
    var root = document.documentElement;
    var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    btn.addEventListener("click", function () {
      var current = root.getAttribute("data-theme") || (mq && mq.matches ? "dark" : "light");
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
    });
  }

  function navUI() {
    var bar = document.getElementById("topbar");
    var onScroll = function () { if (bar) bar.classList.toggle("scrolled", window.scrollY > 240); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();

    var links = Array.prototype.slice.call(document.querySelectorAll(".topbar nav a"));
    if (!("IntersectionObserver" in window)) return;
    var map = {};
    links.forEach(function (a) { map[a.getAttribute("href").slice(1)] = a; });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && map[en.target.id]) {
          links.forEach(function (a) { a.classList.remove("active"); });
          map[en.target.id].classList.add("active");
        }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    Object.keys(map).forEach(function (id) { var sct = document.getElementById(id); if (sct) io.observe(sct); });
  }

  function copyUI() {
    var btn = document.getElementById("copy-bib"), pre = document.getElementById("bib-text");
    if (!btn || !pre) return;
    btn.addEventListener("click", function () {
      var label = btn.querySelector("span");
      var done = function (ok) { label.textContent = ok ? "Copied" : "Select & copy"; setTimeout(function () { label.textContent = "Copy"; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(pre.textContent).then(function () { done(true); }, function () { done(false); });
      } else {
        var r = document.createRange(); r.selectNodeContents(pre);
        var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(r);
        var ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
        done(ok);
      }
    });
  }

  function init() {
    themeUI();
    navUI();
    copyUI();
    mount("chart-core", renderCore);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
