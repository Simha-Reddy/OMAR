(function(){
  const BANNED_PATTERNS = [
    /\beval\s*\(/i,
    /\bFunction\s*\(/i,
    /\bimport\s*\(/i,
    /\bfetch\b/i,
    /XMLHttpRequest/i,
    /\bWebSocket\b/i,
    /\bWorker\b/i,
    /SharedArrayBuffer/i,
    /\bpostMessage\s*\(/i,
    /\bsetTimeout\s*\(/i,
    /\bsetInterval\s*\(/i,
    /localStorage/i,
    /sessionStorage/i,
    /indexedDB/i,
    /document\.cookie/i,
    /window\.top/i,
    /window\.parent/i,
    // Inline event handlers in HTML strings, e.g., "<button onclick=\"...\">"
    /<[^>]*\son[a-z0-9_:-]+\s*=/i,
    // Setting on* via setAttribute('onclick', ...)
    /\bsetAttribute\s*\(\s*['"]on[a-z0-9_:-]+['"]\s*,/i
  ];

  function validate(code){
    const errors = [];
    if(typeof code !== 'string' || !code.trim()){
      errors.push('Empty render_code');
      return { ok: false, errors };
    }
    if(code.length > 50000){
      errors.push('Code too large (>50KB)');
    }
    // Must define a function named render
    if(!/function\s+render\s*\(/.test(code)){
      errors.push('Missing function render(...) definition');
    }
    for(const pat of BANNED_PATTERNS){
      const m = code.match(pat);
      if(m){
        const idx = Math.max(0, (m.index||0) - 10);
        const snippet = code.slice(idx, (m.index||0) + (m[0]?.length||0) + 40).replace(/\s+/g,' ');
        errors.push('Banned token: ' + pat + (snippet? (' near: '+ snippet) : ''));
      }
    }
    return { ok: errors.length === 0, errors };
  }

  window.AgentStaticChecks = { validate };
})();