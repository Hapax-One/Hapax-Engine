/** @odoo-module **/

import { applyBrandColor } from "@intellibus_theme/js/branding";
import { SettingsPage } from "@web/webclient/settings_form_view/settings/settings_page";
import { onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
/* global lucide */

const slugify = (value) =>
    (value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");

patch(SettingsPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.intellibusNav = useState({
            blocks: [],
            selectedBlockKey: "",
        });
        this.intellibusPage = useState({
            title: "",
            subtitle: "",
        });
        this.intellibusBlockSignature = "";
        this.intellibusBlockElements = new Map();
        this.intellibusBrandingInput = null;
        this.intellibusBrandingInputListener = null;
        this.moduleIconMap = {
            general: "chart-column-big",
            inventory: "layers-3",
            discuss: "message-square",
            website: "globe",
            sale: "shopping-cart",
            sales: "shopping-cart",
            accounting: "landmark",
            account: "landmark",
            contacts: "book-user",
            users: "users",
            employees: "users",
            project: "clipboard-list",
            purchase: "shopping-bag",
            apps: "layout-grid",
            settings: "settings-2",
        };

        const syncBlocks = () => {
            const nextState = this._getCurrentAppState();
            const nextSignature = nextState.blocks
                .map((block) => `${block.key}:${block.title}:${block.tip}`)
                .join("|");

            if (nextSignature !== this.intellibusBlockSignature) {
                this.intellibusBlockSignature = nextSignature;
                this.intellibusNav.blocks = nextState.blocks;
            }

            const hasSelectedBlock = nextState.blocks.some(
                (block) => block.key === this.intellibusNav.selectedBlockKey
            );

            if (!hasSelectedBlock) {
                this.intellibusNav.selectedBlockKey = nextState.blocks[0]?.key || "";
            }

            this.intellibusPage.title = nextState.title;
            this.intellibusPage.subtitle = this._getCurrentSubtitle(nextState.blocks);
        };

        onMounted(() => {
            syncBlocks();
            this._applyBlockVisibility();
            this._renderIcons();
            this._syncBrandingPreview();
        });

        onPatched(() => {
            syncBlocks();
            this._applyBlockVisibility();
            this._renderIcons();
            this._syncBrandingPreview();
        });

        onWillUnmount(() => {
            this._teardownBrandingPreview();
        });
    },

    _renderIcons() {
        if (typeof lucide !== "undefined") {
            lucide.createIcons();
        }
    },

    _teardownBrandingPreview() {
        if (this.intellibusBrandingInput && this.intellibusBrandingInputListener) {
            this.intellibusBrandingInput.removeEventListener(
                "input",
                this.intellibusBrandingInputListener
            );
            this.intellibusBrandingInput.removeEventListener(
                "change",
                this.intellibusBrandingInputListener
            );
        }
        this.intellibusBrandingInput = null;
        this.intellibusBrandingInputListener = null;
    },

    _syncBrandingPreview() {
        const brandingInput = this.settingsRef.el?.querySelector(
            "#intellibus_branding input[type='color']"
        );

        if (this.intellibusBrandingInput !== brandingInput) {
            this._teardownBrandingPreview();
            if (brandingInput) {
                this.intellibusBrandingInput = brandingInput;
                this.intellibusBrandingInputListener = (ev) => {
                    applyBrandColor(ev.target.value);
                };
                brandingInput.addEventListener("input", this.intellibusBrandingInputListener);
                brandingInput.addEventListener("change", this.intellibusBrandingInputListener);
            }
        }

        if (brandingInput?.value) {
            applyBrandColor(brandingInput.value);
        }
    },

    _getCurrentAppState() {
        const currentAppEl = this._getCurrentSettingsAppEl();
        const currentModule =
            this.props.modules.find((module) => module.key === this.state.selectedTab) || null;

        this.intellibusBlockElements = new Map();
        const blocks = currentAppEl ? this._getBlocksForCurrentTab(currentAppEl) : [];

        return {
            blocks,
            title: currentModule?.string || "",
        };
    },

    _getBlocksForCurrentTab(currentAppEl) {
        return [
            ...currentAppEl.querySelectorAll(".o_settings_container[data-intellibus-block-title]"),
        ]
            .map((containerEl, index) => {
                const title = containerEl.dataset.intellibusBlockTitle || "";
                const tip = containerEl.dataset.intellibusBlockTip || "";
                const key = `${this.state.selectedTab || "settings"}-${index}`;
                const panelId = `intellibus-settings-section-${slugify(
                    this.state.selectedTab || "settings"
                )}-${index}`;
                const panelEl = this._getBlockPanelEl(currentAppEl, containerEl);
                const elements = this._getBlockElements(currentAppEl, containerEl, panelEl);

                panelEl.id = panelId;
                panelEl.setAttribute("aria-labelledby", `${panelId}-tab`);
                panelEl.setAttribute("role", "region");
                containerEl.dataset.intellibusBlockIndex = String(index);
                this.intellibusBlockElements.set(key, elements);

                return {
                    key,
                    panelId,
                    title,
                    tip,
                };
            });
    },

    _getBlockPanelEl(currentAppEl, containerEl) {
        let panelEl = containerEl;

        while (panelEl.parentElement && panelEl.parentElement !== currentAppEl) {
            panelEl = panelEl.parentElement;
        }

        return panelEl;
    },

    _getBlockElements(currentAppEl, containerEl, panelEl = this._getBlockPanelEl(currentAppEl, containerEl)) {
        if (panelEl !== containerEl) {
            return [panelEl];
        }

        const elements = [containerEl];
        let previousEl = containerEl.previousElementSibling;

        if (previousEl?.tagName === "H3") {
            elements.unshift(previousEl);
            previousEl = previousEl.previousElementSibling;
        }

        if (previousEl?.tagName === "H2") {
            elements.unshift(previousEl);
        }

        return elements.filter(Boolean);
    },

    _getCurrentSubtitle(blocks = this.intellibusNav.blocks) {
        if (this.state.search.value.length) {
            return "";
        }

        const activeBlock =
            blocks.find((block) => block.key === this.intellibusNav.selectedBlockKey) || blocks[0];

        return activeBlock?.tip || blocks.find((block) => block.tip)?.tip || "";
    },

    _getCurrentSettingsAppEl() {
        if (!this.settingsRef || !this.settingsRef.el) {
            return null;
        }

        return (
            [...this.settingsRef.el.querySelectorAll(".app_settings_block")].find(
                (appEl) => appEl.dataset.key === this.state.selectedTab
            ) || null
        );
    },

    _applyBlockVisibility() {
        const blocks = this.intellibusNav.blocks;
        if (!blocks.length) {
            return;
        }

        const showAllBlocks = this.state.search.value.length !== 0;
        if (showAllBlocks) {
            this._toggleAllBlocks(true);
            return;
        }

        const activeBlockKey = this.intellibusNav.selectedBlockKey || blocks[0].key;

        for (const block of blocks) {
            const elements = this.intellibusBlockElements.get(block.key) || [];
            const isVisible = block.key === activeBlockKey;
            this._setBlockVisibility(elements, isVisible);
        }
    },

    _setBlockVisibility(elements, isVisible) {
        for (const element of elements) {
            element.classList.toggle("intellibus-block-hidden", !isVisible);
            element.toggleAttribute("hidden", !isVisible);
        }

        const panelEl = elements[elements.length - 1] || null;
        if (panelEl) {
            panelEl.setAttribute("aria-hidden", isVisible ? "false" : "true");
        }
    },

    _toggleAllBlocks(isVisible) {
        const containerEls =
            this.settingsRef.el?.querySelectorAll(".o_settings_container[data-intellibus-block-title]") ||
            [];

        for (const containerEl of containerEls) {
            const currentAppEl = containerEl.closest(".app_settings_block");
            if (!currentAppEl) {
                continue;
            }

            this._setBlockVisibility(this._getBlockElements(currentAppEl, containerEl), isVisible);
        }
    },

    getModuleIcon(module) {
        const key = `${module?.key || ""} ${module?.string || ""}`.toLowerCase();
        const matchedKey = Object.keys(this.moduleIconMap).find((name) => key.includes(name));
        return matchedKey ? this.moduleIconMap[matchedKey] : "panel-left";
    },

    getModuleChevron(module) {
        return this.state.selectedTab === module.key && this.intellibusNav.blocks.length
            ? "chevron-up"
            : "chevron-down";
    },

    onSettingTabClick(key) {
        super.onSettingTabClick(...arguments);
        this.intellibusNav.selectedBlockKey = "";
    },

    getSettingsAppPanelId(moduleKey) {
        return `intellibus-settings-app-${moduleKey}`;
    },

    onSettingBlockClick(block) {
        this.intellibusNav.selectedBlockKey = block.key;
        this._applyBlockVisibility();
        this.scrollToBlock(block.key);
    },

    scrollToBlock(blockKey) {
        const targetBlock = this.intellibusNav.blocks.find((block) => block.key === blockKey);
        const anchorEl = this.intellibusBlockElements.get(blockKey)?.[0];

        if (!targetBlock || !anchorEl) {
            return;
        }

        anchorEl.scrollIntoView({ behavior: "smooth", block: "start" });
    },
});
