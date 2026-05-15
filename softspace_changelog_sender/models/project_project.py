from odoo import models, fields, api
from odoo.exceptions import UserError


class Project(models.Model):
    _inherit = 'project.project'

    enable_changelog_push = fields.Boolean(
        help="Publish changelogs from tasks in this project."
    )
    client_endpoint_id = fields.Many2one(
        'softspace.client.endpoint', string="Client",
    )
    changelog_stage_id = fields.Many2one(
        'project.task.type', string="Auto-Publish Stage",
        help="Tasks moved to this stage will be published automatically."
    )

    @api.constrains('enable_changelog_push', 'client_endpoint_id')
    def _check_changelog_settings(self):
        for project in self:
            if project.enable_changelog_push and not project.client_endpoint_id:
                raise UserError("Please select a Client before enabling Changelog Push.")
