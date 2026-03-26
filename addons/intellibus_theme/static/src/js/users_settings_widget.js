/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";
import { unique } from "@web/core/utils/arrays";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Component, onMounted, onPatched, onWillStart, useRef, useState } from "@odoo/owl";
/* global lucide */

const INTERNAL_USERS_DOMAIN = [["share", "=", false], ["active", "=", true]];
const USER_FIELDS = ["name", "login", "lang", "login_date", "company_id", "active", "groups_id"];

class IntellibusUsersSettings extends Component {
    static template = "intellibus_theme.IntellibusUsersSettings";
    static props = {
        ...standardWidgetProps,
    };

    setup() {
        this.orm = useService("orm");
        this.invite = useService("user_invite");
        this.action = useService("action");
        this.notification = useService("notification");
        this.emailInputRef = useRef("emailInput");

        this.state = useState({
            emails: "",
            invite: {
                pending_users: [],
                pending_count: 0,
                action_pending_users: null,
            },
            users: [],
            languageLabels: {},
            selectedUserIds: [],
            adminGroupId: null,
            status: "idle",
        });

        onWillStart(async () => {
            await Promise.all([this.refreshUsers(), this.refreshInviteData()]);
        });

        onMounted(() => this.renderIcons());
        onPatched(() => this.renderIcons());
    }

    renderIcons() {
        if (typeof lucide !== "undefined") {
            lucide.createIcons();
        }
    }

    get activeUsersLabel() {
        const count = this.activeUserCount;
        return count === 1
            ? _t("%(count)s Active User", { count })
            : _t("%(count)s Active Users", { count });
    }

    get manageUsersLabel() {
        return _t("Manage Users");
    }

    get inviteSectionTitle() {
        return _t("Invite team members");
    }

    get inviteSectionDescription() {
        return _t("Get your projects up and running faster by inviting your team to collaborate.");
    }

    get invitePlaceholder() {
        return _t("you@example.com");
    }

    get addAnotherLabel() {
        return _t("Add another");
    }

    get inviteHelperText() {
        return _t("Separate multiple email addresses with commas or line breaks.");
    }

    get pendingInvitationsLabel() {
        return _t("Pending invitations:");
    }

    getPendingMoreLabel(count) {
        return _t("%(count)s more", { count });
    }

    get teamMembersTitle() {
        return _t("Team members");
    }

    get teamMembersDescription() {
        return _t("Manage your existing team and change roles or permissions.");
    }

    get nameColumnLabel() {
        return _t("Name");
    }

    get loginColumnLabel() {
        return _t("Login");
    }

    get languageColumnLabel() {
        return _t("Language");
    }

    get latestAuthColumnLabel() {
        return _t("Latest Auth");
    }

    get companyColumnLabel() {
        return _t("Company");
    }

    get statusColumnLabel() {
        return _t("Status");
    }

    get noUsersLabel() {
        return _t("No team members found.");
    }

    get openUserLabel() {
        return _t("Open user");
    }

    get emails() {
        return unique(
            this.state.emails
                .split(/[ ,;\n]+/)
                .map((email) => email.trim())
                .filter(Boolean)
        );
    }

    get inviteButtonText() {
        return this.state.status === "inviting" ? _t("Sending...") : _t("Send invites");
    }

    get pendingUsers() {
        return this.state.invite.pending_users || [];
    }

    get activeUserCount() {
        return this.props.record.data.active_user_count || this.state.users.length;
    }

    get isAllSelected() {
        return this.state.users.length > 0 && this.state.selectedUserIds.length === this.state.users.length;
    }

    async refreshUsers() {
        const [languages, adminGroupData, users] = await Promise.all([
            this.orm.searchRead("res.lang", [], ["code", "name"]),
            this.orm.searchRead(
                "ir.model.data",
                [
                    ["module", "=", "base"],
                    ["name", "=", "group_system"],
                    ["model", "=", "res.groups"],
                ],
                ["res_id"],
                { limit: 1 }
            ),
            this.orm.searchRead("res.users", INTERNAL_USERS_DOMAIN, USER_FIELDS, {
                limit: 100,
                order: "name asc",
            }),
        ]);

        const adminGroupId = adminGroupData[0]?.res_id || null;

        this.state.languageLabels = Object.fromEntries(
            languages.map((language) => [language.code, language.name])
        );
        this.state.adminGroupId = adminGroupId || null;
        this.state.users = users.map((user) => this.enrichUser(user));
        this.state.selectedUserIds = this.state.selectedUserIds.filter((userId) =>
            this.state.users.some((user) => user.id === userId)
        );
    }

    async refreshInviteData(reload = false) {
        this.state.invite = await this.invite.fetchData(reload);
    }

    enrichUser(user) {
        return {
            ...user,
            avatarUrl: this.getAvatarUrl(user.id),
            companyName: user.company_id?.[1] || _t("No company"),
            languageLabel: this.state.languageLabels[user.lang] || user.lang || _t("Not set"),
            lastLoginLabel: user.login_date
                ? formatDateTime(deserializeDateTime(user.login_date))
                : _t("Never"),
            isAdmin:
                Boolean(this.state.adminGroupId) &&
                Array.isArray(user.groups_id) &&
                user.groups_id.includes(this.state.adminGroupId),
            statusLabel: this.getUserStatus(user),
        };
    }

    getAvatarUrl(userId) {
        return `/web/image?model=res.users&id=${userId}&field=avatar_128`;
    }

    getUserStatus(user) {
        if (!user.active) {
            return _t("Archived");
        }
        if (this.state.adminGroupId && user.groups_id?.includes(this.state.adminGroupId)) {
            return _t("Admin");
        }
        return _t("Member");
    }

    validateEmail(email) {
        const re =
            /^([a-z0-9][-a-z0-9_+.]*)@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,63}(?:\.[a-z]{2})?)$/i;
        return re.test(email);
    }

    validateEmails() {
        if (!this.emails.length) {
            throw new Error(_t("Empty email address"));
        }

        const invalidEmails = this.emails.filter((email) => !this.validateEmail(email));
        if (invalidEmails.length) {
            throw new Error(
                invalidEmails.length === 1
                    ? _t("Invalid email address: %(email)s", { email: invalidEmails[0] })
                    : _t("Invalid email addresses: %(emails)s", {
                          emails: invalidEmails.join(", "),
                      })
            );
        }
    }

    focusInviteInput() {
        this.emailInputRef.el?.focus();
    }

    async sendInvite() {
        try {
            this.validateEmails();
        } catch (error) {
            this.notification.add(error.message, { type: "danger" });
            return;
        }

        this.state.status = "inviting";
        const pendingUserEmails = this.pendingUsers.map((user) => user[1]);
        const emailsToProcess = this.emails.filter((email) => !pendingUserEmails.includes(email));

        try {
            if (emailsToProcess.length) {
                await this.orm.call("res.users", "web_create_users", [emailsToProcess]);
                await Promise.all([this.refreshInviteData(true), this.refreshUsers()]);
            }
        } finally {
            this.state.emails = "";
            this.state.status = "idle";
        }
    }

    onKeydownUserEmails(ev) {
        if (["Enter", "Tab", ","].includes(ev.key)) {
            if (ev.key === "Tab" && !this.emails.length) {
                return;
            }
            ev.preventDefault();
            this.sendInvite();
        }
    }

    onClickMore(ev) {
        if (this.state.invite.action_pending_users) {
            this.action.doAction(this.state.invite.action_pending_users);
        }
    }

    onClickPendingInvite(ev, pendingUser) {
        if (!this.state.invite.action_pending_users) {
            return;
        }
        const action = {
            ...this.state.invite.action_pending_users,
            res_id: pendingUser[0],
        };
        this.action.doAction(action);
    }

    openUsersList() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Users"),
            res_model: "res.users",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            target: "current",
            domain: INTERNAL_USERS_DOMAIN,
        });
    }

    openUser(userId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("User"),
            res_model: "res.users",
            res_id: userId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    toggleAllUsers(ev) {
        this.state.selectedUserIds = ev.target.checked ? this.state.users.map((user) => user.id) : [];
    }

    toggleUserSelection(userId, ev) {
        const selectedUserIds = new Set(this.state.selectedUserIds);
        if (ev.target.checked) {
            selectedUserIds.add(userId);
        } else {
            selectedUserIds.delete(userId);
        }
        this.state.selectedUserIds = [...selectedUserIds];
    }

    isUserSelected(userId) {
        return this.state.selectedUserIds.includes(userId);
    }
}

registry.category("view_widgets").add("intellibus_users_settings", {
    component: IntellibusUsersSettings,
});
