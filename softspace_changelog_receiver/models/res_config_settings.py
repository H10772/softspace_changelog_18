import secrets
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    changelog_api_token = fields.Char(
        config_parameter='softspace_changelog.api_token',
    )
    changelog_hmac_secret = fields.Char(
        config_parameter='softspace_changelog.hmac_secret',
    )
    changelog_allowed_ips = fields.Char(
        config_parameter='softspace_changelog.allowed_ips',
        help="Comma-separated. Leave empty to allow all."
    )
    changelog_require_hmac = fields.Boolean(
        config_parameter='softspace_changelog.require_hmac',
    )
    changelog_max_request_age = fields.Integer(
        config_parameter='softspace_changelog.max_request_age',
        default=300,
    )

    def action_generate_api_token(self):
        token = secrets.token_urlsafe(32)
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.api_token', token)
        self.changelog_api_token = token

    def action_generate_hmac_secret(self):
        secret = secrets.token_urlsafe(48)
        self.env['ir.config_parameter'].sudo().set_param(
            'softspace_changelog.hmac_secret', secret)
        self.changelog_hmac_secret = secret
