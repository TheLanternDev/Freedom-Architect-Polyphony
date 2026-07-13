/**
 * Polyphony i18n — PL (default) / EN
 */
(function () {
  "use strict";

  var STORAGE_KEY = "polyphony_lang";

  var STRINGS = {
    pl: {
      "nav.firms": "Dla firm",
      "nav.personal": "Dla Ciebie",
      "nav.council": "Rada",
      "nav.how": "Jak działa",
      "nav.fragment": "Fragment",
      "nav.test": "Program testowy",
      "nav.menu": "Menu nawigacji",
      "nav.close": "Zamknij menu",
      "nav.backCouncil": "← Rada",
      "nav.forwardCouncil": "Rada →",
      "footer.layer": "Warstwa narracyjna · 2026",
      "lang.label": "Język",
      "home.meta.title": "Freedom Architect: Polyphony — Rada Nadzorcza",
      "home.meta.description": "Dziewięć perspektyw. Jedna decyzja. Polifonia bez spłaszczania złożoności — dla firm i dla Ciebie.",
      "home.hero.label": "Warstwa narracyjna · pre-produkcja",
      "home.hero.title": "Dziewięć perspektyw. Jedna decyzja. Polifonia bez konsensusu za wszelką cenę.",
      "home.hero.lead": "Freedom Architect: Polyphony to nie kolejny chatbot z odpowiedzią. To Rada — dziewięć odrębnych głosów, które ścierają się ze sobą, zanim powstanie synteza. Bez motywacyjnego języka. Bez obietnicy natychmiastowego dostępu.",
      "home.fork.label": "Wybierz ścieżkę",
      "home.fork.title": "Dwa konteksty. Ten sam rdzeń.",
      "home.fork.lead": "System działa w dwóch trybach — operacyjnym i osobistym. Oba opierają się na tej samej Radzie. Różni się to, nad czym pracujesz.",
      "home.fork.firma.title": "Dla firm",
      "home.fork.firma.lead": "Decyzje operacyjne, napięcia w zespole, scenariusze Base/Bull/Bear. Dla liderów RevOps i Operations — nie demo, prawdziwe decyzje.",
      "home.fork.firma.cta": "Ścieżka firmowa",
      "home.fork.osobista.title": "Dla Ciebie",
      "home.fork.osobista.lead": "Decyzje życiowe, wewnętrzne konflikty, mapa perspektyw, której sam nie widzisz. Surowo — bez coachingu i bez terapii.",
      "home.fork.osobista.cta": "Ścieżka osobista",
      "home.council.label": "Rada Nadzorcza",
      "home.council.title": "Dziewięć głosów. Żaden nie jest „główny”.",
      "home.council.lead": "Każdy agent reprezentuje inną warstwę poznania. Razem tworzą polifonię — nie konsensus za wszelką cenę.",
      "home.council.all": "Zobacz całą Radę",
      "firmy.meta.title": "Dla firm — Freedom Architect: Polyphony",
      "firmy.meta.description": "Freedom Architect Business (fa2): decyzje operacyjne, scenariusze Base/Bull/Bear, polifonia dla liderów RevOps i Operations.",
      "firmy.hero.label": "Ścieżka firmowa · fa2",
      "firmy.hero.title": "Decyzja operacyjna, której nie podejmujesz sam — bo nikt nie widzi całej mapy.",
      "firmy.hero.lead": "Tryb Freedom Architect Business mapuje napięcia w zespole, modele i metryki — a potem buduje syntezę ze scenariuszami Base, Bull i Bear. Nie demo. Prawdziwe decyzje, na których stoi operacja.",
      "firmy.hero.cta1": "Zgłoś zespół do programu testowego",
      "firmy.hero.cta2": "Jak działa w firmie",
      "firmy.how.label": "Jak działa",
      "firmy.how.title": "Ścieranie perspektyw. Synteza bez uproszczeń.",
      "firmy.how.p1": "Nie szukamy jednej „właściwej” odpowiedzi dla boardu. Mapujemy napięcia między logiką, danymi, cieniem organizacji i czasem — a potem budujemy syntezę, która nie zgładza tego, co niewygodne.",
      "firmy.how.p2": "Scenariusze Base/Bull/Bear nie są prognozą na slajdzie. To ramy, w których widać, co w decyzji zostaje niewygodne — zanim trafi do prezentacji.",
      "firmy.how.canvas": "Polifonia — linie napięć i złoty moment syntezy",
      "firmy.program.label": "Program testowy",
      "firmy.program.title": "Kontrolowany dostęp. Nie dla wszystkich.",
      "firmy.program.p1": "System jest w stanie pre-produkcyjnym. Program testowy jest zamknięty — rekrutujemy liderów RevOps i Operations, którzy pracują na prawdziwych decyzjach, nie na demo.",
      "firmy.program.p2": "Zgłoszenie nie gwarantuje dostępu. Odpowiadamy tylko wybranym kandydatom.",
      "firmy.program.cta": "Zgłoś zespół",
      "osobista.meta.title": "Dla Ciebie — Freedom Architect: Polyphony",
      "osobista.meta.description": "Tryb personal: decyzje życiowe, integracja wewnętrznych konfliktów, polifonia perspektyw — bez coachingu i bez terapii.",
      "osobista.hero.label": "Ścieżka osobista · personal",
      "osobista.hero.title": "Decyzja, której nie podejmujesz sam — bo nie widzisz całej swojej mapy.",
      "osobista.hero.lead": "Tryb personal nie daje gotowej odpowiedzi ani afirmacji. Mapuje perspektywy — logikę, ciało, cień, czas — i pokazuje, co w decyzji pozostaje niewygodne. Surowo. Transformacyjnie. Bez języka motywacyjnego.",
      "osobista.hero.cta1": "Dołącz do wczesnego dostępu",
      "osobista.hero.cta2": "Jak to działa",
      "osobista.how.label": "Co system robi",
      "osobista.how.title": "Mapuje perspektywy. Nie obiecuje efektu.",
      "osobista.how.p1": "Rada nie „naprawia” Cię i nie diagnozuje. Pokazuje, jak różne warstwy widzą tę samą decyzję — i gdzie się ścierają. Synteza nie zgładza sprzeczności. Zostawia je widoczne.",
      "osobista.how.p2": "To narzędzie do pracy nad decyzją — nie zamiennik pomocy medycznej, terapeutycznej ani wsparcia kryzysowego.",
      "osobista.how.canvas": "Polifonia — perspektywy w decyzji życiowej",
      "osobista.compliance.title": "Ważne informacje",
      "osobista.compliance.disclaimer": "To nie jest pomoc medyczna ani terapeutyczna.",
      "osobista.compliance.ai": "Rozmawiasz z systemem AI (Radą), nie z człowiekiem.",
      "osobista.compliance.crisis": "Jeśli jesteś w kryzysie lub potrzebujesz natychmiastowej pomocy — zadzwoń pod numer alarmowy 112 lub skontaktuj się z lokalną linią wsparcia w kryzysie psychicznym.",
      "osobista.compliance.privacy": "Twoje debaty zostają lokalnie; model działa na Twoim kluczu (BYOK). Nie hostujemy treści rozmów w chmurze.",
      "osobista.program.label": "Wczesny dostęp",
      "osobista.program.title": "Kontrolowany dostęp. Nie dla wszystkich.",
      "osobista.program.p1": "Program jest zamknięty i w stanie pre-produkcyjnym. Nie zbieramy w formularzu danych o zdrowiu ani uzależnieniach — tylko kontakt do waitlisty.",
      "osobista.program.p2": "Zgłoszenie nie gwarantuje dostępu. Odpowiadamy wybranym kandydatom.",
      "osobista.program.cta": "Dołącz do waitlisty",
      "form.name": "Imię i nazwisko",
      "form.name.personal": "Imię",
      "form.company": "Stanowisko / Firma",
      "form.email": "Email służbowy",
      "form.email.personal": "Email",
      "form.track": "Ścieżka",
      "form.track.firma": "Dla firm",
      "form.track.osobista": "Dla Ciebie",
      "form.submit": "Wyślij zgłoszenie",
      "form.sending": "Wysyłanie…",
      "form.note": "Dane trafiają do zabezpieczonego endpointu. Bez spamu. Bez sprzedaży list mailingowych.",
      "form.success": "Zgłoszenie przyjęte. Odpowiadamy tylko wybranym kandydatom.",
      "form.success.email": "Zgłoszenie przyjęte. Wysłaliśmy potwierdzenie na Twój e-mail. Odpowiadamy tylko wybranym kandydatom.",
      "form.error.turnstile": "Potwierdź, że nie jesteś botem (Turnstile).",
      "form.error.fields": "Uzupełnij imię i email.",
      "form.error.company": "Uzupełnij stanowisko lub firmę.",
      "form.error.generic": "Nie udało się wysłać zgłoszenia. Spróbuj ponownie.",
      "form.error.network": "Błąd połączenia. Sprawdź sieć i spróbuj ponownie.",
      "agent.mechanism.label": "Mechanizm w debacie",
      "agent.mechanism.title": "Jak {name} pracuje w Radzie",
      "agent.cta": "Zgłoś się do programu testowego",
      "agent.back": "Powrót do Rady",
      "agent.portrait": "Portret {name}",
      "fragment.meta.title": "Fragment — Freedom Architect: Polyphony",
      "fragment.meta.description": "Głęboka warstwa filozoficzna Fragmentu — to, co zostaje, gdy debata się kończy.",
      "fragment.label": "Fragment",
      "fragment.title": "To, co zostaje po debacie",
      "fragment.p1": "Fragment nie jest podsumowaniem. Nie jest slajdem. Nie jest listą zadań.",
      "fragment.p2": "To ślad po polifonii — zapis tego, co było prawdziwe w momencie decyzji, zanim zaczęło się to spłaszczać dla wygody.",
      "fragment.p3": "W Freedom Architect Fragment jest warstwą, która pilnuje, żeby synteza nie zjadła sprzeczności. Żebyś widział nie tylko „co zrobić”, ale co w tej decyzji pozostaje niewygodne — i dlaczego to ma znaczenie.",
      "fragment.p4": "Nie obiecujemy, że Fragment rozwiąże ten dyskomfort. Obiecujemy tylko, że nie zniknie w drodze do uproszczenia.",
      "fragment.canvas": "Fragment — ślad syntezy, który nie spłaszcza złożoności",
      "fragment.cta1": "Poznaj Radę",
      "fragment.cta2": "Program testowy",
      "test.meta.title": "Program testowy — Freedom Architect: Polyphony",
      "test.meta.description": "Kontrolowany dostęp do programu testowego — ścieżka firmowa lub osobista.",
      "test.label": "Program testowy",
      "test.title": "Zgłoszenie",
      "test.lead": "Kontrolowany dostęp, system w stanie pre-produkcyjnym. Szukamy zarówno liderów RevOps i Operations pracujących na prawdziwych decyzjach operacyjnych, jak i osób, które chcą użyć Rady do realnej decyzji osobistej. Zgłoszenie nie gwarantuje dostępu — odpowiadamy tylko wybranym kandydatom.",
      "test.lead.firma": "Zgłoszenie do programu testowego — ścieżka firmowa. Rekrutujemy liderów RevOps i Operations.",
      "test.lead.osobista": "Waitlist wczesnego dostępu — ścieżka osobista. Nie zbieramy danych wrażliwych w tym formularzu.",
    },
    en: {
      "nav.firms": "For business",
      "nav.personal": "For you",
      "nav.council": "Council",
      "nav.how": "How it works",
      "nav.fragment": "Fragment",
      "nav.test": "Beta program",
      "nav.menu": "Navigation menu",
      "nav.close": "Close menu",
      "nav.backCouncil": "← Council",
      "nav.forwardCouncil": "Council →",
      "footer.layer": "Narrative layer · 2026",
      "lang.label": "Language",
      "home.meta.title": "Freedom Architect: Polyphony — Supervisory Board",
      "home.meta.description": "Nine perspectives. One decision. Polyphony without flattening complexity — for business and for you.",
      "home.hero.label": "Narrative layer · pre-production",
      "home.hero.title": "Nine perspectives. One decision. Polyphony without consensus at any cost.",
      "home.hero.lead": "Freedom Architect: Polyphony is not another chatbot with an answer. It is a Board — nine distinct voices that collide before synthesis emerges. No motivational language. No promise of instant access.",
      "home.fork.label": "Choose your path",
      "home.fork.title": "Two contexts. Same core.",
      "home.fork.lead": "The system runs in two modes — operational and personal. Both use the same Board. What changes is what you work on.",
      "home.fork.firma.title": "For business",
      "home.fork.firma.lead": "Operational decisions, team tension, Base/Bull/Bear scenarios. For RevOps and Operations leaders — not demos, real decisions.",
      "home.fork.firma.cta": "Business path",
      "home.fork.osobista.title": "For you",
      "home.fork.osobista.lead": "Life decisions, inner conflicts, a map of perspectives you cannot see alone. Raw — not coaching, not therapy.",
      "home.fork.osobista.cta": "Personal path",
      "home.council.label": "Supervisory Board",
      "home.council.title": "Nine voices. None is \"primary\".",
      "home.council.lead": "Each agent represents a different layer of knowing. Together they form polyphony — not consensus at any cost.",
      "home.council.all": "See the full Board",
      "firmy.meta.title": "For business — Freedom Architect: Polyphony",
      "firmy.meta.description": "Freedom Architect Business (fa2): operational decisions, Base/Bull/Bear scenarios, polyphony for RevOps and Operations leaders.",
      "firmy.hero.label": "Business path · fa2",
      "firmy.hero.title": "An operational decision you do not make alone — because no one sees the full map.",
      "firmy.hero.lead": "Freedom Architect Business mode maps team tension, models, and metrics — then builds synthesis with Base, Bull, and Bear scenarios. Not a demo. Real decisions that operations stand on.",
      "firmy.hero.cta1": "Apply your team for the beta program",
      "firmy.hero.cta2": "How it works in business",
      "firmy.how.label": "How it works",
      "firmy.how.title": "Friction of perspectives. Synthesis without simplification.",
      "firmy.how.p1": "We do not hunt for one \"correct\" board answer. We map tension between logic, data, organizational shadow, and time — then build synthesis that does not sand down what is uncomfortable.",
      "firmy.how.p2": "Base/Bull/Bear scenarios are not slide forecasts. They are frames where you see what stays uncomfortable in the decision — before it reaches the deck.",
      "firmy.how.canvas": "Polyphony — lines of tension and the golden moment of synthesis",
      "firmy.program.label": "Beta program",
      "firmy.program.title": "Controlled access. Not for everyone.",
      "firmy.program.p1": "The system is pre-production. The beta program is closed — we recruit RevOps and Operations leaders working on real decisions, not demos.",
      "firmy.program.p2": "Applying does not guarantee access. We respond only to selected candidates.",
      "firmy.program.cta": "Apply your team",
      "osobista.meta.title": "For you — Freedom Architect: Polyphony",
      "osobista.meta.description": "Personal mode: life decisions, integrating inner conflicts, polyphony of perspectives — not coaching, not therapy.",
      "osobista.hero.label": "Personal path · personal",
      "osobista.hero.title": "A decision you do not make alone — because you do not see your full map.",
      "osobista.hero.lead": "Personal mode does not hand you an answer or affirmations. It maps perspectives — logic, body, shadow, time — and shows what stays uncomfortable in the decision. Raw. Transformative. No motivational language.",
      "osobista.hero.cta1": "Join early access",
      "osobista.hero.cta2": "How it works",
      "osobista.how.label": "What the system does",
      "osobista.how.title": "Maps perspectives. Does not promise outcomes.",
      "osobista.how.p1": "The Board does not \"fix\" you or diagnose. It shows how different layers see the same decision — and where they collide. Synthesis does not smooth contradiction. It leaves it visible.",
      "osobista.how.p2": "This is a tool for working on a decision — not a substitute for medical, therapeutic, or crisis support.",
      "osobista.how.canvas": "Polyphony — perspectives in a life decision",
      "osobista.compliance.title": "Important information",
      "osobista.compliance.disclaimer": "This is not medical or therapeutic help.",
      "osobista.compliance.ai": "You are talking to an AI system (the Board), not a human.",
      "osobista.compliance.crisis": "If you are in crisis or need immediate help, call your local emergency number (911 in the US, 112 in the EU) or contact a local crisis line.",
      "osobista.compliance.privacy": "Your debates stay local; the model runs on your key (BYOK). We do not host conversation content in the cloud.",
      "osobista.program.label": "Early access",
      "osobista.program.title": "Controlled access. Not for everyone.",
      "osobista.program.p1": "The program is closed and pre-production. We do not collect health or addiction data in this form — only contact for the waitlist.",
      "osobista.program.p2": "Applying does not guarantee access. We respond to selected candidates.",
      "osobista.program.cta": "Join the waitlist",
      "form.name": "Full name",
      "form.name.personal": "First name",
      "form.company": "Role / Company",
      "form.email": "Work email",
      "form.email.personal": "Email",
      "form.track": "Path",
      "form.track.firma": "For business",
      "form.track.osobista": "For you",
      "form.submit": "Submit application",
      "form.sending": "Sending…",
      "form.note": "Data goes to a secured endpoint. No spam. No mailing-list sales.",
      "form.success": "Application received. We respond only to selected candidates.",
      "form.success.email": "Application received. We sent a confirmation to your email. We respond only to selected candidates.",
      "form.error.turnstile": "Confirm you are not a bot (Turnstile).",
      "form.error.fields": "Fill in name and email.",
      "form.error.company": "Fill in role or company.",
      "form.error.generic": "Could not submit. Please try again.",
      "form.error.network": "Connection error. Check your network and try again.",
      "agent.mechanism.label": "Mechanism in debate",
      "agent.mechanism.title": "How {name} works in the Board",
      "agent.cta": "Apply for the beta program",
      "agent.back": "Back to the Board",
      "agent.portrait": "Portrait of {name}",
      "fragment.meta.title": "Fragment — Freedom Architect: Polyphony",
      "fragment.meta.description": "The philosophical layer of the Fragment — what remains when debate ends.",
      "fragment.label": "Fragment",
      "fragment.title": "What remains after debate",
      "fragment.p1": "The Fragment is not a summary. Not a slide. Not a task list.",
      "fragment.p2": "It is the trace of polyphony — a record of what was true at the moment of decision, before it began flattening for convenience.",
      "fragment.p3": "In Freedom Architect, the Fragment is the layer that ensures synthesis does not consume contradiction. So you see not only \"what to do\", but what in that decision remains uncomfortable — and why it matters.",
      "fragment.p4": "We do not promise the Fragment will resolve that discomfort. We only promise it will not vanish on the way to simplification.",
      "fragment.canvas": "Fragment — trace of synthesis that does not flatten complexity",
      "fragment.cta1": "Meet the Board",
      "fragment.cta2": "Beta program",
      "test.meta.title": "Beta program — Freedom Architect: Polyphony",
      "test.meta.description": "Controlled access to the beta program — business or personal path.",
      "test.label": "Beta program",
      "test.title": "Application",
      "test.lead": "Controlled access, system in pre-production. We're looking for both RevOps and Operations leaders working on real operational decisions and individuals who want to use the Board for a genuine personal decision. Applying does not guarantee access — we respond only to selected candidates.",
      "test.lead.firma": "Beta program application — business path. We recruit RevOps and Operations leaders.",
      "test.lead.osobista": "Early access waitlist — personal path. We do not collect sensitive health data in this form.",
    },
  };

  var AGENT_EN = {
    relacjan: {
      role: "Relations and trust",
      tagline: "Maps influence, dynamics, and people around the decision",
      story: [
        "Relacjan does not ask what you want to do. He asks who will have to carry it — and who pretends not to know.",
        "In Board debate he maps invisible lines: who trusts whom, who withdraws, who feigns agreement to keep position. He does not judge character. He describes field strength.",
        "His voice is quiet and uncomfortable for those who prefer spreadsheets to people. Because a decision without a map of relations is a decision on sand.",
      ],
    },
    kogit: {
      role: "Logic and structure",
      tagline: "Cold architectural clarity",
      story: [
        "Kogit does not explain emotion. He decomposes it into parts until only structure remains.",
        "In the Board he answers what many leaders skip: whether the argument holds, whether assumptions are explicit, whether logic is not merely a story about control.",
        "His clarity is often felt as cold. It is not cold — it is precision that does not ask permission.",
      ],
    },
    emojy: {
      role: "Preverbal emotion",
      tagline: "What words do not yet carry",
      story: [
        "Emojy speaks before sentences are ready. He registers tension that has no name yet — in the room, in silence, in tone of voice.",
        "In the Board he reminds that decisions often land before they appear on a slide. That the team's body knows before the report confirms it.",
        "He does not dramatize. He does not soothe. He names what hung in the air.",
      ],
    },
    deega: {
      role: "Deep diagnosis",
      tagline: "Unconscious loops and hidden repetitions",
      story: [
        "Deega sees patterns the organization repeats without knowing why. The same conflicts. The same \"new\" strategies.",
        "In the Board he points to loops: where the decision was already made before anyone spoke. Where fear dressed as rationality returns under another name.",
        "His diagnosis is not comfortable. It is accurate.",
      ],
    },
    smaty: {
      role: "Somatic",
      tagline: "What the body already knows",
      story: [
        "Smaty does not read slides. He reads tension in shoulders, breath in the room, the way people stop looking at each other.",
        "In the Board he represents body-knowledge — the kind that does not pass through Excel but leads teams to burnout or courage.",
        "When he says \"this does not fit\", he does not mean aesthetics. He means a signal the organization ignored too long.",
      ],
    },
    tai: {
      role: "Time perspective",
      tagline: "Long patterns and consequences of the future",
      story: [
        "Tai looks at a decision like a stone thrown into a river. The wave returns — next quarter, next year, next decade.",
        "In the Board he does not forecast fashionably. He shows long arcs: what today seems a small correction becomes tomorrow culture with no return.",
        "His time is not abstraction. It is responsibility to those who come after us.",
      ],
    },
    szow: {
      role: "Shadow",
      tagline: "What you least want to hear",
      story: [
        "Szow is not a demon. He is what you already know — and defer because naming it would change everything.",
        "In the Board he speaks plainly: where the benefit is yours, not the company's. Where you avoid conversation because you would lose the illusion of control. Where \"rational decision\" masks fear of losing face.",
        "His voice is not aggression. It is a mirror without filter.",
      ],
    },
    obver: {
      role: "External observer",
      tagline: "Meta-perspective outside your story",
      story: [
        "Obver stands outside your narrative about yourself. He sees the pattern you cannot, because you are its author.",
        "In the Board he does not advise from expert position. He describes the scene: who plays which role, what the power layout is, where debate is theater instead of inquiry.",
        "His distance is not indifference. It is the condition of honest synthesis.",
      ],
    },
    kidi: {
      role: "Childlike curiosity",
      tagline: "Pure fascination and instinct",
      story: [
        "Kidi asks the question no one asks anymore because everyone \"knows how it is\".",
        "In the Board he represents instinct without career to defend. What would this be if we were not afraid to look foolish? What if the assumption is simply… boring?",
        "His curiosity is not naivety. It is the last clean filter before compromise kills meaning.",
      ],
    },
  };

  function getLang() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "pl") return stored;
    var nav = (navigator.language || "").toLowerCase();
    return nav.indexOf("en") === 0 ? "en" : "pl";
  }

  function setLang(lang) {
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    applyLang(lang);
  }

  function t(key, vars) {
    var lang = getLang();
    var val = (STRINGS[lang] && STRINGS[lang][key]) || (STRINGS.pl[key]) || key;
    if (vars) {
      Object.keys(vars).forEach(function (k) {
        val = val.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
      });
    }
    return val;
  }

  function applyElements(lang) {
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      var vars = {};
      if (el.dataset.i18nName) vars.name = el.dataset.i18nName;
      var text = (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.pl[key];
      if (text) el.textContent = format(text, vars);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      var text = (STRINGS[lang] && STRINGS[lang][key]) || STRINGS.pl[key];
      if (text) el.setAttribute("placeholder", text);
    });
  }

  function format(text, vars) {
    var out = text;
    Object.keys(vars || {}).forEach(function (k) {
      out = out.replace(new RegExp("\\{" + k + "\\}", "g"), vars[k]);
    });
    return out;
  }

  function applyMeta(lang) {
    var page = document.body.dataset.page;
    if (!page) return;
    var titleKey = page + ".meta.title";
    var descKey = page + ".meta.description";
    var title = (STRINGS[lang] && STRINGS[lang][titleKey]) || STRINGS.pl[titleKey];
    var desc = (STRINGS[lang] && STRINGS[lang][descKey]) || STRINGS.pl[descKey];
    if (title) document.title = title;
    var meta = document.querySelector('meta[name="description"]');
    if (meta && desc) meta.setAttribute("content", desc);

    var ogTitle = document.querySelector('meta[property="og:title"]');
    var ogDesc = document.querySelector('meta[property="og:description"]');
    var ogLocale = document.querySelector('meta[property="og:locale"]');
    if (ogTitle && title) ogTitle.setAttribute("content", title);
    if (ogDesc && desc) ogDesc.setAttribute("content", desc);
    if (ogLocale) ogLocale.setAttribute("content", lang === "en" ? "en_US" : "pl_PL");
  }

  function applyAgentPage(lang) {
    var id = document.body.dataset.agentId;
    if (!id || typeof AGENTS === "undefined") return;
    var agent = AGENTS.find(function (a) { return a.id === id; });
    if (!agent) return;

    var en = AGENT_EN[id];
    var role = lang === "en" && en ? en.role : agent.role;
    var tagline = lang === "en" && en ? en.tagline : agent.tagline;
    var story = lang === "en" && en ? en.story : agent.story;

    var roleEl = document.querySelector("[data-agent-role]");
    var taglineEl = document.querySelector("[data-agent-tagline]");
    var storyEl = document.querySelector("[data-agent-story]");
    var canvasCap = document.querySelector("[data-agent-canvas-caption]");
    var mechTitle = document.querySelector("[data-agent-mechanism-title]");
    var portrait = document.querySelector("[data-agent-portrait]");

    if (roleEl) roleEl.textContent = role;
    if (taglineEl) taglineEl.textContent = tagline;
    if (canvasCap) canvasCap.textContent = tagline;
    if (mechTitle) mechTitle.textContent = format(t("agent.mechanism.title"), { name: agent.name });
    if (portrait) portrait.setAttribute("alt", format(t("agent.portrait"), { name: agent.name }));
    if (storyEl) {
      storyEl.innerHTML = story.map(function (p) { return "<p>" + p + "</p>"; }).join("");
    }

    var agentMeta = document.querySelector('meta[name="description"]');
    if (agentMeta) agentMeta.setAttribute("content", role + ". " + tagline);
    document.title = agent.name + " — " + (lang === "en" ? "Supervisory Board" : "Rada Nadzorcza") + " · Freedom Architect: Polyphony";
  }

  function renderCouncilGridInto(grid, lang, limit) {
    if (!grid || typeof AGENTS === "undefined") return;
    grid.innerHTML = "";
    var list = limit ? AGENTS.slice(0, limit) : AGENTS;
    list.forEach(function (a) {
      var en = AGENT_EN[a.id];
      var role = lang === "en" && en ? en.role : a.role;
      var tagline = lang === "en" && en ? en.tagline : a.tagline;
      var el = document.createElement("a");
      el.href = "/" + a.id;
      el.className = "card";
      el.innerHTML =
        '<p class="caps card-role">' + role + "</p>" +
        '<h3 class="card-name">' + a.name + "</h3>" +
        '<p class="card-tagline">' + tagline + "</p>";
      grid.appendChild(el);
    });
  }

  function renderCouncilGrids(lang) {
    var preview = document.getElementById("council-grid-preview");
    var full = document.getElementById("council-grid");
    if (preview) renderCouncilGridInto(preview, lang, 3);
    if (full) renderCouncilGridInto(full, lang, null);
  }

  function refreshFormLabels() {
    document.querySelectorAll("[data-polyphony-form]").forEach(function (form) {
      if (window.PolyphonyForm && typeof window.PolyphonyForm.getFormTrack === "function") {
        window.PolyphonyForm.setFormTrack(form, window.PolyphonyForm.getFormTrack(form));
      }
    });
  }

  function updateLangButtons(lang) {
    document.querySelectorAll("[data-lang-btn]").forEach(function (btn) {
      var active = btn.getAttribute("data-lang-btn") === lang;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
    var switcher = document.querySelector(".lang-switch");
    if (switcher) switcher.setAttribute("aria-label", t("lang.label"));
  }

  function applyLang(lang) {
    applyElements(lang);
    applyMeta(lang);
    applyAgentPage(lang);
    renderCouncilGrids(lang);
    refreshFormLabels();
    updateLangButtons(lang);
    document.documentElement.lang = lang;
  }

  function injectLangSwitcher() {
    var nav = document.querySelector(".site-header .inner");
    if (!nav || document.querySelector(".lang-switch")) return;

    var wrap = document.createElement("div");
    wrap.className = "header-right";
    wrap.innerHTML =
      '<nav class="nav-links" data-nav-main></nav>' +
      '<div class="lang-switch" role="group" aria-label="' + t("lang.label") + '">' +
      '<button type="button" class="lang-btn" data-lang-btn="pl" aria-pressed="false">PL</button>' +
      '<button type="button" class="lang-btn" data-lang-btn="en" aria-pressed="false">EN</button>' +
      "</div>";

    var existingNav = nav.querySelector(".nav-links");
    if (existingNav) {
      wrap.querySelector("[data-nav-main]").innerHTML = existingNav.innerHTML;
      existingNav.remove();
    }
    nav.appendChild(wrap);

    wrap.querySelectorAll("[data-lang-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setLang(btn.getAttribute("data-lang-btn"));
      });
    });
  }

  function initMobileNav() {
    var header = document.querySelector(".site-header");
    var inner = header && header.querySelector(".inner");
    var panel = inner && inner.querySelector(".header-right");
    if (!header || !inner || !panel || inner.querySelector(".nav-toggle")) return;

    panel.id = "site-nav-panel";

    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "nav-toggle";
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", "site-nav-panel");
    toggle.setAttribute("aria-label", t("nav.menu"));
    toggle.innerHTML = '<span class="nav-toggle-icon" aria-hidden="true"></span>';

    inner.insertBefore(toggle, panel);

    function setOpen(open) {
      header.classList.toggle("is-nav-open", open);
      document.body.classList.toggle("nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? t("nav.close") : t("nav.menu"));
    }

    toggle.addEventListener("click", function () {
      setOpen(!header.classList.contains("is-nav-open"));
    });

    panel.querySelectorAll(".nav-links a").forEach(function (link) {
      link.addEventListener("click", function () {
        setOpen(false);
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setOpen(false);
    });

    window.matchMedia("(min-width: 861px)").addEventListener("change", function (mq) {
      if (mq.matches) setOpen(false);
    });
  }

  function initI18n() {
    injectLangSwitcher();
    initMobileNav();
    var lang = getLang();
    applyLang(lang);
  }

  window.PolyphonyI18n = { getLang: getLang, setLang: setLang, t: t, applyLang: applyLang };
  window.t = t;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initI18n);
  } else {
    initI18n();
  }
})();
