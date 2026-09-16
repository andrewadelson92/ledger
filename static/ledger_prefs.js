/** Per-user preference catalogs (server-backed, with one-time localStorage import). */
(function(global) {
  const cache = {};
  const inflight = {};

  function localGet(key) {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function localSet(key, items) {
    try {
      localStorage.setItem(key, JSON.stringify(items));
    } catch (e) {}
  }

  function fetchAll() {
    if (cache._all) return Promise.resolve(cache._all);
    if (inflight._all) return inflight._all;
    inflight._all = fetch('/api/preferences', { credentials: 'same-origin' })
      .then(function(r) {
        if (!r.ok) throw new Error('prefs ' + r.status);
        return r.json();
      })
      .then(function(data) {
        cache._all = data || {};
        delete inflight._all;
        return cache._all;
      })
      .catch(function(err) {
        delete inflight._all;
        throw err;
      });
    return inflight._all;
  }

  function loadKind(kind, localKey, normalize) {
    normalize = normalize || function(items) { return items.filter(Boolean); };
    return fetchAll().then(function(all) {
      let items = normalize(Array.isArray(all[kind]) ? all[kind] : []);
      const localItems = normalize(localGet(localKey));
      if ((!items || !items.length) && localItems.length) {
        items = localItems;
        return putKind(kind, localKey, items).then(function() { return items; });
      }
      localSet(localKey, items);
      return items;
    }).catch(function() {
      return normalize(localGet(localKey));
    });
  }

  function putKind(kind, localKey, items) {
    localSet(localKey, items);
    if (cache._all) cache._all[kind] = items;
    return fetch('/api/preferences/' + kind, {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: items }),
    }).then(function(r) {
      if (!r.ok) throw new Error('prefs put ' + r.status);
      return r.json();
    }).catch(function() {
      return { items: items };
    });
  }

  global.LedgerPrefs = {
    loadEmotions: function() {
      return loadKind('saved_emotions', 'ledger_saved_emotions', function(items) {
        return items.filter(Boolean).map(function(x) {
          return typeof x === 'string' ? x : (x && x.name) || '';
        }).filter(Boolean);
      });
    },
    saveEmotions: function(items) {
      return putKind('saved_emotions', 'ledger_saved_emotions', items);
    },
    loadSkills: function() {
      return loadKind('saved_skills', 'ledger_saved_skills', function(items) {
        return items.filter(function(item) {
          return item && item.module && item.skill;
        });
      });
    },
    saveSkills: function(items) {
      return putKind('saved_skills', 'ledger_saved_skills', items);
    },
    loadTargetBehaviors: function() {
      return loadKind('target_behaviors', 'ledger_target_behaviors', function(items) {
        return items.filter(Boolean).map(String);
      });
    },
    saveTargetBehaviors: function(items) {
      return putKind('target_behaviors', 'ledger_target_behaviors', items);
    },
  };
})(window);
