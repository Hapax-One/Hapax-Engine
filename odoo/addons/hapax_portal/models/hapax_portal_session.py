import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HapaxPortalSession(models.Model):
    _name = "hapax.portal.session"
    _description = "Hapax Portal Session"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        ondelete="cascade",
    )
    project_id = fields.Many2one(
        "hapax.project",
        required=True,
        index=True,
        check_company=True,
        ondelete="cascade",
    )
    membership_id = fields.Many2one(
        "hapax.membership",
        check_company=True,
        ondelete="set null",
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        check_company=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    scope = fields.Selection(
        [
            ("customer", "Customer"),
            ("admin", "Admin"),
            ("internal", "Internal"),
        ],
        required=True,
        default="customer",
        index=True,
    )
    token_hash = fields.Char(required=True, index=True)
    token_preview = fields.Char()
    expires_at = fields.Datetime(required=True, index=True)
    last_seen_at = fields.Datetime()
    revoked_at = fields.Datetime(index=True)
    user_agent = fields.Char()
    ip_address = fields.Char()

    _sql_constraints = [
        (
            "hapax_portal_session_token_hash_unique",
            "unique(token_hash)",
            "Portal session token hashes must be unique.",
        ),
    ]

    @api.constrains("project_id", "company_id", "membership_id", "user_id", "partner_id")
    def _check_scope(self):
        for record in self:
            if record.project_id.company_id != record.company_id:
                raise ValidationError("Portal session company must match the project company.")
            if record.membership_id and record.membership_id.project_id != record.project_id:
                raise ValidationError("Portal session membership must belong to the same project.")
            if record.user_id.partner_id != record.partner_id:
                raise ValidationError("Portal session user must match the linked contact.")

    @api.model
    def _hash_token(self, token):
        return hashlib.sha256((token or "").encode("utf-8")).hexdigest()

    @api.model
    def issue_for_user(
        self,
        project,
        user,
        membership=False,
        scope="customer",
        ttl_days=30,
        user_agent=None,
        ip_address=None,
    ):
        project.ensure_one()
        user.ensure_one()
        token = secrets.token_urlsafe(48)
        session = self.sudo().create(
            {
                "company_id": project.company_id.id,
                "project_id": project.id,
                "membership_id": membership.id if membership else False,
                "user_id": user.id,
                "partner_id": user.partner_id.id,
                "scope": scope,
                "token_hash": self._hash_token(token),
                "token_preview": token[:10],
                "expires_at": fields.Datetime.now() + timedelta(days=ttl_days),
                "user_agent": user_agent,
                "ip_address": ip_address,
            }
        )
        return {"token": token, "record": session}

    @api.model
    def authenticate_token(self, token, project=False):
        if not token:
            return self.browse()
        token_hash = self._hash_token(token)
        session = self.sudo().search(
            [
                ("token_hash", "=", token_hash),
                ("revoked_at", "=", False),
                ("expires_at", ">", fields.Datetime.now()),
            ],
            limit=1,
        )
        if not session:
            return self.browse()
        if project and session.project_id != project:
            return self.browse()
        session.sudo().write({"last_seen_at": fields.Datetime.now()})
        return session

    @api.model
    def revoke_token(self, token):
        session = self.authenticate_token(token)
        if session:
            session.sudo().write({"revoked_at": fields.Datetime.now()})
        return session

    def to_public_payload(self):
        self.ensure_one()
        return {
            "id": self.id,
            "scope": self.scope,
            "expiresAt": fields.Datetime.to_string(self.expires_at),
            "userId": self.user_id.id,
            "partnerId": self.partner_id.id,
            "membershipId": self.membership_id.id,
            "projectId": self.project_id.id,
        }
