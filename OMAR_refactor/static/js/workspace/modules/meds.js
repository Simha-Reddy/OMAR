// Placeholder for Meds tab
window.WorkspaceModules = window.WorkspaceModules || {};
window.WorkspaceModules['Meds'] = {
  async render(container) {
    container.innerHTML = `<div class="module-placeholder"><h3>Meds</h3><p>This tab is a placeholder.</p></div>`;
  },
  refresh() {
    // No-op for placeholder
  },
  destroy() {
    // No-op for placeholder
  }
};
