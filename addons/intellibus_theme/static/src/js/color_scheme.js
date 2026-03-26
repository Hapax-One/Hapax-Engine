/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { cookie } from "@web/core/browser/cookie";

export const COLOR_SCHEME_COOKIE = "color_scheme";
export const COLOR_SCHEME_PREFERENCE_COOKIE = "intellibus_color_scheme_preference";
export const COLOR_SCHEME_OPTIONS = ["light", "dark", "system"];

export function getSystemColorScheme() {
    return browser.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function normalizeColorSchemePreference(preference) {
    return COLOR_SCHEME_OPTIONS.includes(preference) ? preference : "light";
}

export function getColorSchemePreference() {
    const preference = cookie.get(COLOR_SCHEME_PREFERENCE_COOKIE);
    if (COLOR_SCHEME_OPTIONS.includes(preference)) {
        return preference;
    }

    return cookie.get(COLOR_SCHEME_COOKIE) === "dark" ? "dark" : "light";
}

export function resolveColorScheme(preference = getColorSchemePreference()) {
    const normalizedPreference = normalizeColorSchemePreference(preference);
    return normalizedPreference === "system" ? getSystemColorScheme() : normalizedPreference;
}

export function applyColorSchemePreference(preference, { reload = true } = {}) {
    const nextPreference = normalizeColorSchemePreference(preference);
    const currentScheme = cookie.get(COLOR_SCHEME_COOKIE) || "light";
    const nextScheme = resolveColorScheme(nextPreference);

    cookie.set(COLOR_SCHEME_PREFERENCE_COOKIE, nextPreference);
    cookie.set(COLOR_SCHEME_COOKIE, nextScheme);

    if (reload && currentScheme !== nextScheme) {
        browser.location.reload();
    }

    return nextScheme;
}
