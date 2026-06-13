from odoo import fields, models, api
from odoo.exceptions import ValidationError

class FleetVehicleLogServices(models.Model):
    _inherit = 'fleet.vehicle.log.services'

    service_category = fields.Selection(
        selection=[
            ('periodic', 'Periodic Maintenance'),
            ('accident', 'Accident'),
        ],
        string='Service Category',
    )
    service_type_id = fields.Many2one(
        required=False,
    )
    responsibility = fields.Selection(
        selection=[
            ('owner', 'Owner'),
            ('company', 'Company'),
        ],
        string='Responsibility',
    )
    service_line_ids = fields.One2many(
        'fleet.service.line',
        'service_id',
        string='Service Lines',
    )
    amount = fields.Monetary(
        string='Cost',
        compute='_compute_amount_from_lines',
        store=True,
        readonly=True,
    )

    @api.depends('service_line_ids', 'service_line_ids.amount')
    def _compute_amount_from_lines(self):
        for service in self:
            service.amount = sum(service.service_line_ids.mapped('amount'))

    @api.constrains('service_line_ids')
    def _check_service_lines(self):
        for service in self:
            if not service.service_line_ids:
                raise ValidationError(
                    "You must add at least one service line."
                )
            for line in service.service_line_ids:
                if not line.service_type_id:
                    raise ValidationError(
                        "Service Type is required for each service line."
                    )


class FleetServiceLine(models.Model):
    _name = 'fleet.service.line'
    _description = 'Fleet Service Line'

    service_id = fields.Many2one(
        'fleet.vehicle.log.services',
        string='Service',
        required=True,
        ondelete='cascade',
    )
    service_type_id = fields.Many2one(
        'fleet.service.type',
        string='Service Type',
        required=True,
    )
    description = fields.Char(string='Description')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one(
        'res.currency',
        related='service_id.currency_id',
    )