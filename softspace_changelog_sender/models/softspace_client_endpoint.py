import secrets
import requests as ext_requests
from odoo import models, fields, api


class SoftspaceClientEndpoint(models.Model):
    _name = 'softspace.client.endpoint'
    _description = 'Client Odoo Endpoint'
    _order = 'name'

    name = fields.Char(required=True, help="Client identifier, e.g. uapp, injaz")
    domain = fields.Char(
        string="Client Domain", required=True,
        help="e.g. odoo.uapp.com"
    )
    use_https = fields.Boolean(default=True)
    api_path = fields.Char(default="/api/changelog")
    api_url = fields.Char(
        compute='_compute_api_url', store=True, readonly=False,
    )
    api_token = fields.Char(
        required=True, groups="base.group_system",
    )
    hmac_secret = fields.Char(groups="base.group_system")
    use_hmac = fields.Boolean(string="Sign Requests (HMAC)")
    active = fields.Boolean(default=True)
    notes = fields.Text()
    last_health_check = fields.Datetime(readonly=True)
    health_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('ok', 'Healthy'),
        ('failed', 'Unreachable'),
    ], default='unknown', readonly=True)

    @api.depends('domain', 'use_https', 'api_path')
    def _compute_api_url(self):
        for rec in self:
            if rec.domain:
                protocol = 'https' if rec.use_https else 'http'
                domain = rec.domain.strip().rstrip('/')
                path = (rec.api_path or '/api/changelog').strip()
                rec.api_url = f"{protocol}://{domain}{path}"
            elif not rec.api_url:
                rec.api_url = False

    def action_generate_token(self):
        self.ensure_one()
        self.api_token = secrets.token_urlsafe(32)

    def action_generate_hmac_secret(self):
        self.ensure_one()
        self.hmac_secret = secrets.token_urlsafe(48)

    def action_check_health(self):
        self.ensure_one()
        if not self.api_url:
            return
        base = self.api_url.rstrip('/').rsplit('/api/changelog', 1)[0]
        health_url = base + '/api/changelog/health'
        try:
            resp = ext_requests.get(health_url, timeout=5)
            self.health_status = 'ok' if resp.status_code == 200 else 'failed'
        except Exception:
            self.health_status = 'failed'
        self.last_health_check = fields.Datetime.now()
