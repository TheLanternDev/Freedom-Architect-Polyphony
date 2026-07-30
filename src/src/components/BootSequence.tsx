/**
 * BootSequence — kinowe uruchomienie z ikony (~2.6 s, pomijalne).
 * Faza 1: pył zbiega do punktu. Faza 2: rdzeń Syeza (realna geometria —
 * icosahedron + siatka + lustro) zapala się ostrym rozbłyskiem.
 * Faza 3: 9 węzłów-głosów materializuje się i spina nićmi w konstelację.
 *
 * Ostrość > mgła: geometria i linie zamiast wielkich miękkich sprite'ów.
 * Skip: klik / Esc / Space / prefers-reduced-motion. Pełny cleanup.
 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import gsap from "gsap";
import { NODE_META } from "@/components/CouncilCircle";
import { syezCore, gpuBudget } from "@/lib/agentForms";

const AGENTS = ["Kogit", "Szow", "Kidi", "Tai", "Obver", "Relacjan", "Emojy", "Smaty", "Deega"];

export function BootSequence({ onDone }: { onDone?: () => void }) {
  const [gone, setGone] = useState(
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (gone) { onDone?.(); return; }
    const mount = mountRef.current;
    if (!mount) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch { setGone(true); onDone?.(); return; }
    const budget = gpuBudget();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 100);
    camera.position.z = 13;

    scene.add(new THREE.AmbientLight(0x776644, 0.6));
    const key = new THREE.PointLight(0xd4af6a, 90, 60);
    key.position.set(5, 6, 7);
    scene.add(key);

    /* Ciasny, ostry punkt świetlny (nie mglisty blob) */
    const c = document.createElement("canvas"); c.width = c.height = 128;
    const x = c.getContext("2d")!;
    const gr = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, "rgba(255,255,255,1)");
    gr.addColorStop(0.22, "rgba(255,255,255,.95)");
    gr.addColorStop(0.45, "rgba(255,255,255,.18)");
    gr.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = gr; x.fillRect(0, 0, 128, 128);
    const DOT = new THREE.CanvasTexture(c);

    /* Faza 1 — pył zbiega do centrum */
    const N = Math.round(600 * budget.particles);
    const pos = new Float32Array(N * 3);
    const start = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(9 + Math.random() * 14);
      start.set([v.x, v.y, v.z], i * 3);
      pos.set([v.x, v.y, v.z], i * 3);
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
      color: 0xd4af6a, size: 0.055, map: DOT, transparent: true, opacity: 0.85,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    scene.add(dust);

    /* Faza 2 — rdzeń Syeza: realna geometria, ostry rozbłysk */
    const core = syezCore(1.15);
    core.scale.setScalar(0.001);
    scene.add(core);
    const flash = new THREE.Sprite(new THREE.SpriteMaterial({
      map: DOT, color: 0xfff3c4, transparent: true, opacity: 0,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    flash.scale.setScalar(0.001);
    scene.add(flash);

    /* Faza 3 — węzły: ostre kule + cienki pierścień, nić do rdzenia */
    const ringR = 5.2;
    const nodes = AGENTS.map((name, i) => {
      const col = new THREE.Color(NODE_META[name]?.stroke ?? "#d4af6a");
      const g = new THREE.Group();
      g.add(new THREE.Mesh(
        new THREE.SphereGeometry(0.17, 20, 20),
        new THREE.MeshBasicMaterial({ color: col }),
      ));
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.28, 0.012, 8, 40),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.7 }),
      );
      ring.rotation.x = Math.PI / 2.6;
      g.add(ring);
      const a = (i / AGENTS.length) * Math.PI * 2 - Math.PI / 2;
      g.userData.target = new THREE.Vector3(Math.cos(a) * ringR, Math.sin(a) * ringR * 0.72, 0);
      g.scale.setScalar(0.001);
      g.visible = false;
      scene.add(g);
      return g;
    });
    const threads = nodes.map((n, i) => {
      const col = new THREE.Color(NODE_META[AGENTS[i]]?.stroke ?? "#d4af6a");
      const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), n.userData.target as THREE.Vector3]);
      const l = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: col, transparent: true, opacity: 0 }));
      scene.add(l);
      return l;
    });

    const state = { t: 0 };
    const tl = gsap.timeline({ onComplete: finish });
    /* zbieg pyłu (0–1.0s) */
    tl.to(state, { t: 1, duration: 1.0, ease: "power3.in" }, 0);
    /* ignicja: błysk krótki i ostry, rdzeń rośnie z geometrią (0.85–1.6s) */
    tl.to(flash.scale, { x: 5, y: 5, z: 1, duration: 0.18, ease: "expo.out" }, 0.9);
    tl.to(flash.material, { opacity: 1, duration: 0.08 }, 0.9);
    tl.to(flash.material, { opacity: 0, duration: 0.35, ease: "power2.out" }, 1.0);
    tl.to(flash.scale, { x: 1.6, y: 1.6, z: 1, duration: 0.35, ease: "power2.out" }, 1.0);
    tl.to(core.scale, { x: 1, y: 1, z: 1, duration: 0.6, ease: "back.out(2.2)" }, 0.95);
    tl.to(dust.material, { opacity: 0, duration: 0.35 }, 0.95);
    /* materializacja 9 głosów + nici (1.35–2.25s) */
    nodes.forEach((g, i) => {
      const t0 = 1.35 + i * 0.065;
      tl.set(g, { visible: true }, t0);
      tl.fromTo(g.position, { x: 0, y: 0, z: 0 },
        { x: (g.userData.target as THREE.Vector3).x, y: (g.userData.target as THREE.Vector3).y, z: 0, duration: 0.65, ease: "back.out(1.5)" }, t0);
      tl.to(g.scale, { x: 1, y: 1, z: 1, duration: 0.4, ease: "expo.out" }, t0 + 0.05);
      tl.to(threads[i].material, { opacity: 0.4, duration: 0.3 }, t0 + 0.45);
    });
    /* fade całości (2.35–2.8s) */
    tl.to(mount, { opacity: 0, duration: 0.45, ease: "power2.inOut" }, 2.35);

    let raf = 0;
    const clock = new THREE.Clock();
    const frame = () => {
      const k = state.t;
      for (let i = 0; i < N; i++) {
        pos[i * 3] = start[i * 3] * (1 - k);
        pos[i * 3 + 1] = start[i * 3 + 1] * (1 - k);
        pos[i * 3 + 2] = start[i * 3 + 2] * (1 - k);
      }
      dustGeo.attributes.position.needsUpdate = true;
      const t = clock.getElapsedTime();
      core.rotation.y = t * 0.5;
      const mirror = core.getObjectByName("syez-mirror");
      if (mirror) { mirror.rotation.y = -t * 1.2; mirror.rotation.x = t * 0.7; }
      nodes.forEach((g, i) => { g.rotation.y = t * 0.8 + i; });
      renderer.render(scene, camera);
      raf = requestAnimationFrame(frame);
    };
    frame();

    function finish() {
      setGone(true);
      onDone?.();
    }
    const skip = () => tl.progress(1);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === " " || e.key === "Enter") skip();
    };
    mount.addEventListener("pointerdown", skip);
    window.addEventListener("keydown", onKey);

    return () => {
      tl.kill();
      cancelAnimationFrame(raf);
      mount.removeEventListener("pointerdown", skip);
      window.removeEventListener("keydown", onKey);
      scene.traverse((o: THREE.Object3D) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((y) => y.dispose());
        else mat?.dispose();
      });
      DOT.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gone]);

  if (gone) return null;
  return (
    <div
      ref={mountRef}
      role="presentation"
      style={{
        position: "fixed", inset: 0, zIndex: 9999, background: "#050505",
        cursor: "pointer",
      }}
    >
      <span style={{
        position: "absolute", bottom: 28, left: "50%", transform: "translateX(-50%)",
        fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase",
        color: "rgba(184,178,164,.5)", fontFamily: "'Space Grotesk',sans-serif",
      }}>
        Rada Nadzorcza · kliknij aby pominąć
      </span>
    </div>
  );
}
