/**
 * agentForms — proceduralne sygile 3D dziewięciu głosów Rady.
 * Każda forma niesie tożsamość agenta (nie dekorację): geometria = charakter.
 * Zero assetów zewnętrznych — wszystko liczone lokalnie (offline, strict CSP).
 *
 * gpuBudget() — degradacja na słabszych GPU / WKWebView.
 */

import * as THREE from "three";

export interface GpuBudget {
  /** mnożnik liczby cząstek (0.3–1) */
  particles: number;
  /** limit devicePixelRatio */
  dpr: number;
  /** detal geometrii (0 = low-poly) */
  detail: 0 | 1;
}

let _budget: GpuBudget | null = null;
export function gpuBudget(): GpuBudget {
  if (_budget) return _budget;
  const cores = navigator.hardwareConcurrency ?? 4;
  const mem = (navigator as unknown as { deviceMemory?: number }).deviceMemory ?? 8;
  const weak = cores <= 4 || mem <= 4;
  _budget = weak
    ? { particles: 0.35, dpr: 1, detail: 0 }
    : { particles: 1, dpr: Math.min(devicePixelRatio, 2), detail: 1 };
  return _budget;
}

function std(color: THREE.ColorRepresentation, opts: Partial<THREE.MeshStandardMaterialParameters> = {}) {
  return new THREE.MeshStandardMaterial({
    color, emissive: color, emissiveIntensity: 0.55, roughness: 0.35, metalness: 0.45, ...opts,
  });
}
function wire(color: THREE.ColorRepresentation, opacity = 0.55) {
  return new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity });
}

/**
 * Sygil agenta. `s` — skala bazowa (promień ~0.4 przy s=1).
 * Zwraca Group; animacja idle (rotacja) — po stronie sceny.
 */
export function agentForm(name: string, colorHex: string, s = 1): THREE.Group {
  const c = new THREE.Color(colorHex);
  const g = new THREE.Group();
  const d = gpuBudget().detail;

  switch (name) {
    case "Kogit": { // krata poznawcza — siatka założeń
      g.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.34 * s, 1), wire(c, 0.8)));
      g.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.2 * s, d), std(c, { emissiveIntensity: 0.8 })));
      break;
    }
    case "Szow": { // cień — ostre, ciemne odłamki
      const m = std(c, { roughness: 0.15, metalness: 0.8, emissiveIntensity: 0.4 });
      const a = new THREE.Mesh(new THREE.TetrahedronGeometry(0.3 * s), m);
      const b = new THREE.Mesh(new THREE.TetrahedronGeometry(0.24 * s), m.clone());
      b.rotation.set(Math.PI / 3, Math.PI / 5, 0);
      b.position.y = 0.08 * s;
      g.add(a, b);
      break;
    }
    case "Kidi": { // jasne, organiczne — pęk kul życia
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.24 * s, 20, 20), std(c, { emissiveIntensity: 0.9, roughness: 0.6, metalness: 0.1 })));
      [[0.2, 0.14, 0.13], [-0.18, 0.18, 0.11], [0.05, -0.22, 0.12]].forEach(([x, y, r]) => {
        const b = new THREE.Mesh(new THREE.SphereGeometry(r * s, 14, 14), std(c, { emissiveIntensity: 0.7 }));
        b.position.set(x * s, y * s, 0.06 * s);
        g.add(b);
      });
      break;
    }
    case "Tai": { // pętle czasowe
      g.add(new THREE.Mesh(new THREE.TorusKnotGeometry(0.2 * s, 0.055 * s, d ? 96 : 48, 8, 2, 3), std(c)));
      break;
    }
    case "Obver": { // nieruchoma geometria — obserwacja bez oceny
      g.add(new THREE.Mesh(new THREE.BoxGeometry(0.4 * s, 0.4 * s, 0.4 * s), wire(c, 0.7)));
      g.add(new THREE.Mesh(new THREE.BoxGeometry(0.2 * s, 0.2 * s, 0.2 * s), std(c, { emissiveIntensity: 0.5 })));
      break;
    }
    case "Relacjan": { // sieć relacji — węzły i nici
      const nodes = new THREE.IcosahedronGeometry(0.3 * s, 0);
      const pts = nodes.getAttribute("position");
      const nodeMat = std(c, { emissiveIntensity: 0.8 });
      for (let i = 0; i < pts.count; i++) {
        const m = new THREE.Mesh(new THREE.SphereGeometry(0.045 * s, 8, 8), nodeMat);
        m.position.fromBufferAttribute(pts, i);
        g.add(m);
      }
      g.add(new THREE.Mesh(nodes, wire(c, 0.45)));
      break;
    }
    case "Emojy": { // płynny kolor — fala emocji zanim ma nazwę
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.26 * s, 24, 24), std(c, { roughness: 0.2, metalness: 0.1, emissiveIntensity: 0.7, transparent: true, opacity: 0.85 })));
      const aura = new THREE.Mesh(new THREE.SphereGeometry(0.34 * s, 16, 16), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.16, blending: THREE.AdditiveBlending, depthWrite: false }));
      g.add(aura);
      break;
    }
    case "Smaty": { // ucieleśniona forma — pion ciała
      g.add(new THREE.Mesh(new THREE.CapsuleGeometry(0.14 * s, 0.3 * s, 6, 14), std(c, { roughness: 0.5 })));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.24 * s, 0.02 * s, 8, 32), std(c, { emissiveIntensity: 0.7 }));
      ring.rotation.x = Math.PI / 2;
      g.add(ring);
      break;
    }
    case "Deega": { // głębokie warstwy — starsze pokłady
      [0.3, 0.24, 0.17].forEach((r, i) => {
        const disc = new THREE.Mesh(new THREE.CylinderGeometry(r * s, r * s, 0.05 * s, d ? 32 : 18), std(c, { emissiveIntensity: 0.4 + i * 0.2 }));
        disc.position.y = (i - 1) * 0.14 * s;
        g.add(disc);
      });
      break;
    }
    default: {
      g.add(new THREE.Mesh(new THREE.SphereGeometry(0.28 * s, 20, 20), std(c)));
    }
  }
  return g;
}

/**
 * Rdzeń Syeza — nie dziesiąty głos, lustro: konwergencja dziewięciu.
 * Icosahedron + siatka + wewnętrzny oktaedr odbijający.
 */
export function syezCore(s = 1): THREE.Group {
  const g = new THREE.Group();
  const gold = new THREE.Color("#d4af6a");
  g.add(new THREE.Mesh(
    new THREE.IcosahedronGeometry(0.9 * s, gpuBudget().detail ? 3 : 1),
    new THREE.MeshStandardMaterial({ color: 0x2a2010, emissive: gold, emissiveIntensity: 0.5, roughness: 0.2, metalness: 0.85 }),
  ));
  g.add(new THREE.Mesh(new THREE.IcosahedronGeometry(1.05 * s, 1), wire(gold, 0.3)));
  const mirror = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.45 * s),
    new THREE.MeshStandardMaterial({ color: 0xf4d896, emissive: 0xf4d896, emissiveIntensity: 1.1, roughness: 0.05, metalness: 1 }),
  );
  mirror.name = "syez-mirror";
  g.add(mirror);
  return g;
}
