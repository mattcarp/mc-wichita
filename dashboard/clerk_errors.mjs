/**
 * Clerk API error normalization (ClerkAPIResponseError + JSON body shapes).
 */

export const CLERK_RATE_LIMIT_MESSAGE =
  "Too many sign-in attempts. Please wait a few minutes and try again.";

export const CLERK_VERIFICATION_CODE_RATE_LIMIT_BODY = {
  errors: [
    {
      message: "Too many verification code requests",
      long_message: "Too many verification code requests. Please try again later.",
      code: "verification_code_rate_limit_exceeded",
    },
  ],
};

export function clerkAPIResponseError(status, body) {
  const errors = Array.isArray(body?.errors) ? body.errors : [];
  const first = errors[0];
  const err = new Error(first?.message || `Clerk API error (${status})`);
  err.name = "ClerkAPIResponseError";
  err.status = status;
  err.clerkError = true;
  err.errors = errors;
  return err;
}

function clerkErrorEntries(err) {
  if (Array.isArray(err?.errors) && err.errors.length) return err.errors;
  if (err?.error) return [err.error];
  return [];
}

function entryLongMessage(entry) {
  return entry?.longMessage || entry?.long_message || "";
}

function entryMessage(entry) {
  return entry?.message || "";
}

export function isClerkRateLimitError(err) {
  if (!err) return false;
  if (err.status === 429) return true;
  const first = clerkErrorEntries(err)[0];
  const code = String(first?.code || "").toLowerCase();
  if (
    code === "too_many_requests" ||
    code === "verification_code_rate_limit_exceeded" ||
    code.includes("rate_limit") ||
    code.includes("rate")
  ) {
    return true;
  }
  const msg = `${entryMessage(first)} ${entryLongMessage(first)} ${err?.message || ""}`.toLowerCase();
  return msg.includes("too many") || msg.includes("rate limit");
}

export function clerkErrorMessage(err) {
  if (isClerkRateLimitError(err)) return CLERK_RATE_LIMIT_MESSAGE;
  const first = clerkErrorEntries(err)[0];
  const fromClerk = entryLongMessage(first) || entryMessage(first);
  if (fromClerk) return fromClerk;
  if (typeof err?.message === "string" && err.message.trim()) return err.message.trim();
  return "Sign-in failed. Please try again.";
}
