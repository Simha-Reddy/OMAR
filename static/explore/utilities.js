// Shared utility helpers for Explore page (ES Module)

export function debounce(fn, delay = 350) { 
    let t; 
    return function(...args){ 
        clearTimeout(t); 
        t = setTimeout(()=>fn.apply(this,args), delay); 
    }; 
}

export function escapeHtml(text = '') { 
    return String(text).replace(/[&<>"']/g, m => ({
        '&':'&amp;',
        '<':'&lt;',
        '>':'&gt;',
        '"':'&quot;',
        '\'':'&#39;'
    }[m])); 
}

export function escapeRegExp(str = '') { 
    return String(str).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); 
}

export function chunkId(section = '', page = '') { 
    return `chunk-${section.replace(/[^a-zA-Z0-9]/g,'')}-${page}`; 
}

export function safeGetEl(id){ 
    return document.getElementById(id); 
}

export function ensureSpinnerFn(){ 
    if(!window.showThinkingSpinner){ 
        window.showThinkingSpinner = ()=>'<em>Thinking...</em>'; 
    } 
}

export function logWarn(...a){ 
    console.warn('[Explore]', ...a); 
}

export function logInfo(...a){ 
    console.log('[Explore]', ...a); 
}