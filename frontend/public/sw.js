/* Tayarishe service worker: makes the app installable and opens offline to the cached shell.
 * It never stores learner data: API calls, sign-in and payments always use the network. */
importScripts('/sw-strategy.js');
var SHELL = 'prep-shell-v1';
var RUNTIME = 'prep-runtime-v1';
var PRECACHE = ['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png', '/icons/icon-512.png'];

self.addEventListener('install', function (event) {
  event.waitUntil(caches.open(SHELL).then(function (cache) { return cache.addAll(PRECACHE); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== SHELL && k !== RUNTIME; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  var how = self.swStrategy(request.url, request.method, request.mode, self.location.origin);
  if (how === 'network') return;                                            // let the browser handle it untouched
  if (how === 'cache-first') {
    event.respondWith(caches.match(request).then(function (hit) {
      return hit || fetch(request).then(function (response) {
        if (response.ok) { var copy = response.clone(); caches.open(RUNTIME).then(function (c) { c.put(request, copy); }); }
        return response;
      });
    }));
  } else if (how === 'page') {
    event.respondWith(fetch(request).then(function (response) {
      if (response.ok) { var copy = response.clone(); caches.open(SHELL).then(function (c) { c.put('/', copy); }); }
      return response;
    }).catch(function () { return caches.match('/'); }));
  } else {
    event.respondWith(caches.match(request).then(function (hit) {
      var refresh = fetch(request).then(function (response) {
        if (response.ok) { var copy = response.clone(); caches.open(RUNTIME).then(function (c) { c.put(request, copy); }); }
        return response;
      }).catch(function () { return hit; });
      return hit || refresh;
    }));
  }
});
