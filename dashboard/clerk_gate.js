/**
 * Passwordless Clerk gate (email link, then email code). Never mounts <SignIn />.
 */

import { mountPasswordlessAuthUI } from "./auth_gate_ui.mjs";
import { setAppVisible } from "./auth_gate_shell.mjs";
import { mountUserMenu } from "./auth_user_menu.mjs";

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
  const activated = await activateSignInSession(Clerk, result);
  if (!activated && !Clerk.user && result?.status !== "complete") {
    throw new Error("Invalid or expired code.");
  }
  if (Clerk.user || activated) {
    revealSignedInDashboard(Clerk);
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

function updateUserMenu(Clerk) {
  const mount = $("#wichitaUserMenu");
  if (!mount) return;
  if (!Clerk.user) {
    userMenuHandle?.destroy();
    userMenuHandle = null;
    return;
  }
  if (!userMenuHandle) {
    userMenuHandle = mountUserMenu(mount, Clerk, {
      onSignOut: () => {
        dashboardBooted = false;
        userMenuHandle?.destroy();
        userMenuHandle = null;
      },
    });
  } else {
    userMenuHandle.update(Clerk.user);
  }
}

async function bootDashboard(Clerk) {
  installAuthenticatedFetch(Clerk);
  updateUserMenu(Clerk);
  if (dashboardBooted) return;
  dashboardBooted = true;
  await import("./dashboard.js?v=20261011-clerk7");
}

function revealSignedInDashboard(Clerk) {
  resetPasswordlessUi();
  setAppVisible(true);
  bootDashboard(Clerk);
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
        throw new Error(clerkErrorMessage(err));
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
        throw new Error(clerkErrorMessage(err));
      }
    },
    onSubmitCode: async (code) => {
      try {
        await submitEmailCode(Clerk, code);
      } catch (err) {
        throw new Error(clerkErrorMessage(err));
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
      revealSignedInDashboard(Clerk);
      hadUser = true;
      return;
    }

    setAppVisible(false);
    if (hadUser) {
      hadUser = false;
      dashboardBooted = false;
      userMenuHandle?.destroy();
      userMenuHandle = null;
      resetPasswordlessUi();
    }
    mountPasswordlessOnce(Clerk, env);
  };

  Clerk.addListener(sync);
  sync();
}

if (!globalThis.__WICHITA_SKIP_AUTH_GATE_AUTOMAIN__) {
  bootstrapAuthGate();
}
