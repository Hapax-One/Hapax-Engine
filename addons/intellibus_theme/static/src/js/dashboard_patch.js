/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { SpreadsheetDashboardAction } from "@spreadsheet_dashboard/bundle/dashboard_action/dashboard_action";

/* global lucide */

const LAST_ACTIVITY_FILTERS = [
    { value: "", label: _t("Last activity") },
    { value: "today", label: _t("Today") },
    { value: "week", label: _t("Last 7 days") },
    { value: "month", label: _t("Last 30 days") },
    { value: "older", label: _t("Older") },
    { value: "none", label: _t("No activity") },
];

const TYPE_LABELS = {
    product: _t("Stockable"),
    consu: _t("Consumable"),
    service: _t("Service"),
    combo: _t("Combo"),
};

const TRACKING_LABELS = {
    serial: _t("Serial"),
    lot: _t("Lot"),
    none: _t("None"),
};

const MOVE_STATE_LABELS = {
    draft: _t("New"),
    waiting: _t("Waiting"),
    confirmed: _t("Waiting availability"),
    partially_available: _t("Partially available"),
    assigned: _t("Available"),
    done: _t("Done"),
    cancel: _t("Cancelled"),
};

const TABLE_COLUMNS = [
    { key: "reference", label: _t("#"), className: "is-reference" },
    { key: "view", label: _t("View"), className: "is-view" },
    { key: "item", label: _t("Item"), className: "is-item" },
    { key: "serialNumber", label: _t("Serial number"), className: "is-serial" },
    { key: "qty", label: _t("Qty"), className: "is-qty" },
    { key: "status", label: _t("Status"), className: "is-status" },
    { key: "category", label: _t("Category"), className: "is-category" },
    { key: "location", label: _t("Location"), className: "is-location" },
    { key: "type", label: _t("Type"), className: "is-type" },
    { key: "tracking", label: _t("Tracking"), className: "is-tracking" },
    { key: "lastActivity", label: _t("Last activity"), className: "is-last-activity" },
    { key: "incoming", label: _t("Incoming"), className: "is-incoming" },
    { key: "reserved", label: _t("Reserved"), className: "is-reserved" },
    { key: "minQty", label: _t("Min qty"), className: "is-min-qty" },
    { key: "latestReference", label: _t("Latest ref"), className: "is-latest-reference" },
    { key: "actions", label: "", className: "is-actions" },
];

function normalizeText(value) {
    return (value || "").toString().trim();
}

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function cleanProductName(displayName, sku) {
    const normalized = normalizeText(displayName);
    if (!normalized) {
        return _t("Unnamed item");
    }
    if (!sku) {
        return normalized;
    }
    const pattern = new RegExp(`^\\[${escapeRegExp(sku)}\\]\\s*`);
    return normalized.replace(pattern, "").trim() || normalized;
}

function getCategoryLabel(categoryValue) {
    const categoryName = Array.isArray(categoryValue) ? categoryValue[1] : categoryValue;
    const normalized = normalizeText(categoryName);
    if (!normalized) {
        return "-";
    }
    const segments = normalized
        .split("/")
        .map((segment) => segment.trim())
        .filter(Boolean);
    return segments[segments.length - 1] || normalized;
}

function getTypeLabel(type) {
    return TYPE_LABELS[type] || "-";
}

function getTrackingLabel(tracking) {
    return TRACKING_LABELS[tracking] || "-";
}

function formatMetric(value, decimals = 0) {
    return new Intl.NumberFormat(undefined, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(Number.isFinite(value) ? value : 0);
}

function formatQuantity(value) {
    const quantity = Number(value || 0);
    if (Number.isInteger(quantity)) {
        return formatMetric(quantity, 0);
    }
    return formatMetric(quantity, 2);
}

function formatDate(value) {
    if (!value) {
        return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "-";
    }
    return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    }).format(date);
}

function formatDateTime(value) {
    if (!value) {
        return "-";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "-";
    }
    return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "numeric",
        minute: "2-digit",
    }).format(date);
}

function formatWeight(value) {
    const weight = Number(value || 0);
    if (!weight) {
        return "-";
    }
    return `${formatMetric(weight, weight < 1 ? 2 : 1)} kg`;
}

function formatVolume(value) {
    const volume = Number(value || 0);
    if (!volume) {
        return "-";
    }
    return `${formatMetric(volume, volume < 1 ? 3 : 2)} m³`;
}

function createInitials(name) {
    const parts = normalizeText(name)
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2);
    if (!parts.length) {
        return "IN";
    }
    return parts.map((part) => part[0]?.toUpperCase() || "").join("");
}

function splitLocationLabel(value) {
    const normalized = normalizeText(value);
    if (!normalized) {
        return { name: "-", path: "-" };
    }
    const segments = normalized
        .split("/")
        .map((segment) => segment.trim())
        .filter(Boolean);
    return {
        name: segments[segments.length - 1] || normalized,
        path: normalized,
    };
}

function getLastActivityFilterValue(value) {
    if (!value) {
        return "none";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return "none";
    }
    const now = new Date();
    const diffInDays = (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24);
    if (diffInDays <= 1) {
        return "today";
    }
    if (diffInDays <= 7) {
        return "week";
    }
    if (diffInDays <= 30) {
        return "month";
    }
    return "older";
}

function createEmptyInventoryState() {
    return {
        loading: true,
        error: "",
        inventoryInstalled: true,
        query: "",
        currentPage: 1,
        pageSize: 10,
        selectedProductIds: [],
        filters: {
            status: "",
            category: "",
            location: "",
            type: "",
            tracking: "",
            lastActivity: "",
        },
        summary: {
            inStockUnits: 0,
            inStockSkus: 0,
            lowStockCount: 0,
            lowStockRules: 0,
            totalItems: 0,
            trackedTypes: 0,
            incomingUnits: 0,
            incomingSkus: 0,
        },
        filterOptions: {
            status: [],
            category: [],
            location: [],
            type: [],
            tracking: [],
        },
        rows: [],
        detail: {
            open: false,
            loading: false,
            error: "",
            item: null,
            mode: "overview",
            moveForm: createEmptyMoveFormState(),
        },
    };
}

function createQuantMap(quants) {
    const quantMap = new Map();
    for (const quant of quants) {
        const productId = quant.product_id?.[0];
        if (!productId) {
            continue;
        }
        if (!quantMap.has(productId)) {
            quantMap.set(productId, {
                reserved: 0,
                primaryLocation: "",
                primaryLocationId: false,
                primaryLocationWeight: -1,
                serialNumber: "",
            });
        }
        const entry = quantMap.get(productId);
        const quantity = Number(quant.quantity || 0);
        const reserved = Number(quant.reserved_quantity || 0);
        const locationName = quant.location_id?.[1] || "";
        const serialNumber = quant.lot_id?.[1] || "";
        const weight = Math.abs(quantity) + Math.abs(reserved);
        entry.reserved += reserved;
        if (weight >= entry.primaryLocationWeight) {
            entry.primaryLocation = locationName;
            entry.primaryLocationId = quant.location_id?.[0] || false;
            entry.primaryLocationWeight = weight;
            if (serialNumber) {
                entry.serialNumber = serialNumber;
            }
        }
        if (!entry.serialNumber && serialNumber) {
            entry.serialNumber = serialNumber;
        }
    }
    return quantMap;
}

function createLatestMoveMap(moves) {
    const moveMap = new Map();
    for (const move of moves) {
        const productId = move.product_id?.[0];
        if (!productId || moveMap.has(productId)) {
            continue;
        }
        moveMap.set(productId, move);
    }
    return moveMap;
}

function createOrderpointMap(orderpoints) {
    const orderpointMap = new Map();
    for (const orderpoint of orderpoints) {
        const productId = orderpoint.product_id?.[0];
        if (!productId) {
            continue;
        }
        const currentMin = Number(orderpoint.product_min_qty || 0);
        const existingMin = orderpointMap.get(productId) || 0;
        orderpointMap.set(productId, Math.max(existingMin, currentMin));
    }
    return orderpointMap;
}

function getInventoryStatus(product, minimumQty, reservedQty) {
    const onHand = Number(product.qty_available || 0);
    const incoming = Number(product.incoming_qty || 0);
    const outgoing = Number(product.outgoing_qty || 0);

    if (onHand <= 0 && incoming > 0) {
        return { label: _t("Incoming"), tone: "brand" };
    }
    if (onHand <= 0) {
        return { label: _t("Out of stock"), tone: "danger" };
    }
    if (minimumQty > 0 && onHand < minimumQty) {
        return { label: _t("Below minimum"), tone: "warning" };
    }
    if (!minimumQty && onHand > 0 && onHand <= 5) {
        return { label: _t("Low stock"), tone: "warning" };
    }
    if (reservedQty > 0 || outgoing > onHand) {
        return { label: _t("Reserved"), tone: "info" };
    }
    return { label: _t("In stock"), tone: "success" };
}

function matchesInventorySearch(row, query) {
    if (!query) {
        return true;
    }
    const haystack = [
        row.reference,
        row.itemName,
        row.sku,
        row.itemMeta,
        row.serialNumber,
        row.category,
        row.location,
        row.typeLabel,
        row.trackingLabel,
        row.statusLabel,
        row.lastReference,
    ]
        .map((value) => normalizeText(value).toLowerCase())
        .join(" ");
    return haystack.includes(query);
}

function getActivityTimestamp(value) {
    if (!value) {
        return 0;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function getMoveStateTone(state) {
    if (state === "done") {
        return "success";
    }
    if (state === "cancel") {
        return "danger";
    }
    if (state === "assigned" || state === "partially_available") {
        return "info";
    }
    if (state === "confirmed" || state === "waiting") {
        return "warning";
    }
    return "neutral";
}

function getMoveEventLabel(move) {
    const source = normalizeText(move.location_id?.[1]);
    const destination = normalizeText(move.location_dest_id?.[1]);
    if (source.includes("Vendors")) {
        return _t("Received");
    }
    if (destination.includes("Customers")) {
        return _t("Checked out");
    }
    if (source.includes("Inventory adjustment") || destination.includes("Inventory adjustment")) {
        return _t("Adjusted");
    }
    return _t("Moved");
}

function buildMoveTimelineItems(moves, uomLabel) {
    return moves.slice(0, 8).map((move, index) => {
        const actorName = normalizeText(move.write_uid?.[1]) || _t("System");
        const source = normalizeText(move.location_id?.[1]) || "-";
        const destination = normalizeText(move.location_dest_id?.[1]) || "-";
        const quantityValue = Number(move.quantity || move.product_uom_qty || 0);
        const quantityLabel = quantityValue ? `${formatQuantity(quantityValue)} ${uomLabel}` : uomLabel;
        const reference = normalizeText(move.reference) || normalizeText(move.picking_id?.[1]) || "-";
        return {
            id: move.id || `${reference}-${index}`,
            actorName,
            actorInitials: createInitials(actorName),
            eventLabel: getMoveEventLabel(move),
            dateLabel: formatDateTime(move.date),
            description: `${source} -> ${destination} · ${quantityLabel} · ${reference}`,
            stateLabel: MOVE_STATE_LABELS[move.state] || move.state || "-",
            stateTone: getMoveStateTone(move.state),
        };
    });
}

function getInventorySecondaryBadge(row) {
    if (row.incomingQty > 0 && row.statusTone !== "brand") {
        return { label: _t("Incoming"), tone: "brand" };
    }
    if (row.reservedQty > 0 && row.statusTone !== "info") {
        return { label: _t("Reserved"), tone: "info" };
    }
    if (row.minQty > 0 && row.qty < row.minQty && row.statusTone !== "warning") {
        return { label: _t("Below minimum"), tone: "warning" };
    }
    return {
        label: row.trackingLabel !== _t("None") ? row.trackingLabel : row.typeLabel,
        tone: "neutral",
    };
}

function buildInventoryDetailRecord(product, row, quants, moves, orderpoints) {
    const quantMap = createQuantMap(quants);
    const quant = quantMap.get(product.id) || {};
    const minimumQty = createOrderpointMap(orderpoints).get(product.id) || row.minQty || 0;
    const status = getInventoryStatus(product, minimumQty, quant.reserved || row.reservedQty || 0);
    const secondaryBadge = getInventorySecondaryBadge({
        ...row,
        qty: Number(product.qty_available || row.qty || 0),
        incomingQty: Number(product.incoming_qty || row.incomingQty || 0),
        reservedQty: Number(quant.reserved || row.reservedQty || 0),
        minQty: minimumQty,
        statusTone: status.tone,
        statusLabel: status.label,
    });
    const locationValue = quant.primaryLocation || row.location || "-";
    const currentLocation = splitLocationLabel(locationValue);
    const barcodeValue = normalizeText(product.barcode);
    const skuValue = normalizeText(product.default_code);
    const codeValue = barcodeValue || skuValue || row.reference;
    const description =
        normalizeText(product.description) ||
        normalizeText(product.description_sale) ||
        normalizeText(product.description_pickingout) ||
        normalizeText(product.description_pickingin) ||
        "-";
    const uomLabel = normalizeText(product.uom_id?.[1]) || _t("Units");
    const detailFields = [
        { label: _t("Product name"), value: row.itemName },
        { label: _t("Reference / SKU"), value: skuValue || row.reference },
        { label: _t("Barcode / RFID"), value: barcodeValue || "-" },
        {
            label: _t("Category"),
            value: row.category,
            tone: "category",
            kind: "badge",
        },
        { label: _t("Unit of measure"), value: uomLabel },
        { label: _t("Product type"), value: row.typeLabel },
        { label: _t("Tracking"), value: row.trackingLabel },
        { label: _t("Status"), value: status.label, tone: status.tone, kind: "badge" },
        { label: _t("Description"), value: description, full: true },
        { label: _t("Weight"), value: formatWeight(product.weight) },
        { label: _t("Volume"), value: formatVolume(product.volume) },
        {
            label: _t("Responsible"),
            value: normalizeText(product.responsible_id?.[1]) || "-",
        },
    ];
    const stockFields = [
        { label: _t("On hand"), value: formatQuantity(product.qty_available || row.qty) },
        { label: _t("Incoming"), value: formatQuantity(product.incoming_qty || row.incomingQty) },
        { label: _t("Reserved"), value: formatQuantity(quant.reserved || row.reservedQty) },
        { label: _t("Minimum quantity"), value: formatQuantity(minimumQty) },
        { label: _t("Latest ref"), value: row.lastReference || "-" },
        { label: _t("Last activity"), value: row.lastActivityLabel || "-" },
    ];

    return {
        id: row.id,
        title: row.itemName,
        subtitle: skuValue || row.reference,
        uomId: product.uom_id?.[0] || false,
        uomLabel,
        onHandQty: Number(product.qty_available || row.qty || 0),
        statusLabel: status.label,
        statusTone: status.tone,
        secondaryBadge,
        currentLocationId: quant.primaryLocationId || false,
        currentLocationName: currentLocation.name,
        currentLocationPath: currentLocation.path,
        currentLocationMeta: `${formatQuantity(product.qty_available || row.qty)} ${uomLabel} · ${formatQuantity(
            quant.reserved || row.reservedQty
        )} ${_t("reserved")}`,
        detailFields,
        stockFields,
        photoUrls: row.imageUrl ? [row.imageUrl] : [],
        codeValue,
        moveTimeline: buildMoveTimelineItems(moves, uomLabel),
    };
}

function buildInventoryRows(products, quants, moves, orderpoints) {
    const quantMap = createQuantMap(quants);
    const latestMoveMap = createLatestMoveMap(moves);
    const orderpointMap = createOrderpointMap(orderpoints);

    // Build a stable row model once so filtering, pagination, and rendering stay predictable.
    return products
        .map((product) => {
            const quant = quantMap.get(product.id) || {};
            const latestMove = latestMoveMap.get(product.id);
            const minimumQty = orderpointMap.get(product.id) || 0;
            const status = getInventoryStatus(product, minimumQty, quant.reserved || 0);
            const itemName = cleanProductName(product.display_name, normalizeText(product.default_code));
            const sku = normalizeText(product.default_code);
            const barcode = normalizeText(product.barcode);
            const itemMeta = sku || barcode || "-";
            const serialNumber = quant.serialNumber || barcode || sku || "-";
            const lastActivityRaw = latestMove?.date || "";

            return {
                id: product.id,
                reference: `#${String(product.id).padStart(4, "0")}`,
                itemName,
                sku,
                itemMeta,
                imageUrl: `/web/image?model=product.product&field=image_128&id=${product.id}`,
                serialNumber,
                qty: Number(product.qty_available || 0),
                reservedQty: Number(quant.reserved || 0),
                incomingQty: Number(product.incoming_qty || 0),
                location: quant.primaryLocation || "-",
                typeLabel: getTypeLabel(product.detailed_type),
                trackingLabel: getTrackingLabel(product.tracking),
                category: getCategoryLabel(product.categ_id),
                statusLabel: status.label,
                statusTone: status.tone,
                lastActivityRaw,
                lastActivityLabel: formatDate(lastActivityRaw),
                lastActivityFilter: getLastActivityFilterValue(lastActivityRaw),
                lastReference: normalizeText(latestMove?.reference) || "-",
                minQty: minimumQty,
            };
        })
        .sort((left, right) => {
            const activityDiff = getActivityTimestamp(right.lastActivityRaw) - getActivityTimestamp(left.lastActivityRaw);
            if (activityDiff) {
                return activityDiff;
            }
            const stockDiff =
                right.qty +
                right.incomingQty +
                right.reservedQty -
                (left.qty + left.incomingQty + left.reservedQty);
            if (stockDiff) {
                return stockDiff;
            }
            return right.id - left.id;
        });
}

function computeInventorySummary(rows, orderpoints) {
    const inStockRows = rows.filter((row) => row.qty > 0);
    const lowStockRows = rows.filter((row) => row.statusTone === "warning");
    const incomingRows = rows.filter((row) => row.incomingQty > 0);
    const trackedTypes = new Set(rows.map((row) => row.typeLabel)).size;

    return {
        inStockUnits: inStockRows.reduce((sum, row) => sum + row.qty, 0),
        inStockSkus: inStockRows.length,
        lowStockCount: lowStockRows.length,
        lowStockRules: orderpoints.length,
        totalItems: rows.length,
        trackedTypes,
        incomingUnits: incomingRows.reduce((sum, row) => sum + row.incomingQty, 0),
        incomingSkus: incomingRows.length,
    };
}

function createEmptyMoveFormState() {
    return {
        loading: false,
        submitting: false,
        error: "",
        currentUser: null,
        sourceLocationId: false,
        destinationLocationId: false,
        assigneeId: false,
        description: "",
        locationOptions: [],
        assigneeOptions: [],
        pickingTypes: [],
    };
}

function getLocationRootKey(locationPath) {
    return normalizeText(locationPath).split("/")[0] || "";
}

function chooseInternalPickingType(pickingTypes, sourceLocationPath) {
    const sourceRoot = getLocationRootKey(sourceLocationPath);
    if (!pickingTypes.length) {
        return null;
    }

    const scoredTypes = pickingTypes.map((type) => {
        const sourceLabel = normalizeText(type.default_location_src_id?.[1]);
        const sourceTypeRoot = getLocationRootKey(sourceLabel);
        const name = normalizeText(type.name).toLowerCase();
        let score = 0;
        if (sourceRoot && sourceTypeRoot === sourceRoot) {
            score += 3;
        }
        if (name.includes("internal")) {
            score += 2;
        }
        if (sourceLabel && normalizeText(sourceLocationPath).startsWith(sourceLabel)) {
            score += 1;
        }
        return { score, type };
    });

    scoredTypes.sort((left, right) => right.score - left.score || left.type.id - right.type.id);
    return scoredTypes[0]?.type || null;
}

function formatMoveFormUser(userRecord) {
    return {
        id: userRecord.id,
        name: normalizeText(userRecord.partner_id?.[1]) || normalizeText(userRecord.login) || _t("Unknown user"),
        email: normalizeText(userRecord.login) || normalizeText(userRecord.partner_email) || "-",
        avatarUrl: `/web/image?model=res.users&field=avatar_128&id=${userRecord.id}`,
    };
}

function buildFilterOptions(rows, fieldName) {
    return [...new Set(rows.map((row) => row[fieldName]).filter(Boolean))].sort((left, right) =>
        left.localeCompare(right)
    );
}

patch(SpreadsheetDashboardAction.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.user = useService("user");
        this.inventoryDashboardState = useState(createEmptyInventoryState());
        this.intellibusViewportListener = null;

        onWillStart(async () => {
            await this.loadInventoryDashboardData();
        });
        onMounted(() => {
            this._setupInventoryViewportWatcher();
            this.renderInventoryIcons();
            this.syncInventoryDetailShellState();
        });
        onPatched(() => {
            this.renderInventoryIcons();
            this.syncInventoryDetailShellState();
        });
        onWillUnmount(() => {
            this.syncInventoryDetailShellState(true);
            this._teardownInventoryViewportWatcher();
        });
    },

    getInitialActiveDashboard() {
        return undefined;
    },

    renderInventoryIcons() {
        if (typeof lucide !== "undefined") {
            lucide.createIcons();
        }
    },

    _getInventoryRootEl() {
        return document.querySelector(".o_web_client");
    },

    _setupInventoryViewportWatcher() {
        if (this.intellibusViewportListener || typeof window === "undefined") {
            return;
        }
        this.intellibusViewportListener = () => {
            if (this.hasInventoryDetailOpen()) {
                this._syncInventoryDetailViewportMetrics();
            }
        };
        window.addEventListener("resize", this.intellibusViewportListener);
    },

    _teardownInventoryViewportWatcher() {
        if (!this.intellibusViewportListener || typeof window === "undefined") {
            return;
        }
        window.removeEventListener("resize", this.intellibusViewportListener);
        this.intellibusViewportListener = null;
    },

    _clearInventoryDetailViewportMetrics() {
        const rootEl = this._getInventoryRootEl();
        if (!rootEl) {
            return;
        }
        rootEl.style.removeProperty("--intellibus-dashboard-overlay-top");
        rootEl.style.removeProperty("--intellibus-dashboard-overlay-right");
        rootEl.style.removeProperty("--intellibus-dashboard-overlay-bottom");
        rootEl.style.removeProperty("--intellibus-dashboard-overlay-left");
    },

    _syncInventoryDetailViewportMetrics() {
        const rootEl = this._getInventoryRootEl();
        const dashboardEl = this.el?.querySelector(".intellibus-inventory-dashboard");
        if (!rootEl || !dashboardEl) {
            return;
        }

        const rect = dashboardEl.getBoundingClientRect();
        rootEl.style.setProperty(
            "--intellibus-dashboard-overlay-top",
            `${Math.max(Math.round(rect.top), 0)}px`
        );
        rootEl.style.setProperty(
            "--intellibus-dashboard-overlay-right",
            `${Math.max(Math.round(window.innerWidth - rect.right), 0)}px`
        );
        rootEl.style.setProperty(
            "--intellibus-dashboard-overlay-bottom",
            `${Math.max(Math.round(window.innerHeight - rect.bottom), 0)}px`
        );
        rootEl.style.setProperty(
            "--intellibus-dashboard-overlay-left",
            `${Math.max(Math.round(rect.left), 0)}px`
        );
    },

    syncInventoryDetailShellState(forceClosed = false) {
        const isOpen = !forceClosed && this.hasInventoryDetailOpen();
        const rootEl = this._getInventoryRootEl();
        document.documentElement.classList.toggle("intellibus-inventory-detail-open", isOpen);
        document.body.classList.toggle("intellibus-inventory-detail-open", isOpen);
        rootEl?.classList.toggle("intellibus-inventory-detail-open", isOpen);
        if (isOpen) {
            this._syncInventoryDetailViewportMetrics();
        } else {
            this._clearInventoryDetailViewportMetrics();
        }
    },

    onInventoryDetailOverlayWheel(ev) {
        if (
            ev.target.closest(
                ".intellibus-inventory-detail-panel-scroll, .intellibus-inventory-detail-log"
            )
        ) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
    },

    async loadInventoryDashboardData() {
        this.inventoryDashboardState.loading = true;
        this.inventoryDashboardState.error = "";
        this.inventoryDashboardState.inventoryInstalled = true;
        try {
            const products = await this.orm.searchRead(
                "product.product",
                [
                    ["active", "=", true],
                    ["detailed_type", "in", ["product", "consu"]],
                ],
                [
                    "id",
                    "display_name",
                    "default_code",
                    "barcode",
                    "qty_available",
                    "incoming_qty",
                    "outgoing_qty",
                    "detailed_type",
                    "tracking",
                    "categ_id",
                ],
                {
                    limit: 200,
                    order: "id desc",
                }
            );

            const productIds = products.map((product) => product.id);

            const [quants, moves, orderpoints] = await Promise.all([
                productIds.length
                    ? this.orm.searchRead(
                          "stock.quant",
                          [["product_id", "in", productIds]],
                          ["product_id", "location_id", "lot_id", "quantity", "reserved_quantity"],
                          { limit: 500 }
                      )
                    : Promise.resolve([]),
                productIds.length
                    ? this.orm.searchRead(
                          "stock.move",
                          [["product_id", "in", productIds]],
                          ["product_id", "date", "state", "reference"],
                          {
                              limit: 500,
                              order: "date desc",
                          }
                      )
                    : Promise.resolve([]),
                productIds.length
                    ? this.orm.searchRead(
                          "stock.warehouse.orderpoint",
                          [["product_id", "in", productIds]],
                          ["product_id", "product_min_qty"],
                          { limit: 200 }
                      )
                    : Promise.resolve([]),
            ]);

            const rows = buildInventoryRows(products, quants, moves, orderpoints);
            this.inventoryDashboardState.rows = rows;
            this.inventoryDashboardState.summary = computeInventorySummary(rows, orderpoints);
            this.inventoryDashboardState.filterOptions = {
                status: buildFilterOptions(rows, "statusLabel"),
                category: buildFilterOptions(rows, "category"),
                location: buildFilterOptions(rows, "location"),
                type: buildFilterOptions(rows, "typeLabel"),
                tracking: buildFilterOptions(rows, "trackingLabel"),
            };
        } catch (error) {
            const message = error?.message || _t("Unable to load inventory dashboard.");
            const loweredMessage = message.toLowerCase();
            if (
                loweredMessage.includes("qty_available") ||
                loweredMessage.includes("stock.quant") ||
                loweredMessage.includes("stock.warehouse.orderpoint")
            ) {
                this.inventoryDashboardState.inventoryInstalled = false;
            }
            this.inventoryDashboardState.error =
                message;
        } finally {
            this.inventoryDashboardState.loading = false;
        }
    },

    getInventoryTitle() {
        return _t("Inventory");
    },

    getInventorySubtitle() {
        return _t("This is where inventory lives and moves");
    },

    getInventorySearchPlaceholder() {
        return _t("Search items, SKU, serial...");
    },

    getEditLabel() {
        return _t("Edit");
    },

    getResetFiltersLabel() {
        return _t("Reset filters");
    },

    getInventoryFiltersGroupLabel() {
        return _t("Inventory filters");
    },

    getInventoryLoadingLabel() {
        return _t("Loading inventory dashboard...");
    },

    getOpenInventoryItemLabel() {
        return _t("Open item");
    },

    getInventoryDetailTitle() {
        if (this.isInventoryMoveMode()) {
            return _t("Move item");
        }
        return _t("About this item");
    },

    getInventoryDetailLabel() {
        return _t("Details");
    },

    getInventoryCurrentLocationLabel() {
        return _t("Current location");
    },

    getInventoryMoveLogLabel() {
        return _t("Move log");
    },

    getInventoryPhotosLabel() {
        return _t("Photo");
    },

    getInventoryAssignedCodeLabel() {
        return _t("Assigned code");
    },

    getInventoryStockLabel() {
        return _t("Inventory");
    },

    getInventoryMoveYouLabel() {
        return _t("You");
    },

    getInventoryMoveCurrentLocationFieldLabel() {
        return _t("Current location");
    },

    getInventoryMoveDestinationLabel() {
        return _t("Move to");
    },

    getInventoryMoveAssigneeLabel() {
        return _t("Assign to someone");
    },

    getInventoryMoveDescriptionLabel() {
        return _t("Description");
    },

    getInventoryMoveDescriptionOptionalLabel() {
        return _t("(optional)");
    },

    getInventoryMoveDescriptionPlaceholder() {
        return _t("Enter a description...");
    },

    getInventoryMoveAssigneePlaceholder() {
        return _t("Name, email, or group");
    },

    getInventoryMoveDestinationPlaceholder() {
        return _t("Select a location");
    },

    getInventoryMoveSeparatorLabel() {
        return _t("Move this item to");
    },

    getInventoryMoveScanLabel() {
        return _t("Scan item with phone");
    },

    getInventoryMoveCloseLabel() {
        return _t("Close");
    },

    getInventoryMoveSubmitLabel() {
        if (this.getInventoryMoveForm().submitting) {
            return _t("Moving...");
        }
        return _t("Move item");
    },

    getInventoryMoveHelperLabel() {
        return _t("Others will be notified in your inventory.");
    },

    getInventoryMoveScanUnavailableLabel() {
        return _t("Phone scanning is not configured in this database yet.");
    },

    getViewLabel() {
        return _t("View");
    },

    getViewAllLabel() {
        return _t("View all");
    },

    getCloseInventoryDetailLabel() {
        return _t("Close item details");
    },

    getInventoryPagesLabel() {
        return _t("Inventory pages");
    },

    getRestockLabel() {
        return _t("Restock");
    },

    getCheckInLabel() {
        return _t("Check-In");
    },

    getMoveInventoryItemLabel() {
        return _t("Move an item");
    },

    getAddInventoryItemLabel() {
        return _t("Add to inventory");
    },

    getCheckoutLabel() {
        return _t("Check out");
    },

    getPreviousPageLabel() {
        return _t("Previous");
    },

    getNextPageLabel() {
        return _t("Next");
    },

    getInventoryErrorTitle() {
        if (!this.inventoryDashboardState.inventoryInstalled) {
            return _t("Inventory is not installed for this database.");
        }
        return this.inventoryDashboardState.error || _t("Unable to load inventory dashboard.");
    },

    getInventoryEmptyStateLabel() {
        return _t("No inventory items match your current search or filters.");
    },

    getInventoryDetailEmptyMovesLabel() {
        return _t("No inventory moves have been recorded for this item yet.");
    },

    getInventoryNoPhotoLabel() {
        return _t("No product photo is available yet.");
    },

    isInventoryMoveSubmitDisabled() {
        const detail = this.getInventoryDetail();
        const moveForm = this.getInventoryMoveForm();
        return (
            !detail ||
            moveForm.submitting ||
            moveForm.loading ||
            !moveForm.sourceLocationId ||
            !moveForm.destinationLocationId ||
            moveForm.destinationLocationId === moveForm.sourceLocationId ||
            detail.onHandQty < 1
        );
    },

    getInventoryTableColumns() {
        return TABLE_COLUMNS;
    },

    formatInventoryQuantity(value) {
        return formatQuantity(value);
    },

    getInventoryFilterDefinitions() {
        return [
            {
                key: "status",
                label: _t("Status"),
                options: this.inventoryDashboardState.filterOptions.status,
            },
            {
                key: "category",
                label: _t("Category"),
                options: this.inventoryDashboardState.filterOptions.category,
            },
            {
                key: "location",
                label: _t("Location"),
                options: this.inventoryDashboardState.filterOptions.location,
            },
            {
                key: "type",
                label: _t("Type"),
                options: this.inventoryDashboardState.filterOptions.type,
            },
            {
                key: "lastActivity",
                label: _t("Last activity"),
                options: LAST_ACTIVITY_FILTERS.slice(1).map((filter) => filter.label),
                mappedOptions: LAST_ACTIVITY_FILTERS,
            },
            {
                key: "tracking",
                label: _t("Tracking"),
                options: this.inventoryDashboardState.filterOptions.tracking,
            },
        ];
    },

    getInventorySummaryCards() {
        const summary = this.inventoryDashboardState.summary;
        return [
            {
                key: "in-stock",
                label: _t("In-stock"),
                value: formatQuantity(summary.inStockUnits),
                badge: `${summary.inStockSkus} ${_t("SKUs")}`,
                tone: "success",
            },
            {
                key: "low-stocks",
                label: _t("Low stocks"),
                value: formatMetric(summary.lowStockCount),
                badge: `${summary.lowStockRules} ${_t("rules")}`,
                tone: summary.lowStockCount ? "warning" : "success",
            },
            {
                key: "total-items",
                label: _t("Total items"),
                value: formatMetric(summary.totalItems),
                badge: `${summary.trackedTypes} ${_t("types")}`,
                tone: "neutral",
            },
            {
                key: "incoming",
                label: _t("Incoming"),
                value: formatQuantity(summary.incomingUnits),
                badge: `${summary.incomingSkus} ${_t("SKUs")}`,
                tone: summary.incomingUnits ? "brand" : "neutral",
            },
        ];
    },

    getInventoryMetricCardClass(card) {
        return `intellibus-inventory-metric-card is-${card.tone}`;
    },

    getInventoryMetricBadgeClass(tone) {
        return `intellibus-inventory-pill is-${tone}`;
    },

    onInventorySearchInput(ev) {
        this.inventoryDashboardState.query = ev.target.value || "";
        this.inventoryDashboardState.currentPage = 1;
    },

    resetInventoryFilters() {
        this.inventoryDashboardState.query = "";
        this.inventoryDashboardState.currentPage = 1;
        for (const key of Object.keys(this.inventoryDashboardState.filters)) {
            this.inventoryDashboardState.filters[key] = "";
        }
    },

    onInventoryFilterChange(filterKey, ev) {
        this.inventoryDashboardState.filters[filterKey] = ev.target.value || "";
        this.inventoryDashboardState.currentPage = 1;
    },

    getInventoryFilteredRows() {
        const query = normalizeText(this.inventoryDashboardState.query).toLowerCase();
        const filters = this.inventoryDashboardState.filters;

        return this.inventoryDashboardState.rows.filter((row) => {
            if (!matchesInventorySearch(row, query)) {
                return false;
            }
            if (filters.status && row.statusLabel !== filters.status) {
                return false;
            }
            if (filters.category && row.category !== filters.category) {
                return false;
            }
            if (filters.location && row.location !== filters.location) {
                return false;
            }
            if (filters.type && row.typeLabel !== filters.type) {
                return false;
            }
            if (filters.tracking && row.trackingLabel !== filters.tracking) {
                return false;
            }
            if (filters.lastActivity && row.lastActivityFilter !== filters.lastActivity) {
                return false;
            }
            return true;
        });
    },

    getInventoryFilteredRowCount() {
        return this.getInventoryFilteredRows().length;
    },

    getInventoryPageCount() {
        return Math.max(
            1,
            Math.ceil(this.getInventoryFilteredRows().length / this.inventoryDashboardState.pageSize)
        );
    },

    getInventoryCurrentPage() {
        return Math.min(this.inventoryDashboardState.currentPage, this.getInventoryPageCount());
    },

    getInventoryVisibleRows() {
        const currentPage = this.getInventoryCurrentPage();
        const pageSize = this.inventoryDashboardState.pageSize;
        const start = (currentPage - 1) * pageSize;
        return this.getInventoryFilteredRows().slice(start, start + pageSize);
    },

    getInventoryPaginationItems() {
        const pageCount = this.getInventoryPageCount();
        const currentPage = this.getInventoryCurrentPage();
        if (pageCount <= 7) {
            return Array.from({ length: pageCount }, (_, index) => ({
                type: "page",
                value: index + 1,
            }));
        }

        const items = [{ type: "page", value: 1 }];
        const start = Math.max(2, currentPage - 1);
        const end = Math.min(pageCount - 1, currentPage + 1);

        if (start > 2) {
            items.push({ type: "ellipsis", value: "start-ellipsis" });
        }

        for (let page = start; page <= end; page++) {
            items.push({ type: "page", value: page });
        }

        if (end < pageCount - 1) {
            items.push({ type: "ellipsis", value: "end-ellipsis" });
        }

        items.push({ type: "page", value: pageCount });
        return items;
    },

    goToInventoryPage(page) {
        if (page < 1 || page > this.getInventoryPageCount()) {
            return;
        }
        this.inventoryDashboardState.currentPage = page;
    },

    goToPreviousInventoryPage() {
        this.goToInventoryPage(this.getInventoryCurrentPage() - 1);
    },

    goToNextInventoryPage() {
        this.goToInventoryPage(this.getInventoryCurrentPage() + 1);
    },

    onInventoryPaginationItemClick(item) {
        if (item.type === "page") {
            this.goToInventoryPage(item.value);
        }
    },

    isInventoryPageSelected() {
        const visibleRows = this.getInventoryVisibleRows();
        return (
            visibleRows.length > 0 &&
            visibleRows.every((row) =>
                this.inventoryDashboardState.selectedProductIds.includes(row.id)
            )
        );
    },

    isInventoryRowSelected(productId) {
        return this.inventoryDashboardState.selectedProductIds.includes(productId);
    },

    toggleInventoryPageSelection() {
        const visibleIds = this.getInventoryVisibleRows().map((row) => row.id);
        const allSelected = visibleIds.every((id) =>
            this.inventoryDashboardState.selectedProductIds.includes(id)
        );

        if (allSelected) {
            this.inventoryDashboardState.selectedProductIds =
                this.inventoryDashboardState.selectedProductIds.filter(
                    (id) => !visibleIds.includes(id)
                );
            return;
        }

        this.inventoryDashboardState.selectedProductIds = [
            ...new Set([
                ...this.inventoryDashboardState.selectedProductIds,
                ...visibleIds,
            ]),
        ];
    },

    toggleInventoryRowSelection(productId) {
        if (this.inventoryDashboardState.selectedProductIds.includes(productId)) {
            this.inventoryDashboardState.selectedProductIds =
                this.inventoryDashboardState.selectedProductIds.filter((id) => id !== productId);
            return;
        }
        this.inventoryDashboardState.selectedProductIds = [
            ...this.inventoryDashboardState.selectedProductIds,
            productId,
        ];
    },

    getInventoryRowImageStyle(row) {
        return `background-image: url('${row.imageUrl}')`;
    },

    getInventoryBadgeClass(tone) {
        return `intellibus-inventory-badge is-${tone}`;
    },

    hasInventoryDetailOpen() {
        return this.inventoryDashboardState.detail.open;
    },

    getInventoryDetail() {
        return this.inventoryDashboardState.detail.item;
    },

    isInventoryMoveMode() {
        return this.inventoryDashboardState.detail.mode === "move";
    },

    getInventoryMoveForm() {
        return this.inventoryDashboardState.detail.moveForm;
    },

    closeInventoryDetail() {
        this.inventoryDashboardState.detail.open = false;
        this.inventoryDashboardState.detail.loading = false;
        this.inventoryDashboardState.detail.error = "";
        this.inventoryDashboardState.detail.item = null;
        this.inventoryDashboardState.detail.mode = "overview";
        this.inventoryDashboardState.detail.moveForm = createEmptyMoveFormState();
    },

    getInventoryDetailError() {
        return this.inventoryDashboardState.detail.error || _t("Unable to load this item.");
    },

    async loadInventoryDetail(row) {
        const [product] = await this.orm.searchRead(
            "product.product",
            [["id", "=", row.id]],
            [
                "id",
                "display_name",
                "default_code",
                "barcode",
                "qty_available",
                "incoming_qty",
                "outgoing_qty",
                "detailed_type",
                "tracking",
                "categ_id",
                "uom_id",
                "description",
                "description_sale",
                "description_pickingin",
                "description_pickingout",
                "weight",
                "volume",
                "responsible_id",
            ],
            { limit: 1 }
        );

        const [quants, moves, orderpoints] = await Promise.all([
            this.orm.searchRead(
                "stock.quant",
                [["product_id", "=", row.id]],
                ["product_id", "location_id", "lot_id", "quantity", "reserved_quantity"],
                { limit: 100 }
            ),
            this.orm.searchRead(
                "stock.move",
                [["product_id", "=", row.id]],
                [
                    "id",
                    "reference",
                    "date",
                    "state",
                    "product_uom_qty",
                    "quantity",
                    "location_id",
                    "location_dest_id",
                    "picking_id",
                    "write_uid",
                ],
                {
                    limit: 20,
                    order: "date desc",
                }
            ),
            this.orm.searchRead(
                "stock.warehouse.orderpoint",
                [["product_id", "=", row.id]],
                ["product_id", "product_min_qty"],
                { limit: 10 }
            ),
        ]);

        return buildInventoryDetailRecord(product, row, quants, moves, orderpoints);
    },

    async openInventoryCatalog() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Inventory Items"),
            res_model: "product.product",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["detailed_type", "in", ["product", "consu"]]],
            target: "current",
        });
    },

    async openInventoryCreate() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Add inventory item"),
            res_model: "product.product",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_detailed_type: "product",
            },
        });
    },

    async openInventoryRestock() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Restock"),
            res_model: "stock.warehouse.orderpoint",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
        });
    },

    async openInventoryCheckIn() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Check-In"),
            res_model: "stock.picking",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["picking_type_code", "=", "incoming"]],
            target: "current",
        });
    },

    async openInventoryMoves() {
        const selectedIds = this.inventoryDashboardState.selectedProductIds;
        const detail = this.getInventoryDetail();
        if (detail) {
            await this.openInventoryDetailInternalMoves();
            return;
        }
        if (selectedIds.length === 1) {
            const row = this.inventoryDashboardState.rows.find((inventoryRow) => inventoryRow.id === selectedIds[0]);
            if (row) {
                await this.openInventoryRow(row);
                await this.openInventoryDetailInternalMoves();
                return;
            }
        }
        this.notification.add(_t("Select a single inventory item to move."), {
            type: "warning",
        });
    },

    async openInventoryRow(row) {
        this.inventoryDashboardState.detail.open = true;
        this.inventoryDashboardState.detail.loading = true;
        this.inventoryDashboardState.detail.error = "";
        this.inventoryDashboardState.detail.mode = "overview";
        this.inventoryDashboardState.detail.moveForm = createEmptyMoveFormState();
        this.inventoryDashboardState.detail.item = null;
        try {
            this.inventoryDashboardState.detail.item = await this.loadInventoryDetail(row);
        } catch (error) {
            this.inventoryDashboardState.detail.error =
                error?.message || _t("Unable to load this item.");
        } finally {
            this.inventoryDashboardState.detail.loading = false;
        }
    },

    async openInventoryDetailForm() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: detail.title,
            res_model: "product.product",
            res_id: detail.id,
            views: [[false, "form"]],
            target: "current",
        });
    },

    async openInventoryDetailLocation() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        const domain = [["product_id", "=", detail.id]];
        if (detail.currentLocationId) {
            domain.push(["location_id", "=", detail.currentLocationId]);
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Current location"),
            res_model: "stock.quant",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain,
            target: "current",
        });
    },

    async openInventoryDetailMoves() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Move log"),
            res_model: "stock.move",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["product_id", "=", detail.id]],
            target: "current",
        });
    },

    async openInventoryDetailCheckout() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Check out"),
            res_model: "stock.move",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [
                ["product_id", "=", detail.id],
                ["location_dest_id.usage", "=", "customer"],
            ],
            target: "current",
        });
    },

    async openInventoryDetailRestock() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Restock"),
            res_model: "stock.move",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [
                ["product_id", "=", detail.id],
                ["location_id.usage", "=", "supplier"],
            ],
            target: "current",
        });
    },

    async openInventoryDetailInternalMoves() {
        const detail = this.getInventoryDetail();
        if (!detail) {
            return;
        }
        const moveForm = this.getInventoryMoveForm();
        this.inventoryDashboardState.detail.mode = "move";
        moveForm.loading = true;
        moveForm.error = "";
        moveForm.destinationLocationId = false;
        moveForm.assigneeId = false;
        moveForm.description = "";

        try {
            const [currentUserRecords, locationRecords, assigneeRecords, pickingTypes] = await Promise.all([
                this.orm.searchRead(
                    "res.users",
                    [["id", "=", this.user.userId]],
                    ["id", "login", "partner_id"],
                    { limit: 1 }
                ),
                this.orm.searchRead(
                    "stock.location",
                    [["usage", "=", "internal"]],
                    ["id", "name", "complete_name"],
                    { limit: 200, order: "complete_name" }
                ),
                this.orm.searchRead(
                    "res.users",
                    [["active", "=", true]],
                    ["id", "login", "partner_id"],
                    { limit: 200, order: "partner_id" }
                ),
                this.orm.searchRead(
                    "stock.picking.type",
                    [["code", "=", "internal"]],
                    ["id", "name", "default_location_src_id", "warehouse_id"],
                    { limit: 50 }
                ),
            ]);

            const currentUser = currentUserRecords[0]
                ? formatMoveFormUser(currentUserRecords[0])
                : null;
            const locationOptions = locationRecords.map((location) => ({
                id: location.id,
                name: normalizeText(location.name) || location.complete_name || "-",
                path: normalizeText(location.complete_name) || normalizeText(location.name) || "-",
            }));
            const assigneeOptions = assigneeRecords.map((userRecord) => formatMoveFormUser(userRecord));

            moveForm.currentUser = currentUser;
            moveForm.sourceLocationId = detail.currentLocationId || false;
            moveForm.locationOptions = locationOptions;
            moveForm.assigneeOptions = assigneeOptions;
            moveForm.pickingTypes = pickingTypes;
        } catch (error) {
            moveForm.error = error?.message || _t("Unable to load move form.");
        } finally {
            moveForm.loading = false;
        }
    },

    closeInventoryMoveMode() {
        this.inventoryDashboardState.detail.mode = "overview";
        this.inventoryDashboardState.detail.moveForm = createEmptyMoveFormState();
    },

    openInventoryMoveScanner() {
        this.notification.add(this.getInventoryMoveScanUnavailableLabel(), {
            type: "info",
        });
    },

    onInventoryMoveDestinationChange(ev) {
        const value = Number(ev.target.value || 0);
        this.getInventoryMoveForm().destinationLocationId = value || false;
    },

    onInventoryMoveAssigneeChange(ev) {
        const value = Number(ev.target.value || 0);
        this.getInventoryMoveForm().assigneeId = value || false;
    },

    onInventoryMoveDescriptionInput(ev) {
        this.getInventoryMoveForm().description = ev.target.value || "";
    },

    getInventoryMoveSourceLabel() {
        const moveForm = this.getInventoryMoveForm();
        const detail = this.getInventoryDetail();
        const sourceLocation = moveForm.locationOptions.find(
            (option) => option.id === moveForm.sourceLocationId
        );
        return sourceLocation?.path || detail?.currentLocationPath || "-";
    },

    getInventoryMoveDestinationOptions() {
        const moveForm = this.getInventoryMoveForm();
        return moveForm.locationOptions.filter(
            (option) => option.id !== moveForm.sourceLocationId
        );
    },

    getInventorySelectedAssignee() {
        const moveForm = this.getInventoryMoveForm();
        return (
            moveForm.assigneeOptions.find((option) => option.id === moveForm.assigneeId) || null
        );
    },

    getInventorySelectedAssigneeLabel() {
        const assignee = this.getInventorySelectedAssignee();
        if (!assignee) {
            return "";
        }
        return assignee.email && assignee.email !== "-" ? assignee.email : assignee.name;
    },

    async submitInventoryDetailMove() {
        const detail = this.getInventoryDetail();
        const moveForm = this.getInventoryMoveForm();
        if (!detail) {
            return;
        }

        if (!moveForm.destinationLocationId) {
            moveForm.error = _t("Choose a destination location.");
            return;
        }
        if (!moveForm.sourceLocationId) {
            moveForm.error = _t("This item does not have a current internal location yet.");
            return;
        }
        if (moveForm.destinationLocationId === moveForm.sourceLocationId) {
            moveForm.error = _t("Choose a different destination location.");
            return;
        }
        if (detail.onHandQty < 1) {
            moveForm.error = _t("This item has no on-hand stock available to move.");
            return;
        }

        moveForm.submitting = true;
        moveForm.error = "";

        try {
            const pickingType = chooseInternalPickingType(
                moveForm.pickingTypes,
                detail.currentLocationPath
            );
            if (!pickingType) {
                throw new Error(_t("No internal transfer operation type is configured."));
            }

            const payload = {
                picking_type_id: pickingType.id,
                location_id: moveForm.sourceLocationId,
                location_dest_id: moveForm.destinationLocationId,
                origin: _t("Inventory dashboard transfer"),
                note: normalizeText(moveForm.description) || false,
                user_id: moveForm.assigneeId || false,
                move_ids_without_package: [
                    [
                        0,
                        0,
                        {
                            name: detail.title,
                            product_id: detail.id,
                            product_uom_qty: 1,
                            product_uom: detail.uomId,
                            location_id: moveForm.sourceLocationId,
                            location_dest_id: moveForm.destinationLocationId,
                            description_picking: normalizeText(moveForm.description) || false,
                        },
                    ],
                ],
            };

            const pickingId = await this.orm.call("stock.picking", "create", [payload]);
            await this.orm.call("stock.picking", "action_confirm", [[pickingId]]);
            await this.orm.call("stock.picking", "action_assign", [[pickingId]]);

            await this.loadInventoryDashboardData();
            const refreshedRow =
                this.inventoryDashboardState.rows.find((row) => row.id === detail.id) ||
                this.inventoryDashboardState.rows[0];
            if (refreshedRow) {
                this.inventoryDashboardState.detail.item = await this.loadInventoryDetail(refreshedRow);
            }
            this.closeInventoryMoveMode();
            this.notification.add(_t("Internal transfer created."), { type: "success" });
        } catch (error) {
            moveForm.error = error?.message || _t("Unable to move this item.");
        } finally {
            moveForm.submitting = false;
        }
    },
});
