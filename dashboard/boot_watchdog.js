/* Loading watchdog: a classic script, so it still runs when a module fails to parse or load.
   Never leaves the Harbour map or side panel as a blank box: after 15 s of the signed-in app
   still loading, or on any script error, it shows a clear message with a Retry button. */
(function () {
  var started = null;
  function showError(msg) {
    ["mapLoading", "sideLoading"].forEach(function (id) {
      var el = document.getElementById(id);
      if (!el || el.getAttribute("data-state") === "done") return;
      window.wichitaLoadError(el, msg);
    });
  }
  window.wichitaLoadError = function (el, msg, onRetry) {
    el.hidden = false;
    el.setAttribute("data-state", "error");
    el.innerHTML = "";
    var m = document.createElement("span");
    m.className = "load-msg";
    m.textContent = msg;
    var b = document.createElement("button");
    b.type = "button";
    b.className = "load-retry";
    b.textContent = "Retry";
    b.addEventListener("click", function () {
      if (onRetry) {
        el.setAttribute("data-state", "loading");
        el.innerHTML = '<span class="load-spin" aria-hidden="true"></span><span class="load-msg">Loading…</span>';
        onRetry();
      } else {
        location.reload();
      }
    });
    el.appendChild(m);
    el.appendChild(b);
  };
  window.addEventListener("error", function (ev) {
    if (ev && ev.filename && ev.filename.indexOf("/dashboard/") !== -1) {
      showError("The map could not load (a script failed). Retry, or reload the page.");
    }
  });
  window.addEventListener("unhandledrejection", function () {});
  setInterval(function () {
    var shell = document.getElementById("appShell");
    if (!shell || shell.hidden) return;
    if (started === null) started = Date.now();
    if (Date.now() - started > 15000) showError("The map is taking too long to load. Retry, or reload the page.");
  }, 1000);
})();
