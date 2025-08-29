(function(){
  function log(msg){ try{ window.AgentDebug && window.AgentDebug.log && window.AgentDebug.log(msg); }catch(_){} }
  function safeScriptContent(s){ return String(s==null?'':s).replace(/<\/?script/gi, function(m){ return m.replace(/<\//, '<\\/'); }); }

  function run(opts){
    const { code, datasets, mount, timeoutMs = 2000, minimal = false, forceEval = false } = (opts||{});
    return new Promise(function(resolve){
      if(!mount){ resolve({ ok:false, error:'Missing mount container' }); return; }
      mount.innerHTML = '';
      var token = Math.random().toString(36).slice(2) + String(Date.now());
      var iframe = document.createElement('iframe');
      var sandboxFlags = 'allow-scripts';
      try { if (window.SANDBOX_DEBUG) { sandboxFlags = 'allow-scripts allow-same-origin'; log('Sandbox DEBUG: using allow-same-origin for diagnostics'); } } catch(_){ }
      iframe.setAttribute('sandbox', sandboxFlags);
      iframe.style.width = '100%'; iframe.style.border = '0';

      var lastEvent = 'none'; var done = false; var timer = null;
      function finish(result){
        if(done) return; done = true;
        try{ if(timer) clearTimeout(timer);}catch(_){ }
        try{
          // On success keep iframe and listener so post-render events (like open-document) work
          var shouldRemoveIframe = !(result && result.ok === true);
          if(iframe && shouldRemoveIframe){ mount.removeChild(iframe); }
        }catch(_){ }
        // Only remove the message listener on failure; keep it alive on success to handle clicks
        try{ if(!(result && result.ok === true)) { window.removeEventListener('message', onMsg); } }catch(_){ }
        resolve(result);
      }
      function armTimeout(ms){ try{ if(timer) clearTimeout(timer);}catch(_){ } var d = Math.max(250, (ms|0)); log('Sandbox timeout set: '+d+'ms'); timer = setTimeout(function(){ finish({ ok:false, error:'Render timeout (last event: '+lastEvent+')' }); }, d); }
      function onMsg(e){ var d = e && e.data || {}; if(!d || d.__sandbox !== token) return; if(d.type==='boot-started'){ lastEvent='boot-started'; log('Sandbox: boot-started'); }
        else if(d.type==='render-started'){ lastEvent='render-started'; log('Sandbox: render-started'); armTimeout((timeoutMs|0)+4000); }
        else if(d.type==='render-done'){ lastEvent='render-done'; log('Sandbox: render-done'); finish({ ok:true }); }
        else if(d.type==='render-error'){ lastEvent='render-error'; var err = d.error || 'Unknown error'; log('Sandbox: render-error: '+err); finish({ ok:false, error: err }); }
        else if(d.type==='console-log'){ try{ var a=d.args||[]; log('[Sandbox] '+a.map(function(x){return String(x);}).join(' ')); }catch(_){ } }
        else if(d.type==='agent-open-document'){
          lastEvent='agent-open-document';
          try{ log('Sandbox: agent-open-document docId='+(d.docId||'')); }catch(_){ }
          try{
            var payload = { docId: d.docId, excerptText: d.excerptText };
            if(typeof window.AgentOpenDocument === 'function'){ window.AgentOpenDocument(payload); }
            else if(typeof window.openDocument === 'function'){ window.openDocument(payload); }
            else { log('No AgentOpenDocument or openDocument handler on host'); }
          }catch(_){ }
        }
      }
      window.addEventListener('message', onMsg);

      var datasetsJson = JSON.stringify(datasets || {});
      var codeText = String(code || '');

      // Child script content
      var childJs = '';
      if(minimal){
        childJs = ''+
          '(function(){\n'+
          '  var TOKEN = '+JSON.stringify(token)+';\n'+
          '  try {\n'+
          '    try{ parent.postMessage({ type:\'boot-started\', __sandbox: TOKEN }, \'*\'); }catch(_){ }\n'+
          '    try{\n'+
          '      window.addEventListener(\'error\', function(ev){ try{ var m = ev && ev.message ? ev.message : String(ev); parent.postMessage({ type:\'render-error\', error: "syntax-error: "+ m, __sandbox: TOKEN }, "*"); }catch(_){ } });\n'+
          '      window.addEventListener(\'unhandledrejection\', function(ev){ try{ parent.postMessage({ type:\'render-error\', error: "unhandledrejection: "+ String(ev&&ev.reason||\'\') , __sandbox: TOKEN }, "*"); }catch(_){ } });\n'+
          '    }catch(_){ }\n'+
          '    try{ var c = document.getElementById(\'container\'); parent.postMessage({ type:\'render-started\', __sandbox: TOKEN }, "*"); var el=document.createElement(\'div\'); el.style.padding=\'8px\'; el.style.background=\'#e6f7ff\'; el.textContent=\'Hello Sandbox!\'; c.appendChild(el); parent.postMessage({ type:\'render-done\', __sandbox: TOKEN }, "*"); } catch (eRun) { parent.postMessage({ type:\'render-error\', error:String(eRun), __sandbox: TOKEN }, "*"); }\n'+
          '  } catch (e) { try{ parent.postMessage({ type:\'render-error\', error:String(e), __sandbox: TOKEN }, "*"); }catch(_){ } }\n'+
          '})();\n';
      } else {
        // Replace full-mode childJs with a more diagnostic-rich version
        childJs = ''+
          '(function(){\n'+
          '  var TOKEN = '+JSON.stringify(token)+';\n'+
          '  try {\n'+
          '    function blocked(name){ return function(){ throw new Error(name+" blocked"); }; }\n'+
          '    try{ Object.defineProperty(window, "top", { get:function(){ throw new Error("window.top blocked"); } }); }catch(_){ }\n'+
          '    try{\n'+
          '      var _log = console.log, _err = console.error;\n'+
          '      console.log = function(){ try{ parent.postMessage({ type:\'console-log\', args: Array.prototype.slice.call(arguments), __sandbox: TOKEN }, "*"); }catch(_){ } try{ _log.apply(console, arguments); }catch(_){ } };\n'+
          '      console.error = function(){ try{ parent.postMessage({ type:\'console-log\', args: [\'[error]\'].concat(Array.prototype.slice.call(arguments)), __sandbox: TOKEN }, "*"); }catch(_){ } try{ _err.apply(console, arguments); }catch(_){ } };\n'+
          '      window.addEventListener(\'error\', function(ev){ try{ var msg = ev && ev.error && ev.error.stack ? ev.error.stack : (ev && ev.message ? ev.message : String(ev)); parent.postMessage({ type:\'render-error\', error: "uncaught: "+ msg, __sandbox: TOKEN }, "*"); }catch(_){ } });\n'+
          '      window.addEventListener(\'unhandledrejection\', function(ev){ try{ var reason = ev && ev.reason ? (ev.reason.stack || String(ev.reason)) : ""; parent.postMessage({ type:\'render-error\', error: "unhandledrejection: "+ String(reason), __sandbox: TOKEN }, "*"); }catch(_){ } });\n'+
          '    }catch(_){ }\n'+
          '    var DATA = {}; try{ DATA = JSON.parse(document.getElementById(\'datasets-json\').textContent || "{}"); }catch(_){ }\n'+
          '    // Sanitize datasets: filter null/undefined in arrays\n'+
          '    function sanitizeShallow(v){ if(Array.isArray(v)) return v.filter(function(x){ return x!=null; }); if(v && typeof v==="object"){ var o={}; for(var k in v){ if(Object.prototype.hasOwnProperty.call(v,k)){ var val=v[k]; o[k]=Array.isArray(val)? val.filter(function(x){ return x!=null; }) : val; } } return o; } return v; }\n'+
          '    var DATA_SAFE = sanitizeShallow(DATA);\n'+
          '    try{ var sz={}; if(DATA && typeof DATA===\'object\'){ for(var k in DATA){ if(Object.prototype.hasOwnProperty.call(DATA,k)){ var v=DATA[k]; var n = Array.isArray(v)? v.length : (v && typeof v===\'object\' && typeof v.length===\'number\' ? v.length : (v?1:0)); sz[k]=n; } } parent.postMessage({ type:\'console-log\', args:[\'dataset sizes\', JSON.stringify(sz)], __sandbox: TOKEN }, "*"); } }catch(_){ }\n'+
          '    var CODE = document.getElementById(\'code-js\').textContent || "";\n'+
          '    try{ if(CODE && CODE.charCodeAt && CODE.charCodeAt(0)===0xFEFF){ CODE = CODE.slice(1); } }catch(_){ }\n'+
          '    try{ var prev = String(CODE).slice(0,240).replace(/[\\r\\n\\t]/g,function(m){return m===\'\\n\'?\'\\n\':(m===\'\\r\'?\'\\r\':\'\\t\');}); parent.postMessage({ type:\'console-log\', args:[\'codeLen=\', (CODE?CODE.length:0), "preview:", prev], __sandbox: TOKEN }, "*"); }catch(_){ }\n'+
          '    try{ new Function("\\\"use strict\\\";\\n"+CODE); } catch(ePrep){ parent.postMessage({ type:\'render-error\', error: "preparse: "+ String(ePrep), __sandbox: TOKEN }, "*"); return; }\n'+
          '    var renderFn = null;\n'+
          '    try { renderFn = (0, eval)("(function(){\\n" + CODE + "\\n;return (typeof render===\\\"function\\\"? render : (typeof window!==\\\"undefined\\\" && typeof window.render===\\\"function\\\"? window.render : null));})()" ); }\n'+
          '    catch (eEval) { parent.postMessage({ type:\'render-error\', error: (eEval && eEval.stack ? "eval user code: "+eEval.stack : "eval user code: "+ String(eEval)), __sandbox: TOKEN }, "*"); return; }\n'+
          '    try{ parent.postMessage({ type:\'console-log\', args:[\'typeof renderFn=\', typeof renderFn], __sandbox: TOKEN }, "*"); }catch(_){ }\n'+
          '    if(typeof renderFn !== "function"){ parent.postMessage({ type:\'render-error\', error: "render is not a function" , __sandbox: TOKEN }, "*"); return; }\n'+
          '    // Helpers expected by user code\n'+
          '    var Tabulator = { createTable: function(container, rows){ try{ container.innerHTML=\'\'; var table=document.createElement(\'table\'); table.style.borderCollapse=\'collapse\'; table.style.width=\'100%\'; if(Array.isArray(rows) && rows.length){ var thead=document.createElement(\'thead\'); var tr=document.createElement(\'tr\'); var cols=Object.keys(rows[0]); cols.forEach(function(k){ var th=document.createElement(\'th\'); th.textContent=k; th.style.border=\'1px solid #ddd\'; th.style.padding=\'4px\'; tr.appendChild(th); }); thead.appendChild(tr); table.appendChild(thead); var tbody=document.createElement(\'tbody\'); rows.forEach(function(r){ var tr=document.createElement(\'tr\'); cols.forEach(function(k){ var td=document.createElement(\'td\'); td.textContent=(r[k]===undefined?\'\':String(r[k])); td.style.border=\'1px solid #eee\'; td.style.padding=\'4px\'; tr.appendChild(td); }); tbody.appendChild(tr); }); table.appendChild(tbody); } container.appendChild(table); }catch(_){} } };\n'+
          '    var SimplePlots = { line: function(container, points){ try{ container.innerHTML=\'\'; var canvas=document.createElement(\'canvas\'); canvas.width=Math.max(300, container.clientWidth||600); canvas.height=220; var ctx=canvas.getContext(\'2d\'); ctx.strokeStyle=\'#2a6\'; ctx.lineWidth=2; points=Array.isArray(points)?points:[]; if(points.length<2){ container.textContent=\'Not enough data to plot\'; return; } var xs=points.map(function(p){ return +new Date(p && (p.x||p.date||p[0])); }); var ys=points.map(function(p){ return (p && ((+p.y)||(+p.value)||(+p[1])))||0; }); var xmin=Math.min.apply(null,xs), xmax=Math.max.apply(null,xs), ymin=Math.min.apply(null,ys), ymax=Math.max.apply(null,ys); ctx.beginPath(); for(var i=0;i<points.length;i++){ var p=points[i]||{}; var x=((+new Date(p.x||p.date||p[0]) - xmin)/(xmax - xmin || 1))*(canvas.width - 20) + 10; var y=canvas.height - 10 - (((+p.y||+p.value||+p[1]) - ymin)/(ymax - ymin || 1))*(canvas.height - 20); if(i===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);} ctx.stroke(); container.appendChild(canvas); }catch(e){ try{ parent.postMessage({ type:\'render-error\', error: String(e), __sandbox: TOKEN }, "*"); }catch(_){ } } } };\n'+
          '    var Formatter = { date: function(s){ try{ return s? new Date(s).toLocaleString(): ""; }catch(e){ return String(s||\'\'); } }, unit: function(v,u){ return (v!==undefined && u)? (v+\' \'+u) : String((v===undefined||v===null)?\'\':v); } };\n'+
          '    try{ var container=document.getElementById(\'container\'); parent.postMessage({ type:\'render-started\', __sandbox: TOKEN }, "*"); renderFn({ datasets: DATA_SAFE, container: container, Tabulator: Tabulator, SimplePlots: SimplePlots, Formatter: Formatter }); parent.postMessage({ type:\'render-done\', __sandbox: TOKEN }, "*"); } catch (e3) { var msg=(e3&&e3.stack)?e3.stack:String(e3); parent.postMessage({ type:\'render-error\', error: msg, __sandbox: TOKEN }, "*"); }\n'+
          '    // Delegate click handler for citation links\n'+
          '    try{ document.addEventListener(\'click\', function(ev){ try{ var t=ev.target; if(!t) return; var a=t.closest ? t.closest(\'a.agent-citation\') : null; if(!a) return; var ds=a.dataset||{}; var docId = ds.docId || ds.noteId; if(!docId) return; ev.preventDefault(); var ex = ds.excerpt || ds.excerptText || ""; parent.postMessage({ type: "agent-open-document", docId: docId, excerptText: ex, __sandbox: TOKEN }, "*"); }catch(_){ } }, true); }catch(_){ }\n'+
          '  } catch (e4) { try { parent.postMessage({ type:\'render-error\', error: (e4&&e4.stack)?e4.stack:String(e4), __sandbox: TOKEN }, "*"); } catch (e5) { } }\n'+
          '})();\n';
      }

      // Loader: raw or eval
      var childB64 = null; try { childB64 = btoa(unescape(encodeURIComponent(childJs))); } catch (e) { log('Sandbox: b64 encode failed: '+String(e)); childB64 = null; }
      var preferRaw = false; try { preferRaw = !!window.SANDBOX_DEBUG && !forceEval; } catch(_){ }
      var loaderScript = '';
      if (childB64 && !preferRaw) {
        loaderScript = ''+
          '(function(){var T='+JSON.stringify(token)+';try{parent.postMessage({type:\'boot-started\',__sandbox:T},\'*\');var _raw=atob('+JSON.stringify(childB64)+');var _utf;try{_utf=decodeURIComponent(escape(_raw));}catch(e){_utf=_raw;}try{eval(_utf);}catch(e2){try{parent.postMessage({type:\'render-error\',error:\'boot-eval failed: \'+String(e2),__sandbox:T},\'*\');parent.postMessage({type:\'console-log\',args:[\'decoded preview:\',String(_utf).slice(0,240)],__sandbox:T},\'*\');}catch(_){}}}catch(e){try{parent.postMessage({type:\'render-error\',error:\'boot-decode failed: \'+String(e),__sandbox:T},\'*\');}catch(_){}}})();';
      } else {
        loaderScript = ''+
          '(function(){var T='+JSON.stringify(token)+';try{parent.postMessage({type:\'boot-started\',__sandbox:T},\'*\');}catch(_){}})();';
      }

      var prebootScript = ''+
        '(function(){var T='+JSON.stringify(token)+';try{window.__SANDBOX_TOKEN=T;window.addEventListener(\'error\',function(ev){try{var m=ev&&ev.message?ev.message:String(ev);parent.postMessage({type:\'render-error\',error:\'syntax-error: \'+m,__sandbox:T},\'*\');}catch(_){ }},true);window.addEventListener(\'unhandledrejection\',function(ev){try{var r=ev&&ev.reason?ev.reason:\'\';parent.postMessage({type:\'render-error\',error:\'unhandledrejection(preload): \'+String(r),__sandbox:T},\'*\');}catch(_){ }},true);}catch(_){ }})();';

      var html = ''+
        '<!doctype html><html><head><meta charset="utf-8">'+
        '<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;}</style>'+
        '</head><body>'+
        '<div id="container"></div>'+
        '<script id="datasets-json" type="application/json">'+ safeScriptContent(datasetsJson) +'</script>'+
        '<script id="code-js" type="text/plain">'+ safeScriptContent(codeText) +'</script>'+
        '<script>'+ prebootScript +'</script>'+
        '<script>'+ loaderScript +'</script>'+
        (preferRaw ? ('<script>'+ childJs.replace(/<\//g,'<\\/') +'</script>') : '')+
        '</body></html>';

      log('Mounting sandbox iframe');
      iframe.srcdoc = html; mount.appendChild(iframe);

      // Diagnostics: list scripts in iframe (debug only)
      try{ if(window.SANDBOX_DEBUG){ setTimeout(function(){ try{ var doc=iframe.contentDocument; if(!doc) return; var ss=doc.getElementsByTagName('script'); log('Sandbox diag: scripts='+ss.length); for(var i=0;i<ss.length;i++){ var sc=ss[i]; var t=(sc.getAttribute('type')||'').toLowerCase(); var txt=''; try{ txt = sc.textContent || ''; }catch(_){ } var prev=(txt||'').slice(0,160).replace(/[\r\n\t]/g,function(m){return m==='\n'?'\\n':(m==='\r'?'\\r':'\\t');}); log('script['+i+'] type='+(t||'')+' len='+(txt?txt.length:0)+' prev="'+prev+'"'); } }catch(_){ } }, 0); } }catch(_){ }

      try { setTimeout(function(){ try{ iframe.contentWindow && iframe.contentWindow.postMessage({ type:'ping', __sandbox: token }, '*'); log('Sandbox ping sent'); }catch(_){ } }, 0); } catch(_){ }
      armTimeout(Math.max(250, timeoutMs|0));
    });
  }

  window.AgentSandboxRunner = { run };
})();