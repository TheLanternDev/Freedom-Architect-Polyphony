'use strict';
const REDUCED = matchMedia('(prefers-reduced-motion:reduce)').matches;
const FINE = matchMedia('(pointer:fine)').matches;
const IS_SAFARI = /^((?!chrome|android|crios|fxios).)*safari/i.test(navigator.userAgent);
if(!FINE) document.body.classList.add('touch');
else document.body.classList.add('custom-cursor');

function getScrollY(){
  return window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;
}
function scrollMax(driver){
  if(!driver) return 0;
  return Math.max(0, driver.offsetHeight - window.innerHeight);
}

/* ---------- LANGUAGE ---------- */
const LANG_KEY = 'polyphony_lang';
const langBtn = document.getElementById('langtoggle');
const VIEW_LABELS = {
  pl: { rada:'RADA', debata:'DEBATA', aksjomat:'AKSJOMAT 0', personal:'PERSONAL', business:'BUSINESS', daily:'DAILY SIGNAL' },
  en: { rada:'COUNCIL', debata:'DEBATE', aksjomat:'AXIOM 0', personal:'PERSONAL', business:'BUSINESS', daily:'DAILY SIGNAL' }
};
const TENSION_MSG = {
  pl: (a,b)=>`${a} i ${b} nie widzą tego samego — oboje mają rację na swojej warstwie.`,
  en: (a,b)=>`${a} and ${b} don't see the same thing — both are right at their layer.`
};
function viewHudLabel(name){
  const lang = document.body.classList.contains('lang-en') ? 'en' : 'pl';
  return VIEW_LABELS[lang][name] || name.toUpperCase();
}
function applyPlaceholders(isEn){
  document.querySelectorAll('[data-ph-pl]').forEach(el=>{
    el.placeholder = isEn ? (el.dataset.phEn || el.dataset.phPl) : el.dataset.phPl;
  });
  const audio = document.getElementById('audiotoggle');
  if(audio?.dataset.titlePl) audio.title = isEn ? audio.dataset.titleEn : audio.dataset.titlePl;
}
function applyPageMeta(isEn){
  const root = document.documentElement;
  const title = isEn ? root.dataset.titleEn : root.dataset.titlePl;
  const desc = isEn ? root.dataset.descEn : root.dataset.descPl;
  if(title) document.title = title;
  const metaDesc = document.querySelector('meta[name="description"]');
  if(metaDesc && desc) metaDesc.setAttribute('content', desc);
  root.lang = isEn ? 'en' : 'pl';
}
function applyLang(isEn, persist){
  document.body.classList.toggle('lang-en', isEn);
  langBtn.textContent = isEn ? 'PL' : 'EN';
  const tl0 = document.getElementById('tl0');
  if(tl0){
    tl0.textContent = isEn?'SMILE':'UŚMIECH';
    document.getElementById('tl1').textContent = isEn?'PERSPECTIVE':'PERSPEKTYWA';
    document.getElementById('tl2').textContent = isEn?'PATH':'DROGA';
  }
  if(typeof currentView !== 'undefined' && hudView) hudView.textContent = viewHudLabel(currentView);
  applyPlaceholders(isEn);
  applyPageMeta(isEn);
  if(focusedAgent!==null) openAgentDetail(focusedAgent);
  if(persist) localStorage.setItem(LANG_KEY, isEn ? 'en' : 'pl');
  window.dispatchEvent(new CustomEvent('polyphony:langchange'));
}
langBtn.addEventListener('click', ()=>{
  applyLang(!document.body.classList.contains('lang-en'), true);
});

/* ---------- CURSOR ---------- */
const cursor = document.getElementById('cursor'), ring = document.getElementById('cursor-ring');
let mouseX=0, mouseY=0; // -0.5..0.5
if(FINE){
  let cx=innerWidth/2, cy=innerHeight/2, rx=cx, ry=cy;
  cursor.style.left=cx+'px'; cursor.style.top=cy+'px';
  ring.style.left=rx+'px'; ring.style.top=ry+'px';
  window.addEventListener('mousemove', e=>{
    cx=e.clientX; cy=e.clientY;
    cursor.style.left=cx+'px'; cursor.style.top=cy+'px';
    mouseX=e.clientX/innerWidth-.5; mouseY=e.clientY/innerHeight-.5;
  });
  gsap.ticker.add(()=>{ rx+=(cx-rx)*.15; ry+=(cy-ry)*.15; ring.style.left=rx+'px'; ring.style.top=ry+'px'; });
  document.addEventListener('mouseover', e=>{
    if(e.target.closest('a,button,input')) gsap.to(ring,{width:56,height:56,duration:.3});
    else gsap.to(ring,{width:34,height:34,duration:.3});
  });
}

/* ---------- THREE — persistent scene ---------- */
const canvas = document.getElementById('scene');
let renderer;
try{
  renderer = new THREE.WebGLRenderer({canvas, alpha:true, antialias:!IS_SAFARI, powerPreference:'default'});
}catch(e){
  console.error('WebGL unavailable', e);
}
if(!renderer || !renderer.getContext()){
  const loaderEl = document.getElementById('loader');
  if(loaderEl){
    loaderEl.querySelector('.loader-sub').textContent = IS_SAFARI
      ? 'WebGL niedostępny — włącz w ustawieniach Safari lub wyłącz blokowanie treści'
      : 'WebGL unavailable';
    loaderEl.classList.add('done');
    setTimeout(()=>loaderEl.remove(), 4000);
  }
}
const scene = new THREE.Scene();
if(renderer){
  renderer.setSize(innerWidth, innerHeight);
  renderer.setPixelRatio(Math.min(devicePixelRatio, IS_SAFARI ? 1.5 : 2));
}
scene.fog = new THREE.FogExp2(0x040406, .028);
const camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, .1, 100);
camera.position.set(0, 1.4, 9);
const camTarget = new THREE.Vector3(0,0,0);

/* nebula — GLSL particle field (cool-mix uniform for business mode) */
const N = 3400;
const nGeo = new THREE.BufferGeometry();
{
  const pos=new Float32Array(N*3), aSeed=new Float32Array(N), aSize=new Float32Array(N);
  for(let i=0;i<N;i++){
    const r = 4.5 + Math.pow(Math.random(),1.6)*11;
    const th = Math.random()*Math.PI*2, ph = Math.acos(2*Math.random()-1);
    pos[i*3]=r*Math.sin(ph)*Math.cos(th); pos[i*3+1]=r*Math.sin(ph)*Math.sin(th)*.72; pos[i*3+2]=r*Math.cos(ph);
    aSeed[i]=Math.random()*100; aSize[i]=.5+Math.random()*1.8;
  }
  nGeo.setAttribute('position', new THREE.BufferAttribute(pos,3));
  nGeo.setAttribute('aSeed', new THREE.BufferAttribute(aSeed,1));
  nGeo.setAttribute('aSize', new THREE.BufferAttribute(aSize,1));
}
const uniforms = { uTime:{value:0}, uMouse:{value:new THREE.Vector2()}, uCool:{value:0}, uDim:{value:1} };
scene.add(new THREE.Points(nGeo, new THREE.ShaderMaterial({
  uniforms, transparent:true, depthWrite:false, blending:THREE.AdditiveBlending,
  vertexShader:`
    precision mediump float;
    attribute float aSeed; attribute float aSize;
    uniform float uTime; uniform vec2 uMouse; varying float vA;
    void main(){
      vec3 p = position;
      float t = uTime*.16 + aSeed;
      p.x += sin(t + p.y*.35)*.55; p.y += cos(t*.8 + p.x*.3)*.45; p.z += sin(t*.6 + p.z*.4)*.55;
      float ang = uTime*.015;
      float ca=cos(ang), sa=sin(ang); p.xz = mat2(ca,-sa,sa,ca)*p.xz;
      p.x += uMouse.x*1.4; p.y -= uMouse.y*1.1;
      vec4 mv = modelViewMatrix*vec4(p,1.);
      float tw = .55 + .45*sin(uTime*1.4 + aSeed*7.);
      vA = tw*smoothstep(30.,7.,-mv.z);
      gl_PointSize = aSize*tw*(90./-mv.z);
      gl_Position = projectionMatrix*mv;
    }`,
  fragmentShader:`
    precision mediump float;
    uniform float uCool, uDim; varying float vA;
    void main(){
      vec2 uv = gl_PointCoord-.5; float d = length(uv);
      float a = smoothstep(.5,.02,d)*vA;
      vec3 warm = mix(vec3(.83,.686,.416), vec3(1.,.95,.78), smoothstep(.35,.0,d));
      vec3 cool = mix(vec3(.35,.62,.72), vec3(.78,.95,1.), smoothstep(.35,.0,d));
      gl_FragColor = vec4(mix(warm,cool,uCool), a*.88*uDim);
    }`
})));

/* glow sprite texture */
function glowTex(){
  const c=document.createElement('canvas'); c.width=c.height=128;
  const g=c.getContext('2d'), gr=g.createRadialGradient(64,64,0,64,64,64);
  gr.addColorStop(0,'rgba(255,255,255,1)'); gr.addColorStop(.32,'rgba(255,235,190,.4)'); gr.addColorStop(1,'rgba(255,235,190,0)');
  g.fillStyle=gr; g.fillRect(0,0,128,128);
  return new THREE.CanvasTexture(c);
}
const GLOW = glowTex();
function makeGlow(hex, sc, op){
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({map:GLOW, color:hex, transparent:true, opacity:op??.8, blending:THREE.AdditiveBlending, depthWrite:false}));
  sp.scale.set(sc,sc,1); return sp;
}
const lineMat = (hex,op)=> new THREE.LineBasicMaterial({color:hexToInt(hex), transparent:true, opacity:op, blending:THREE.AdditiveBlending});
const meshMat = (hex,op)=> new THREE.MeshBasicMaterial({color:hexToInt(hex), transparent:true, opacity:op, blending:THREE.AdditiveBlending, depthWrite:false});

/* ---------- SYEZ CORE — mirror: convergence of nine ---------- */
const constellation = new THREE.Group();
scene.add(constellation);
const core = new THREE.Group();
constellation.add(core);
{
  core.add(new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(.55,1)), lineMat(SYEZ.ring,.5)));
  const inner = new THREE.Mesh(new THREE.IcosahedronGeometry(.26,1), meshMat(SYEZ.ring,.55));
  inner.name='coreInner'; core.add(inner);
  core.add(makeGlow(hexToInt(SYEZ.ring), 2.4, .75));
  AGENTS.forEach((a,i)=>{
    const sh = new THREE.Mesh(new THREE.TetrahedronGeometry(.055), meshMat(a.ring,.9));
    sh.userData.orb = { a:(i/9)*Math.PI*2, tilt:(i%3-1)*.5 };
    core.add(sh); core.userData.shards = core.userData.shards||[]; core.userData.shards.push(sh);
  });
}

/* ---------- SIGIL BUILDERS ---------- */
const SIGIL = {
  lattice(c){ const g=new THREE.Group();
    g.add(new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.BoxGeometry(.4,.4,.4,2,2,2)), lineMat(c,.7))); return g; },
  shards(c){ const g=new THREE.Group();
    [[0,0,0,.17],[.14,.1,-.06,.1],[-.13,-.09,.08,.09],[.05,-.14,-.1,.075]].forEach(([x,y,z,s])=>{
      const m = new THREE.Mesh(new THREE.TetrahedronGeometry(s), new THREE.MeshBasicMaterial({color:0x0a0a0c}));
      m.position.set(x,y,z); m.rotation.set(x*7,y*7,z*7); g.add(m);
      g.add(new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry), lineMat(c,.8)).translateX(x).translateY(y).translateZ(z));
    }); return g; },
  seed(c){ const g=new THREE.Group();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.13,20,20), meshMat(c,.95));
    m.userData.pulse=true; g.add(m);
    g.add(new THREE.LineSegments(new THREE.WireframeGeometry(new THREE.SphereGeometry(.22,8,6)), lineMat(c,.25))); return g; },
  loops(c){ const g=new THREE.Group();
    const t1 = new THREE.Mesh(new THREE.TorusGeometry(.2,.012,8,60), meshMat(c,.85));
    const t2 = new THREE.Mesh(new THREE.TorusGeometry(.13,.01,8,60), meshMat(c,.6));
    t2.rotation.x=Math.PI/2; t2.userData.counter=true; g.add(t1,t2); return g; },
  octa(c){ const g=new THREE.Group();
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.OctahedronGeometry(.22)), lineMat(c,.85)));
    g.add(new THREE.Mesh(new THREE.OctahedronGeometry(.1), meshMat(c,.4)));
    g.userData.still=true; return g; },
  web(c){ const g=new THREE.Group(); const pts=[];
    for(let i=0;i<6;i++){ const th=i/6*Math.PI*2;
      pts.push(new THREE.Vector3(Math.cos(th)*.2, Math.sin(th)*.2, (i%2?-.08:.08))); }
    const seg=[];
    pts.forEach((p,i)=>pts.forEach((q,j)=>{ if(j>i) seg.push(p,q); }));
    g.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(seg), lineMat(c,.35)));
    pts.forEach(p=>{ const n=new THREE.Mesh(new THREE.SphereGeometry(.028,8,8), meshMat(c,.95)); n.position.copy(p); g.add(n); });
    return g; },
  fluid(c){ const g=new THREE.Group();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.17,24,24), meshMat(c,.85));
    m.userData.fluid=true;
    const hsl = {h:0,s:0,l:0};
    new THREE.Color(c).getHSL(hsl);
    m.userData.baseHue = hsl.h;
    g.add(m); return g; },
  body(c){ const g=new THREE.Group();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.14,20,20), meshMat(c,.8));
    m.scale.set(1,1.55,1); m.userData.breathe=true; g.add(m);
    g.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.CylinderGeometry(.2,.2,.42,10,1,true)), lineMat(c,.25)));
    return g; },
  strata(c){ const g=new THREE.Group();
    for(let i=0;i<4;i++){
      const m = new THREE.Mesh(new THREE.BoxGeometry(.36-.03*i,.022,.36-.03*i), meshMat(c,.85-.18*i));
      m.position.y = .12-.08*i; g.add(m);
    } return g; }
};

/* ---------- AGENT NODES + THREADS ---------- */
const nodes = [];
const threads = [];
COUNCIL_ORDER.forEach((name,i)=>{
  const a = AGENTS.find(x=>x.name===name);
  const node = new THREE.Group();
  node.name = name;
  node.add(SIGIL[a.sigil](a.ring));
  node.add(makeGlow(hexToInt(a.ring), 1.15, .6));
  const hit = new THREE.Mesh(new THREE.SphereGeometry(.42,8,8), new THREE.MeshBasicMaterial({visible:false}));
  hit.name = name; node.add(hit);
  node.userData = { agent:a, idx:i, target:new THREE.Vector3(), hit };
  constellation.add(node); nodes.push(node);
  const tg = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
  const tl = new THREE.Line(tg, lineMat(a.ring,.12));
  constellation.add(tl); threads.push(tl);
});
const nodeOf = n => nodes.find(x=>x.name===n) || core;

/* ---------- TRIAD (AKSJOMAT 0) ---------- */
const TRIAD_C = ['#f0d878','#9ad8e8','#d4915a'];
const triad = new THREE.Group();
triad.visible=false; triad.scale.setScalar(.001);
scene.add(triad);
const triadOrbs = [];
{
  TRIAD_C.forEach((c,i)=>{
    const o = new THREE.Group();
    const m = new THREE.Mesh(new THREE.SphereGeometry(.24,24,24), meshMat(c,.9));
    o.add(m, makeGlow(hexToInt(c), 1.9, .8));
    o.userData = { phase:i/3*Math.PI*2 };
    triad.add(o); triadOrbs.push(o);
  });
  /* arcs between the three — the system that sustains itself */
  for(let i=0;i<3;i++){
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(),new THREE.Vector3(),new THREE.Vector3()]);
    const geo = new THREE.BufferGeometry().setFromPoints(new Array(24).fill(0).map(()=>new THREE.Vector3()));
    const ln = new THREE.Line(geo, lineMat(TRIAD_C[i],.4));
    ln.userData = {curve, from:i, to:(i+1)%3};
    triad.add(ln); triad.userData.arcs = triad.userData.arcs||[]; triad.userData.arcs.push(ln);
  }
  /* circulating spark — energy moving through the triad */
  const spark = makeGlow(0xffffff,.5,.9);
  triad.add(spark); triad.userData.spark = spark;
}
const triadRot = {x:.2, y:0, vx:0, vy:.0016};

/* ---------- DAILY ARC (18h horizon) ---------- */
const daily = new THREE.Group();
daily.visible=false; daily.scale.setScalar(.001);
scene.add(daily);
{
  const pts=[]; const R=3.4;
  for(let i=0;i<=64;i++){ const t=-Math.PI*.75 + (i/64)*Math.PI*1.5;
    pts.push(new THREE.Vector3(Math.cos(t)*R, Math.sin(t)*R*.42, 0)); }
  daily.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), lineMat('#d4af6a',.5)));
  /* hour ticks */
  const tickSeg=[];
  for(let i=0;i<=18;i++){ const t=-Math.PI*.75 + (i/18)*Math.PI*1.5;
    const p=new THREE.Vector3(Math.cos(t)*R, Math.sin(t)*R*.42, 0);
    const q=p.clone().multiplyScalar(1.035); tickSeg.push(p,q); }
  daily.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(tickSeg), lineMat('#d4af6a',.25)));
  daily.userData.markers=[];
  [0.18,0.5,0.82].forEach((f,i)=>{
    const t=-Math.PI*.75 + f*Math.PI*1.5;
    const o = new THREE.Group();
    o.position.set(Math.cos(t)*R, Math.sin(t)*R*.42, 0);
    const m = new THREE.Mesh(new THREE.SphereGeometry(.12,16,16), meshMat(TRIAD_C[i],.9));
    o.add(m, makeGlow(hexToInt(TRIAD_C[i]),1.2,.7));
    daily.add(o); daily.userData.markers.push(o);
  });
}

/* ---------- FORMATIONS (dynamic targets) ---------- */
let formation = 'rada';
let formationA = 'rada', formationB = 'rada', formationMix = 0;
const tmpFA = new THREE.Vector3(), tmpFB = new THREE.Vector3();
let orbitSpeed = .06;
function formationOf(name){ return (name==='aksjomat'||name==='daily') ? 'recede' : name; }
function targetFor(node, i, form, t, out){
  const n = nodes.length;
  if(form==='rada'){
    const a = (i/n)*Math.PI*2 + t*orbitSpeed;
    out.set(Math.cos(a)*3.0, Math.sin(a*2)*.45, Math.sin(a)*3.0*.55);
  } else if(form==='debata'){
    const a = (i/n)*Math.PI*2 + t*orbitSpeed*1.6;
    out.set(Math.cos(a)*2.1, Math.sin(a*3)*.12, Math.sin(a)*2.1);
  } else if(form==='personal'){
    const k = i+.5, phi = Math.acos(1-2*k/n), th = Math.PI*(1+Math.sqrt(5))*k + t*.03;
    out.set(2.7*Math.sin(phi)*Math.cos(th), 2.7*Math.cos(phi)*.8, 2.7*Math.sin(phi)*Math.sin(th));
  } else if(form==='business'){
    const col=i%3, row=(i-col)/3;
    out.set((col-1)*1.7, .0, (row-1)*1.7);
  } else {
    const a = (i/n)*Math.PI*2 + t*.02;
    out.set(Math.cos(a)*7.5, -1.6+Math.sin(a*2)*.3, -5+Math.sin(a)*2);
  }
}
function setTargets(t){
  nodes.forEach((node,i)=>{
    const tg = node.userData.target;
    if(formationMix<=0.001) targetFor(node, i, formationA, t, tg);
    else if(formationMix>=0.999) targetFor(node, i, formationB, t, tg);
    else{
      targetFor(node, i, formationA, t, tmpFA);
      targetFor(node, i, formationB, t, tmpFB);
      tg.lerpVectors(tmpFA, tmpFB, formationMix);
    }
  });
}

/* ---------- RENDER LOOP ---------- */
const clock = new THREE.Clock();
let demoRunning = false;
let frame = 0;
const tmpV = new THREE.Vector3();
function render(){
  requestAnimationFrame(render);
  if(!renderer) return;
  frame++;
  const heavy = demoRunning;              /* degrade during live debate stream */
  if(heavy && frame%2) { return; }        /* half framerate for the 3D layer  */
  const t = clock.getElapsedTime();
  uniforms.uTime.value = t;
  uniforms.uMouse.value.lerp(new THREE.Vector2(mouseX,mouseY), .04);

  setTargets(t);
  nodes.forEach(node=>{
    node.position.lerp(node.userData.target, .05);
    node.children[0].children.forEach(part=>{
      if(part.userData.pulse){ const s=1+Math.sin(t*2.4)*.18; part.scale.setScalar(s); }
      if(part.userData.breathe){ const s=1+Math.sin(t*1.1)*.08; part.scale.set(s, 1.55*s, s); }
      if(part.userData.fluid){ part.material.color.setHSL((part.userData.baseHue + Math.sin(t*.5)*.06+1)%1, .7, .6); }
    });
    if(!heavy && !node.children[0].userData.still){
      node.children[0].rotation.y += .004;
      node.children[0].rotation.x += .0015;
      const c2 = node.children[0].children.find(m=>m.userData.counter);
      if(c2) c2.rotation.z -= .012;
    }
  });
  threads.forEach((tl,i)=>{
    const p = tl.geometry.attributes.position;
    p.setXYZ(0, core.position.x, core.position.y, core.position.z);
    p.setXYZ(1, nodes[i].position.x, nodes[i].position.y, nodes[i].position.z);
    p.needsUpdate = true;
  });
  /* core: mirror rotation + nine shards converging */
  core.children[0].rotation.y = t*.12; core.children[0].rotation.z = t*.05;
  core.children[1].rotation.y = -t*.2;
  (core.userData.shards||[]).forEach((sh,i)=>{
    const o = sh.userData.orb;
    const r = .62 + Math.sin(t*.7 + i)*  .14;   /* convergence breath */
    const a = o.a + t*.35;
    sh.position.set(Math.cos(a)*r, Math.sin(a*1.3 + o.tilt)*r*.5, Math.sin(a)*r);
    sh.rotation.x = t + i; sh.rotation.y = t*.7;
  });

  /* triad */
  if(triad.visible){
    if(!dragging){ triadRot.y += triadRot.vy + triadRot.vx*.0; triadRot.x += triadRot.vx; triadRot.vx*=.94; }
    triad.rotation.set(triadRot.x, triadRot.y, 0);
    triadOrbs.forEach((o,i)=>{
      const a = o.userData.phase + t*.22;
      o.position.set(Math.cos(a)*1.7, Math.sin(a)*1.7*.35, Math.sin(a)*1.1);
    });
    (triad.userData.arcs||[]).forEach(ln=>{
      const A=triadOrbs[ln.userData.from].position, B=triadOrbs[ln.userData.to].position;
      const mid = tmpV.copy(A).add(B).multiplyScalar(.5).multiplyScalar(1.45);
      ln.userData.curve.points[0].copy(A); ln.userData.curve.points[1].copy(mid); ln.userData.curve.points[2].copy(B);
      const pts = ln.userData.curve.getPoints(23), p = ln.geometry.attributes.position;
      pts.forEach((pt,j)=>p.setXYZ(j,pt.x,pt.y,pt.z)); p.needsUpdate=true;
    });
    /* spark cycles Uśmiech → Perspektywa → Droga → … */
    const cyc = (t*.25)%3, leg = Math.floor(cyc), f = cyc-leg;
    const arc = triad.userData.arcs[leg];
    if(arc){ const pt = arc.userData.curve.getPoint(f); triad.userData.spark.position.copy(pt); }
    /* project labels */
    triadOrbs.forEach((o,i)=>{
      tmpV.copy(o.position).applyMatrix4(triad.matrixWorld).project(camera);
      const el = document.getElementById('tl'+i);
      el.style.left = (tmpV.x*.5+.5)*innerWidth+'px';
      el.style.top  = (-tmpV.y*.5+.5)*innerHeight+'px';
      el.style.opacity = (currentView==='aksjomat' && tmpV.z<1) ? .9 : 0;
    });
  }
  if(daily.visible){
    daily.userData.markers.forEach((o,i)=>{ o.children[0].scale.setScalar(1+Math.sin(t*1.6+i*2)*.2); });
    daily.rotation.y = mouseX*.2;
  }

  constellation.rotation.y = mouseX*.14;
  constellation.rotation.x = mouseY*.1;
  camera.position.x += (camPos.x + mouseX*.7 - camera.position.x)*.05;
  camera.position.y += (camPos.y - mouseY*.7 - camera.position.y)*.05;
  camera.position.z += (camPos.z - camera.position.z)*.05;
  camera.lookAt(camTarget);
  renderer.render(scene, camera);
  if(FINE && frame%3===0) raycast();
}
window.addEventListener('resize', ()=>{
  camera.aspect=innerWidth/innerHeight; camera.updateProjectionMatrix();
  if(renderer) renderer.setSize(innerWidth,innerHeight);
  if(SCROLL_MODE) applyScrollProgress(getScrollProgress());
});

/* ---------- RAYCASTER — hover + click on agent nodes ---------- */
const ray = new THREE.Raycaster();
const mouseNDC = new THREE.Vector2();
const tip = document.getElementById('nodeTip');
let hovered = null, tipXY = {x:0,y:0};
window.addEventListener('mousemove', e=>{ mouseNDC.set(e.clientX/innerWidth*2-1, -(e.clientY/innerHeight)*2+1); tipXY={x:e.clientX,y:e.clientY}; });
function raycast(){
  if(currentView!=='rada' && currentView!=='debata' && currentView!=='personal'){ setHover(null); return; }
  ray.setFromCamera(mouseNDC, camera);
  const hits = ray.intersectObjects(nodes.map(n=>n.userData.hit).concat(core.children[1]), true);
  const hitName = hits.length ? hits[0].object.name : null;
  setHover(hitName ? (hitName==='coreInner' ? 'Syez' : hitName) : null);
}
function setHover(name){
  if(name===hovered) { if(name){ tip.style.left=tipXY.x+'px'; tip.style.top=tipXY.y+'px'; } return; }
  hovered = name;
  document.body.style.setProperty('--hover', name?1:0);
  if(canvas) canvas.style.cursor = name ? 'pointer' : (currentView==='aksjomat' ? 'grab' : 'default');
  if(name){
    const a = name==='Syez' ? SYEZ : AGENTS.find(x=>x.name===name);
    const isEn = document.body.classList.contains('lang-en');
    tip.querySelector('b').textContent = a.name;
    tip.querySelector('span').textContent = isEn?a.role_en:a.role_pl;
    tip.style.opacity = 1;
    const node = nodeOf(name);
    gsap.to(node.scale, {x:1.35,y:1.35,z:1.35, duration:.4, ease:'power2.out'});
    blip(PITCH[name]||330, .02);
  } else {
    tip.style.opacity = 0;
    nodes.forEach(n=>gsap.to(n.scale,{x:1,y:1,z:1,duration:.5}));
  }
}
function pickNameAt(clientX, clientY){
  const rect = canvas.getBoundingClientRect();
  if(!rect.width || !rect.height) return null;
  const x = ((clientX - rect.left) / rect.width) * 2 - 1;
  const y = -(((clientY - rect.top) / rect.height) * 2 - 1);
  mouseNDC.set(x, y);
  tipXY = {x: clientX, y: clientY};
  ray.setFromCamera(mouseNDC, camera);
  const hits = ray.intersectObjects(nodes.map(n=>n.userData.hit).concat(core.children[1]), true);
  const hitName = hits.length ? hits[0].object.name : null;
  return hitName ? (hitName==='coreInner' ? 'Syez' : hitName) : null;
}
canvas.addEventListener('pointermove', (e)=>{
  if(!e.isPrimary) return;
  pickNameAt(e.clientX, e.clientY);
});
canvas.addEventListener('pointerdown', (e)=>{
  if(!e.isPrimary) return;
  if(currentView==='aksjomat') return;
  const picked = pickNameAt(e.clientX, e.clientY);
  if(!picked) return;
  e.preventDefault();
  setHover(picked);
  focusAgent(picked);
});

/* ---------- TRIAD DRAG (grab & rotate) ---------- */
let dragging = false, dragStart = null;
canvas.addEventListener('pointerdown', e=>{
  if(currentView!=='aksjomat') return;
  canvas.style.cursor = 'grabbing';
  canvas.style.touchAction = 'none';
  dragging = true; dragStart = {x:e.clientX, y:e.clientY, rx:triadRot.x, ry:triadRot.y};
});
window.addEventListener('pointermove', e=>{
  if(!dragging) return;
  triadRot.y = dragStart.ry + (e.clientX-dragStart.x)*.006;
  triadRot.x = Math.max(-1.1, Math.min(1.1, dragStart.rx + (e.clientY-dragStart.y)*.005));
});
window.addEventListener('pointerup', e=>{
  if(dragging && dragStart){ triadRot.vx = 0; triadRot.vy = Math.max(-.02, Math.min(.02, (e.movementX||0)*.0009)) || .0016; }
  setTimeout(()=>dragging=false, 30);
  canvas.style.cursor = hovered ? 'pointer' : (currentView==='aksjomat' ? 'grab' : 'default');
  canvas.style.touchAction = currentView==='aksjomat' ? 'none' : 'manipulation';
});

/* ---------- VIEW MANAGER — cinematic camera tabs ---------- */
const camPos = new THREE.Vector3(0, 1.4, 9);
const VIEWS = {
  rada:     {cam:[0, 1.4, 9],   look:[0,0,0],  accent:'#e8d5a3', cool:0, dim:1},
  debata:   {cam:[0, 3.4, 6.8], look:[0,0,0],  accent:'#e8d5a3', cool:0, dim:.95},
  aksjomat: {cam:[0, .2, 6],    look:[0,0,0],  accent:'#f0d878', cool:0, dim:.82},
  personal: {cam:[0, .1, 1.2],  look:[0,0,-2], accent:'#e8d5a3', cool:0, dim:.95},
  business: {cam:[0, 5.6, 4.6], look:[0,0,0],  accent:'#9ad8e8', cool:1, dim:.9},
  daily:    {cam:[0, .4, 7.2],  look:[0,.6,0], accent:'#f0d878', cool:0, dim:.85}
};
let currentView = 'rada';
let focusedAgent = null;
const hudView = document.getElementById('hudView'), hudMode = document.getElementById('hudMode');

(function initLang(){
  const savedLang = localStorage.getItem(LANG_KEY);
  if(savedLang === 'en') applyLang(true, false);
  else if(savedLang === 'pl') applyLang(false, false);
  else {
    const nav = (navigator.language || '').toLowerCase();
    applyLang(nav.startsWith('en'), false);
  }
  if(hudView) hudView.textContent = viewHudLabel(currentView);
})();

function revealPanels(viewEl){
  const els = viewEl.querySelectorAll('[data-st]');
  gsap.fromTo(els, {opacity:0, y:26}, {opacity:1, y:0, duration:REDUCED?0:.9, stagger:REDUCED?0:.07, ease:'power3.out', delay:.25, overwrite:true});
}
function setView(name, opts={}){
  if(name===currentView && !opts.force) return;
  const prevEl = document.getElementById('v-'+currentView);
  currentView = name;
  closeAgentDetail(true);
  if(canvas){
    canvas.style.touchAction = name==='aksjomat' ? 'none' : 'manipulation';
    if(name==='aksjomat') canvas.style.cursor = 'grab';
    else if(hovered) canvas.style.cursor = 'pointer';
    else canvas.style.cursor = 'default';
  }
  document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active', b.dataset.view===name));
  const V = VIEWS[name];
  const D = REDUCED ? 0 : 1.1;

  /* formation + special groups */
  formation = formationOf(name);
  formationA = formationB = formation;
  formationMix = 0;
  if(name==='aksjomat'){ triad.visible=true; gsap.to(triad.scale,{x:1,y:1,z:1,duration:D,ease:'power3.inOut'}); }
  else gsap.to(triad.scale,{x:.001,y:.001,z:.001,duration:D*.7,ease:'power3.in', onComplete:()=>{ if(currentView!=='aksjomat') triad.visible=false; }});
  if(name==='daily'){ daily.visible=true; gsap.to(daily.scale,{x:1,y:1,z:1,duration:D,ease:'power3.inOut'}); }
  else gsap.to(daily.scale,{x:.001,y:.001,z:.001,duration:D*.7,ease:'power3.in', onComplete:()=>{ if(currentView!=='daily') daily.visible=false; }});
  gsap.to(core.scale, {x:name==='personal'?.55:1, y:name==='personal'?.55:1, z:name==='personal'?.55:1, duration:D, ease:'power3.inOut'});

  /* camera choreography */
  gsap.to(camPos,     {x:V.cam[0], y:V.cam[1], z:V.cam[2], duration:D, ease:'power3.inOut'});
  gsap.to(camTarget,  {x:V.look[0], y:V.look[1], z:V.look[2], duration:D, ease:'power3.inOut'});
  gsap.to(uniforms.uCool, {value:V.cool, duration:D});
  gsap.to(uniforms.uDim,  {value:V.dim,  duration:D});
  document.documentElement.style.setProperty('--accent', V.accent);

  /* threads brighter in debate */
  threads.forEach(tl=> gsap.to(tl.material, {opacity: name==='debata'?.3:(formation==='recede'?.04:.12), duration:D}));

  /* panels */
  const el = document.getElementById('v-'+name);
  if(prevEl && prevEl!==el){
    gsap.to(prevEl.querySelectorAll('.panel,.draghint,.hint'), {opacity:0, y:14, duration:.35, ease:'power2.in',
      onComplete:()=>{ prevEl.classList.remove('active'); }});
  }
  setTimeout(()=>{
    el.classList.add('active');
    gsap.set(el.querySelectorAll('.panel,.draghint,.hint'), {opacity:1, y:0});
    revealPanels(el);
  }, prevEl&&prevEl!==el ? 360 : 0);

  /* mode sync */
  if(name==='business') setDemoMode('fa2');
  if(name==='personal') setDemoMode('personal');
  hudView.textContent = viewHudLabel(name);
  blip(name==='business'?294:392, .03);
}
const SCROLL_VIEWS = ['rada','debata','aksjomat','personal','business','daily'];
const SCROLL_MODE = document.body.dataset.scroll === '1' && !document.body.dataset.initialView;
let scrollSyncLock = false;
let scrollRevealed = new Set();
function lerpN(a,b,t){ return a+(b-a)*t; }
function smooth(t){ return t*t*(3-2*t); }
function threadOpacityFor(name){
  if(name==='debata') return .3;
  return formationOf(name)==='recede' ? .04 : .12;
}
function coreScaleFor(name){ return name==='personal' ? .55 : 1; }
function applyScrollProgress(p){
  const i0 = Math.min(Math.floor(p), SCROLL_VIEWS.length-1);
  const frac = smooth(p - i0);
  const i1 = Math.min(i0+1, SCROLL_VIEWS.length-1);
  const n0 = SCROLL_VIEWS[i0], n1 = SCROLL_VIEWS[i1];
  const V0 = VIEWS[n0], V1 = VIEWS[n1];

  camPos.set(lerpN(V0.cam[0],V1.cam[0],frac), lerpN(V0.cam[1],V1.cam[1],frac), lerpN(V0.cam[2],V1.cam[2],frac));
  camTarget.set(lerpN(V0.look[0],V1.look[0],frac), lerpN(V0.look[1],V1.look[1],frac), lerpN(V0.look[2],V1.look[2],frac));
  uniforms.uCool.value = lerpN(V0.cool, V1.cool, frac);
  uniforms.uDim.value = lerpN(V0.dim, V1.dim, frac);
  formationA = formationOf(n0);
  formationB = formationOf(n1);
  formationMix = frac;

  const triadP = Math.max(0, 1 - Math.abs(p - 2) / .9);
  triad.visible = triadP > .02;
  triad.scale.setScalar(triadP);
  const dailyP = Math.max(0, 1 - Math.abs(p - 5) / .9);
  daily.visible = dailyP > .02;
  daily.scale.setScalar(dailyP);
  const coreS = lerpN(coreScaleFor(n0), coreScaleFor(n1), frac);
  core.scale.set(coreS, coreS, coreS);
  const thOp = lerpN(threadOpacityFor(n0), threadOpacityFor(n1), frac);
  threads.forEach(tl=>{ tl.material.opacity = thOp; });

  document.documentElement.style.setProperty('--accent', frac < .5 ? V0.accent : V1.accent);
  const activeIdx = Math.round(p);
  const activeName = SCROLL_VIEWS[activeIdx];
  if(activeName !== currentView){
    currentView = activeName;
    closeAgentDetail(true);
    document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active', b.dataset.view===activeName));
    if(activeName==='business') setDemoMode('fa2');
    if(activeName==='personal') setDemoMode('personal');
    hudView.textContent = viewHudLabel(activeName);
  }
  SCROLL_VIEWS.forEach((v,i)=>{
    const el = document.getElementById('v-'+v);
    const op = Math.max(0, 1 - Math.abs(p - i) * 1.1);
    if(op > .02){
      el.classList.add('active');
      el.querySelectorAll('.panel,.draghint,.hint').forEach(pan=>{
        pan.style.opacity = op;
        pan.style.transform = 'translateY('+(1-op)*18+'px)';
      });
      if(!scrollRevealed.has(v) && op > .55){
        scrollRevealed.add(v);
        gsap.fromTo(el.querySelectorAll('[data-st]'), {opacity:0, y:20}, {opacity:1, y:0, duration:REDUCED?0:.7, stagger:REDUCED?0:.05, ease:'power2.out', overwrite:true});
      }
    } else el.classList.remove('active');
  });
  const hint = document.getElementById('scroll-hint');
  if(hint) hint.style.opacity = p < .35 ? String(.75 - p) : '0';
}
function getScrollProgress(){
  const driver = document.getElementById('scroll-driver');
  const max = scrollMax(driver);
  return max > 0 ? (getScrollY() / max) * (SCROLL_VIEWS.length - 1) : 0;
}
function initScrollDriver(){
  if(!SCROLL_MODE) return;
  document.documentElement.classList.add('scroll-scene');
  document.body.classList.add('scroll-scene');
  const driver = document.createElement('div');
  driver.id = 'scroll-driver';
  SCROLL_VIEWS.forEach(v=>{
    const sec = document.createElement('div');
    sec.className = 'scroll-section';
    sec.dataset.view = v;
    driver.appendChild(sec);
  });
  document.body.appendChild(driver);
  const hint = document.createElement('div');
  hint.id = 'scroll-hint';
  hint.innerHTML = '<span class="lang-pl">PRZEWIŃ — scena 3D reaguje na scroll</span><span class="lang-en">SCROLL — the 3D scene follows you</span>';
  document.body.appendChild(hint);
  let ticking = false;
  function onScroll(){
    if(scrollSyncLock) return;
    if(!ticking){
      ticking = true;
      requestAnimationFrame(()=>{
        applyScrollProgress(getScrollProgress());
        ticking = false;
      });
    }
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  document.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('touchmove', onScroll, {passive:true});
  window.addEventListener('wheel', onScroll, {passive:true});
  onScroll();
  setTimeout(onScroll, 300);
}
function navigateToView(name, opts={}){
  if(SCROLL_MODE){
    const idx = SCROLL_VIEWS.indexOf(name);
    if(idx < 0) return;
    const driver = document.getElementById('scroll-driver');
    const max = scrollMax(driver);
    const targetY = max > 0 ? (idx / (SCROLL_VIEWS.length - 1)) * max : 0;
    const sec = document.querySelector('#scroll-driver .scroll-section[data-view="'+name+'"]');
    scrollSyncLock = true;
    if(sec && IS_SAFARI){
      sec.scrollIntoView({behavior:REDUCED?'auto':'smooth', block:'start'});
    } else {
      window.scrollTo({top: targetY, behavior: REDUCED ? 'auto' : 'smooth'});
    }
    setTimeout(()=>{ scrollSyncLock = false; applyScrollProgress(idx); }, REDUCED ? 60 : 950);
    return;
  }
  setView(name, opts);
}
initScrollDriver();
document.querySelectorAll('.tab').forEach(b=> b.addEventListener('click', ()=>{
  if(b.dataset.view) navigateToView(b.dataset.view);
}));
document.querySelectorAll('[data-goto]').forEach(b=> b.addEventListener('click', ()=>{
  if(b.dataset.setmode) setDemoMode(b.dataset.setmode);
  navigateToView(b.dataset.goto);
}));

/* ---------- AGENT FOCUS (rada view) ---------- */
const detail = document.getElementById('agentDetail');
const detailBody = document.getElementById('agentDetailBody');
function openAgentDetail(name){
  const a = name==='Syez' ? SYEZ : AGENTS.find(x=>x.name===name);
  const isEn = document.body.classList.contains('lang-en');
  detail.style.setProperty('--dot', a.ring);
  detailBody.innerHTML = `
    <span class="agent-role" style="color:${a.ring}">${isEn?a.role_en:a.role_pl}</span>
    <h3 class="agent-name">${a.name}</h3>
    <p class="agent-bio">${isEn?a.bio_en:a.bio_pl}</p>
    <div class="divider"></div>
    <p class="small-note">${isEn?a.sig_en:a.sig_pl}</p>`;
  detail.style.visibility='visible';
  gsap.fromTo(detail, {opacity:0, x:40}, {opacity:1, x:0, duration:.7, ease:'power3.out'});
  gsap.fromTo(detailBody.children, {opacity:0, y:16}, {opacity:1, y:0, duration:.6, stagger:.06, ease:'power2.out', delay:.15});
}
function focusAgent(name){
  focusedAgent = name;
  document.querySelectorAll('.chip').forEach(c=>c.classList.toggle('focused', c.dataset.name===name));
  const node = nodeOf(name);
  const D = REDUCED?0:1;
  if(name!=='Syez'){
    /* camera dollies toward the agent; constellation turns to face it */
    const p = node.userData.target.clone().normalize().multiplyScalar(5.4);
    gsap.to(camPos,    {x:p.x, y:p.y+1, z:Math.max(p.z,3.4), duration:D, ease:'power3.inOut'});
    gsap.to(camTarget, {x:node.userData.target.x*.6, y:node.userData.target.y*.6, z:node.userData.target.z*.6, duration:D, ease:'power3.inOut'});
    orbitSpeed = .012; /* slow the orbit while listening to one voice */
    gsap.fromTo(node.scale,{x:1,y:1,z:1},{x:1.6,y:1.6,z:1.6,duration:.6,ease:'back.out(2)'});
    const th = threads[node.userData.idx];
    gsap.to(th.material, {opacity:.7, duration:.6});
  } else {
    gsap.to(camPos, {x:0,y:.6,z:4.6, duration:D, ease:'power3.inOut'});
    gsap.to(camTarget, {x:0,y:0,z:0, duration:D, ease:'power3.inOut'});
  }
  openAgentDetail(name);
  blip(PITCH[name]||330, .05);
}
function closeAgentDetail(silent){
  if(focusedAgent===null) return;
  const node = nodeOf(focusedAgent);
  if(node!==core){ gsap.to(node.scale,{x:1,y:1,z:1,duration:.5}); gsap.to(threads[node.userData.idx].material,{opacity:.12,duration:.5}); }
  focusedAgent = null;
  orbitSpeed = .06;
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('focused'));
  gsap.to(detail, {opacity:0, x:30, duration:.4, onComplete:()=>detail.style.visibility='hidden'});
  if(!silent){
    if(SCROLL_MODE){
      const driver = document.getElementById('scroll-driver');
      applyScrollProgress(getScrollProgress());
    } else {
      const V = VIEWS.rada;
      gsap.to(camPos, {x:V.cam[0],y:V.cam[1],z:V.cam[2], duration:1, ease:'power3.inOut'});
      gsap.to(camTarget, {x:0,y:0,z:0, duration:1, ease:'power3.inOut'});
    }
  }
}
document.getElementById('detailClose').addEventListener('click', ()=>closeAgentDetail(false));

/* agent chips */
const chipsEl = document.getElementById('agentChips');
[SYEZ, ...AGENTS].forEach(a=>{
  const b = document.createElement('button');
  b.className='chip'; b.dataset.name=a.name;
  b.style.setProperty('--dot', a.ring);
  b.innerHTML = `<i></i>${a.name}`;
  b.addEventListener('click', ()=>focusAgent(a.name));
  chipsEl.appendChild(b);
});

/* ---------- DEBATE — templates (simulation fallback) ---------- */
const TPL = {
  personal:{
    Relacjan:{pl:t=>`Kto w Twoim otoczeniu ma zdanie na temat „${t}”, którego jeszcze nie nazwałeś głośno?`, en:t=>`Who around you has an opinion on "${t}" that you haven't voiced out loud yet?`},
    Kogit:{pl:t=>`Sprawdź, jakie założenie o „${t}” przyjąłeś, zanim zacząłeś się zastanawiać.`, en:t=>`Check what assumption about "${t}" you accepted before you even started thinking.`},
    Emojy:{pl:t=>`Co czujesz, myśląc o „${t}” — zanim nazwiesz to słowem?`, en:t=>`What do you feel thinking about "${t}" — before you put it into words?`},
    Deega:{pl:t=>`To nie pierwszy raz, kiedy stoisz przed czymś takim jak „${t}”. Co powtarza się od lat?`, en:t=>`This isn't the first time you've faced something like "${t}." What's been repeating for years?`},
    Smaty:{pl:t=>`Co mówi ciało, gdy wypowiadasz na głos „${t}”? Napięcie czy ulga?`, en:t=>`What does the body say when you say "${t}" out loud? Tension or relief?`},
    Szow:{pl:t=>`Jest coś w „${t}”, czego unikasz nazwać wprost. Nazwij to.`, en:t=>`There's something in "${t}" you avoid naming directly. Name it.`},
    Tai:{pl:t=>`„${t}” nie dzieje się w próżni. Jaki wzorzec czasowy się tu powtarza?`, en:t=>`"${t}" doesn't happen in a vacuum. What time pattern is repeating here?`},
    Obver:{pl:t=>`Patrzę na sekwencję zdarzeń wokół „${t}” bez oceny. Oto, co widzę.`, en:t=>`I'm looking at the sequence of events around "${t}" without judgment. Here's what I see.`},
    Kidi:{pl:t=>`Zanim nauczyłeś się, co jest „rozsądne” — czego naprawdę chciałeś w sprawie „${t}”?`, en:t=>`Before you learned what's "reasonable" — what did you actually want regarding "${t}"?`}
  },
  fa2:{
    Relacjan:{pl:t=>`Kto w zespole ma zdanie na temat „${t}”, którego jeszcze nie wypowiedział wprost?`, en:t=>`Who on the team has an opinion on "${t}" they haven't stated directly?`},
    Kogit:{pl:t=>`Jakie założenie biznesowe o „${t}” przyjęliście bez testowania?`, en:t=>`What business assumption about "${t}" did you accept without testing?`},
    Emojy:{pl:t=>`Jaka emocja krąży w zespole wokół „${t}” — strach, ambicja, zmęczenie?`, en:t=>`What emotion is circulating in the team around "${t}" — fear, ambition, fatigue?`},
    Deega:{pl:t=>`To nie pierwszy raz, kiedy organizacja mierzy się z czymś jak „${t}”. Co się powtarza?`, en:t=>`This isn't the first time the org has faced something like "${t}." What repeats?`},
    Smaty:{pl:t=>`Gdzie w operacji czuć napięcie, kiedy mowa o „${t}”?`, en:t=>`Where in the operation is the tension felt when "${t}" comes up?`},
    Szow:{pl:t=>`Jest coś w „${t}”, czego zarząd unika nazwać wprost.`, en:t=>`There's something in "${t}" leadership avoids naming directly.`},
    Tai:{pl:t=>`Jaki cykl — kwartalny, sezonowy — wpływa na timing „${t}”?`, en:t=>`What cycle — quarterly, seasonal — affects the timing of "${t}"?`},
    Obver:{pl:t=>`Sekwencja zdarzeń wokół „${t}” — bez oceny, same fakty.`, en:t=>`The sequence of events around "${t}" — no judgment, just facts.`},
    Kidi:{pl:t=>`Zanim policzyliście ROI — czego zespół naprawdę chciał w „${t}”?`, en:t=>`Before you calculated the ROI — what did the team actually want in "${t}"?`}
  }
};
const TENSION_PAIRS = [['Emojy','Kogit'],['Szow','Relacjan'],['Kidi','Deega']];
const SYNTH = {
  personal:{
    pl:t=>`Rada nie jest zgodna co do „${t}”. Synteza nie wygładza tych sprzeczności — zostawia je widoczne. To, co pozostaje niewygodne, zostaje częścią decyzji, nie przeszkodą do usunięcia.`,
    en:t=>`The Council isn't unanimous on "${t}." The synthesis doesn't smooth over these contradictions — it leaves them visible. What stays uncomfortable becomes part of the decision, not an obstacle to remove.`
  },
  fa2:{
    pl:t=>`Base: „${t}” utrzymuje obecny kurs, ryzyko rozłożone w czasie. Bull: szybka decyzja wzmacnia przewagę, ale odsłania to, co Szow nazwał wprost. Bear: zwłoka kosztuje więcej niż błąd. Rada nie wybiera scenariusza za Was.`,
    en:t=>`Base: "${t}" keeps the current course, risk spread over time. Bull: a fast decision strengthens the edge, but exposes what Szow named directly. Bear: delay costs more than a mistake. The Council doesn't choose the scenario for you.`
  }
};
const CLOSURE = {
  pl:t=>`Najmniejszy możliwy krok w ciągu 60 minut: nazwij na głos jedno zdanie o „${t}”, którego dotąd nie powiedziałeś nikomu.`,
  en:t=>`The smallest possible step in the next 60 minutes: say one sentence about "${t}" out loud that you haven't told anyone yet.`
};

/* ---------- DEBATE VISUALS — pulses + light flowing to Syez ---------- */
function pulseNode(name){
  const node = nodeOf(name);
  gsap.fromTo(node.scale, {x:1,y:1,z:1}, {x:1.9,y:1.9,z:1.9, duration:.35, yoyo:true, repeat:1, ease:'power2.out'});
  if(node!==core){
    const th = threads[node.userData.idx];
    gsap.fromTo(th.material, {opacity:.25}, {opacity:.85, duration:.3, yoyo:true, repeat:1});
    flowLight(node, node.userData.agent.ring);
  }
  blip(PITCH[name]||330, .045);
}
function pulseAll(){ COUNCIL_ORDER.forEach((n,i)=>setTimeout(()=>pulseNode(n), i*70)); setTimeout(()=>pulseNode('Syez'), 700); }
function flowLight(node, ringHex){
  if(REDUCED) return;
  const sp = makeGlow(hexToInt(ringHex), .55, .95);
  sp.position.copy(node.position);
  constellation.add(sp);
  gsap.to(sp.position, {x:0, y:0, z:0, duration:.9, ease:'power2.in',
    onComplete(){ constellation.remove(sp); sp.material.dispose();
      gsap.fromTo(core.scale,{x:1,y:1,z:1},{x:1.18,y:1.18,z:1.18,duration:.25,yoyo:true,repeat:1}); }});
  gsap.to(sp.material, {opacity:.2, duration:.9});
}

/* ---------- DEBATE FEED ---------- */
const feedScroll = document.getElementById('feedScroll');
const demoFeed = document.getElementById('demoFeed');
const demoPlaceholder = document.getElementById('demoPlaceholder');
const runBtn = document.getElementById('runDebate');
let demoMode = 'personal';
function setDemoMode(m){
  demoMode = m;
  document.querySelectorAll('.mode-btn').forEach(b=>b.classList.toggle('active', b.dataset.mode===m));
  hudMode.textContent = m;
}
document.querySelectorAll('.mode-btn').forEach(btn=> btn.addEventListener('click', ()=>{ if(!demoRunning) setDemoMode(btn.dataset.mode); }));
document.querySelectorAll('.preset').forEach(btn=> btn.addEventListener('click', ()=>{
  const isEn = document.body.classList.contains('lang-en');
  document.getElementById(isEn?'demoInputEn':'demoInput').value = btn.dataset.topic;
}));
const wait = ms => new Promise(r=>setTimeout(r,ms));

async function addLine(cls, nameHtml, text, colorHex, pulseName){
  if(pulseName) pulseNode(pulseName);
  const el = document.createElement('div');
  el.className = 'demo-line '+cls;
  el.innerHTML = (nameHtml ? `<div class="demo-dot" style="background:${colorHex||'#d4af6a'};color:${colorHex||'#d4af6a'}"></div>` : '') +
    `<div>${nameHtml?`<span class="name">${nameHtml}</span>`:''}<p><span class="demo-cursor"></span></p></div>`;
  demoFeed.appendChild(el);
  gsap.to(el, {opacity:1, duration:.3});
  const pEl = el.querySelector('p'), curEl = el.querySelector('.demo-cursor');
  if(text.includes('<')){
    pEl.insertAdjacentHTML('afterbegin', text);
    feedScroll.scrollTop = feedScroll.scrollHeight;
    await wait(300);
  } else {
    const tt = document.createElement('span'); pEl.insertBefore(tt, curEl);
    for(let i=0;i<text.length;i+=2){
      tt.textContent = text.slice(0,i+2);
      feedScroll.scrollTop = feedScroll.scrollHeight;
      await wait(13);
    }
  }
  curEl?.remove();
}

/* ---------- LIVE COUNCIL (BYOK · OpenRouter) ---------- */
const LLM_MODEL = 'openrouter/free';
const keyInput = document.getElementById('apiKey');
keyInput.value = localStorage.getItem('fa_key') || '';
keyInput.addEventListener('change', ()=> localStorage.setItem('fa_key', keyInput.value.trim()));

function councilPrompt(mode, lang){
  const rolesPL = 'Relacjan (sieć relacji i niewypowiedziane oczekiwania innych), Kogit (ukryte założenia i przekonania), Emojy (emocja jako informacja, zanim zostanie nazwana), Deega (stare wzorce i lojalności wobec przeszłości), Smaty (sygnały ciała), Szow (cień — wyparte i sabotujące, brutalnie szczerze), Tai (pętle i wzorce czasowe), Obver (meta-obserwacja sekwencji zdarzeń bez oceny), Kidi (dziecięca, instynktowna prawda sprzed ograniczeń)';
  const rolesEN = 'Relacjan (web of relationships and unspoken expectations), Kogit (hidden assumptions and beliefs), Emojy (emotion as information, before it gets named), Deega (old patterns and loyalties to the past), Smaty (body signals), Szow (the shadow — repressed and self-sabotaging, bluntly honest), Tai (time loops and patterns), Obver (meta-observation of event sequences, no judgment), Kidi (childlike instinctive truth from before limits)';
  const ctx = mode==='fa2'
    ? (lang==='pl' ? 'Kontekst: decyzja operacyjna zespołu/organizacji. Synteza MUSI zawierać scenariusze Base / Bull / Bear i nie wybierać za zespół.'
                   : 'Context: an operational team/org decision. The synthesis MUST include Base / Bull / Bear scenarios and must not choose for the team.')
    : (lang==='pl' ? 'Kontekst: osobista decyzja użytkownika. Dodaj pole "closure": najmniejszy możliwy krok do wykonania w ciągu 60 minut.'
                   : 'Context: a personal decision. Add a "closure" field: the smallest possible step doable within 60 minutes.');
  const base = lang==='pl'
    ? `Jesteś Radą Nadzorczą — dziewięcioma odrębnymi głosami analizującymi decyzję. Głosy i role: ${rolesPL}. Każdy głos: 1–2 zdania, po polsku, drugoosobowo, surowo i konkretnie, zero języka motywacyjnego, zero gotowych porad. ${ctx} Wskaż jedno realne napięcie między dwoma głosami. Synteza (Syez) uczciwie konsoliduje — nie wygładza sprzeczności i nie decyduje za użytkownika.`
    : `You are the Supervisory Board — nine distinct voices analyzing a decision. Voices and roles: ${rolesEN}. Each voice: 1–2 sentences, in English, second person, raw and specific, no motivational language, no ready-made advice. ${ctx} Name one real tension between two voices. The synthesis (Syez) honestly consolidates — it does not smooth contradictions and does not decide for the user.`;
  return base + ' Return ONLY JSON: {"voices":[{"name":"Relacjan","text":"…"},…] in this exact order: Relacjan,Kogit,Emojy,Deega,Smaty,Szow,Tai,Obver,Kidi, "tension":{"a":"<voice>","b":"<voice>","text":"…"},"synthesis":"…"' + (mode==='personal' ? ',"closure":"…"' : '') + '}';
}
async function askCouncil(topic, mode, lang, key){
  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method:'POST',
    headers:{'Content-Type':'application/json', 'Authorization':'Bearer '+key},
    body:JSON.stringify({ model:LLM_MODEL, temperature:.9, response_format:{type:'json_object'},
      messages:[{role:'system', content:councilPrompt(mode,lang)}, {role:'user', content:topic}] })
  });
  if(!res.ok) throw new Error('HTTP '+res.status);
  const data = await res.json();
  const txt = data.choices[0].message.content;
  const m = txt.match(/\{[\s\S]*\}/);
  return JSON.parse(m ? m[0] : txt);
}

function finishDemo(isEn){
  const replay = document.createElement('button');
  replay.className = 'demo-replay';
  replay.innerHTML = isEn ? 'REPLAY ↺' : 'ODTWÓRZ PONOWNIE ↺';
  replay.onclick = ()=>{ demoRunning=false; runBtn.disabled=false; runBtn.style.opacity=1; runDemo(); };
  demoFeed.appendChild(replay);
  requestAnimationFrame(()=> replay.classList.add('show'));
  runBtn.disabled = false; runBtn.style.opacity = 1;
  demoRunning = false;
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
}

async function runDemo(){
  if(demoRunning) return;
  demoRunning = true;
  renderer.setPixelRatio(1); /* degrade gracefully while streaming */
  if(currentView!=='debata') navigateToView('debata');
  const isEn = document.body.classList.contains('lang-en');
  const raw = document.getElementById(isEn?'demoInputEn':'demoInput').value.trim();
  const topic = raw || (isEn ? 'A decision I keep postponing' : 'Decyzja, którą odkładam');
  const lang = isEn ? 'en' : 'pl';
  demoFeed.innerHTML = '';
  demoPlaceholder.style.display = 'none';
  runBtn.disabled = true; runBtn.style.opacity = .5;
  document.querySelector('.demo-replay')?.remove();

  const key = keyInput.value.trim();
  if(key){
    const hb = setInterval(()=> pulseNode(COUNCIL_ORDER[Math.floor(Math.random()*COUNCIL_ORDER.length)]), 420);
    try{
      await addLine('a0', null, isEn?'<em>The Council is deliberating — a real debate, on your key…</em>':'<em>Rada obraduje — prawdziwa debata, na Twoim kluczu…</em>');
      const R = await askCouncil(topic, demoMode, lang, key);
      clearInterval(hb);
      for(const v of (R.voices||[])){
        await addLine('', v.name, v.text, ringOf(v.name), v.name);
        await wait(320);
      }
      if(R.tension){
        pulseNode(R.tension.a); setTimeout(()=>pulseNode(R.tension.b), 180);
        await addLine('tension', isEn?'Tension':'Napięcie', `${R.tension.a} ⇄ ${R.tension.b} — ${R.tension.text}`, '#c98a6a');
        await wait(400);
      }
      await addLine('synth', 'Syez', R.synthesis, '#f4c85a', 'Syez');
      if(R.closure){
        pulseAll();
        await addLine('closure', isEn?'AXIOM 2 · Completion':'AKSJOMAT 2 · Domknięcie', R.closure, '#8ac98a');
      }
      finishDemo(isEn);
      return;
    }catch(err){
      clearInterval(hb);
      await addLine('tension', 'Offline', isEn?('Live call failed ('+err.message+') — playing the simulation.'):('Połączenie nie wyszło ('+err.message+') — odtwarzam symulację.'), '#c98a6a');
      await wait(400);
    }
  }

  if(demoMode==='personal'){
    pulseNode('Syez');
    await addLine('a0', null, isEn?'<em>A0 — distilling the dream behind the question…</em>':'<em>A0 — destylacja marzenia stojącego za pytaniem…</em>');
    await wait(500);
  }
  for(const name of COUNCIL_ORDER){
    await addLine('', name, TPL[demoMode][name][lang](topic), ringOf(name), name);
    await wait(550);
  }
  const [a,b] = TENSION_PAIRS[Math.floor(Math.random()*TENSION_PAIRS.length)];
  pulseNode(a); setTimeout(()=>pulseNode(b), 180);
  await addLine('tension', isEn?'Tension':'Napięcie', TENSION_MSG[lang](a,b), '#c98a6a');
  await wait(500);
  await addLine('synth', 'Syez', SYNTH[demoMode][lang](topic), '#f4c85a', 'Syez');
  await wait(500);
  if(demoMode==='personal'){
    pulseAll();
    await addLine('closure', isEn?'AXIOM 2 · Completion':'AKSJOMAT 2 · Domknięcie', CLOSURE[lang](topic), '#8ac98a');
  }
  finishDemo(isEn);
}
runBtn.addEventListener('click', runDemo);
document.querySelectorAll('#demoInput,#demoInputEn').forEach(inp=> inp.addEventListener('keydown', e=>{ if(e.key==='Enter') runDemo(); }));

/* ---------- DAILY SIGNAL — session memory + marker feedback ---------- */
const dailySignal = ['','',''];
document.querySelectorAll('.signal-slot input').forEach(inp=>{
  inp.addEventListener('input', ()=>{
    const i = +inp.dataset.slot;
    dailySignal[i] = inp.value;
    const m = daily.userData.markers[i];
    gsap.to(m.children[1].material, {opacity: inp.value.trim()? 1 : .7, duration:.4});
    gsap.to(m.scale, {x:inp.value.trim()?1.35:1, y:inp.value.trim()?1.35:1, z:inp.value.trim()?1.35:1, duration:.5, ease:'back.out(2)'});
  });
});

/* ---------- AMBIENT AUDIO ---------- */
const PITCH = {Syez:392, Relacjan:261.6, Kogit:293.7, Emojy:329.6, Deega:220, Smaty:246.9, Szow:196, Tai:349.2, Obver:277.2, Kidi:440};
let AC=null, master=null, audioOn=false;
const audioBtn = document.getElementById('audiotoggle');
function buildDrone(){
  AC = new (window.AudioContext||window.webkitAudioContext)();
  master = AC.createGain(); master.gain.value = 0; master.connect(AC.destination);
  const lp = AC.createBiquadFilter(); lp.type='lowpass'; lp.frequency.value=340; lp.connect(master);
  [[55,.5],[82.41,.22],[110,.12],[164.8,.05]].forEach(([f,g])=>{
    const o=AC.createOscillator(), og=AC.createGain();
    o.type='sine'; o.frequency.value=f; og.gain.value=g;
    const lfo=AC.createOscillator(), lg=AC.createGain();
    lfo.frequency.value=.05+Math.random()*.06; lg.gain.value=g*.45;
    lfo.connect(lg); lg.connect(og.gain);
    o.connect(og); og.connect(lp); o.start(); lfo.start();
  });
}
function blip(freq, vol){
  if(!audioOn||!AC) return;
  const o=AC.createOscillator(), g=AC.createGain();
  o.type='sine'; o.frequency.value=freq;
  g.gain.setValueAtTime(.0001, AC.currentTime);
  g.gain.exponentialRampToValueAtTime(vol??.045, AC.currentTime+.03);
  g.gain.exponentialRampToValueAtTime(.0001, AC.currentTime+.6);
  o.connect(g); g.connect(AC.destination);
  o.start(); o.stop(AC.currentTime+.65);
}
audioBtn.addEventListener('click', ()=>{
  if(!AC) buildDrone();
  if(AC.state==='suspended') AC.resume();
  audioOn = !audioOn;
  master.gain.cancelScheduledValues(AC.currentTime);
  master.gain.linearRampToValueAtTime(audioOn?.14:0, AC.currentTime+1.4);
  audioBtn.textContent = audioOn ? '◉' : '◎';
  audioBtn.classList.toggle('on', audioOn);
});

/* ---------- MOBILE MENU (actions) ---------- */
const menuBtn = document.getElementById('menutoggle');
if(menuBtn){
  menuBtn.addEventListener('click', (e)=>{
    e.stopPropagation();
    document.body.classList.toggle('menu-open');
  });
  document.addEventListener('click', (e)=>{
    if(!document.body.classList.contains('menu-open')) return;
    if(e.target.closest('#topbar')) return;
    document.body.classList.remove('menu-open');
  });
  window.addEventListener('resize', ()=>{
    if(innerWidth > 768) document.body.classList.remove('menu-open');
  });
}

/* ---------- BOOT ---------- */
setTargets(0);
nodes.forEach(n=>n.position.copy(n.userData.target));
render();
const loaderEl = document.getElementById('loader');
const countEl = loaderEl.querySelector('.loader-count');
const barEl = loaderEl.querySelector('.loader-bar i');
const load = {v:0};
gsap.to(load, {v:100, duration:1.7, ease:'power2.inOut',
  onUpdate(){ countEl.textContent = String(Math.round(load.v)).padStart(2,'0'); barEl.style.width = load.v+'%'; },
  onComplete(){
    loaderEl.classList.add('done');
    setTimeout(()=>loaderEl.remove(), 1000);
    const initialView = document.body.dataset.initialView;
    const initialAgent = document.body.dataset.initialAgent;
    function afterEntry(){
      if(initialView && VIEWS[initialView]){
        setView(initialView, {force:true});
      } else if(SCROLL_MODE){
        scrollRevealed.add('rada');
        applyScrollProgress(0);
      } else {
        revealPanels(document.getElementById('v-rada'));
      }
      if(initialAgent) setTimeout(()=>focusAgent(initialAgent), REDUCED?0:800);
    }
    if(SCROLL_MODE || REDUCED){
      camPos.set(0, 1.4, 9); camera.position.copy(camPos);
      afterEntry();
    } else {
      camPos.set(0, 6, 16); camera.position.set(0,6,16);
      gsap.to(camPos, {x:0, y:1.4, z:9, duration:2.2, ease:'power3.inOut', onComplete:afterEntry});
    }
  }});
