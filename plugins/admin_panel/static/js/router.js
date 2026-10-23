const routes = {
  "/admin": "overview",
  "/admin/overview": "overview",
  "/admin/reports": "reports",
  "/admin/checks": "checks",
  "/admin/ai": "services",
  "/admin/services": "services",
  "/admin/skills": "skills",
  "/admin/business": "business",
  "/admin/prompts": "prompts",
  "/admin/commands": "commands",
  "/admin/logs": "logs",
  "/admin/tasks": "tasks",
  "/admin/config": "config",
};

export const viewPaths = {
  overview: "/admin/overview",
  reports: "/admin/reports",
  checks: "/admin/checks",
  services: "/admin/ai",
  skills: "/admin/skills",
  business: "/admin/business",
  prompts: "/admin/prompts",
  commands: "/admin/commands",
  logs: "/admin/logs",
  tasks: "/admin/tasks",
  config: "/admin/config",
};

export function resolveView(pathname) {
  const clean = (pathname || "").replace(/\/+$/, "") || "/admin";
  return routes[clean] || "overview";
}

export function currentView() {
  return resolveView(window.location.pathname);
}

export function navigate(view, replace = false) {
  const path = viewPaths[view] || viewPaths.overview;
  if (window.location.pathname === path) return;
  if (replace) {
    window.history.replaceState({ view }, "", path);
  } else {
    window.history.pushState({ view }, "", path);
  }
}

export function onRouteChange(handler) {
  window.addEventListener("popstate", () => handler(currentView()));
}
