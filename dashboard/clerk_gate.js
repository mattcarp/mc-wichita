/**
 * Clerk sign-in gate: loads dashboard modules only after a valid session exists.
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

/** Sign-in only: allowlisted emails via Clerk dashboard; no sign-up path in UI. */
const SIGN_IN_APPEARANCE = {
  ...CLERK_THEME,
  elements: {
    ...CLERK_APPEARANCE.elements,
    socialButtonsRoot: { display: "none" },
    dividerRow: { display: "none" },
    footerAction: { display: "none" },
    footerActionText: { display: "none" },
    footerActionLink: { display: "none" },
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

let dashboardBooted = false;
let signInMounted = false;

function signInHomeUrl() {
  return `${window.location.origin}/`;
}

/** Drop stale hash routes from earlier hash-based SignIn mounts. */
function clearStaleClerkHashRoute() {
  const hash = window.location.hash;
  if (!hash || hash === "#" || !hash.startsWith("#/")) return;
  const path = window.location.pathname + window.location.search;
  window.history.replaceState(null, "", path);
}

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

function mountSignInOnce(Clerk) {
  if (signInMounted) return;
  const el = $("#clerkSignIn");
  if (!el) return;
  clearStaleClerkHashRoute();
  const home = signInHomeUrl();
  Clerk.mountSignIn(el, {
    appearance: SIGN_IN_APPEARANCE,
    routing: "virtual",
    withSignUp: false,
    fallbackRedirectUrl: home,
    signInFallbackRedirectUrl: home,
  });
  signInMounted = true;
}

function unmountSignIn(Clerk) {
  if (!signInMounted) return;
  const el = $("#clerkSignIn");
  if (el && typeof Clerk.unmountSignIn === "function") {
    Clerk.unmountSignIn(el);
  } else if (el) {
    el.innerHTML = "";
  }
  signInMounted = false;
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

  let hadUser = Boolean(Clerk.user);

  const sync = () => {
    if (Clerk.user) {
      unmountSignIn(Clerk);
      setAppVisible(true);
      bootDashboard(Clerk);
      hadUser = true;
      return;
    }

    setAppVisible(false);
    mountSignInOnce(Clerk);

    if (hadUser) {
      hadUser = false;
      dashboardBooted = false;
    }
  };

  Clerk.addListener(sync);
  sync();
}

main();
