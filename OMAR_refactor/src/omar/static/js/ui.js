export function qs(sel, root=document){ return root.querySelector(sel); }
export function qsa(sel, root=document){ return Array.from(root.querySelectorAll(sel)); }

export function showLoading(el){ if (!el) return; el.innerHTML = '<span class="loading" aria-label="loading"></span>'; }
export function hideLoading(el){ if (!el) return; el.innerHTML = ''; }

export async function csrfFetch(url, options={}){
  const token = getCsrfToken();
  const headers = Object.assign({ 'X-CSRF-Token': token, 'Content-Type': 'application/json' }, options.headers||{});
  const resp = await fetch(url, { ...options, headers, credentials: 'same-origin' });
  if (!resp.ok) {
    const msg = await safeText(resp);
    throw new Error(msg || (`HTTP ${resp.status}`));
  }
  return resp;
}

function getCsrfToken(){
  const m = document.cookie.match(/(?:^|; )csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

async function safeText(resp){
  try { return await resp.text(); } catch { return ''; }
}
