/* Decides how the service worker treats a request. Kept separate so tests can load it directly.
 * Rule: only the app shell and static files are ever cached. Learner data, sign-in, payments and
 * anything that changes state always go to the network. */
self.swStrategy = function (url, method, mode, origin) {
  var u = new URL(url);
  if (method !== 'GET' || u.origin !== origin) return 'network';
  if (/^\/(api|auth|webhooks|metrics|health)(\/|$)/.test(u.pathname)) return 'network';
  if (u.pathname.indexOf('/assets/') === 0) return 'cache-first';          // content-hashed by Vite: safe forever
  if (mode === 'navigate') return 'page';                                  // network first, cached shell offline
  return 'stale-while-revalidate';                                         // icons, fonts, editor assets
};
