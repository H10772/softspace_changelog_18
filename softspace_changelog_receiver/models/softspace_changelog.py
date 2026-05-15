from odoo import models, fields


class SoftspaceChangelog(models.Model):
    _name = 'softspace.changelog'
    _description = 'Changelog Entry'
    _order = 'release_date desc, received_date desc'

    name = fields.Char(string="Title", required=True)
    external_id = fields.Char(required=True, index=True)
    source_task_id = fields.Integer()
    version = fields.Char(index=True)
    release_date = fields.Date(index=True)
    change_type = fields.Selection([
        ('added', 'Added'),
        ('fixed', 'Fixed'),
        ('deleted', 'Deleted'),
        ('obsolete', 'Obsolete'),
        ('changed', 'Changed'),
    ], default='added')
    description = fields.Html()
    source_project = fields.Char()
    client_name = fields.Char()
    client_domain = fields.Char(index=True)
    active = fields.Boolean(default=True, index=True)
    received_date = fields.Datetime(default=fields.Datetime.now)
    last_update_date = fields.Datetime()

    _sql_constraints = [
        ('external_id_unique', 'unique(external_id)',
         'External ID must be unique!'),
    ]
