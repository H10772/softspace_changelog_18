from datetime import timedelta
from odoo import models, fields


class ChangelogApiLog(models.Model):
    _name = 'softspace.changelog.api.log'
    _description = 'API Request Audit Log'
    _order = 'create_date desc'
    _log_access = True

    request_ip = fields.Char(index=True)
    request_method = fields.Char()
    request_path = fields.Char()
    status_code = fields.Integer()
    status = fields.Selection([
        ('success', 'Success'),
        ('auth_failed', 'Auth Failed'),
        ('rate_limited', 'Rate Limited'),
        ('bad_request', 'Bad Request'),
        ('error', 'Server Error'),
    ], index=True)
    error_message = fields.Text()
    external_id = fields.Char(index=True)
    hmac_valid = fields.Boolean()
    response_time_ms = fields.Float()

    def _gc_old_logs(self):
        """Remove logs older than 30 days. Called by scheduled action."""
        cutoff = fields.Datetime.now() - timedelta(days=30)
        self.search([('create_date', '<', cutoff)]).unlink()
        return True
