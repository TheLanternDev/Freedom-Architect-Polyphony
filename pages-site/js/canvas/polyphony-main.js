/**
 * Główny Canvas — polifonia Rady (9 węzłów, linie napięć, złota synteza).
 */
(function () {
  const GOLD = "#c9a227";
  const GOLD_DIM = "rgba(201, 162, 39, 0.25)";
  const LINE = "rgba(161, 161, 170, 0.18)";
  const NODE = "#1a1b1f";

  function initPolyphonyCanvas(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    let w, h, dpr, nodes, mouse = { x: 0.5, y: 0.5, active: false };
    let t = 0;

    function resize() {
      const rect = canvas.parentElement.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = rect.width;
      const isMobile = window.matchMedia("(max-width: 860px)").matches;
      const minH = isMobile ? 260 : 360;
      const maxH = isMobile ? 380 : 520;
      const ratio = isMobile ? 0.72 : 0.55;
      h = Math.max(minH, Math.min(maxH, w * ratio));
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      buildNodes();
    }

    function buildNodes() {
      const cx = w / 2;
      const cy = h / 2;
      const r = Math.min(w, h) * 0.34;
      const count = 9;
      nodes = Array.from({ length: count }, (_, i) => {
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
        return {
          x: cx + Math.cos(angle) * r,
          y: cy + Math.sin(angle) * r,
          label: ["R", "K", "E", "D", "S", "T", "Sz", "O", "Ki"][i],
          phase: i * 0.7,
        };
      });
    }

    function draw() {
      t += 0.008;
      ctx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;
      const mx = mouse.active ? mouse.x * w : cx;
      const my = mouse.active ? mouse.y * h : cy;

      // Złoty obszar syntezy
      const pulse = 0.85 + Math.sin(t * 2) * 0.08;
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 90 * pulse);
      grad.addColorStop(0, "rgba(201, 162, 39, 0.22)");
      grad.addColorStop(0.5, "rgba(201, 162, 39, 0.06)");
      grad.addColorStop(1, "transparent");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, 95 * pulse, 0, Math.PI * 2);
      ctx.fill();

      // Linie napięć między węzłami + do centrum
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const tension = 0.35 + Math.sin(t + i + j) * 0.15;
          ctx.strokeStyle = LINE;
          ctx.lineWidth = 0.6 + tension * 0.4;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        const n = nodes[i];
        const pull = mouse.active ? 0.15 : 0.08;
        const tx = n.x + (cx - n.x) * pull + (mx - cx) * 0.03 * Math.sin(n.phase + t);
        const ty = n.y + (cy - n.y) * pull + (my - cy) * 0.03 * Math.cos(n.phase + t);
        ctx.strokeStyle = GOLD_DIM;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(n.x, n.y);
        ctx.lineTo(tx, ty);
        ctx.stroke();
      }

      // Węzły
      nodes.forEach((n, i) => {
        const bob = Math.sin(t * 1.5 + n.phase) * 3;
        const nx = n.x + (mouse.active ? (mx - cx) * 0.02 : 0);
        const ny = n.y + bob + (mouse.active ? (my - cy) * 0.02 : 0);
        ctx.fillStyle = NODE;
        ctx.strokeStyle = GOLD_DIM;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(nx, ny, 14, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = GOLD;
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(n.label, nx, ny);
      });

      // Rdzeń syntezy
      ctx.fillStyle = GOLD;
      ctx.beginPath();
      ctx.arc(cx, cy, 5 + Math.sin(t * 3) * 1.5, 0, Math.PI * 2);
      ctx.fill();

      requestAnimationFrame(draw);
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
    draw();
  }

  window.initPolyphonyCanvas = initPolyphonyCanvas;
})();
