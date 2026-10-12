/**
 * Passwordless Clerk gate (email link, then email code). Never mounts <SignIn />.
 */

const CLERK_THEME = {
  variables: {
    colorBackground: "#070b14",
    colorInputBackground: "#0e1420",
    colorNeutral: "#e8eaef",
    colorPrimary: "#3ec6c9",
    colorText: "#e8eaef",
    colorTextSecondary: "#9aa3b2",
    borderRadius: "0.5rem",
  },
};

const CLERK_APPEARANCE = {
  ...CLERK_THEME,
  elements: {
    rootBox: { width: "100%" },
    card: {
      backgroundColor: "#0e1420",
      border: "1px solid #252a36",
      boxShadow: "0 12px 40px rgba(0,0,0,0.45)",
    },
  },
};

function $(sel) {
  return document.querySelector(sel);
}

function setAppVisible(visible) {
  const shell = $("#appShell");
  const gate = $("#authGate");
  if (shell) shell.hidden = !visible;
  if (gate) gate.hidden = visible;
  document.body.classList.toggle("auth-pending", !visible);
}

function loadClerkScript(frontendApi, publishableKey) {
  const src = `${frontendApi.replace(/\/$/, "")}/npm/@clerk/clerk-js@5/dist/clerk.browser.js`;
  return new Promise((resolve, reject) => {
    if (window.Clerk) {
      resolve(window.Clerk);
      return;
    }
    const existing = document.querySelector('script[data-clerk-publishable-key]');
    if (existing) {
      existing.addEventListener("load", () => resolve(window.Clerk));
      existing.addEventListener("error", reject);
      return;
    }
    const script = document.createElement("script");
    script.async = true;
    script.crossOrigin = "anonymous";
    script.type = "text/javascript";
    script.dataset.clerkPublishableKey = publishableKey;
    script.src = src;
    script.onload = () => resolve(window.Clerk);
    script.onerror = () => reject(new Error("Clerk script failed to load"));
    document.head.appendChild(script);
  });
}

async function fetchClerkEnv() {
  const res = await fetch("/dashboard/clerk-env.json", { credentials: "same-origin" });
  if (!res.ok) throw new Error("Clerk config unavailable");
  return res.json();
}

function installAuthenticatedFetch(Clerk) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const nextInit = { ...init, credentials: init.credentials ?? "include" };
    const headers = new Headers(nextInit.headers || {});
    try {
      const session = Clerk.session;
      if (session) {
        const token = await session.getToken();
        if (token && !headers.has("Authorization")) {
          headers.set("Authorization", `Bearer ${token}`);
        }
      }
    } catch {
      /* session not ready */
    }
    nextInit.headers = headers;
    return nativeFetch(input, nextInit);
  };
}

function clerkErrorMessage(err) {
  const first = err?.errors?.[0];
  return first?.longMessage || first?.message || err?.message || "Sign-in failed.";
}

function isEmailLinkReturnUrl() {
  const q = window.location.search;
  return (
    q.includes("__clerk_ticket") ||
    q.includes("__clerk_status") ||
    q.includes("__clerk_created_session") ||
    q.includes("__clerk_redirect_url")
  );
}

function clearStaleClerkHashRoute() {
  const hash = window.location.hash;
  if (!hash || hash === "#" || !hash.startsWith("#/")) return;
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

function emailLinkRedirectUrl(env) {
  if (env?.emailLinkRedirectUrl) return env.emailLinkRedirectUrl;
  return `${window.location.origin}/`;
}

async function activateSignInSession(Clerk, signIn) {
  if (signIn?.status === "complete" && signIn.createdSessionId) {
    await Clerk.setActive({ session: signIn.createdSessionId });
    return true;
  }
  return false;
}

async function completeEmailLinkIfPresent(Clerk, redirectUrl) {
  if (typeof Clerk.handleEmailLinkVerification !== "function") return false;
  if (!isEmailLinkReturnUrl()) return false;
  await Clerk.handleEmailLinkVerification({ redirectUrl });
  const signIn = Clerk.client?.signIn;
  if (signIn && (await activateSignInSession(Clerk, signIn))) {
    return true;
  }
  if (Clerk.user) {
    window.history.replaceState(null, "", redirectUrl);
    return true;
  }
  return false;
}

function factorByStrategy(factors, strategy) {
  return (factors || []).find((f) => f.strategy === strategy);
}

async function startPasswordlessSignIn(Clerk, email, redirectUrl) {
  const signIn = Clerk.client.signIn;
  await signIn.create({ identifier: email.trim() });
  const factors = signIn.supportedFirstFactors || [];

  const linkFactor = factorByStrategy(factors, "email_link");
  if (linkFactor?.emailAddressId) {
    await signIn.prepareFirstFactor({
      strategy: "email_link",
      emailAddressId: linkFactor.emailAddressId,
      redirectUrl,
    });
    return { mode: "link" };
  }

  const codeFactor = factorByStrategy(factors, "email_code");
  if (codeFactor?.emailAddressId) {
    await signIn.prepareFirstFactor({
      strategy: "email_code",
      emailAddressId: codeFactor.emailAddressId,
    });
    return { mode: "code" };
  }

  throw new Error("Email sign-in is not available for this address.");
}

async function submitEmailCode(Clerk, code) {
  const signIn = Clerk.client.signIn;
  const result = await signIn.attemptFirstFactor({
    strategy: "email_code",
    code: code.trim(),
  });
  await activateSignInSession(Clerk, result);
  if (!Clerk.user && result?.status !== "complete") {
    throw new Error("Invalid or expired code.");
  }
}

async function waitForEmailLinkCompletion(Clerk) {
  const signIn = Clerk.client?.signIn;
  if (!signIn) return;
  if (typeof signIn.waitForEmailLinkVerification === "function") {
    await signIn.waitForEmailLinkVerification();
  }
  await activateSignInSession(Clerk, signIn);
}

let dashboardBooted = false;
let passwordlessUiMounted = false;
let linkWaitAbort = null;

async function bootDashboard(Clerk) {
  if (dashboardBooted) return;
  dashboardBooted = true;
  installAuthenticatedFetch(Clerk);
  const userMount = $("#clerkUserButton");
  if (userMount) {
    Clerk.mountUserButton(userMount, { appearance: CLERK_APPEARANCE });
  }
  await import("./dashboard.js?v=20261011-clerk1");
}

function renderPasswordlessForm(Clerk, env) {
  const mount = $("#clerkSignIn");
  if (!mount) return;

  const redirectUrl = emailLinkRedirectUrl(env);
  let view = "email";
  let busy = false;

  const shell = document.createElement("div");
  shell.className = "auth-form-shell";

  const status = document.createElement("p");
  status.className = "auth-form-status muted";
  status.hidden = true;
  status.setAttribute("role", "status");

  const emailForm = document.createElement("form");
  emailForm.className = "auth-form";
  emailForm.noValidate = true;
  emailForm.innerHTML = `
    <label class="auth-form-label" for="authEmail">Email</label>
    <input id="authEmail" class="auth-form-input" type="email" name="email" autocomplete="email" required placeholder="you@example.com" />
    <button type="submit" class="auth-form-btn">Continue with email</button>
  `;

  const linkPanel = document.createElement("div");
  linkPanel.className = "auth-form-panel";
  linkPanel.hidden = true;
  linkPanel.innerHTML = `
    <p class="auth-form-lead">Check your email for a sign-in link.</p>
    <p class="muted small">Open the link on this device if asked. The link returns you to Wichita.</p>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="use-code">Use a code instead</button>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="restart">Use a different email</button>
  `;

  const codeForm = document.createElement("form");
  codeForm.className = "auth-form";
  codeForm.hidden = true;
  codeForm.noValidate = true;
  codeForm.innerHTML = `
    <p class="auth-form-lead">Enter the code from your email.</p>
    <label class="auth-form-label" for="authCode">Verification code</label>
    <input id="authCode" class="auth-form-input mono" type="text" name="code" inputmode="numeric" autocomplete="one-time-code" required placeholder="123456" />
    <button type="submit" class="auth-form-btn">Verify</button>
    <button type="button" class="auth-form-btn auth-form-btn-ghost" data-action="restart">Start over</button>
  `;

  const verifyPanel = document.createElement("div");
  verifyPanel.className = "auth-form-panel";
  verifyPanel.hidden = true;
  verifyPanel.innerHTML = `<p class="auth-form-lead">Completing sign-in…</p>`;

  function showError(message) {
    status.textContent = message;
    status.hidden = !message;
  }

  function setView(next) {
    view = next;
    emailForm.hidden = next !== "email";
    linkPanel.hidden = next !== "link";
    codeForm.hidden = next !== "code";
    verifyPanel.hidden = next !== "verify";
  }

  function setBusy(on) {
    busy = on;
    emailForm.querySelector("button[type=submit]").disabled = on;
    codeForm.querySelector("button[type=submit]").disabled = on;
  }

  function restart() {
    if (linkWaitAbort) {
      linkWaitAbort.aborted = true;
      linkWaitAbort = null;
    }
    showError("");
    setView("email");
    emailForm.reset();
    codeForm.reset();
  }

  emailForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (busy) return;
    showError("");
    const email = emailForm.email.value;
    if (!email?.trim()) return;
    setBusy(true);
    try {
      const result = await startPasswordlessSignIn(Clerk, email, redirectUrl);
      if (result.mode === "link") {
        setView("link");
        const token = { aborted: false };
        linkWaitAbort = token;
        waitForEmailLinkCompletion(Clerk).catch(() => {});
      } else {
        setView("code");
        codeForm.code.focus();
      }
    } catch (err) {
      showError(clerkErrorMessage(err));
    } finally {
      setBusy(false);
    }
  });

  linkPanel.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("[data-action]");
    if (!btn) return;
    if (btn.dataset.action === "restart") {
      restart();
      return;
    }
    if (btn.dataset.action === "use-code") {
      showError("");
      setBusy(true);
      try {
        const signIn = Clerk.client.signIn;
        const factors = signIn.supportedFirstFactors || [];
        const codeFactor = factorByStrategy(factors, "email_code");
        if (!codeFactor?.emailAddressId) {
          throw new Error("Email code sign-in is not available.");
        }
        await signIn.prepareFirstFactor({
          strategy: "email_code",
          emailAddressId: codeFactor.emailAddressId,
        });
        setView("code");
        codeForm.code.focus();
      } catch (err) {
        showError(clerkErrorMessage(err));
      } finally {
        setBusy(false);
      }
    }
  });

  codeForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (busy) return;
    showError("");
    const code = codeForm.code.value;
    if (!code?.trim()) return;
    setBusy(true);
    try {
      await submitEmailCode(Clerk, code);
    } catch (err) {
      showError(clerkErrorMessage(err));
    } finally {
      setBusy(false);
    }
  });

  codeForm.querySelector('[data-action="restart"]').addEventListener("click", restart);

  shell.append(status, emailForm, linkPanel, codeForm, verifyPanel);
  mount.replaceChildren(shell);
}

function mountPasswordlessOnce(Clerk, env) {
  if (passwordlessUiMounted) return;
  clearStaleClerkHashRoute();
  renderPasswordlessForm(Clerk, env);
  passwordlessUiMounted = true;
}

function resetPasswordlessUi() {
  passwordlessUiMounted = false;
  const el = $("#clerkSignIn");
  if (el) el.replaceChildren();
}

async function main() {
  setAppVisible(false);
  let env;
  try {
    env = await fetchClerkEnv();
  } catch {
    const gate = $("#authGate");
    if (gate) {
      gate.innerHTML =
        '<p class="auth-gate-message">Sign-in configuration is unavailable. Check API server env.</p>';
    }
    return;
  }

  const Clerk = await loadClerkScript(env.frontendApi, env.publishableKey);
  await Clerk.load();

  const redirectUrl = emailLinkRedirectUrl(env);

  try {
    if (isEmailLinkReturnUrl()) {
      setAppVisible(false);
      const gate = $("#authGate");
      if (gate) gate.hidden = false;
      const mount = $("#clerkSignIn");
      if (mount) {
        mount.replaceChildren(
          Object.assign(document.createElement("p"), {
            className: "auth-form-lead",
            textContent: "Completing sign-in from your email link…",
          }),
        );
      }
      await completeEmailLinkIfPresent(Clerk, redirectUrl);
    }
  } catch (err) {
    const mount = $("#clerkSignIn");
    if (mount) {
      mount.replaceChildren(
        Object.assign(document.createElement("p"), {
          className: "auth-form-status",
          textContent: clerkErrorMessage(err),
        }),
      );
    }
    passwordlessUiMounted = true;
  }

  let hadUser = Boolean(Clerk.user);

  const sync = () => {
    if (Clerk.user) {
      resetPasswordlessUi();
      setAppVisible(true);
      bootDashboard(Clerk);
      hadUser = true;
      return;
    }

    setAppVisible(false);
    if (hadUser) {
      hadUser = false;
      dashboardBooted = false;
      resetPasswordlessUi();
    }
    mountPasswordlessOnce(Clerk, env);
  };

  Clerk.addListener(sync);
  sync();
}

main();
