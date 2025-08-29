// Central shared state for Explore page (ES Module)

export const exploreState = {
  moduleRunControllers: new Map(),
  savingSession: false,
  pendingSessionSave: false,
  chartPages: [],
  chartPageSections: [],
  chartChunks: [],
  currentModalPage: 0,
  highlightSection: null,
  keywordHighlight: '',
  exploreQAHistory: []
};

export function setChartParsing({pages, sections}){ exploreState.chartPages = pages; exploreState.chartPageSections = sections; }
export function setChartChunks(chunks){ exploreState.chartChunks = Array.isArray(chunks)?chunks:[]; }

// --- Simple Event Bus for Explore ---
const listeners = new Map(); // event -> Set<fn>

export const EVENTS = {
  OPEN_DOCUMENT: 'open-document',
};

export function on(event, handler){
  if(!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(handler);
}

export function off(event, handler){
  const set = listeners.get(event);
  if(set){ set.delete(handler); if(set.size === 0) listeners.delete(event); }
}

export function emit(event, payload){
  const set = listeners.get(event);
  if(set){
    for(const fn of Array.from(set)){
      try { fn(payload); } catch(_e){}
    }
  }
}

export function openDocument({ docId, excerptText, excerptIndex } = {}){
  emit(EVENTS.OPEN_DOCUMENT, { docId, excerptText, excerptIndex });
}