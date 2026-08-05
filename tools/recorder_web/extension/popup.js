/*
 * Popup controller. Injects the Recorder into the active tab's MAIN world (so it can
 * reach the page's `window.sap`) plus a small ISOLATED bridge (for the toolbar badge),
 * and drives it (rec/pause, export, stop). Uses `activeTab`: access is granted for the
 * current tab when the user clicks the toolbar icon, so no host permissions are needed.
 * `api` is `browser` on Firefox, `chrome` on Chromium (cross-browser shim).
 */
const api = (typeof browser !== "undefined") ? browser : chrome;

async function getActiveTab() {
  const [tab] = await api.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

// Exécute `func` dans le MAIN world de TOUTES les frames de l'onglet (Work Zone /
// cFLP ouvrent l'app dans une iframe : le shell top-level n'a pas ses contrôles).
// Retourne le premier résultat truthy, sinon le résultat de la frame principale.
// NB : sans host permissions, Chrome n'injecte pas dans les iframes cross-origin :
// l'injection y échoue silencieusement, le reste des frames fonctionne.
async function runInPage(tabId, func) {
  try {
    const results = await api.scripting.executeScript({
      target: { tabId, allFrames: true }, world: "MAIN", func,
    });
    const hit = (results || []).find((r) => r && r.result);
    if (hit) return hit.result;
    return results && results[0] ? results[0].result : null;
  } catch (err) {
    setStatus("Error: " + err);
    return null;
  }
}

async function isRunning(tabId) {
  return await runInPage(tabId, () => !!window.__ui5RecorderApi);
}

async function isRecording(tabId) {
  return await runInPage(tabId, () => !!(window.__ui5RecorderApi && window.__ui5RecorderApi.isRecording()));
}

async function refresh() {
  const tab = await getActiveTab();
  if (!tab || !tab.id) return;
  const running = await isRunning(tab.id);
  const recording = running && await isRecording(tab.id);
  document.getElementById("start").disabled = running;
  document.getElementById("rec").disabled = !running;
  document.getElementById("export").disabled = !running;
  document.getElementById("stop").disabled = !running;
  document.getElementById("rec").textContent = recording ? "Pause" : "Rec";
  setStatus(running ? (recording ? "Recording…" : "Capture mode") : "Not started");
}

document.getElementById("start").addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab || !tab.id) return;
  try {
    // bridge (ISOLATED) for the badge, then the recorder (MAIN world), in ALL
    // frames, so launchpad-embedded apps (Work Zone/cFLP iframes) get a panel too.
    await api.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, files: ["bridge.js"] });
    await api.scripting.executeScript({ target: { tabId: tab.id, allFrames: true }, world: "MAIN", files: ["recorder.js"] });
    await refresh();
  } catch (err) {
    setStatus("Could not start: " + err);
  }
});

document.getElementById("rec").addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab || !tab.id) return;
  // État EXPLICITE pour toutes les frames (un toggle par frame dériverait en
  // anti-phase quand les frames ne partagent pas le même état de départ).
  const recording = await isRecording(tab.id);
  try {
    await api.scripting.executeScript({
      target: { tabId: tab.id, allFrames: true }, world: "MAIN",
      args: [!recording],
      func: (on) => {
        if (window.__ui5RecorderApi && window.__ui5RecorderApi.setRec) window.__ui5RecorderApi.setRec(on);
      },
    });
  } catch (err) {
    setStatus("Error: " + err);
  }
  await refresh();
});

document.getElementById("export").addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab || !tab.id) return;
  await runInPage(tab.id, () => window.__ui5RecorderApi && window.__ui5RecorderApi.exportScript());
  setStatus("Exported recorded.robot");
});

document.getElementById("stop").addEventListener("click", async () => {
  const tab = await getActiveTab();
  if (!tab || !tab.id) return;
  await runInPage(tab.id, () => window.__ui5RecorderApi && window.__ui5RecorderApi.stop());
  await refresh();
});

refresh();
