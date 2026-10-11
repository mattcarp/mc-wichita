/**
 * Clerk sign-in gate: loads dashboard modules only after a valid session exists.
 */

const CLERK_APPEARANCE = {
  variables: {
    colorBackground: "#070b14",
    colorInputBackground: "#0e1420",
    colorNeutral: "#e8eaef",
    colorPrimary: "#3ec6c9",
    colorText: "#e8eaef",
    colorTextSecondary: "#9aa3b2",
    borderRadius: "0.5rem",
  },
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

let dashboardBooted = false;

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

function mountSignIn(Clerk) {
  const el = $("#clerkSignIn");
  if (!el) return;
  el.innerHTML = "";
  Clerk.mountSignIn(el, {
    appearance: CLERK_APPEARANCE,
    routing: "hash",
    signUpUrl: undefined,
  });
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

  const sync = () => {
    if (Clerk.user) {
      setAppVisible(true);
      bootDashboard(Clerk);
    } else {
      dashboardBooted = false;
      setAppVisible(false);
      mountSignIn(Clerk);
    }
  };

  Clerk.addListener(sync);
  sync();
}

main();
