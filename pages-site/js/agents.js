/**
 * Kanon Rady — źródło: manifest.yaml (13 VI 2026)
 * Kolejność montażu Polyphony. Nie zmieniaj bez wyraźnego polecenia.
 */
const AGENTS = [
  {
    id: "relacjan",
    name: "Relacjan",
    file: "Relacjan.png",
    role: "Relacje i zaufanie",
    tagline: "Mapuje wpływ, dynamikę i ludzi wokół decyzji",
    canvas: "network",
    story: [
      "Relacjan nie pyta, co chcesz zrobić. Pyta, kto będzie musiał to udźwignąć — i kto udaje, że nie wie.",
      "W debacie Rady mapuje niewidzialne linie: kto komu ufa, kto się wycofuje, kto udaje zgodę, żeby nie stracić pozycji. Nie ocenia charakterów. Opisuje siłę pola.",
      "Jego głos jest cichy i niewygodny dla tych, którzy wolą tabele zamiast ludzi. Bo decyzja bez mapy relacji to decyzja na piasku.",
    ],
  },
  {
    id: "kogit",
    name: "Kogit",
    file: "Kogit.png",
    role: "Logika i struktura",
    tagline: "Zimna architektoniczna jasność",
    canvas: "structure",
    story: [
      "Kogit nie tłumaczy emocji. Rozkłada je na elementy składowe, aż zostaje sama konstrukcja.",
      "W Radzie odpowiada za to, co wielu liderów omija: czy argument się spina, czy założenia są jawne, czy logika nie jest tylko opowieścią o kontroli.",
      "Jego jasność bywa odczuwana jako chłód. To nie chłód — to precyzja, która nie prosi o zgodę.",
    ],
  },
  {
    id: "emojy",
    name: "Emojy",
    file: "Emojy.png",
    role: "Emocje prewerbalne",
    tagline: "To, czego słowa jeszcze nie niosą",
    canvas: "waves",
    story: [
      "Emojy mówi zanim zdania są gotowe. Rejestruje napięcie, które jeszcze nie ma nazwy — w pokoju, w ciszy, w tonie głosu.",
      "W Radzie przypomina, że decyzja często zapada wcześniej niż pojawia się na slajdzie. Że ciało zespołu wie, zanim raport to potwierdzi.",
      "Nie dramatyzuje. Nie uspokaja. Nazywa to, co wisiało w powietrzu.",
    ],
  },
  {
    id: "deega",
    name: "Deega",
    file: "Deega.png",
    role: "Głęboka diagnoza",
    tagline: "Nieświadome pętle i ukryte powtórzenia",
    canvas: "loops",
    story: [
      "Deega widzi schematy, które organizacja powtarza, nie wiedząc dlaczego. Te same konflikty. Te same „nowe” strategie.",
      "W Radzie wskazuje pętle: gdzie decyzja jest już podjęta, zanim ktoś otworzy usta. Gdzie strach przebrany za racjonalność wraca pod inną nazwą.",
      "Jego diagnoza nie jest wygodna. Jest dokładna.",
    ],
  },
  {
    id: "smaty",
    name: "Smaty",
    file: "Smaty.png",
    role: "Somatyczny",
    tagline: "To, co ciało już wie",
    canvas: "pulse",
    story: [
      "Smaty nie czyta slajdów. Czyta napięcie w barkach, oddech w sali, sposób, w jaki ludzie przestają patrzeć na siebie.",
      "W Radzie reprezentuje wiedzę ciała — tę, która nie przechodzi przez Excela, ale prowadzi zespoły do wypalenia albo do odwagi.",
      "Gdy mówi, że „to nie pasuje”, nie chodzi o estetykę. Chodzi o sygnał, który organizacja zignorowała za długo.",
    ],
  },
  {
    id: "tai",
    name: "Tai",
    file: "Tai.png",
    role: "Perspektywa czasu",
    tagline: "Długie wzorce i konsekwencje przyszłości",
    canvas: "time",
    story: [
      "Tai patrzy na decyzję jak na kamień wrzucony do rzeki. Fala wraca — za kwartał, za rok, za dekadę.",
      "W Radzie nie prognozuje modnie. Pokazuje długie łuki: co dziś wydaje się drobną korektą, a jutro staje się kulturą, od której nie ma odwrotu.",
      "Jego czas nie jest abstrakcją. To odpowiedzialność wobec tych, którzy przyjdą po nas.",
    ],
  },
  {
    id: "szow",
    name: "Szow",
    file: "Szow.png",
    role: "Cień",
    tagline: "To, czego najmniej chcesz usłyszeć",
    canvas: "shadow",
    story: [
      "Szow nie jest demonem. Jest tym, co już wiesz — i odkładasz na później, bo nazwanie tego zmieni wszystko.",
      "W Radzie mówi wprost: gdzie korzyść jest twoja, a nie firmy. Gdzie unikasz rozmowy, bo stracisz iluzję kontroli. Gdzie „racjonalna decyzja” maskuje lęk przed stratą twarzy.",
      "Jego głos nie jest agresją. Jest lustrem bez filtra.",
    ],
  },
  {
    id: "obver",
    name: "Obver",
    file: "Obver.png",
    role: "Obserwator zewnętrzny",
    tagline: "Meta-perspektywa poza twoją historią",
    canvas: "lens",
    story: [
      "Obver stoi poza twoją narracją o sobie. Widzi wzorzec, którego ty nie widzisz, bo jesteś jego autorem.",
      "W Radzie nie doradza z pozycji eksperta. Opisuje scenę: kto gra jaką rolę, jaki jest układ sił, gdzie debata jest teatrem zamiast badaniem.",
      "Jego dystans nie jest obojętnością. To warunek uczciwej syntezy.",
    ],
  },
  {
    id: "kidi",
    name: "Kidi",
    file: "Kidi.png",
    role: "Dziecięca ciekawość",
    tagline: "Czysta fascynacja i instynkt",
    canvas: "spark",
    story: [
      "Kidi zadaje pytanie, którego nikt już nie zadaje, bo wszyscy „wiedzą, jak jest”.",
      "W Radzie reprezentuje instynkt bez kariery do obrony. Co by tu było, gdybyśmy nie bali się wyglądać głupio? Co jeśli założenie jest po prostu… nudne?",
      "Jego ciekawość nie jest naiwnością. To ostatni czysty filtr przed kompromisem, który zabije sens.",
    ],
  },
];

function getAgent(id) {
  return AGENTS.find((a) => a.id === id);
}

function getAgentNeighbors(id) {
  const i = AGENTS.findIndex((a) => a.id === id);
  if (i < 0) return { prev: null, next: null };
  return {
    prev: i > 0 ? AGENTS[i - 1] : null,
    next: i < AGENTS.length - 1 ? AGENTS[i + 1] : null,
  };
}
