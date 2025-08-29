// filepath: static/explore/popover.js
// Global Popover Utility (simple, dependency-free)
// Usage: window.Popover.open(anchorEl, { html: '<b>Hi</b>' })
//        window.Popover.openText(anchorEl, 'Plain text...')
//        window.Popover.openList(anchorEl, 'Title', ['Row 1', { text: 'Row 2', severity: 'abnormal' }])
//        window.Popover.toggle(anchorEl, options)
//        window.Popover.close()
(function(){
  if(window.Popover) return; // singleton

  let activePopover = null;
  let activeAnchor = null;
  let hideTimer = null;

  function _escape(s){
    return String(s ?? '')
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;')
      .replace(/'/g,'&#39;');
  }

  function _ensureStyles(el){
    Object.assign(el.style, {
      position: 'absolute', maxWidth: '520px', whiteSpace: 'pre-wrap',
      background: '#fff', color: '#222', border: '1px solid #d1d5db',
      padding: '8px 10px', borderRadius: '6px', boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
      zIndex: '9999', fontSize: '12px', lineHeight: '1.45'
    });
  }

  function _placeNear(anchor, pop, placement){
    const r = anchor.getBoundingClientRect();
    const pr = pop.getBoundingClientRect();
    const pad = 8, vw = window.innerWidth, vh = window.innerHeight;
    let top, left;
    const mode = placement || 'bottom';
    if(mode === 'top'){
      top = window.scrollY + r.top - pr.height - 6;
      left = window.scrollX + r.left;
    } else if(mode === 'right'){
      top = window.scrollY + r.top;
      left = window.scrollX + r.right + 6;
    } else if(mode === 'left'){
      top = window.scrollY + r.top;
      left = window.scrollX + r.left - pr.width - 6;
    } else { // bottom
      top = window.scrollY + r.bottom + 6;
      left = window.scrollX + r.left;
    }
    // keep in viewport
    if(left + pr.width > window.scrollX + vw - pad){ left = window.scrollX + vw - pad - pr.width; }
    if(left < window.scrollX + pad){ left = window.scrollX + pad; }
    if(top + pr.height > window.scrollY + vh - pad){ top = window.scrollY + r.top - pr.height - 6; }
    if(top < window.scrollY + pad){ top = window.scrollY + pad; }
    pop.style.left = left + 'px';
    pop.style.top = top + 'px';
  }

  function _onDocClick(ev){
    if(!activePopover) return;
    const el = ev.target;
    if(activePopover.contains(el) || (activeAnchor && activeAnchor.contains(el))) return;
    close();
  }

  function open(anchorEl, options){
    if(!anchorEl) return;
    // second-click toggle
    if(activeAnchor === anchorEl){ close(); return; }
    close();

    const opts = options || {};
    const pop = document.createElement('div');
    pop.className = 'global-popover' + (opts.className ? (' '+opts.className) : '');
    _ensureStyles(pop);

    if(opts.title){
      const h = document.createElement('h4');
      h.textContent = String(opts.title);
      Object.assign(h.style, { margin: '0 0 6px 0', fontSize: '12px', color:'#111' });
      pop.appendChild(h);
    }
    if(opts.html){
      pop.innerHTML += String(opts.html);
    } else if(opts.text){
      pop.textContent = String(opts.text);
    } else if(Array.isArray(opts.rows)){
      opts.rows.forEach(r=>{
        const div = document.createElement('div');
        div.className = 'row';
        if(r && typeof r === 'object' && 'text' in r){
          div.textContent = String(r.text);
          if(r.severity === 'abnormal') div.classList.add('abnormal');
          if(r.severity === 'critical') div.classList.add('critical');
        } else {
          div.textContent = String(r);
        }
        pop.appendChild(div);
      });
    }
    document.body.appendChild(pop);
    // initial measure + place
    try { _placeNear(anchorEl, pop, opts.placement); } catch(_e){}

    activePopover = pop;
    activeAnchor = anchorEl;
    setTimeout(()=> document.addEventListener('click', _onDocClick, true), 0);

    // optional hover persistence
    if(opts.hover){
      pop.addEventListener('mouseenter', ()=>{ if(hideTimer){ clearTimeout(hideTimer); hideTimer = null; } });
      pop.addEventListener('mouseleave', ()=>{ hideTimer = setTimeout(()=> close(), 150); });
    }
    return pop;
  }

  function openText(anchorEl, text, opts){
    return open(anchorEl, Object.assign({ text, hover:true }, opts||{}));
  }

  function openHtml(anchorEl, html, opts){
    return open(anchorEl, Object.assign({ html, hover:true }, opts||{}));
  }

  function openList(anchorEl, title, rows, opts){
    return open(anchorEl, Object.assign({ title, rows, hover:false }, opts||{}));
  }

  function toggle(anchorEl, options){
    if(activeAnchor === anchorEl){ close(); return; }
    open(anchorEl, options);
  }

  function close(){
    if(hideTimer){ clearTimeout(hideTimer); hideTimer = null; }
    if(activePopover){ try{ activePopover.remove(); }catch(_e){} activePopover = null; }
    activeAnchor = null;
    try{ document.removeEventListener('click', _onDocClick, true); }catch(_e){}
  }

  function hoverAttach(anchorEl, getContent){
    if(!anchorEl) return;
    anchorEl.addEventListener('mouseenter', (e)=>{
      if(typeof getContent === 'function'){
        const res = getContent(anchorEl);
        if(!res) return;
        if(typeof res === 'string') openText(anchorEl, res, { hover:true });
        else if(res && typeof res === 'object' && ('html' in res || 'text' in res || 'rows' in res)) open(anchorEl, Object.assign({ hover:true }, res));
        else openText(anchorEl, String(res), { hover:true });
      }
    });
    anchorEl.addEventListener('mouseleave', ()=>{
      hideTimer = setTimeout(()=> close(), 150);
    });
  }

  window.Popover = { open, openText, openHtml, openList, toggle, close, hoverAttach };
})();
