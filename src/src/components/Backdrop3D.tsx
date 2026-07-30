/**
 * Backdrop3D — trwała scena 3D: żywy umysł Rady pod całym UI.
 *
 * Konstelacja 9 sygili (agentForms) wokół lustra Syeza — zawsze obecna,
 * oddycha, reaguje na kursor. Widoki UI (tryb Osobisty/Biznesowy, fazy
 * debaty) sterują choreografią kamery przez sceneBus — morfing konstelacji,
 * nigdy płaska podmiana widoku.
 *
 * z-index:-1, pointer-events:none, pauza gdy karta ukryta, budżet GPU
 * (gpuBudget) degraduje cząstki na słabszych maszynach / WKWebView.
 */

import { useEffect, useRef } from "react";
import * as THREE from "three";
import gsap from "gsap";
import { NODE_META } from "@/components/CouncilCircle";
import {
  agentForm,
  syezCore,
  gpuBudget,
  prefersReducedMotion,
  onReducedMotionChange,
} from "@/lib/agentForms";
import { onSceneView, type SceneView } from "@/lib/sceneBus";

const AGENTS = ["Kogit", "Szow", "Kidi", "Tai", "Obver", "Relacjan", "Emojy", "Smaty", "Deega"];

/* Choreografia kamery i formacji per widok — każdy ruch niesie znaczenie */
const PRESETS: Record<SceneView, { z: number; y: number; x: number; r: number; energy: number }> = {
  personal:  { z: 24, y: 1.5, x: 0,   r: 10.5, energy: 0.5 },  // otwarta, oddychająca
  fa2:       { z: 19, y: 3.5, x: 0,   r: 8,    energy: 0.35 }, // ciaśniej, z góry — analiza
  debate:    { z: 30, y: 0.5, x: -6,  r: 13,   energy: 0.8 },  // tło schodzi w bok, energia rośnie
  synthesis: { z: 21, y: 0,   x: -4,  r: 5.5,  energy: 1 },    // konwergencja do lustra
  done:      { z: 23, y: 1,   x: 0,   r: 9,    energy: 0.65 }, // domknięcie — powrót otwartej formy
  idle:      { z: 24, y: 1.5, x: 0,   r: 10.5, energy: 0.45 },
};

let _dot: THREE.CanvasTexture | null = null;
function softDot(): THREE.CanvasTexture {
  if (_dot) return _dot;
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d")!;
  const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  gr.addColorStop(0, "rgba(255,255,255,.9)");
  gr.addColorStop(0.4, "rgba(255,255,255,.22)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
  _dot = new THREE.CanvasTexture(c);
  return _dot;
}

export function Backdrop3D() {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const mount = ref.current;
    if (!mount) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "low-power" });
    } catch { return; }
    const budget = gpuBudget();
    renderer.setPixelRatio(Math.min(budget.dpr, 1.5));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050505, 0.02);
    const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 140);
    camera.position.set(0, 1.5, 24);

    scene.add(new THREE.AmbientLight(0x776644, 0.5));
    const key = new THREE.PointLight(0xd4af6a, 70, 80); key.position.set(6, 8, 8); scene.add(key);
    const rim = new THREE.PointLight(0x4a6a8a, 30, 80); rim.position.set(-8, -4, -6); scene.add(rim);

    const DOT = softDot();

    /* Lustro Syeza */
    const core = syezCore(1);
    const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({
      map: DOT, color: 0xd4af6a, transparent: true, opacity: 0.5,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    coreGlow.scale.set(6, 6, 1);
    core.add(coreGlow);
    scene.add(core);

    /* 9 sygili */
    const sigils = AGENTS.map((name, i) => {
      const color = NODE_META[name]?.stroke ?? "#d4af6a";
      const form = agentForm(name, color, 1.15);
      form.userData = { angle: (i / AGENTS.length) * Math.PI * 2, phase: Math.random() * Math.PI * 2 };
      scene.add(form);
      return form;
    });

    /* Nici — jarzące połączenia sygil → lustro */
    const threads = sigils.map((s) => {
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
      const color = new THREE.Color(NODE_META[AGENTS[sigils.indexOf(s)]]?.stroke ?? "#d4af6a");
      const l = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.1 }));
      scene.add(l);
      return l;
    });

    /* Pył — trzy warstwy głębi */
    const layers: THREE.Points[] = [0.7, 1, 1.5].map((depth) => {
      const N = Math.round(220 * budget.particles);
      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        pos[i * 3] = (Math.random() - 0.5) * 100;
        pos[i * 3 + 1] = (Math.random() - 0.5) * 60;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 50 - depth * 8;
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      const p = new THREE.Points(g, new THREE.PointsMaterial({
        color: 0xd4af6a, size: 0.09 * depth, transparent: true,
        opacity: 0.18 + depth * 0.07, map: DOT,
        blending: THREE.AdditiveBlending, depthWrite: false,
      }));
      scene.add(p);
      return p;
    });

    /* Stan choreografii — GSAP tweenuje, pętla czyta */
    const st = { ...PRESETS.personal, spin: 0 };
    const applyView = (v: SceneView) => {
      const p = PRESETS[v] ?? PRESETS.idle;
      gsap.to(st, { ...p, duration: 1.1, ease: "power3.inOut", overwrite: "auto" });
      if (v === "done") {
        // rozbłysk lustra — synteza domknięta
        gsap.fromTo(coreGlow.material, { opacity: 1.4 }, { opacity: 0.5, duration: 1.6, ease: "power2.out" });
      }
    };
    const offBus = onSceneView(applyView);

    /* Paralaksa */
    const ptr = { x: 0, y: 0 };
    const onMove = (e: PointerEvent) => {
      ptr.x = (e.clientX / innerWidth) * 2 - 1;
      ptr.y = -(e.clientY / innerHeight) * 2 + 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    const resize = () => {
      camera.aspect = innerWidth / innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight);
    };
    resize();
    window.addEventListener("resize", resize);

    const clock = new THREE.Clock();
    let raf = 0;
    let running = true;
    const frame = () => {
      if (!running) return;
      const t = clock.getElapsedTime();
      st.spin = t * 0.04;

      core.rotation.y = t * 0.1;
      const mirror = core.getObjectByName("syez-mirror");
      if (mirror) { mirror.rotation.y = -t * 0.35; mirror.rotation.x = t * 0.2; }
      coreGlow.material.opacity = Math.max(coreGlow.material.opacity * 0.995, (0.35 + st.energy * 0.35) + Math.sin(t * 1.4) * 0.08);
      core.scale.setScalar(1 + Math.sin(t * 1.4) * 0.02 + st.energy * 0.12);

      sigils.forEach((s, i) => {
        const { angle, phase } = s.userData as { angle: number; phase: number };
        const a = angle + st.spin;
        const y = Math.sin(t * 0.6 + phase) * 0.7;
        s.position.set(Math.cos(a) * st.r, y + Math.sin(angle * 2) * 1.1, Math.sin(a) * st.r * 0.55);
        s.rotation.y = t * 0.25 + phase;
        // kursor „budzi" najbliższy sygil
        const ndc = s.position.clone().project(camera);
        const d = Math.hypot(ndc.x - ptr.x, ndc.y - ptr.y);
        const wake = Math.max(0, 1 - d * 2.2);
        s.scale.setScalar(1 + wake * 0.35);

        threads[i].geometry.setFromPoints([s.position, core.position]);
        (threads[i].material as THREE.LineBasicMaterial).opacity =
          0.05 + st.energy * 0.12 + wake * 0.3 + Math.sin(t * 2 + phase) * 0.02;
      });

      layers.forEach((p, i) => {
        p.rotation.y = t * 0.008 * (i + 1);
        p.position.y = Math.sin(t * 0.1 + i) * 0.6;
      });

      camera.position.x += (st.x + ptr.x * 1.6 - camera.position.x) * 0.03;
      camera.position.y += (st.y + ptr.y * 0.9 - camera.position.y) * 0.03;
      camera.position.z += (st.z - camera.position.z) * 0.03;
      camera.lookAt(st.x * 0.4, 0, 0);

      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    };
    // prefers-reduced-motion: renderujemy JEDNĄ klatkę (scena zostaje, ruch nie)
    // i nie startujemy pętli rAF. CSS-owe @media samo tej pętli nie zatrzymywało.
    let reduced = prefersReducedMotion();
    if (reduced) {
      renderer.render(scene, camera);
    } else {
      frame();
    }

    const offReduced = onReducedMotionChange((next) => {
      reduced = next;
      if (reduced) {
        running = false;
        cancelAnimationFrame(raf);
        renderer.render(scene, camera);
      } else if (!document.hidden) {
        running = true;
        clock.getDelta();
        frame();
      }
    });

    const onVis = () => {
      running = !document.hidden && !reduced;
      if (running) { clock.getDelta(); frame(); }
      else cancelAnimationFrame(raf);
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      offBus();
      offReduced();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("resize", resize);
      scene.traverse((o: THREE.Object3D) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      style={{ position: "fixed", inset: 0, zIndex: -1, pointerEvents: "none" }}
    />
  );
}
