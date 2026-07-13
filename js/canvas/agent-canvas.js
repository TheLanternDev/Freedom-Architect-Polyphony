/**
 * Canvas agentów — indywidualne metafory mechanizmu w debacie.
 */
(function () {
  const GOLD = "#c9a227";
  const GOLD_DIM = "rgba(201, 162, 39, 0.3)";
  const MUTED = "rgba(161, 161, 170, 0.2)";

  const MODES = {
    shadow: drawShadow,
    time: drawTime,
    pulse: drawPulse,
    network: drawNetwork,
    structure: drawStructure,
    waves: drawWaves,
    loops: drawLoops,
    lens: drawLens,
    spark: drawSpark,
  };

  function initAgentCanvas(canvasId, mode) {
    const canvas = document.getElementById(canvasId);
    const drawFn = MODES[mode] || drawShadow;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let w, h, dpr, t = 0;
    let mouse = { x: 0.5, y: 0.5, active: false };

    function resize() {
      const rect = canvas.parentElement.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      const isMobile = window.matchMedia("(max-width: 860px)").matches;
      const minH = isMobile ? 220 : 280;
      const maxH = isMobile ? 320 : 400;
      const ratio = isMobile ? 0.58 : 0.65;
      h = Math.max(minH, Math.min(maxH, w * ratio));
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function loop() {
      t += 0.012;
      ctx.clearRect(0, 0, w, h);
      drawFn(ctx, w, h, t, mouse);
      requestAnimationFrame(loop);
    }

    canvas.addEventListener("mousemove", (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = (e.clientX - rect.left) / rect.width;
      mouse.y = (e.clientY - rect.top) / rect.height;
      mouse.active = true;
    });
    canvas.addEventListener("mouseleave", () => { mouse.active = false; });

    resize();
    window.addEventListener("resize", resize);
    loop();
  }

  /** Szow — split + pęknięcie */
  function drawShadow(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    const split = cx + Math.sin(t) * 8 + (mouse.active ? (mouse.x - 0.5) * 40 : 0);

    ctx.fillStyle = "rgba(0,0,0,0.55)";
    ctx.fillRect(0, 0, split, h);

    ctx.fillStyle = "rgba(201, 162, 39, 0.06)";
    ctx.fillRect(split, 0, w - split, h);

    ctx.strokeStyle = GOLD;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let y = 0; y <= h; y += 4) {
      const crack = Math.sin(y * 0.08 + t * 4) * 6 + Math.sin(y * 0.02) * 12;
      if (y === 0) ctx.moveTo(split + crack, y);
      else ctx.lineTo(split + crack, y);
    }
    ctx.stroke();

    ctx.fillStyle = GOLD_DIM;
    ctx.font = "11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("to, co wiesz", w * 0.25, cy);
    ctx.fillText("to, czego nie chcesz", w * 0.75, cy);
  }

  /** Tai — zegary i piasek */
  function drawTime(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    for (let i = 0; i < 3; i++) {
      const r = 40 + i * 28;
      const angle = t * (0.4 + i * 0.15) + (mouse.active ? mouse.x * 0.5 : 0);
      ctx.strokeStyle = GOLD_DIM;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(angle) * r * 0.85, cy + Math.sin(angle) * r * 0.85);
      ctx.stroke();
    }
    // Piasek
    for (let i = 0; i < 40; i++) {
      const px = (i * 17 + t * 30) % w;
      const py = h * 0.75 + Math.sin(i + t * 2) * 8;
      ctx.fillStyle = `rgba(201, 162, 39, ${0.15 + (i % 5) * 0.05})`;
      ctx.fillRect(px, py, 2, 2);
    }
  }

  /** Smaty — pulsujące linie energetyczne */
  function drawPulse(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    const mx = mouse.active ? mouse.x * w : cx;
    const my = mouse.active ? mouse.y * h : cy;

    ctx.strokeStyle = GOLD_DIM;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(cx, cy, 55, 90, 0, 0, Math.PI * 2);
    ctx.stroke();

    for (let i = 0; i < 12; i++) {
      const phase = t * 2 + i * 0.5;
      const amp = 8 + Math.sin(phase) * 6;
      ctx.strokeStyle = `rgba(201, 162, 39, ${0.2 + Math.sin(phase) * 0.15})`;
      ctx.beginPath();
      for (let x = 40; x < w - 40; x += 3) {
        const y = cy + Math.sin(x * 0.04 + phase) * amp + (mx - cx) * 0.01;
        if (x === 40) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  /** Relacjan — sieć relacji */
  function drawNetwork(ctx, w, h, t, mouse) {
    const pts = Array.from({ length: 8 }, (_, i) => ({
      x: w * (0.2 + (i % 4) * 0.2) + Math.sin(t + i) * 6,
      y: h * (0.25 + Math.floor(i / 4) * 0.5) + Math.cos(t + i) * 6,
    }));
    ctx.strokeStyle = MUTED;
    pts.forEach((a, i) => pts.forEach((b, j) => {
      if (i >= j) return;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }));
    pts.forEach((p) => {
      ctx.fillStyle = GOLD;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  /** Kogit — struktura geometryczna */
  function drawStructure(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    const rot = t * 0.2 + (mouse.active ? (mouse.x - 0.5) * 0.5 : 0);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(rot);
    ctx.strokeStyle = GOLD_DIM;
    for (let i = 0; i < 6; i++) {
      const a = (i / 6) * Math.PI * 2;
      const x1 = Math.cos(a) * 70;
      const y1 = Math.sin(a) * 70;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(x1, y1);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(x1, y1, 18, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  /** Emojy — fale prewerbalne */
  function drawWaves(ctx, w, h, t, mouse) {
    for (let layer = 0; layer < 5; layer++) {
      ctx.strokeStyle = `rgba(201, 162, 39, ${0.08 + layer * 0.04})`;
      ctx.beginPath();
      for (let x = 0; x <= w; x += 2) {
        const y = h / 2 + Math.sin(x * 0.02 + t * (1 + layer * 0.3) + layer) * (20 + layer * 8);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  /** Deega — pętle */
  function drawLoops(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    for (let i = 0; i < 4; i++) {
      const r = 30 + i * 22;
      ctx.strokeStyle = GOLD_DIM;
      ctx.setLineDash([4, 6]);
      ctx.beginPath();
      ctx.arc(cx, cy, r, t + i, t + i + Math.PI * 1.6);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  /** Obver — soczewka meta-perspektywy */
  function drawLens(ctx, w, h, t, mouse) {
    const cx = w / 2;
    const cy = h / 2;
    const r = 80;
    ctx.strokeStyle = GOLD_DIM;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = MUTED;
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2 + t * 0.1;
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a) * (r + 10), cy + Math.sin(a) * (r + 10));
      ctx.lineTo(cx + Math.cos(a) * (r + 40), cy + Math.sin(a) * (r + 40));
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(201, 162, 39, 0.08)";
    ctx.beginPath();
    ctx.arc(cx, cy, r * 0.6, 0, Math.PI * 2);
    ctx.fill();
  }

  /** Kidi — iskry ciekawości */
  function drawSpark(ctx, w, h, t, mouse) {
    for (let i = 0; i < 24; i++) {
      const bx = (Math.sin(i * 2.1 + t) * 0.4 + 0.5) * w;
      const by = (Math.cos(i * 1.7 + t * 1.2) * 0.4 + 0.5) * h;
      const size = 2 + Math.sin(t * 3 + i) * 1.5;
      ctx.fillStyle = `rgba(201, 162, 39, ${0.3 + Math.sin(t + i) * 0.2})`;
      ctx.beginPath();
      ctx.arc(bx, by, size, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  window.initAgentCanvas = initAgentCanvas;
})();
