// The theme of the page: ?theme=dark|light for this display only (the manager's config window),
// else the choice kept by the browser for this origin, else dark. Pages read the colours their
// SVG attributes need with pybiscusTheme.color('--fit') and redraw on the "pybiscus-theme" event.
(function () {
  const KEY = 'pybiscus-theme', THEMES = ['dark', 'light'];
  const forced = new URLSearchParams(location.search).get('theme');
  let stored = null;
  try { stored = localStorage.getItem(KEY); } catch (e) { /* dark */ }
  let current = THEMES.includes(forced) ? forced : (THEMES.includes(stored) ? stored : 'dark');
  const root = document.documentElement;
  root.setAttribute('data-theme', current);

  function apply(theme, keep) {
    if (!THEMES.includes(theme)) return;
    current = theme;
    root.setAttribute('data-theme', theme);
    if (keep) try { localStorage.setItem(KEY, theme); } catch (e) { /* this page only */ }
    window.dispatchEvent(new CustomEvent('pybiscus-theme', { detail: theme }));
  }

  window.pybiscusTheme = {
    get: () => current,
    set: theme => apply(theme, !THEMES.includes(forced)),
    toggle: () => window.pybiscusTheme.set(current === 'dark' ? 'light' : 'dark'),
    color: name => getComputedStyle(root).getPropertyValue(name).trim(),
  };
  // the other pages of the same origin (an agent's pages, the manager's windows) follow
  addEventListener('storage', e => { if (e.key === KEY && !THEMES.includes(forced)) apply(e.newValue, false); });
  // the manager's page tells its config window (another origin) its theme
  addEventListener('message', e => { if (e.data && THEMES.includes(e.data.pybiscusTheme)) apply(e.data.pybiscusTheme, false); });
  document.addEventListener('click', e => {
    if (e.target.closest && e.target.closest('.pybiscus-theme-toggle')) window.pybiscusTheme.toggle();
  });
})();
