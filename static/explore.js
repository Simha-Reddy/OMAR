// Lightweight bridge replacing previous monolithic explore.js
// The full implementation has been modularized under /static/explore/*.js
// This file is kept for backward compatibility. It dynamically injects the new ES module bundle.
(function(){
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', inject, {once:true});
  } else { inject(); }
  function inject(){
    // Avoid double injection
    if(document.querySelector('script[data-explore-entry]')) return;
    const s = document.createElement('script');
    s.type = 'module';
  // Cache-bust to ensure latest module code is loaded
  const v = Date.now();
  s.src = '/static/explore/index.js?v=' + v;
    s.dataset.exploreEntry = '1';
    document.head.appendChild(s);
  }
})();