/*
 * Pont ISOLATED <-> service worker. Le recorder tourne dans le MAIN world (pour accéder
 * à window.sap) où les API chrome.* n'existent pas. Ce petit script, injecté dans le
 * monde ISOLATED, écoute l'événement DOM d'état émis par le recorder et le relaie au
 * service worker, qui met à jour le badge de l'icône. Les deux mondes partagent le DOM,
 * donc l'événement traverse la frontière.
 */
(function () {
  if (window.__ui5RecorderBridge) return;     // idempotent
  window.__ui5RecorderBridge = true;
  var api = (typeof browser !== "undefined") ? browser : chrome;
  document.addEventListener("__ui5RecorderState", function (e) {
    try { api.runtime.sendMessage({ type: "ui5RecorderState", recording: !!e.detail }); } catch (err) {}
  }, true);
})();
