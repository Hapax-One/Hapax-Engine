/** @odoo-module **/

export const DEFAULT_INTELLIBUS_BRAND_COLOR = "#71639e";

export function getBrandRgbChannels(color = DEFAULT_INTELLIBUS_BRAND_COLOR) {
    const normalized = normalizeBrandColor(color).replace("#", "");
    const value =
        normalized.length === 3
            ? normalized
                  .split("")
                  .map((channel) => `${channel}${channel}`)
                  .join("")
            : normalized;

    const red = Number.parseInt(value.slice(0, 2), 16);
    const green = Number.parseInt(value.slice(2, 4), 16);
    const blue = Number.parseInt(value.slice(4, 6), 16);

    if ([red, green, blue].some((channel) => Number.isNaN(channel))) {
        return "113 99 158";
    }

    return `${red} ${green} ${blue}`;
}

export function normalizeBrandColor(color) {
    const value = (color || "").trim();
    if (!value) {
        return DEFAULT_INTELLIBUS_BRAND_COLOR;
    }
    return value.startsWith("#") ? value : `#${value}`;
}

export function applyBrandColor(color) {
    const normalizedColor = normalizeBrandColor(color);
    const rgbChannels = getBrandRgbChannels(normalizedColor);
    document.documentElement.style.setProperty("--intellibus-brand-color", normalizedColor);
    document.documentElement.style.setProperty("--intellibus-brand-rgb", rgbChannels);
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
