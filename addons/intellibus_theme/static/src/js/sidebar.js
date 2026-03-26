/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { applyCompanyBrandColor } from "@intellibus_theme/js/branding";
import {
    applyColorSchemePreference,
    getColorSchemePreference,
} from "@intellibus_theme/js/color_scheme";
import { browser } from "@web/core/browser/browser";
/* global lucide */

patch(NavBar.prototype, {
    setup() {
        super.setup(...arguments);
        this.companyService = useService("company");
        this.orm = useService("orm");
        this.intellibusState = useState({
            collapsed: false,
            colorSchemePreference: getColorSchemePreference(),
        });
        this.intellibusBrandCompanyId = null;
        this.intellibusColorSchemeMediaQuery = null;
        this.intellibusColorSchemeListener = null;
        this.appIconMap = {
            'Discuss': 'message-square',
            'Inventory': 'package',
            'Apps': 'layout-grid',
            'Settings': 'settings',
            'Sales': 'shopping-cart',
            'CRM': 'users',
            'Accounting': 'landmark',
            'Project': 'clipboard-list',
            'Purchase': 'shopping-bag',
            'Employees': 'user-check',
            'Time Off': 'calendar',
            'Expenses': 'credit-card',
            'Documents': 'file-text',
            'Fleet': 'truck',
            'Point of Sale': 'calculator',
            'Manufacturing': 'factory',
            'Quality': 'badge-check',
            'Maintenance': 'tool',
            'Helpdesk': 'life-buoy',
            'Field Service': 'map-pin',
            'Planning': 'calendar-range',
            'Subscriptions': 'refresh-cw',
            'Events': 'ticket',
            'Surveys': 'file-question',
            'Website': 'globe',
            'Social Marketing': 'share-2',
            'Email Marketing': 'mail',
            'Invoicing': 'receipt',
            'Live Chat': 'message-circle',
            'Knowledge': 'book-open',
            'Approvals': 'check-circle-2',
            'Lunch': 'utensils',
            'Barcodes': 'barcode'
        };
        
        onMounted(() => {
            this._renderIcons();
            this._syncCompanyBranding();
            this._syncColorSchemeWatcher();
        });
        
        onPatched(() => {
            this._renderIcons();
            this._syncCompanyBranding();
            this._syncColorSchemeWatcher();
        });

        onWillUnmount(() => {
            this._teardownColorSchemeWatcher();
        });
    },
    
    _renderIcons() {
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    toggleSidebar() {
        this.intellibusState.collapsed = !this.intellibusState.collapsed;
    },

    switchCompany(companyId) {
        if (companyId !== this.companyService.currentCompany.id) {
            this.intellibusBrandCompanyId = null;
            this.companyService.setCompanies([companyId]);
        }
    },

    _teardownColorSchemeWatcher() {
        if (!this.intellibusColorSchemeMediaQuery || !this.intellibusColorSchemeListener) {
            return;
        }

        if (this.intellibusColorSchemeMediaQuery.removeEventListener) {
            this.intellibusColorSchemeMediaQuery.removeEventListener(
                "change",
                this.intellibusColorSchemeListener
            );
        } else if (this.intellibusColorSchemeMediaQuery.removeListener) {
            this.intellibusColorSchemeMediaQuery.removeListener(this.intellibusColorSchemeListener);
        }

        this.intellibusColorSchemeMediaQuery = null;
        this.intellibusColorSchemeListener = null;
    },

    _syncColorSchemeWatcher() {
        if (this.intellibusState.colorSchemePreference !== "system") {
            this._teardownColorSchemeWatcher();
            return;
        }

        if (
            this.intellibusColorSchemeMediaQuery &&
            this.intellibusColorSchemeListener
        ) {
            return;
        }

        const mediaQuery = browser.matchMedia("(prefers-color-scheme: dark)");
        const listener = () => applyColorSchemePreference("system");

        if (mediaQuery.addEventListener) {
            mediaQuery.addEventListener("change", listener);
        } else if (mediaQuery.addListener) {
            mediaQuery.addListener(listener);
        }

        this.intellibusColorSchemeMediaQuery = mediaQuery;
        this.intellibusColorSchemeListener = listener;
    },

    async _syncCompanyBranding() {
        const companyId = this.companyService.currentCompany?.id;
        if (!companyId || companyId === this.intellibusBrandCompanyId) {
            return;
        }

        this.intellibusBrandCompanyId = companyId;
        await applyCompanyBrandColor(this.orm, companyId);
    },

    getColorSchemeIcon() {
        if (this.intellibusState.colorSchemePreference === "dark") {
            return "moon-star";
        }

        if (this.intellibusState.colorSchemePreference === "system") {
            return "monitor";
        }

        return "sun-medium";
    },

    setColorSchemePreference(preference) {
        this.intellibusState.colorSchemePreference = preference;
        applyColorSchemePreference(preference);
        this._syncColorSchemeWatcher();
    },

    getCompanyOptions() {
        const allowedCompanies = Object.values(this.companyService.allowedCompanies || {});
        const allowedCompanyIds = new Set(allowedCompanies.map((company) => company.id));
        const childrenByParent = new Map();

        const sortCompanies = (companies) =>
            companies.sort((companyA, companyB) => {
                const sequenceA = companyA.sequence || 0;
                const sequenceB = companyB.sequence || 0;

                if (sequenceA !== sequenceB) {
                    return sequenceA - sequenceB;
                }

                return companyA.name.localeCompare(companyB.name);
            });

        for (const company of allowedCompanies) {
            const parentId = allowedCompanyIds.has(company.parent_id) ? company.parent_id : null;
            const siblings = childrenByParent.get(parentId) || [];
            siblings.push(company);
            childrenByParent.set(parentId, siblings);
        }

        for (const siblings of childrenByParent.values()) {
            sortCompanies(siblings);
        }

        const options = [];
        const visitCompanies = (parentId = null, level = 0) => {
            for (const company of childrenByParent.get(parentId) || []) {
                options.push({ ...company, level });
                visitCompanies(company.id, level + 1);
            }
        };

        visitCompanies();
        return options;
    },

    getLucideIcon(app) {
        return this.appIconMap[app.name] || 'package';
    }
});
