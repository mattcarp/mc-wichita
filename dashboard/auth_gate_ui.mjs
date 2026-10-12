/**
 * Passwordless sign-in step UI (email / link-wait / code / completing).
 * Exported for clerk_gate.js and Playwright step tests.
 */

export const AUTH_STEPS = ["email", "link", "code", "verify"];

/**
 * @param {HTMLElement} mount
 * @param {{
 *   onSubmitEmail?: (email: string) => Promise<void>,
 *   onSubmitCode?: (code: string) => Promise<void>,
 *   onUseCodeInstead?: () => Promise<void>,
 *   onRestart?: () => void,
 * }} handlers
 */
export function mountPasswordlessAuthUI(mount, handlers = {}) {
  const shell = document.createElement("div");
  shell.className = "auth-form-shell";

  const status = document.createElement("p");
  status.className = "auth-form-status muted";
  status.dataset.authStep = "status";
  status.hidden = true;
  status.setAttribute("role", "status");

  const emailForm = document.createElement("form");
  emailForm.className = "auth-step auth-form";
  emailForm.dataset.authStep = "email";
  emailForm.noValidate = true;
  emailForm.innerHTML = `
    <label class="auth-form-label" for="authEmail">Email</label>
    <input id="authEmail" class="auth-form-input" type="email" name="email" autocomplete="email" required placeholder="you@example.com" />
    <button type="submit" class="auth-form-btn">Continue with email</button>
  `;

  const linkPanel = document.createElement("div");
  linkPanel.className = "auth-step auth-form-panel";
  linkPanel.dataset.authStep = "link";
  linkPanel.innerHTML = `
    <p class="auth-form-lead">Check your email for a sign-in link.</p>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="use-code">Use a code instead</button>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="restart">Use a different email</button>
  `;

  const codeForm = document.createElement("form");
  codeForm.className = "auth-step auth-form";
  codeForm.dataset.authStep = "code";
  codeForm.noValidate = true;
  codeForm.innerHTML = `
    <p class="auth-form-lead">Enter the code from your email.</p>
    <label class="auth-form-label" for="authCode">Verification code</label>
    <input id="authCode" class="auth-form-input mono" type="text" name="code" inputmode="numeric" autocomplete="one-time-code" required placeholder="123456" />
    <button type="submit" class="auth-form-btn">Verify</button>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="restart">Start over</button>
  `;

  const verifyPanel = document.createElement("div");
  verifyPanel.className = "auth-step auth-form-panel";
  verifyPanel.dataset.authStep = "verify";
  verifyPanel.innerHTML = `<p class="auth-form-lead">Completing sign-in…</p>`;

  let view = "email";
  let busy = false;

  function showError(message) {
    status.textContent = message;
    status.hidden = !message;
    status.classList.toggle("auth-form-status-visible", Boolean(message));
  }

  function setView(next) {
    if (!AUTH_STEPS.includes(next)) return;
    view = next;
    for (const step of AUTH_STEPS) {
      const el = shell.querySelector(`[data-auth-step="${step}"]`);
      if (!el) continue;
      const active = step === next;
      el.classList.toggle("is-visible", active);
      el.toggleAttribute("hidden", !active);
    }
  }

  function setBusy(on) {
    busy = on;
    emailForm.querySelector("button[type=submit]").disabled = on;
    codeForm.querySelector("button[type=submit]").disabled = on;
  }

  function restart() {
    showError("");
    setView("email");
    emailForm.reset();
    codeForm.reset();
    handlers.onRestart?.();
  }

  emailForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (busy || !handlers.onSubmitEmail) return;
    showError("");
    const email = emailForm.email.value;
    if (!email?.trim()) return;
    setBusy(true);
    try {
      await handlers.onSubmitEmail(email.trim());
    } catch (err) {
      showError(err?.message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  });

  linkPanel.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-action]");
    if (!btn || busy) return;
    if (btn.dataset.action === "restart") {
      restart();
      return;
    }
    if (btn.dataset.action === "use-code" && handlers.onUseCodeInstead) {
      showError("");
      setBusy(true);
      try {
        await handlers.onUseCodeInstead();
      } catch (err) {
        showError(err?.message || "Sign-in failed.");
      } finally {
        setBusy(false);
      }
    }
  });

  codeForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (busy || !handlers.onSubmitCode) return;
    showError("");
    const code = codeForm.code.value;
    if (!code?.trim()) return;
    setBusy(true);
    try {
      await handlers.onSubmitCode(code.trim());
    } catch (err) {
      showError(err?.message || "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  });

  codeForm.querySelector('[data-action="restart"]').addEventListener("click", restart);

  shell.append(status, emailForm, linkPanel, codeForm, verifyPanel);
  mount.replaceChildren(shell);
  setView("email");

  return {
    setView,
    getView: () => view,
    showError,
    clearError: () => showError(""),
    shell,
    emailForm,
    linkPanel,
    codeForm,
    verifyPanel,
    restart,
  };
}

/** @param {HTMLElement} el */
export function isAuthStepDisplayed(el) {
  if (!el || el.hidden) return false;
  const style = window.getComputedStyle(el);
  return style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0";
}
