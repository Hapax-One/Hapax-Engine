/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { components } from "@odoo/o-spreadsheet";

const { ScorecardChart } = components;

function cssVar(styles, name, fallback) {
    const value = styles.getPropertyValue(name).trim();
    return value || fallback;
}

function getDashboardScorecardPalette() {
    const root =
        document.querySelector(".o_web_client") ||
        document.documentElement ||
        document.body;
    const styles = getComputedStyle(root);
    return {
        surface: cssVar(styles, "--intellibus-kpi-surface", "#ffffff"),
        border: cssVar(styles, "--intellibus-kpi-border", "#e3e8ef"),
        title: cssVar(styles, "--intellibus-kpi-text", "#475467"),
        value: cssVar(styles, "--intellibus-kpi-heading", "#101828"),
        positiveBg: cssVar(styles, "--intellibus-kpi-badge-bg", "#ecfdf3"),
        positiveText: cssVar(styles, "--intellibus-kpi-badge-text", "#027a48"),
        negativeBg: cssVar(styles, "--intellibus-kpi-danger-bg", "#fef3f2"),
        negativeText: cssVar(styles, "--intellibus-kpi-danger-text", "#b42318"),
        neutralBg: cssVar(styles, "--intellibus-kpi-neutral-bg", "#f2f4f7"),
        neutralText: cssVar(styles, "--intellibus-kpi-neutral-text", "#475467"),
    };
}

function fitFontSize(ctx, text, fontWeight, initialSize, minSize, maxWidth) {
    let size = initialSize;
    while (size > minSize) {
        ctx.font = `${fontWeight} ${size}px Inter, sans-serif`;
        if (ctx.measureText(text).width <= maxWidth) {
            break;
        }
        size -= 1;
    }
    return size;
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
    const boundedRadius = Math.max(0, Math.min(radius, width / 2, height / 2));
    ctx.beginPath();
    ctx.moveTo(x + boundedRadius, y);
    ctx.lineTo(x + width - boundedRadius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + boundedRadius);
    ctx.lineTo(x + width, y + height - boundedRadius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - boundedRadius, y + height);
    ctx.lineTo(x + boundedRadius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - boundedRadius);
    ctx.lineTo(x, y + boundedRadius);
    ctx.quadraticCurveTo(x, y, x + boundedRadius, y);
    ctx.closePath();
}

function getBadgePalette(direction, palette) {
    if (direction === "down") {
        return {
            background: palette.negativeBg,
            text: palette.negativeText,
        };
    }
    if (direction === "neutral") {
        return {
            background: palette.neutralBg,
            text: palette.neutralText,
        };
    }
    return {
        background: palette.positiveBg,
        text: palette.positiveText,
    };
}

function splitBaselineText(display, description) {
    const normalizedDisplay = (display || "").trim();
    const normalizedDescription = (description || "").trim();

    if (!normalizedDisplay) {
        return {
            badgeText: "",
            captionText: normalizedDescription,
        };
    }

    const percentageMatch = normalizedDisplay.match(
        /^([+\-−]?\d[\d\s,.\u202f]*%)(?:\s+(.*))?$/u
    );

    if (!percentageMatch) {
        return {
            badgeText: normalizedDisplay,
            captionText: normalizedDescription,
        };
    }

    return {
        badgeText: percentageMatch[1].trim(),
        captionText: (percentageMatch[2] || normalizedDescription).trim(),
    };
}

function drawTrendArrow(ctx, x, y, direction, color) {
    if (direction === "neutral") {
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x + 8, y);
        ctx.stroke();
        ctx.restore();
        return;
    }

    const sign = direction === "down" ? 1 : -1;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(x, y + 6);
    ctx.lineTo(x + 4, y + 2 + sign * 2);
    ctx.lineTo(x + 8, y + 2 + sign * 2);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x + 8, y + 2 + sign * 2);
    ctx.lineTo(x + 8, y + 6 + sign * 4);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x + 8, y + 2 + sign * 2);
    ctx.lineTo(x + 5.5, y + 4 + sign * 4);
    ctx.moveTo(x + 8, y + 2 + sign * 2);
    ctx.lineTo(x + 10.5, y + 4 + sign * 4);
    ctx.stroke();
    ctx.restore();
}

function drawDashboardScorecard(canvas, runtime) {
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const height = Math.max(1, rect.height);
    const dpr = window.devicePixelRatio || 1;
    const ctx = canvas.getContext("2d");
    const palette = getDashboardScorecardPalette();
    const paddingX = Math.max(16, Math.min(20, width * 0.08));
    const paddingY = Math.max(16, Math.min(20, height * 0.18));
    const titleText = runtime?.title || "";
    const valueText = runtime?.keyValue || "";
    const { badgeText, captionText } = splitBaselineText(
        runtime?.baselineDisplay,
        runtime?.baselineDescr
    );
    const badgeDirection = runtime?.baselineArrow || "neutral";
    const badgePalette = getBadgePalette(badgeDirection, palette);
    const radius = 12;

    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    drawRoundedRect(ctx, 0.5, 0.5, width - 1, height - 1, radius);
    ctx.fillStyle = palette.surface;
    ctx.fill();
    ctx.strokeStyle = palette.border;
    ctx.lineWidth = 1;
    ctx.stroke();

    if (titleText) {
        const titleFontSize = fitFontSize(ctx, titleText, 500, 14, 12, width - paddingX * 2);
        ctx.font = `500 ${titleFontSize}px Inter, sans-serif`;
        ctx.fillStyle = palette.title;
        ctx.textBaseline = "top";
        ctx.fillText(titleText, paddingX, paddingY);
    }

    let badgeWidth = 0;
    let badgeHeight = 0;
    if (badgeText) {
        ctx.font = "500 14px Inter, sans-serif";
        badgeWidth = ctx.measureText(badgeText).width + 28;
        badgeHeight = 24;
    }

    const captionOffset = captionText ? 18 : 0;
    const valueBaselineY = height - paddingY - captionOffset;

    if (valueText) {
        const maxValueWidth = Math.max(72, width - paddingX * 2 - (badgeWidth ? badgeWidth + 16 : 0));
        const valueFontSize = fitFontSize(ctx, valueText, 600, 30, 20, maxValueWidth);
        ctx.font = `600 ${valueFontSize}px Inter, sans-serif`;
        ctx.fillStyle = palette.value;
        ctx.textBaseline = "alphabetic";
        ctx.fillText(valueText, paddingX, valueBaselineY);

        if (badgeText) {
            const valueWidth = ctx.measureText(valueText).width;
            const badgeX = Math.min(
                width - paddingX - badgeWidth,
                paddingX + valueWidth + 16
            );
            const badgeY = valueBaselineY - badgeHeight + 1;
            drawRoundedRect(ctx, badgeX, badgeY, badgeWidth, badgeHeight, badgeHeight / 2);
            ctx.fillStyle = badgePalette.background;
            ctx.fill();
            drawTrendArrow(ctx, badgeX + 8, badgeY + 6, badgeDirection, badgePalette.text);
            ctx.font = "500 14px Inter, sans-serif";
            ctx.fillStyle = badgePalette.text;
            ctx.textBaseline = "middle";
            ctx.fillText(badgeText, badgeX + 20, badgeY + badgeHeight / 2 + 0.5);
        }
    }

    if (captionText) {
        const captionFontSize = fitFontSize(ctx, captionText, 500, 12, 11, width - paddingX * 2);
        ctx.font = `500 ${captionFontSize}px Inter, sans-serif`;
        ctx.fillStyle = palette.title;
        ctx.textBaseline = "alphabetic";
        ctx.fillText(captionText, paddingX, height - paddingY);
    }

    const ariaParts = [titleText, valueText, badgeText, captionText]
        .filter(Boolean)
        .join(". ");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", ariaParts);
}

patch(ScorecardChart.prototype, {
    createChart() {
        const canvas = this.canvas.el;
        if (!canvas || !canvas.closest(".o_spreadsheet_dashboard_action")) {
            return super.createChart(...arguments);
        }
        canvas.closest(".o-chart-container")?.classList.add("intellibus-dashboard-scorecard");
        drawDashboardScorecard(canvas, this.runtime);
    },
});
