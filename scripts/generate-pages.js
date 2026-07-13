#!/usr/bin/env node
/**
 * Generuje podstrony agentów + fragment.html + testuj.html z szablonu.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");

const AGENTS = [
  { id: "relacjan", name: "Relacjan", file: "Relacjan.png", role: "Relacje i zaufanie", tagline: "Mapuje wpływ, dynamikę i ludzi wokół decyzji", canvas: "network", story: [
    "Relacjan nie pyta, co chcesz zrobić. Pyta, kto będzie musiał to udźwignąć — i kto udaje, że nie wie.",
    "W debacie Rady mapuje niewidzialne linie: kto komu ufa, kto się wycofuje, kto udaje zgodę, żeby nie stracić pozycji. Nie ocenia charakterów. Opisuje siłę pola.",
    "Jego głos jest cichy i niewygodny dla tych, którzy wolą tabele zamiast ludzi. Bo decyzja bez mapy relacji to decyzja na piasku.",
  ]},
  { id: "kogit", name: "Kogit", file: "Kogit.png", role: "Logika i struktura", tagline: "Zimna architektoniczna jasność", canvas: "structure", story: [
    "Kogit nie tłumaczy emocji. Rozkłada je na elementy składowe, aż zostaje sama konstrukcja.",
    "W Radzie odpowiada za to, co wielu liderów omija: czy argument się spina, czy założenia są jawne, czy logika nie jest tylko opowieścią o kontroli.",
    "Jego jasność bywa odczuwana jako chłód. To nie chłód — to precyzja, która nie prosi o zgodę.",
  ]},
  { id: "emojy", name: "Emojy", file: "Emojy.png", role: "Emocje prewerbalne", tagline: "To, czego słowa jeszcze nie niosą", canvas: "waves", story: [
    "Emojy mówi zanim zdania są gotowe. Rejestruje napięcie, które jeszcze nie ma nazwy — w pokoju, w ciszy, w tonie głosu.",
    "W Radzie przypomina, że decyzja często zapada wcześniej niż pojawia się na slajdzie. Że ciało zespołu wie, zanim raport to potwierdzi.",
    "Nie dramatyzuje. Nie uspokaja. Nazywa to, co wisiało w powietrzu.",
  ]},
  { id: "deega", name: "Deega", file: "Deega.png", role: "Głęboka diagnoza", tagline: "Nieświadome pętle i ukryte powtórzenia", canvas: "loops", story: [
    "Deega widzi schematy, które organizacja powtarza, nie wiedząc dlaczego. Te same konflikty. Te same „nowe” strategie.",
    "W Radzie wskazuje pętle: gdzie decyzja jest już podjęta, zanim ktoś otworzy usta. Gdzie strach przebrany za racjonalność wraca pod inną nazwą.",
    "Jego diagnoza nie jest wygodna. Jest dokładna.",
  ]},
  { id: "smaty", name: "Smaty", file: "Smaty.png", role: "Somatyczny", tagline: "To, co ciało już wie", canvas: "pulse", story: [
    "Smaty nie czyta slajdów. Czyta napięcie w barkach, oddech w sali, sposób, w jaki ludzie przestają patrzeć na siebie.",
    "W Radzie reprezentuje wiedzę ciała — tę, która nie przechodzi przez Excela, ale prowadzi zespoły do wypalenia albo do odwagi.",
    "Gdy mówi, że „to nie pasuje”, nie chodzi o estetykę. Chodzi o sygnał, który organizacja zignorowała za długo.",
  ]},
  { id: "tai", name: "Tai", file: "Tai.png", role: "Perspektywa czasu", tagline: "Długie wzorce i konsekwencje przyszłości", canvas: "time", story: [
    "Tai patrzy na decyzję jak na kamień wrzucony do rzeki. Fala wraca — za kwartał, za rok, za dekadę.",
    "W Radzie nie prognozuje modnie. Pokazuje długie łuki: co dziś wydaje się drobną korektą, a jutro staje się kulturą, od której nie ma odwrotu.",
    "Jego czas nie jest abstrakcją. To odpowiedzialność wobec tych, którzy przyjdą po nas.",
  ]},
  { id: "szow", name: "Szow", file: "Szow.png", role: "Cień", tagline: "To, czego najmniej chcesz usłyszeć", canvas: "shadow", story: [
    "Szow nie jest demonem. Jest tym, co już wiesz — i odkładasz na później, bo nazwanie tego zmieni wszystko.",
    "W Radzie mówi wprost: gdzie korzyść jest twoja, a nie firmy. Gdzie unikasz rozmowy, bo stracisz iluzję kontroli. Gdzie „racjonalna decyzja” maskuje lęk przed stratą twarzy.",
    "Jego głos nie jest agresją. Jest lustrem bez filtra.",
  ]},
  { id: "obver", name: "Obver", file: "Obver.png", role: "Obserwator zewnętrzny", tagline: "Meta-perspektywa poza twoją historią", canvas: "lens", story: [
    "Obver stoi poza twoją narracją o sobie. Widzi wzorzec, którego ty nie widzisz, bo jesteś jego autorem.",
    "W Radzie nie doradza z pozycji eksperta. Opisuje scenę: kto gra jaką rolę, jaki jest układ sił, gdzie debata jest teatrem zamiast badaniem.",
    "Jego dystans nie jest obojętnością. To warunek uczciwej syntezy.",
  ]},
  { id: "kidi", name: "Kidi", file: "Kidi.png", role: "Dziecięca ciekawość", tagline: "Czysta fascynacja i instynkt", canvas: "spark", story: [
    "Kidi zadaje pytanie, którego nikt już nie zadaje, bo wszyscy „wiedzą, jak jest”.",
    "W Radzie reprezentuje instynkt bez kariery do obrony. Co by tu było, gdybyśmy nie bali się wyglądać głupio? Co jeśli założenie jest po prostu… nudne?",
    "Jego ciekawość nie jest naiwnością. To ostatni czysty filtr przed kompromisem, który zabije sens.",
  ]},
];

function agentPage(agent, prev, next) {
  const storyHtml = agent.story.map((p) => `<p>${p}</p>`).join("\n          ");
  const prevLink = prev ? `<a href="/${prev.id}">← ${prev.name}</a>` : `<a href="/#rada">← Rada</a>`;
  const nextLink = next ? `<a href="/${next.id}">${next.name} →</a>` : `<a href="/#rada">Rada →</a>`;

  return `<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${agent.name} — Rada Nadzorcza · Freedom Architect: Polyphony</title>
  <meta name="description" content="${agent.role}. ${agent.tagline}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles/main.css">
</head>
<body>
  <header class="site-header">
    <div class="container inner">
      <a href="/" class="brand">Freedom Architect<span>:</span> Polyphony</a>
      <nav class="nav-links">
        <a href="/#rada">Rada</a>
        <a href="/#jak-dziala">Jak działa</a>
        <a href="/fragment">Fragment</a>
        <a href="/testuj">Program testowy</a>
      </nav>
    </div>
  </header>

  <main class="container">
    <section class="agent-hero">
      <div class="agent-portrait">
        <img src="/assets/council/${agent.file}" alt="Portret ${agent.name}" width="480" height="640" loading="eager">
      </div>
      <div>
        <p class="caps">${agent.role}</p>
        <h1 class="serif" style="font-size: clamp(2.2rem, 4vw, 3rem); margin: 0.5rem 0 1rem;">${agent.name}</h1>
        <p class="lead">${agent.tagline}</p>
        <div class="agent-story" style="margin-top: 2rem;">
          ${storyHtml}
        </div>
        <div class="btn-row">
          <a href="/testuj" class="btn btn-ghost">Zgłoś się do programu testowego</a>
        </div>
      </div>
    </section>

    <section>
      <p class="caps section-label">Mechanizm w debacie</p>
      <h2 class="section-title">Jak ${agent.name} pracuje w Radzie</h2>
      <div class="canvas-wrap">
        <canvas id="agent-canvas" aria-label="Wizualizacja mechanizmu ${agent.name}"></canvas>
        <p class="canvas-caption">${agent.tagline}</p>
      </div>
    </section>

    <nav class="agent-nav">
      ${prevLink}
      <a href="/#rada">Powrót do Rady</a>
      ${nextLink}
    </nav>
  </main>

  <footer class="site-footer">
    <div class="container inner">
      <span>Freedom Architect: Polyphony · mypolyphony.com</span>
      <span class="muted">Warstwa narracyjna · 2026</span>
    </div>
  </footer>

  <script src="/js/canvas/agent-canvas.js"></script>
  <script>initAgentCanvas("agent-canvas", "${agent.canvas}");</script>
  <script src="/js/i18n.js"></script>
</body>
</html>
`;
}

function fragmentPage() {
  return `<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fragment — Freedom Architect: Polyphony</title>
  <meta name="description" content="Głęboka warstwa filozoficzna Fragmentu — to, co zostaje, gdy debata się kończy.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles/main.css">
</head>
<body>
  <header class="site-header">
    <div class="container inner">
      <a href="/" class="brand">Freedom Architect<span>:</span> Polyphony</a>
      <nav class="nav-links">
        <a href="/#rada">Rada</a>
        <a href="/testuj">Program testowy</a>
      </nav>
    </div>
  </header>

  <main class="container" style="padding: 4rem 0;">
    <p class="caps section-label">Fragment</p>
    <h1 class="serif" style="font-size: clamp(2.4rem, 5vw, 3.2rem); margin-bottom: 1.5rem;">To, co zostaje po debacie</h1>

    <div class="split" style="margin-bottom: 3rem;">
      <div class="agent-story">
        <p>Fragment nie jest podsumowaniem. Nie jest slajdem. Nie jest „action item listą”.</p>
        <p>To ślad po polifonii — zapis tego, co było prawdziwe w momencie decyzji, zanim organizacja zaczęła to upraszczać dla prezentacji.</p>
        <p>W Freedom Architect Fragment jest warstwą, która pilnuje, żeby synteza nie zjadła sprzeczności. Żeby lider widział nie tylko „co zrobić”, ale co w tej decyzji pozostaje niewygodne — i dlaczego to ma znaczenie.</p>
        <p>Nie obiecujemy, że Fragment rozwiąże ten dyskomfort. Obiecujemy tylko, że nie zniknie w drodze do PowerPointa.</p>
      </div>
      <div class="canvas-wrap">
        <canvas id="fragment-canvas" aria-label="Wizualizacja Fragmentu"></canvas>
        <p class="canvas-caption">Fragment — ślad syntezy, który nie spłaszcza złożoności</p>
      </div>
    </div>

    <div class="btn-row">
      <a href="/#rada" class="btn btn-ghost">Poznaj Radę</a>
      <a href="/testuj" class="btn btn-primary">Program testowy</a>
    </div>
  </main>

  <footer class="site-footer">
    <div class="container inner">
      <span>Freedom Architect: Polyphony · mypolyphony.com</span>
      <span class="muted">Warstwa narracyjna · 2026</span>
    </div>
  </footer>

  <script src="/js/canvas/agent-canvas.js"></script>
  <script>
    // Fragment: złoty rdzeń + rozproszone ślady (hybryda lens + waves)
    (function() {
      const canvas = document.getElementById("fragment-canvas");
      const ctx = canvas.getContext("2d");
      let w, h, dpr, t = 0;
      function resize() {
        const rect = canvas.parentElement.getBoundingClientRect();
        dpr = Math.min(devicePixelRatio || 1, 2);
        w = rect.width; h = Math.max(300, w * 0.55);
        canvas.width = w * dpr; canvas.height = h * dpr;
        canvas.style.height = h + "px";
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      function draw() {
        t += 0.01;
        ctx.clearRect(0, 0, w, h);
        const cx = w/2, cy = h/2;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, 100);
        g.addColorStop(0, "rgba(201,162,39,0.2)");
        g.addColorStop(1, "transparent");
        ctx.fillStyle = g;
        ctx.beginPath(); ctx.arc(cx, cy, 100, 0, Math.PI*2); ctx.fill();
        for (let i = 0; i < 12; i++) {
          const a = (i/12)*Math.PI*2 + t*0.05;
          ctx.strokeStyle = "rgba(201,162,39,0.15)";
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(cx + Math.cos(a)*120, cy + Math.sin(a)*80);
          ctx.stroke();
        }
        requestAnimationFrame(draw);
      }
      resize(); window.addEventListener("resize", resize); draw();
    })();
  </script>
  <script src="/js/i18n.js"></script>
</body>
</html>
`;
}

function testujPage() {
  return `<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Program testowy — Freedom Architect: Polyphony</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles/main.css">
  <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</head>
<body>
  <header class="site-header">
    <div class="container inner">
      <a href="/" class="brand">Freedom Architect<span>:</span> Polyphony</a>
      <nav class="nav-links">
        <a href="/#rada">Rada</a>
        <a href="/fragment">Fragment</a>
      </nav>
    </div>
  </header>

  <main class="container" style="padding: 4rem 0; max-width: 560px;">
    <p class="caps section-label">Program testowy</p>
    <h1 class="serif section-title">Zgłoszenie</h1>
    <p class="muted" style="margin-bottom: 2rem;">
      Kontrolowany dostęp. System w stanie pre-produkcyjnym. Odpowiadamy tylko wybranym kandydatom.
    </p>

    <div class="form-panel">
      <form data-polyphony-form novalidate>
        <div class="form-grid">
          <div class="form-field">
            <label for="name">Imię i nazwisko</label>
            <input type="text" id="name" name="name" required maxlength="200">
          </div>
          <div class="form-field">
            <label for="company">Stanowisko / Firma</label>
            <input type="text" id="company" name="company" required maxlength="200">
          </div>
          <div class="form-field">
            <label for="email">Email służbowy</label>
            <input type="email" id="email" name="email" required maxlength="200">
          </div>
          <div class="hp-field" aria-hidden="true">
            <input type="text" name="website" tabindex="-1" autocomplete="off">
            <input type="text" name="hp" tabindex="-1" autocomplete="off">
          </div>
          <div class="cf-turnstile"></div>
          <button type="submit" class="btn btn-primary" style="width:100%">Wyślij zgłoszenie</button>
        </div>
        <div class="form-status" role="status" aria-live="polite"></div>
      </form>
    </div>
  </main>

  <footer class="site-footer">
    <div class="container inner">
      <span>Freedom Architect: Polyphony · mypolyphony.com</span>
    </div>
  </footer>

  <script src="/js/config.js"></script>
  <script src="/js/form.js"></script>
  <script src="/js/i18n.js"></script>
</body>
</html>
`;
}

AGENTS.forEach((agent, i) => {
  const prev = i > 0 ? AGENTS[i - 1] : null;
  const next = i < AGENTS.length - 1 ? AGENTS[i + 1] : null;
  const html = agentPage(agent, prev, next);
  const file = path.join(ROOT, `${agent.id}.html`);
  fs.writeFileSync(file, html);
  console.log("Wrote", file);
});

fs.writeFileSync(path.join(ROOT, "fragment.html"), fragmentPage());
fs.writeFileSync(path.join(ROOT, "testuj.html"), testujPage());
console.log("Done.");
