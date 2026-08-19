/*!
 * Arbor booking widget. Drop this on any page:
 *   <script src="https://<your-deployment>/embed.js" async></script>
 * Optional: <script ... data-label="Book a table"></script>
 * Optional: <script ... data-mode="buttonless"></script> — skips the floating
 * launcher; use window.Arbor.open()/close() from your own buttons instead.
 *
 * One deployment = one business (tenancy.mode: "single"), so this script
 * needs no provider code — its own <script src> origin is the business.
 * Theming comes from that deployment's domain.config.json (applied inside
 * the iframe), not from attributes here, so there's only one place to set a
 * brand color instead of two that could drift.
 *
 * Plain JS, no build step, on purpose: this runs on a third party's site, and
 * a single readable file is easier for them to audit before they paste it in
 * than a bundler's output would be.
 */
(function () {
  "use strict";

  var CURRENT_SCRIPT = document.currentScript;
  if (!CURRENT_SCRIPT) return; // can't self-locate (e.g. loaded via eval) — nothing safe to do

  var ORIGIN = new URL(CURRENT_SCRIPT.src).origin;
  var EMBED_URL = ORIGIN + "/embed";
  var LABEL = CURRENT_SCRIPT.getAttribute("data-label") || "Book now";
  var BUTTONLESS = CURRENT_SCRIPT.getAttribute("data-mode") === "buttonless";
  var MAX_HEIGHT_VH = 90;

  var modal = null; // { backdrop, iframe } once created, reused across opens

  function createModal() {
    var backdrop = document.createElement("div");
    backdrop.setAttribute("aria-hidden", "false");
    backdrop.style.cssText = [
      "position:fixed", "inset:0", "z-index:2147483000",
      "background:rgba(15,15,20,0.45)",
      "display:flex", "align-items:center", "justify-content:center",
      "padding:16px", "box-sizing:border-box",
    ].join(";");

    var panel = document.createElement("div");
    panel.style.cssText = [
      "position:relative", "width:min(420px, 100%)", "max-height:" + MAX_HEIGHT_VH + "vh",
      "background:#fff", "border-radius:16px", "overflow:hidden",
      "box-shadow:0 20px 60px rgba(0,0,0,0.35)",
    ].join(";");

    var closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.setAttribute("aria-label", "Close");
    closeBtn.textContent = "×";
    closeBtn.style.cssText = [
      "position:absolute", "top:8px", "right:8px", "z-index:1",
      "width:28px", "height:28px", "border-radius:9999px", "border:none",
      "background:rgba(0,0,0,0.06)", "color:#111", "font-size:18px", "line-height:1",
      "cursor:pointer",
    ].join(";");
    closeBtn.onclick = closeModal;

    var iframe = document.createElement("iframe");
    iframe.src = EMBED_URL;
    iframe.title = "Booking";
    iframe.style.cssText = "display:block;width:100%;height:520px;border:0;";

    panel.appendChild(closeBtn);
    panel.appendChild(iframe);
    backdrop.appendChild(panel);

    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) closeModal();
    });

    return { backdrop: backdrop, panel: panel, iframe: iframe };
  }

  function openModal() {
    if (!modal) modal = createModal();
    if (!modal.backdrop.isConnected) document.body.appendChild(modal.backdrop);
    document.addEventListener("keydown", onKeydown);
  }

  function closeModal() {
    if (modal && modal.backdrop.isConnected) modal.backdrop.remove();
    document.removeEventListener("keydown", onKeydown);
  }

  function onKeydown(e) {
    if (e.key === "Escape") closeModal();
  }

  // Public API — lets a host page (e.g. this project's own landing page,
  // loaded in buttonless mode) open/close the modal from its own buttons
  // instead of the floating launcher.
  window.Arbor = { open: openModal, close: closeModal };

  window.addEventListener("message", function (event) {
    if (event.origin !== ORIGIN) return; // only trust our own iframe
    if (!modal || event.source !== modal.iframe.contentWindow) return;
    var data = event.data;
    if (!data || data.type !== "codaro:resize" || typeof data.height !== "number") return;
    var vh = window.innerHeight * (MAX_HEIGHT_VH / 100);
    modal.iframe.style.height = Math.max(320, Math.min(data.height, vh)) + "px";
  });

  function createLauncher() {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = LABEL;
    btn.style.cssText = [
      "position:fixed", "right:20px", "bottom:20px", "z-index:2147483000",
      "padding:12px 20px", "border-radius:9999px", "border:none",
      "background:#111827", "color:#fff", "font:600 14px/1.2 system-ui,sans-serif",
      "box-shadow:0 8px 24px rgba(0,0,0,0.25)", "cursor:pointer",
    ].join(";");
    btn.onclick = openModal;
    return btn;
  }

  function init() {
    if (!BUTTONLESS) document.body.appendChild(createLauncher());
  }

  if (document.body) init();
  else document.addEventListener("DOMContentLoaded", init);
})();
