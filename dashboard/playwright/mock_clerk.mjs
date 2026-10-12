/** Minimal Clerk mock for dashboard Playwright flows. */

import {
  clerkAPIResponseError,
  CLERK_VERIFICATION_CODE_RATE_LIMIT_BODY,
} from "../clerk_errors.mjs";

const PREPARE_FIRST_FACTOR_URL =
  "https://example.clerk.accounts.dev/v1/client/sign_ins/sign_in_harness/prepare_first_factor";

const DEFAULT_USER = {
  id: "user_harness",
  firstName: "Mattie",
  primaryEmailAddress: { emailAddress: "mattie@wichitawire.com" },
};

export function clerkEnvPayload() {
  return {
    publishableKey: "pk_test_harness",
    frontendApi: "https://example.clerk.accounts.dev",
    emailLinkRedirectUrl: "https://wichitawire.com/",
  };
}

export function installFetchMocks({ dashboardJs = "export {};" } = {}) {
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = String(input);
    if (url.includes("clerk-env.json")) {
      return new Response(JSON.stringify(clerkEnvPayload()), {
        headers: { "Content-Type": "application/json" },
      });
    }
    if (url.includes("dashboard.js")) {
      return new Response(dashboardJs, { headers: { "Content-Type": "text/javascript" } });
    }
    if (url.startsWith("/api/") || url.includes("/api/")) {
      return new Response(JSON.stringify({}), {
        headers: { "Content-Type": "application/json" },
        status: 200,
      });
    }
    return nativeFetch(input, init);
  };
}

/**
 * @param {{
 *   user?: object | null,
 *   rateLimitOnCode?: boolean,
 * }} config
 */
export function createMockClerk(config = {}) {
  const listeners = new Set();
  let rateLimitOnCode = Boolean(config.rateLimitOnCode);
  let operationDelayMs = Number(config.operationDelayMs) || 0;
  let signOutNotifiesListener = config.signOutNotifiesListener !== false;
  let rateLimitOnCreate = Boolean(config.rateLimitOnCreate);
  let rateLimitOnPrepareLink = Boolean(config.rateLimitOnPrepareLink);
  const useNetworkPrepare = Boolean(config.useNetworkPrepare);
  let notifyOnSignInCreate = config.notifyOnSignInCreate !== false;

  function verificationCodeRateLimitError() {
    return clerkAPIResponseError(429, CLERK_VERIFICATION_CODE_RATE_LIMIT_BODY);
  }

  async function delay() {
    if (operationDelayMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, operationDelayMs));
    }
  }

  const signIn = {
    supportedFirstFactors: [
      { strategy: "email_link", emailAddressId: "ea_harness" },
      { strategy: "email_code", emailAddressId: "ea_harness" },
    ],
    async create() {
      await delay();
      if (rateLimitOnCreate) {
        throw verificationCodeRateLimitError();
      }
      if (notifyOnSignInCreate) {
        clerk._notify();
      }
      return signIn;
    },
    async prepareFirstFactor({ strategy } = {}) {
      await delay();
      if (useNetworkPrepare && strategy === "email_link") {
        const res = await fetch(PREPARE_FIRST_FACTOR_URL, { method: "POST" });
        let body = {};
        try {
          body = await res.json();
        } catch {
          body = {};
        }
        if (!res.ok) {
          throw clerkAPIResponseError(res.status, body);
        }
        return signIn;
      }
      if (strategy === "email_link" && rateLimitOnPrepareLink) {
        throw verificationCodeRateLimitError();
      }
      if (strategy === "email_code" && rateLimitOnCode) {
        rateLimitOnCode = false;
        throw verificationCodeRateLimitError();
      }
      return signIn;
    },
    async attemptFirstFactor({ code }) {
      await delay();
      if (code === "000000") {
        throw verificationCodeRateLimitError();
      }
      if (code !== "123456") {
        throw {
          errors: [
            {
              code: "form_code_incorrect",
              message: "Incorrect code",
              longMessage: "Incorrect code. Try again.",
            },
          ],
        };
      }
      return { status: "complete", createdSessionId: "sess_harness" };
    },
  };

  const clerk = {
    user: config.user ?? null,
    get session() {
      return clerk.user ? { getToken: async () => "harness-session-jwt" } : null;
    },
    client: { signIn },
    async load() {},
    addListener(cb) {
      listeners.add(cb);
    },
    _notify() {
      listeners.forEach((cb) => cb());
    },
    async setActive() {
      clerk.user = { ...DEFAULT_USER, ...(config.userOnActivate || {}) };
      clerk._notify();
    },
    async signOut() {
      await delay();
      clerk.user = null;
      if (signOutNotifiesListener) {
        clerk._notify();
      }
    },
    setSignOutNotifiesListener(on) {
      signOutNotifiesListener = Boolean(on);
    },
    setRateLimitOnCreate(on) {
      rateLimitOnCreate = Boolean(on);
    },
    setRateLimitOnPrepareLink(on) {
      rateLimitOnPrepareLink = Boolean(on);
    },
    setNotifyOnSignInCreate(on) {
      notifyOnSignInCreate = Boolean(on);
    },
    mountUserButton() {},
    setRateLimitOnCode(on) {
      rateLimitOnCode = Boolean(on);
    },
    setOperationDelay(ms) {
      operationDelayMs = Math.max(0, Number(ms) || 0);
    },
    setUser(next) {
      clerk.user = next;
      clerk._notify();
    },
  };

  return clerk;
}
