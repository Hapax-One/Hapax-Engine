/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillStart, useState } from "@odoo/owl";
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

function buildFilterOptions(rows, fieldName) {
    return [...new Set(rows.map((row) => row[fieldName]).filter(Boolean))].sort((left, right) =>
        left.localeCompare(right)
    );
}

patch(SpreadsheetDashboardAction.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
        this.inventoryDashboardState = useState(createEmptyInventoryState());

        onWillStart(async () => {
            await this.loadInventoryDashboardData();
        });
        onMounted(() => this.renderInventoryIcons());
        onPatched(() => this.renderInventoryIcons());
    },

    getInitialActiveDashboard() {
        return undefined;
    },

    renderInventoryIcons() {
        if (typeof lucide !== "undefined") {
            lucide.createIcons();
        }
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
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: _t("Move an item"),
            res_model: "stock.picking",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["picking_type_code", "=", "internal"]],
            target: "current",
        });
    },

    async openInventoryRow(row) {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: row.itemName,
            res_model: "product.product",
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    },
});
