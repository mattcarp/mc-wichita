/**
 * Signed-in header user chip + dropdown (replaces Clerk UserButton).
 */

function primaryEmail(user) {
  if (!user) return "";
  if (user.primaryEmailAddress?.emailAddress) return user.primaryEmailAddress.emailAddress;
  if (Array.isArray(user.emailAddresses) && user.emailAddresses[0]?.emailAddress) {
    return user.emailAddresses[0].emailAddress;
  }
  if (typeof user.email === "string") return user.email;
  return "";
}

export function userDisplayName(user) {
  const first = user?.firstName?.trim();
  if (first) return first;
  const email = primaryEmail(user);
  if (email.includes("@")) return email.split("@")[0];
  return "Account";
}

export function userInitial(user) {
  const ch = userDisplayName(user).charAt(0);
  return ch ? ch.toUpperCase() : "?";
}

/**
 * @param {HTMLElement} container
 * @param {object} Clerk
 * @param {{ onSignOut?: () => void | Promise<void> }} options
 */
export function mountUserMenu(container, Clerk, options = {}) {
  if (!container) return { update() {}, destroy() {} };

  let menuOpen = false;
  let docListener = null;

  const root = document.createElement("div");
  root.className = "wichita-user-menu";

  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "wichita-user-trigger";
  trigger.setAttribute("aria-haspopup", "menu");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("data-testid", "wichita-user-trigger");

  const avatar = document.createElement("span");
  avatar.className = "wichita-user-avatar";
  avatar.setAttribute("aria-hidden", "true");

  const label = document.createElement("span");
  label.className = "wichita-user-name";

  const chevron = document.createElement("span");
  chevron.className = "wichita-user-chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "▾";

  trigger.append(avatar, label, chevron);

  const panel = document.createElement("div");
  panel.className = "wichita-user-dropdown";
  panel.setAttribute("role", "menu");
  panel.hidden = true;
  panel.setAttribute("data-testid", "wichita-user-dropdown");

  const emailLine = document.createElement("p");
  emailLine.className = "wichita-user-dropdown-email mono";

  const signOutBtn = document.createElement("button");
  signOutBtn.type = "button";
  signOutBtn.className = "wichita-user-signout";
  signOutBtn.setAttribute("role", "menuitem");
  signOutBtn.textContent = "Sign out";
  signOutBtn.setAttribute("data-testid", "wichita-user-signout");

  panel.append(emailLine, signOutBtn);
  root.append(trigger, panel);
  container.replaceChildren(root);
  container.hidden = false;

  function closeMenu() {
    menuOpen = false;
    panel.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (docListener) {
      document.removeEventListener("click", docListener);
      docListener = null;
    }
  }

  function openMenu() {
    menuOpen = true;
    panel.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    docListener = (ev) => {
      if (!root.contains(ev.target)) closeMenu();
    };
    document.addEventListener("click", docListener);
  }

  trigger.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (menuOpen) closeMenu();
    else openMenu();
  });

  signOutBtn.addEventListener("click", async (ev) => {
    ev.preventDefault();
    closeMenu();
    if (typeof Clerk.signOut === "function") {
      await Clerk.signOut();
    }
    await options.onSignOut?.();
  });

  function paint(user) {
    if (!user) {
      container.hidden = true;
      closeMenu();
      return;
    }
    container.hidden = false;
    avatar.textContent = userInitial(user);
    label.textContent = userDisplayName(user);
    emailLine.textContent = primaryEmail(user) || "—";
    trigger.setAttribute("aria-label", `Account menu for ${userDisplayName(user)}`);
  }

  paint(Clerk.user);

  return {
    update(user) {
      paint(user);
    },
    openMenu() {
      openMenu();
    },
    destroy() {
      closeMenu();
      container.replaceChildren();
      container.hidden = true;
    },
  };
}
