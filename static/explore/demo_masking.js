// Demo masking utilities for privacy protection during demonstrations

class DemoMasking {
    constructor() {
        this.enabled = false;
        this.init();
    }
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setupToggle());
        } else {
            this.setupToggle();
        }
    }

    setupToggle() {
        // Initialize toggle state from localStorage
        const savedState = localStorage.getItem('demoMode');
        this.enabled = savedState === 'true';
        
        // Set up toggle
        const toggle = document.getElementById('demoToggle');
        if (toggle) {
            toggle.checked = this.enabled;
            toggle.addEventListener('change', (e) => {
                this.enabled = e.target.checked;
                localStorage.setItem('demoMode', this.enabled.toString());
                this.applyMasking();
                
                // Trigger refresh of patient display
                if (window.updatePatientNameDisplay) {
                    window.updatePatientNameDisplay();
                }
            });
        }

        // Apply initial masking if enabled
        if (this.enabled) {
            this.applyMasking();
        }
    }

    /**
     * Mask a string showing only first 2 characters + 6 asterisks
     * @param {string} text - Text to mask
     * @returns {string} - Masked text
     */
    maskText(text) {
        if (!this.enabled || !text || typeof text !== 'string') {
            return text;
        }
        
        const trimmed = text.trim();
        if (trimmed.length <= 2) {
            return trimmed;
        }
        
        return trimmed.substring(0, 2) + '******';
    }

    /**
     * Mask names (handles formats like "First Last", "LAST,FIRST", etc.)
     * @param {string} name - Name to mask
     * @returns {string} - Masked name
     */
    maskName(name) {
        if (!this.enabled || !name || typeof name !== 'string') {
            return name;
        }

        const trimmed = name.trim();
        if (trimmed.length <= 2) {
            return trimmed;
        }

        // For comma-separated names like "LAST,FIRST"
        if (trimmed.includes(',')) {
            return trimmed.substring(0, 2) + '******';
        }

        // For space-separated names like "First Last"
        if (trimmed.includes(' ')) {
            return trimmed.substring(0, 2) + '******';
        }

        // Single name
        return trimmed.substring(0, 2) + '******';
    }

    /**
     * Mask dates (handles formats like "8-28-25", "08/28/2025", etc.)
     * @param {string} date - Date to mask
     * @returns {string} - Masked date
     */
    maskDate(date) {
        if (!this.enabled || !date || typeof date !== 'string') {
            return date;
        }

        const trimmed = date.trim();
        if (trimmed.length <= 2) {
            return trimmed;
        }

        return trimmed.substring(0, 2) + '******';
    }

    /**
     * Legacy: Mask input field value as user types (kept for compatibility but unused for patient search)
     * @param {HTMLInputElement} input - Input element
     */
    maskInputField(input) {
        if (!this.enabled || !input) {
            return;
        }

        const originalValue = input.value;
        if (originalValue && originalValue.length > 2) {
            const maskedValue = originalValue.substring(0, 2) + '******';
            if (input.value !== maskedValue) {
                input.value = maskedValue;
                // Store original for potential unmasking
                input.dataset.originalValue = originalValue;
            }
        }
    }

    /**
     * Conceal an input's characters visually without changing its value
     * Switches input type to password while preserving original type
     * @param {HTMLInputElement} input
     */
    concealInput(input) {
        if (!input) return;
        if (this.enabled) {
            if (!input.dataset.originalType) {
                input.dataset.originalType = input.type || 'text';
            }
            // Only switch to password if not already
            if (input.type !== 'password') {
                try { input.type = 'password'; } catch(_e) {}
                // Also disable autocomplete display
                try { input.setAttribute('autocomplete', 'off'); } catch(_e) {}
            }
        } else {
            // Restore original type
            if (input.dataset.originalType && input.type !== input.dataset.originalType) {
                try { input.type = input.dataset.originalType; } catch(_e) {}
            } else if (!input.dataset.originalType && input.type !== 'text') {
                try { input.type = 'text'; } catch(_e) {}
            }
        }
    }

    /**
     * Apply masking to all relevant elements on the page
     */
    applyMasking() {
        if (!this.enabled) {
            // If disabled, restore original values
            this.restoreOriginalValues();
            return;
        }

        // Mask patient name in top bar
        const patientDisplay = document.getElementById('patientLookupResults');
        if (patientDisplay && patientDisplay.textContent) {
            if (!patientDisplay.dataset.originalText) {
                patientDisplay.dataset.originalText = patientDisplay.textContent;
            }
            patientDisplay.textContent = this.maskName(patientDisplay.dataset.originalText);
        }

        // Conceal patient search input (do not alter its value)
        const searchInput = document.getElementById('patientSearchInput');
        if (searchInput) {
            this.concealInput(searchInput);
        }

        // Mask any existing dropdown items
        this.maskDropdownItems();

        // Mask notes QA content
        this.maskNotesContent();

        // Mask other patient info displays
        this.maskPatientInfo();
    }

    /**
     * Restore original values when demo mode is disabled
     */
    restoreOriginalValues() {
        // Restore patient name in top bar
        const patientDisplay = document.getElementById('patientLookupResults');
        if (patientDisplay && patientDisplay.dataset.originalText) {
            patientDisplay.textContent = patientDisplay.dataset.originalText;
        }

        // Restore search input value and type
        const searchInput = document.getElementById('patientSearchInput');
        if (searchInput) {
            if (searchInput.dataset.originalValue) {
                searchInput.value = searchInput.dataset.originalValue;
                delete searchInput.dataset.originalValue;
            }
            if (searchInput.dataset.originalType) {
                try { searchInput.type = searchInput.dataset.originalType; } catch(_e) {}
                delete searchInput.dataset.originalType;
            } else {
                try { searchInput.type = 'text'; } catch(_e) {}
            }
        }

        // Clear stored original values
        document.querySelectorAll('[data-original-text]').forEach(el => {
            if (el.dataset.originalText) {
                el.textContent = el.dataset.originalText;
                delete el.dataset.originalText;
            }
        });
    }

    /**
     * Mask dropdown items in patient search
     */
    maskDropdownItems() {
        const dropdown = document.querySelector('.patient-dropdown');
        if (!dropdown) return;

        dropdown.querySelectorAll('div').forEach(item => {
            if (!item.dataset.originalText && item.textContent) {
                item.dataset.originalText = item.textContent;
            }
            if (item.dataset.originalText) {
                // Mask the name part but preserve DFN format
                const text = item.dataset.originalText;
                const dfnMatch = text.match(/\(DFN: \d+\)$/);
                const namepart = text.replace(/\s*\(DFN: \d+\)$/, '');
                const maskedName = this.maskName(namepart);
                item.textContent = maskedName + (dfnMatch ? ' ' + dfnMatch[0] : '');
            }
        });
    }

    /**
     * Mask content in notes QA answers
     */
    maskNotesContent() {
        const answerBox = document.getElementById('notesAnswerBox');
        if (answerBox) {
            this.maskElementContent(answerBox);
        }

        const exploreAnswer = document.getElementById('exploreGptAnswer');
        if (exploreAnswer) {
            this.maskElementContent(exploreAnswer);
        }
    }

    /**
     * Mask patient info displays
     */
    maskPatientInfo() {
        // Mask any patient info in demographics
        const demoContent = document.getElementById('patientDemoContent');
        if (demoContent) {
            this.maskElementContent(demoContent);
        }

        // Mask table content
        this.maskTableContent();
    }

    /**
     * Mask content in tables (medications, labs, etc.)
     */
    maskTableContent() {
        // This will be called whenever tables are rendered
        // The actual masking will be applied in the table renderers
    }

    /**
     * Recursively mask text content in an element
     * @param {HTMLElement} element - Element to mask
     */
    maskElementContent(element) {
        if (!element) return;

        // Store original HTML if not already stored
        if (!element.dataset.originalHtml) {
            element.dataset.originalHtml = element.innerHTML;
        }

        if (this.enabled) {
            // Apply masking to the stored original content
            let html = element.dataset.originalHtml;
            
            // Simple regex-based masking for common patterns
            // Names (word boundaries, proper case)
            html = html.replace(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g, (match) => this.maskName(match));
            
            // Names (all caps with comma)
            html = html.replace(/\b[A-Z]+,[A-Z]+\b/g, (match) => this.maskName(match));
            
            // Dates (various formats)
            html = html.replace(/\b\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}\b/g, (match) => this.maskDate(match));
            html = html.replace(/\b\d{1,2}\/\d{1,2}\/\d{4}\b/g, (match) => this.maskDate(match));
            
            element.innerHTML = html;
        } else {
            // Restore original content
            element.innerHTML = element.dataset.originalHtml;
        }
    }

    /**
     * Mask a string for use in API responses (like notes_qa)
     * @param {string} text - Text to mask
     * @returns {string} - Masked text
     */
    maskApiResponse(text) {
        if (!this.enabled || !text || typeof text !== 'string') {
            return text;
        }

        let masked = text;
        
        // Names (proper case)
        masked = masked.replace(/\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b/g, (match) => this.maskName(match));
        
        // Names (all caps with comma)
        masked = masked.replace(/\b[A-Z]+,[A-Z]+\b/g, (match) => this.maskName(match));
        
        // Dates
        masked = masked.replace(/\b\d{1,2}[-\/]\d{1,2}[-\/]\d{2,4}\b/g, (match) => this.maskDate(match));
        masked = masked.replace(/\b\d{1,2}\/\d{1,2}\/\d{4}\b/g, (match) => this.maskDate(match));
        
        return masked;
    }
}

// Create global instance
window.demoMasking = new DemoMasking();

// Export for use in other modules
export default window.demoMasking;
