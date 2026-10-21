// Runs only inside the app's own site-specific browser. No Python bridge is exposed.
(() => {
  if (window.__pcMedia) return;
  const state = window.__pcMedia = {posts: [], ended: false, responses: 0, errors: 0};
  const owner = location.pathname.split('/').filter(Boolean)[0]?.toLowerCase();
  const isX = /(^|\.)x\.com$|(^|\.)twitter\.com$/.test(location.hostname);
  const add = u => { if (!state.posts.includes(u)) state.posts.push(u); };
  function walk(v, path = '') {
    if (!v || typeof v !== 'object') return;
    if (isX && v.legacy?.extended_entities?.media?.length) {
      const name = v.core?.user_results?.result?.legacy?.screen_name || v.core?.user_results?.result?.core?.screen_name;
      if (name?.toLowerCase() === owner && v.legacy.id_str) add(`https://x.com/${name}/status/${v.legacy.id_str}`);
    }
    if (!isX && (v.code || v.shortcode) && (v.media_type || v.image_versions2 || /^Graph(Image|Video|Sidecar)$/.test(v.__typename || ''))) {
      const name = v.user?.username || v.owner?.username;
      if (!name || name.toLowerCase() === owner) add(`https://www.instagram.com/p/${v.code || v.shortcode}/`);
    }
    if (isX && v.type === 'TimelineTerminateTimeline' && v.direction === 'Bottom') state.ended = true;
    if (isX && v.type === 'TimelineAddEntries' && Array.isArray(v.entries) && v.entries.length === 0) state.ended = true;
    if (!isX && /timeline|feed|edge_owner_to_timeline_media/i.test(path) && (v.has_next_page === false || v.more_available === false)) state.ended = true;
    for (const [k, child] of Object.entries(v)) if (child && typeof child === 'object') walk(child, path + '/' + k);
  }
  function capture(url, data) {
    const eligible = isX ? /\/UserMedia(?:\?|$)/.test(url) : /graphql|\/feed\/user\//.test(url);
    if (!eligible) return;
    state.responses++;
    try { walk(data); } catch (_) { state.errors++; }
  }
  const fetchOriginal = window.fetch;
  window.fetch = async function(...args) {
    const r = await fetchOriginal.apply(this, args);
    const u = r.url;
    if (/graphql|\/feed\/user\//.test(u)) r.clone().text().then(t => { try {capture(u, JSON.parse(t));} catch (_) {} });
    return r;
  };
  const open = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this.addEventListener('load', () => { try { capture(this.responseURL, this.responseType === 'json' ? this.response : JSON.parse(this.responseText)); } catch (_) {} });
    return open.call(this, method, url, ...rest);
  };
})();
