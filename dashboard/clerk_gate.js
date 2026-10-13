/**
 * Passwordless Clerk gate (email link, then email code). Never mounts <SignIn />.
 */

import { mountPasswordlessAuthUI } from "./auth_gate_ui.mjs";
import { setAppVisible } from "./auth_gate_shell.mjs";
import { clearUserMenuHost, mountUserMenu } from "./auth_user_menu.mjs";
import { clerkErrorMessage } from "./clerk_errors.mjs";

export { CLERK_RATE_LIMIT_MESSAGE, clerkErrorMessage, isClerkRateLimitError } from "./clerk_errors.mjs";

function $(sel) {
  return document.querySelector(sel);
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

let restoreNativeFetch = null;

function installAuthenticatedFetch(Clerk) {
  if (restoreNativeFetch) return;
  const nativeFetch = window.fetch.bind(window);
  restoreNativeFetch = () => {
    window.fetch = nativeFetch;
    restoreNativeFetch = null;
  };
  window.fetch = async (input, init = {}) => {
    const nextInit = { ...init, credentials: init.credentials ?? "include" };
    const headers = new Headers(nextInit.headers || {});
    if (Clerk.user) {
      try {
        const session = Clerk.session;
        if (session) {
          const token = await session.getToken();
          if (token && !headers.has("Authorization")) {
            headers.set("Authorization", `Bearer ${token}`);
          }
        }
      } catch {
        /* session ended */
      }
    }
    nextInit.headers = headers;
    return nativeFetch(input, nextInit);
  };
}

function tearDownAuthenticatedFetch() {
  restoreNativeFetch?.();
}

function throwClerkSignInError(err) {
  throw new Error(clerkErrorMessage(err));
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
  const activated = await activateSignInSession(Clerk, result);
  if (!activated && !Clerk.user && result?.status !== "complete") {
    throw new Error("Invalid or expired code.");
  }
  if (Clerk.user || activated) {
    revealSignedInDashboard(Clerk, gateEnv);
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
let userMenuHandle = null;
let signingOut = false;
let gateEnv = null;

function syncSignedOutGate(Clerk, env, { forceRemount = false } = {}) {
  if (forceRemount && linkWaitAbort) {
    linkWaitAbort.aborted = true;
    linkWaitAbort = null;
  }
  setAppVisible(false);
  userMenuHandle?.destroy();
  userMenuHandle = null;
  clearUserMenuHost($("#wichitaUserMenu"));
  const gate = $("#authGate");
  if (gate) {
    gate.hidden = false;
    gate.removeAttribute("hidden");
  }
  if (forceRemount) {
    tearDownAuthenticatedFetch();
    dashboardBooted = false;
    resetPasswordlessUi();
    passwordlessUiMounted = false;
  }
  if (!passwordlessUiMounted || forceRemount) {
    mountPasswordlessOnce(Clerk, env);
  }
}

function applySignedOutShell(Clerk, env) {
  syncSignedOutGate(Clerk, env, { forceRemount: true });
}

async function waitForClerkSignedOut(Clerk, timeoutMs = 8000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!Clerk.user) return true;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  return !Clerk.user;
}

async function handleUserSignOut(Clerk, env) {
  signingOut = true;
  applySignedOutShell(Clerk, env);
  try {
    if (typeof Clerk.signOut === "function") {
      await Clerk.signOut();
    }
  } catch (err) {
    console.warn("Wichita sign-out:", err);
  }
  await waitForClerkSignedOut(Clerk);

  if (globalThis.__WICHITA_SKIP_SIGN_OUT_RELOAD__) {
    signingOut = false;
    if (!Clerk.user) {
      applySignedOutShell(Clerk, env);
    }
    return;
  }

  signingOut = false;
  window.location.replace(`${window.location.origin}/`);
}

function updateUserMenu(Clerk, env) {
  const mount = $("#wichitaUserMenu");
  if (!mount) return;
  if (!Clerk.user) {
    userMenuHandle?.destroy();
    userMenuHandle = null;
    clearUserMenuHost(mount);
    return;
  }
  if (!userMenuHandle) {
    userMenuHandle = mountUserMenu(mount, Clerk, {
      onSignOut: () => handleUserSignOut(Clerk, env),
    });
  } else {
    userMenuHandle.update(Clerk.user);
  }
}

async function bootDashboard(Clerk, env) {
  installAuthenticatedFetch(Clerk);
  updateUserMenu(Clerk, env);
  if (dashboardBooted) return;
  dashboardBooted = true;
  await import("./dashboard.js?v=20261013-sp8");
}

function revealSignedInDashboard(Clerk, env) {
  resetPasswordlessUi();
  setAppVisible(true);
  bootDashboard(Clerk, env);
}

function renderPasswordlessForm(Clerk, env) {
  const mount = $("#clerkSignIn");
  if (!mount) return;

  const redirectUrl = emailLinkRedirectUrl(env);
  let ui;

  ui = mountPasswordlessAuthUI(mount, {
    onRestart: () => {
      if (linkWaitAbort) {
        linkWaitAbort.aborted = true;
        linkWaitAbort = null;
      }
    },
    onSubmitEmail: async (email) => {
      try {
        const result = await startPasswordlessSignIn(Clerk, email, redirectUrl);
        if (result.mode === "link") {
          ui.setView("link");
          linkWaitAbort = { aborted: false };
          waitForEmailLinkCompletion(Clerk).catch(() => {});
        } else {
          ui.setView("code");
          ui.codeForm.code.focus();
        }
      } catch (err) {
        throwClerkSignInError(err);
      }
    },
    onUseCodeInstead: async () => {
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
        ui.setView("code");
        ui.codeForm.code.focus();
      } catch (err) {
        throwClerkSignInError(err);
      }
    },
    onSubmitCode: async (code) => {
      try {
        await submitEmailCode(Clerk, code);
      } catch (err) {
        throwClerkSignInError(err);
      }
    },
  });
  mount.__wichitaAuthUi = ui;
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

export async function bootstrapAuthGate() {
  setAppVisible(false);
  clearUserMenuHost($("#wichitaUserMenu"));
  let env;
  try {
    env = await fetchClerkEnv();
    gateEnv = env;
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
    if (signingOut) return;

    if (Clerk.user) {
      revealSignedInDashboard(Clerk, env);
      hadUser = true;
      return;
    }

    if (hadUser) {
      syncSignedOutGate(Clerk, env, { forceRemount: true });
      hadUser = false;
      return;
    }
    if (!passwordlessUiMounted) {
      syncSignedOutGate(Clerk, env, { forceRemount: false });
    }
  };

  Clerk.addListener(sync);
  sync();
}

if (!globalThis.__WICHITA_SKIP_AUTH_GATE_AUTOMAIN__) {
  bootstrapAuthGate();
}
