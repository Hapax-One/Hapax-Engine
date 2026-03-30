/** @odoo-module **/

import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

function syncListShellBranding(controlPanel) {
    if (controlPanel.env.config.viewType !== "list" || !controlPanel.root.el) {
        return;
    }

    const controlPanelEl = controlPanel.root.el;
    const actionEl = controlPanelEl.parentElement;
    const rootStyles = getComputedStyle(document.documentElement);
    const brandColor =
        rootStyles.getPropertyValue("--intellibus-brand-color").trim() || "#71639e";
    const brandRgb =
        rootStyles.getPropertyValue("--intellibus-brand-rgb").trim() || "113 99 158";

    controlPanelEl.classList.add("intellibus-list-control-panel");
    controlPanelEl.style.setProperty("--intellibus-brand-color", brandColor);
    controlPanelEl.style.setProperty("--intellibus-brand-rgb", brandRgb);

    if (actionEl) {
        actionEl.classList.add("intellibus-list-action-shell");
        actionEl.style.setProperty("--intellibus-brand-color", brandColor);
        actionEl.style.setProperty("--intellibus-brand-rgb", brandRgb);
    }
}

function teardownListShellBranding(controlPanel) {
    const controlPanelEl = controlPanel.root.el;
    const actionEl = controlPanelEl?.parentElement;

    controlPanelEl?.classList.remove("intellibus-list-control-panel");
    controlPanelEl?.style.removeProperty("--intellibus-brand-color");
    controlPanelEl?.style.removeProperty("--intellibus-brand-rgb");

    actionEl?.classList.remove("intellibus-list-action-shell");
    actionEl?.style.removeProperty("--intellibus-brand-color");
    actionEl?.style.removeProperty("--intellibus-brand-rgb");
}

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(() => syncListShellBranding(this));
        onPatched(() => syncListShellBranding(this));
        onWillUnmount(() => teardownListShellBranding(this));
    },
});
