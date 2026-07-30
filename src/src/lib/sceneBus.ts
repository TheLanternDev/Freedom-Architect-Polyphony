/**
 * sceneBus — szyna zdarzeń UI → trwała scena 3D.
 * Widok (tab/tryb/faza debaty) emituje intencję; scena odpowiada
 * choreografią kamery. Zero sprzężenia komponentów.
 */

export type SceneView =
  | "personal"      // tryb osobisty — konstelacja otwarta, oddycha
  | "fa2"           // tryb biznesowy — ciaśniejszy, chłodniejszy kadr
  | "debate"        // agenci mówią — konstelacja schodzi w tło, energia rośnie
  | "synthesis"     // Syez syntetyzuje — konwergencja do rdzenia
  | "done"          // domknięcie — rozbłysk, powrót do otwartej formy
  | "idle";         // spoczynek

const EVT = "aw:scene-view";

export function sceneView(view: SceneView): void {
  window.dispatchEvent(new CustomEvent<SceneView>(EVT, { detail: view }));
}

export function onSceneView(cb: (view: SceneView) => void): () => void {
  const h = (e: Event) => cb((e as CustomEvent<SceneView>).detail);
  window.addEventListener(EVT, h);
  return () => window.removeEventListener(EVT, h);
}
