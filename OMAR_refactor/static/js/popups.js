// filepath: static/popups.js
(function(){
  if(window.Popups) return;
  window.Popups = (function(){
    let activeEl = null;
    let activeAnchor = null;

    function close(){
      try{ if(activeEl && activeEl.parentNode){ activeEl.parentNode.removeChild(activeEl); } }catch(_e){}
      activeEl = null; activeAnchor = null;
      try{ document.removeEventListener('click', onDocClick, true); }catch(_e){}
    }

    function onDocClick(ev){
      if(!activeEl) return;
      const t = ev && ev.target;
      try{
        if(activeEl.contains(t) || (activeAnchor && activeAnchor.contains && activeAnchor.contains(t))) return;
      }catch(_e){}
      close();
    }

    function position(pop, anchor, opts){
      const pad = 8;
      const ar = anchor.getBoundingClientRect();
      let top = window.scrollY + ar.bottom + 6;
      let left = window.scrollX + ar.left;
      // pre-measure
      pop.style.visibility = 'hidden';
      document.body.appendChild(pop);
      const pr = pop.getBoundingClientRect();
      const vw = window.innerWidth, vh = window.innerHeight;
      if(left + pr.width > window.scrollX + vw - pad){ left = window.scrollX + vw - pad - pr.width; }
      if(left < window.scrollX + pad){ left = window.scrollX + pad; }
      if(top + pr.height > window.scrollY + vh - pad){
        top = window.scrollY + ar.top - pr.height - 6;
        if(top < window.scrollY + pad) top = window.scrollY + pad;
      }
      pop.style.left = left + 'px';
      pop.style.top = top + 'px';
      pop.style.visibility = '';
    }

    function build(content, opts){
      const div = document.createElement('div');
      div.className = 'popup';
      Object.assign(div.style, {
        position: 'absolute',
        maxWidth: (opts && opts.maxWidth) || '480px',
        whiteSpace: 'pre-wrap',
        background: '#fff', color: '#222',
        border: '1px solid #d1d5db', padding: '8px 10px', borderRadius: '6px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.15)', zIndex: 10000,
        fontSize: (opts && opts.fontSize) || '12px', lineHeight: '1.4'
      });
      if(opts && opts.className){ try{ div.classList.add(opts.className); }catch(_e){} }
      if(typeof content === 'string'){
        div.textContent = content;
      } else if(content instanceof Node){
        div.appendChild(content);
      }
      return div;
    }

    function show(anchorEl, content, opts){
      if(!anchorEl) return null;
      // Second-click toggle: clicking the same anchor closes the popover
      if(activeAnchor === anchorEl){ close(); return null; }
      close();
      const pop = build(content, opts || {});
      // Append and position
      document.body.appendChild(pop);
      position(pop, anchorEl, opts || {});
      activeEl = pop; activeAnchor = anchorEl;
      // Outside click to close
      setTimeout(()=>{ try{ document.addEventListener('click', onDocClick, true); }catch(_e){} }, 0);
      return pop;
    }

    function showList(anchorEl, title, rows, opts){
      const wrap = document.createElement('div');
      if(title){
        const h = document.createElement('h4');
        h.textContent = String(title);
        h.style.margin = '0 0 6px 0';
        wrap.appendChild(h);
      }
      (rows||[]).forEach(r=>{
        const line = document.createElement('div');
        if(r && typeof r === 'object' && 'text' in r){
          line.textContent = r.text;
          if(r.severity){ try{ line.classList.add(r.severity); }catch(_e){} }
        } else {
          line.textContent = String(r);
        }
        wrap.appendChild(line);
      });
      return show(anchorEl, wrap, Object.assign({ className: 'popup-list' }, opts || {}));
    }

    function isOpenOn(el){ return !!activeEl && activeAnchor === el; }

    return { show, showList, close, isOpenOn };
  })();
})();