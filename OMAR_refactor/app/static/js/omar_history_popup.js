(function(){
  function bindOmarPopup(){
    try{
      var title = document.querySelector('.global-top-bar .left-controls .header-title') || document.querySelector('.header-title');
      if(!title || title._omarPopupBound) return;
      title._omarPopupBound = true;
      try{ title.style.cursor = 'pointer'; }catch(_e){}
      title.addEventListener('click', function(e){
        try{ if(e){ e.preventDefault(); e.stopPropagation(); } }catch(_e){}
        var wrap = document.createElement('div');
        wrap.style.maxWidth = '560px';
        wrap.style.lineHeight = '1.45';
        var img = document.createElement('img');
        img.src = '/static/images/magnusson_bradley_hawley.webp';
        img.alt = 'Dr. Paul Magnuson, General Omar Bradley, and Dr. Paul Hawley';
        img.style.width = '100%';
        img.style.borderRadius = '8px';
        img.style.marginBottom = '8px';
        img.style.border = '1px solid #e5e7eb';
  var p = document.createElement('p');
        p.style.margin = '0';
  p.style.fontSize = '14px';
        p.style.color = '#111827';
        p.textContent = 'General Omar Bradley, known as the “Soldier’s General” for his steadfast, humane leadership in WWII, brought those same values to his role as the first Administrator of the post‑war Veterans Administration in 1945. Working with medical directors Dr. Paul Hawley and Dr. Paul Magnuson (pictured above), he led a radical transformation of the VA—rapidly expanding to meet the needs of a generation of returning service members, forging deep partnerships with medical schools nationwide, and embedding teaching and research into the VA’s mission. Their work established a lasting legacy of excellence that continues to shape veteran care today.';
        var link = document.createElement('a');
        link.href = 'https://department.va.gov/history/featured-stories/omar-bradley/';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Read more at VA History';
        link.style.display = 'inline-block';
        link.style.marginTop = '6px';
        link.style.color = 'var(--color-primary, #1976d2)';
        link.addEventListener('click', function(ev){ ev.stopPropagation(); });
        wrap.appendChild(img);
        wrap.appendChild(p);
        wrap.appendChild(link);
        if(window.Popups && typeof window.Popups.show === 'function'){
          window.Popups.show(title, wrap, { maxWidth: '560px', fontSize: '14px' });
        } else {
          window.open('https://department.va.gov/history/featured-stories/omar-bradley/', '_blank');
        }
      });
    }catch(_e){}
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', bindOmarPopup);
  } else {
    bindOmarPopup();
  }
})();
