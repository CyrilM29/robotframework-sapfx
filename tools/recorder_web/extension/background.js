/*
 * Service worker (MV3). Two jobs:
 *   1. Toolbar badge — reflects the recording state relayed by bridge.js (REC = recording).
 *   2. Keyboard shortcut (Alt+Shift+R, command "toggle-record") — injects the recorder if
 *      absent (bridge + recorder) and toggles recording, without opening the popup.
 * A keyboard command grants `activeTab` on the current tab, so no host permissions are
 * needed. Chromium (MV3 service worker + scripting world MAIN, Chrome 111+) is the
 * supported target; the `browser` fallback below is defensive only — Firefox would
 * additionally need background.scripts and browser_specific_settings to run this.
 */
const api = (typeof browser !== "undefined") ? browser : chrome;

function setBadge(tabId, recording) {
  if (tabId == null) return;
  api.action.setBadgeText({ tabId, text: recording ? "REC" : "" });
  if (recording) api.action.setBadgeBackgroundColor({ tabId, color: "#d0021b" });
}

// Badge driven by the in-page recorder (panel rec button, shortcut, etc.) via bridge.js.
api.runtime.onMessage.addListener((msg, sender) => {
  if (msg && msg.type === "ui5RecorderState" && sender.tab) {
    setBadge(sender.tab.id, msg.recording);
  }
});

api.commands.onCommand.addListener(async (command) => {
  if (command !== "toggle-record") return;
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) return;
  try {
    // Lire l'état AVANT la (ré-)injection, puis poser UNE cible explicite sur
    // toutes les frames : des toggles par frame dériveraient en anti-phase
    // (une frame démarre l'enregistrement pendant qu'une autre l'arrête).
    const probes = await api.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true }, world: "MAIN",
      func: () => !!(window.__ui5RecorderApi && window.__ui5RecorderApi.isRecording()),
    });
    const anyRecording = (probes || []).some((p) => p && p.result);
    // Toujours injecter, allFrames : les deux fichiers sont idempotents — les
    // frames déjà instrumentées no-opent, et les iframes apparues depuis la
    // dernière injection (navigation intra-launchpad) sont couvertes aussi.
    await api.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ["bridge.js"] });
    await api.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, world: "MAIN", files: ["recorder.js"] });
    await api.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true }, world: "MAIN",
      args: [!anyRecording],
      func: (on) => {
        if (window.__ui5RecorderApi && window.__ui5RecorderApi.setRec) window.__ui5RecorderApi.setRec(on);
      },
    });
  } catch (e) {
    // chrome://, le Web Store, le visualiseur PDF… : l'injection y est interdite
    // — l'afficher sur le badge plutôt que mourir en rejection non gérée.
    api.action.setBadgeText({ tabId: tab.id, text: "n/a" });
    setTimeout(() => api.action.setBadgeText({ tabId: tab.id, text: "" }), 1500);
  }
});
