/** @odoo-module **/

export const DEFAULT_INTELLIBUS_BRAND_COLOR = "#71639e";

export function normalizeBrandColor(color) {
    const value = (color || "").trim();
    if (!value) {
        return DEFAULT_INTELLIBUS_BRAND_COLOR;
    }
    return value.startsWith("#") ? value : `#${value}`;
}

export function applyBrandColor(color) {
    const normalizedColor = normalizeBrandColor(color);
    document.documentElement.style.setProperty("--intellibus-brand-color", normalizedColor);
    return normalizedColor;
}

export async function applyCompanyBrandColor(orm, companyId) {
    if (!orm || !companyId) {
        return applyBrandColor(DEFAULT_INTELLIBUS_BRAND_COLOR);
    }

    try {
        const companies = await orm.read("res.company", [companyId], ["primary_color"]);
        const company = companies && companies[0];
        return applyBrandColor(company && company.primary_color);
    } catch (error) {
        return applyBrandColor(DEFAULT_INTELLIBUS_BRAND_COLOR);
    }
}
