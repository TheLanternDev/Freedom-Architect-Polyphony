/**
 * Council3D — immersywna sala Rady w WebGL (Three.js + GSAP).
 *
 * Nakładka wizualna na CouncilCircle: te same Props, ten sam panel detalu
 * (AgentDetail / TensionList importowane 1:1 z CouncilCircle), te same
 * statusy i interakcje. Gdy WebGL niedostępny → pełny fallback do
 * oryginalnego CouncilCircle (SVG). Żadna funkcja nie została usunięta.
 *
 * Bezpieczeństwo: tekst agenta renderowany wyłącznie przez AgentDetail
 * (text node), scena 3D nie dotyka treści LLM.
 */

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import gsap from "gsap";
import { useLang } from "@/lib/i18n";
import type { AgentState, LiveTensionPair } from "@/types/debate";
import {
  CouncilCircle,
  NODE_META,
  nodeMeta,
  edgeColor,
  AgentDetail,
  TensionList,
} from "@/components/CouncilCircle";
import {
  agentForm,
  gpuBudget,
  prefersReducedMotion,
  onReducedMotionChange,
} from "@/lib/agentForms";

const AGENT_ORDER = [
  "Kogit", "Szow", "Kidi", "Tai", "Obver", "Relacjan", "Emojy", "Smaty", "Deega",
];

const ORBIT_R = 5.6;

interface Props {
  agents: AgentState[];
  tensions: LiveTensionPair[];
}

function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/* Współdzielona tekstura glow */
let _glow: THREE.CanvasTexture | null = null;
function glowTex(): THREE.CanvasTexture {
  if (_glow) return _glow;
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,.9)");
  gr.addColorStop(0.35, "rgba(255,255,255,.25)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  _glow = new THREE.CanvasTexture(c);
  return _glow;
}

function labelSprite(text: string, color: string): THREE.Sprite {
  const c = document.createElement("canvas");
  c.width = 512; c.height = 128;
  const g = c.getContext("2d")!;
  g.font = '600 46px "Space Grotesk", "DM Sans", sans-serif';
  g.textAlign = "center"; g.textBaseline = "middle";
  g.shadowColor = "rgba(0,0,0,.9)"; g.shadowBlur = 12;
  g.fillStyle = color;
  g.fillText(text, 256, 64);
  const t = new THREE.CanvasTexture(c);
  const s = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false })
  );
  s.scale.set(2.2, 0.55, 1);
  return s;
}

interface OrbRefs {
  name: string;
  group: THREE.Group;
  /** niewidzialny proxy do raycastu — sygil ma nieregularną geometrię */
  orb: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  /** sygil tożsamości (agentForms) */
  form: THREE.Group;
  /** materiały sygilu — sterowanie emisją per status */
  mats: THREE.MeshStandardMaterial[];
  halo: THREE.Sprite;
  ring: THREE.Mesh<THREE.TorusGeometry, THREE.MeshBasicMaterial>;
  pulse: THREE.Sprite;
  angle: number;
  phase: number;
  focus: number;
  intro: number;
}

export function Council3D({ agents, tensions }: Props) {
  const { t } = useLang();
  const [selected, setSelected] = useState<string | null>(null);
  const [glOk] = useState(webglAvailable);
  const mountRef = useRef<HTMLDivElement | null>(null);

  // Żywe dane dla pętli renderującej (bez rekonstrukcji sceny na każdy chunk SSE)
  const liveRef = useRef({ agents, tensions, selected });
  liveRef.current = { agents, tensions, selected };

  const agentMap = new Map(agents.map((a) => [a.name, a]));
  const selectedAgent = selected ? agentMap.get(selected) : null;

  useEffect(() => {
    if (!glOk || !mountRef.current) return;
    const mount = mountRef.current;

    const budget = gpuBudget();
    // antialias sterowany budżetem GPU (review 2026-07-30): Backdrop3D leciał
    // z `antialias: false, powerPreference: "low-power"`, a ta scena z twardym
    // `antialias: true` — dwa konteksty WebGL na jednym ekranie z rozjechanymi
    // ustawieniami. Na słabym GPU (budget.detail === 0) MSAA idzie precz;
    // przy dpr ≥ 2 i tak jest praktycznie niewidoczny.
    const renderer = new THREE.WebGLRenderer({
      antialias: budget.detail > 0 && budget.dpr < 2,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(budget.dpr);
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x050505, 0.03);
    const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    camera.position.set(0, 2.4, 13);

    scene.add(new THREE.AmbientLight(0x776644, 0.55));
    const key = new THREE.PointLight(0xd4af6a, 50, 50);
    key.position.set(4, 6, 6);
    scene.add(key);
    const rim = new THREE.PointLight(0x4a6a8a, 25, 50);
    rim.position.set(-6, -3, -4);
    scene.add(rim);

    const GLOW = glowTex();

    /* Rdzeń — Syez */
    const core = new THREE.Group();
    const coreMesh = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.95, 3),
      new THREE.MeshStandardMaterial({
        color: 0x2a2010, emissive: 0xd4af6a, emissiveIntensity: 0.5,
        roughness: 0.25, metalness: 0.7,
      })
    );
    const coreWire = new THREE.Mesh(
      new THREE.IcosahedronGeometry(1.1, 1),
      new THREE.MeshBasicMaterial({ color: 0xd4af6a, wireframe: true, transparent: true, opacity: 0.26 })
    );
    const coreGlow = new THREE.Sprite(
      new THREE.SpriteMaterial({ map: GLOW, color: 0xd4af6a, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    coreGlow.scale.set(5.6, 5.6, 1);
    const coreLabel = labelSprite("SYEZ", "#f4d896");
    coreLabel.position.y = -1.7;
    core.add(coreMesh, coreWire, coreGlow, coreLabel);
    scene.add(core);

    /* Orby agentów — kolory 1:1 z NODE_META (spójność z SVG i TensionAxis) */
    const present = AGENT_ORDER.filter((n) => liveRef.current.agents.some((a) => a.name === n));
    const orbs: OrbRefs[] = present.map((name, i) => {
      const meta = NODE_META[name] ?? nodeMeta(name);
      const col = new THREE.Color(meta.stroke);
      const group = new THREE.Group();
      const angle = (i / present.length) * Math.PI * 2 - Math.PI / 2;

      // proxy do raycastu (sygile mają nieregularne kształty)
      const orb = new THREE.Mesh(
        new THREE.SphereGeometry(0.5, 8, 8),
        new THREE.MeshBasicMaterial({ visible: false })
      );
      // sygil tożsamości — geometria = charakter głosu
      const form = agentForm(name, meta.stroke, 1);
      const mats: THREE.MeshStandardMaterial[] = [];
      form.traverse((obj: THREE.Object3D) => {
        const mm = (obj as THREE.Mesh).material;
        if (mm instanceof THREE.MeshStandardMaterial) mats.push(mm);
      });
      const halo = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: GLOW, color: col, transparent: true, opacity: 0.5, blending: THREE.AdditiveBlending, depthWrite: false })
      );
      halo.scale.set(2.1, 2.1, 1);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.54, 0.014, 8, 64),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity: 0.45 })
      );
      ring.rotation.x = Math.PI / 2.4;
      // Pierścień pulsu "speaking" (złoty)
      const pulse = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: GLOW, color: 0xd4af6a, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false })
      );
      pulse.scale.set(3.4, 3.4, 1);
      const lbl = labelSprite(name, meta.stroke);
      lbl.position.y = -0.95;

      group.add(orb, form, halo, ring, pulse, lbl);
      scene.add(group);

      const ref: OrbRefs = { name, group, orb, form, mats, halo, ring, pulse, angle, phase: Math.random() * Math.PI * 2, focus: 1, intro: 0 };
      // GSAP — wejście orba (mnożnik, nie nadpisywany przez pętlę)
      gsap.to(ref, { intro: 1, duration: 1.1, delay: 0.15 + i * 0.07, ease: "elastic.out(1,.6)" });
      return ref;
    });

    /* Linie do rdzenia */
    const links = orbs.map(() => {
      const g = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
      const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0xd4af6a, transparent: true, opacity: 0.14 }));
      scene.add(l);
      return l;
    });

    /* Łuki napięć — pula 16 linii (limit jak w SVG), zasilane na żywo */
    const tensionPool = Array.from({ length: 16 }, () => {
      const l = new THREE.Line(
        new THREE.BufferGeometry(),
        new THREE.LineBasicMaterial({ transparent: true, opacity: 0 })
      );
      scene.add(l);
      return l;
    });

    /* Strumień światła SSE: głos płynie agent → lustro Syeza.
       Aktywny gdy agent mówi; po zakończeniu wszystkich — konwergencja syntezy. */
    const FLOW_PER = Math.max(4, Math.round(10 * budget.particles));
    const flowN = orbs.length * FLOW_PER;
    const flowPos = new Float32Array(flowN * 3);
    flowPos.fill(-9999);
    const flowCol = new Float32Array(flowN * 3);
    orbs.forEach((o, i) => {
      const fc = new THREE.Color((NODE_META[o.name] ?? nodeMeta(o.name)).stroke);
      for (let j = 0; j < FLOW_PER; j++) fc.toArray(flowCol, (i * FLOW_PER + j) * 3);
    });
    const flowGeo = new THREE.BufferGeometry();
    flowGeo.setAttribute("position", new THREE.BufferAttribute(flowPos, 3));
    flowGeo.setAttribute("color", new THREE.BufferAttribute(flowCol, 3));
    const flow = new THREE.Points(flowGeo, new THREE.PointsMaterial({
      size: 0.16, vertexColors: true, map: GLOW, transparent: true, opacity: 0.9,
      blending: THREE.AdditiveBlending, depthWrite: false,
    }));
    scene.add(flow);

    /* Pole cząstek */
    {
      const N = Math.round(500 * budget.particles);
      const pos = new Float32Array(N * 3);
      for (let i = 0; i < N; i++) {
        pos[i * 3] = (Math.random() - 0.5) * 50;
        pos[i * 3 + 1] = (Math.random() - 0.5) * 30;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 50;
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      scene.add(new THREE.Points(g, new THREE.PointsMaterial({
        color: 0xd4af6a, size: 0.05, transparent: true, opacity: 0.35,
        map: GLOW, blending: THREE.AdditiveBlending, depthWrite: false,
      })));
    }

    // GSAP — dolly kamery na wejściu
    gsap.from(camera.position, { z: 20, y: 5, duration: 1.6, ease: "power3.out" });

    /* Interakcja */
    const ray = new THREE.Raycaster();
    const ptr = new THREE.Vector2(-9, -9);
    let hovered: OrbRefs | null = null;

    const onMove = (e: PointerEvent) => {
      const r = mount.getBoundingClientRect();
      ptr.x = ((e.clientX - r.left) / r.width) * 2 - 1;
      ptr.y = -((e.clientY - r.top) / r.height) * 2 + 1;
    };
    const onClick = () => {
      if (hovered) {
        const name = hovered.name;
        setSelected((prev) => (prev === name ? null : name));
      }
    };
    mount.addEventListener("pointermove", onMove);
    mount.addEventListener("click", onClick);

    /* Resize */
    const resize = () => {
      const w = mount.clientWidth, h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(mount);

    /* Pętla */
    const clock = new THREE.Clock();
    const v3 = new THREE.Vector3();
    let raf = 0;
    const frame = () => {
      const t0 = clock.getElapsedTime();
      const live = liveRef.current;
      const anySpeaking = live.agents.some((a) => a.status === "speaking" || a.status === "analyzing");
      const allDone = live.agents.length > 0 && live.agents.every((a) => a.status === "done");

      core.rotation.y = t0 * 0.12;
      coreWire.rotation.x = t0 * 0.2;
      coreWire.rotation.z = -t0 * 0.14;
      coreGlow.material.opacity = (allDone ? 1.1 : 0.7) * (0.85 + Math.sin(t0 * 1.6) * 0.1);
      coreMesh.scale.setScalar(1 + (anySpeaking ? Math.sin(t0 * 2.4) * 0.05 : Math.sin(t0 * 1.2) * 0.02));

      orbs.forEach((o, i) => {
        const st = live.agents.find((a) => a.name === o.name);
        const speaking = st?.status === "speaking" || st?.status === "analyzing";
        const done = st?.status === "done";
        const err = st?.status === "error";
        const idle = st?.status === "idle";
        const isSel = live.selected === o.name;

        const a = o.angle + t0 * 0.05;
        const y = Math.sin(t0 * 0.7 + o.phase) * 0.4;
        o.group.position.set(Math.cos(a) * ORBIT_R, y, Math.sin(a) * ORBIT_R * 0.6);

        const target = speaking || isSel ? 1.5 : done ? 1.1 : idle ? 0.85 : 1;
        o.focus = THREE.MathUtils.lerp(o.focus, target, 0.1);
        o.group.scale.setScalar(Math.max(0.001, o.focus * o.intro));

        const dim = idle && !isSel ? 0.35 : 1;
        const emi = (speaking ? 1.2 : done ? 0.75 : 0.45) * dim;
        o.mats.forEach((mm) => {
          mm.emissiveIntensity = emi;
          if (err) mm.emissive.set("#f87171");
        });
        o.form.rotation.y = t0 * (speaking ? 0.8 : 0.25) + o.phase;
        o.halo.material.opacity = (0.4 * o.focus + (speaking ? Math.sin(t0 * 3 + o.phase) * 0.2 : 0)) * dim;
        o.ring.material.opacity = (isSel ? 0.9 : 0.4) * dim;
        o.ring.rotation.z = t0 * (0.4 + i * 0.03);
        o.pulse.material.opacity = speaking ? 0.35 + Math.sin(t0 * 4) * 0.2 : 0;
        o.pulse.material.color.set(done ? "#3A8484" : "#d4af6a");

        links[i].geometry.setFromPoints([o.group.position, core.position]);
        (links[i].material as THREE.LineBasicMaterial).opacity =
          (0.08 + (speaking ? 0.3 : 0) + (isSel ? 0.25 : 0)) * dim + (allDone ? 0.12 : 0);

        /* strumień światła: mówienie = pełny nurt; synteza = cicha konwergencja */
        const flowing = speaking || allDone;
        const speed = speaking ? 0.45 : 0.18;
        for (let j = 0; j < FLOW_PER; j++) {
          const fi = (i * FLOW_PER + j) * 3;
          if (!flowing) { flowPos[fi + 1] = -9999; continue; }
          const k = (t0 * speed + j / FLOW_PER + o.phase) % 1;
          flowPos[fi]     = THREE.MathUtils.lerp(o.group.position.x, 0, k);
          flowPos[fi + 1] = THREE.MathUtils.lerp(o.group.position.y, 0, k)
            + Math.sin(k * Math.PI) * 0.7 + Math.sin(t0 * 3 + j) * 0.07;
          flowPos[fi + 2] = THREE.MathUtils.lerp(o.group.position.z, 0, k);
        }
      });
      flowGeo.attributes.position.needsUpdate = true;

      /* Napięcia na żywo — kolor/grubość wg intensity (logika edgeColor) */
      const byName = new Map(orbs.map((o) => [o.name, o]));
      tensionPool.forEach((l, i) => {
        const p = live.tensions[i];
        const mat = l.material as THREE.LineBasicMaterial;
        if (!p) { mat.opacity = 0; return; }
        const A = byName.get(p.a), B = byName.get(p.b);
        if (!A || !B) { mat.opacity = 0; return; }
        const mid = v3.copy(A.group.position).add(B.group.position).multiplyScalar(0.5);
        mid.y += 1.3;
        const curve = new THREE.QuadraticBezierCurve3(
          A.group.position.clone(), mid.clone(), B.group.position.clone()
        );
        l.geometry.setFromPoints(curve.getPoints(24));
        mat.color.set(edgeColor(p.intensity));
        mat.opacity = 0.25 + p.intensity * 0.5 + Math.sin(t0 * 2.4) * 0.1;
      });

      /* Kamera — subtelna paralaksa */
      camera.position.lerp(v3.set(ptr.x === -9 ? 0 : ptr.x * 1.1, 2.4 - (ptr.y === -9 ? 0 : ptr.y * 0.5), 13), 0.05);
      camera.lookAt(0, 0.1, 0);

      /* Hover */
      ray.setFromCamera(ptr, camera);
      const hits = ray.intersectObjects(orbs.map((o) => o.orb));
      hovered = hits.length ? orbs.find((o) => o.orb === hits[0].object) ?? null : null;
      mount.style.cursor = hovered ? "pointer" : "";

      renderer.render(scene, camera);
      if (!reducedMotion) raf = requestAnimationFrame(frame);
    };

    // prefers-reduced-motion: jedna klatka zamiast pętli rAF (patrz Backdrop3D).
    // Konstelacja Rady zostaje widoczna i klikalna, tylko przestaje się ruszać.
    let reducedMotion = prefersReducedMotion();
    frame();
    const offReduced = onReducedMotionChange((next) => {
      reducedMotion = next;
      cancelAnimationFrame(raf);
      frame(); // przy next=false pętla wznawia się sama w środku frame()
    });

    return () => {
      cancelAnimationFrame(raf);
      offReduced();
      ro.disconnect();
      mount.removeEventListener("pointermove", onMove);
      mount.removeEventListener("click", onClick);
      scene.traverse((obj: THREE.Object3D) => {
        const m = obj as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
        const mat = (m as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
    // Scena montowana raz; dane płyną przez liveRef (SSE nie przebudowuje WebGL).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [glOk]);

  /* Fallback: brak WebGL → oryginalny CouncilCircle (pełna funkcjonalność SVG) */
  if (!glOk) {
    return <CouncilCircle agents={agents} tensions={tensions} />;
  }

  return (
    <div className="flex items-stretch min-h-[420px]">
      {/* ── Scena 3D ── */}
      <div
        ref={mountRef}
        className="flex-1 min-w-0 relative rounded-card overflow-hidden"
        style={{ minHeight: 420 }}
        aria-label="Sala Rady — orkiestracja 3D agentów"
        role="img"
      />

      {/* ── Panel detalu — 1:1 z CouncilCircle ── */}
      <div className="w-[240px] shrink-0 border-l border-border bg-[rgba(9,9,7,0.7)] backdrop-blur-xl flex flex-col overflow-hidden">
        {selectedAgent ? (
          <AgentDetail agent={selectedAgent} t={t} onClose={() => setSelected(null)} />
        ) : (
          <div className="flex-1 flex flex-col gap-4 px-4 py-5">
            <p className="text-[11px] text-text-tertiary leading-relaxed">
              {t("council_circle.select_hint") || "Kliknij agenta w przestrzeni, aby zobaczyć pełny głos."}
            </p>
            {tensions.length > 0 && <TensionList tensions={tensions} />}
          </div>
        )}
      </div>
    </div>
  );
}
