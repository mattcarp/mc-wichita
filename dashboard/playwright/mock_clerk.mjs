/** Minimal Clerk mock for dashboard Playwright flows. */

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

  const signIn = {
    supportedFirstFactors: [
      { strategy: "email_link", emailAddressId: "ea_harness" },
      { strategy: "email_code", emailAddressId: "ea_harness" },
    ],
    async create() {
      return signIn;
    },
    async prepareFirstFactor({ strategy } = {}) {
      if (strategy === "email_code" && rateLimitOnCode) {
        rateLimitOnCode = false;
        throw {
          errors: [
            {
              code: "too_many_requests",
              message: "Too many requests",
              longMessage:
                "Too many requests. Wait a minute, then try again or use the sign-in link already in your email.",
            },
          ],
        };
      }
      return signIn;
    },
    async attemptFirstFactor({ code }) {
      if (code === "000000") {
        throw {
          errors: [
            {
              code: "too_many_requests",
              message: "Too many requests",
              longMessage: "Too many requests. Wait a minute, then try again.",
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
      clerk.user = null;
      clerk._notify();
    },
    mountUserButton() {},
    setRateLimitOnCode(on) {
      rateLimitOnCode = Boolean(on);
    },
    setUser(next) {
      clerk.user = next;
      clerk._notify();
    },
  };

  return clerk;
}
