from odoo import fields, models, api


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    has_gps = fields.Boolean(string='GPS')
    driving_license_expiry = fields.Date(string='Driving License Expiry Date')
    motor_number = fields.Char(string='Motor Number')
    insurance_type_id = fields.Many2one(
        'fleet.vehicle.insurance.type',
        string='Insurance Type'
    )
    insurance_end_date = fields.Date(string='Insurance End Date')
    gps_installation_date = fields.Date(string='GPS Installation Date')

    # Computed fields from the active contract's insurer_id
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        compute='_compute_owner_fields',
        store=True,
    )
    owner_mobile = fields.Char(
        string='Mobile',
        compute='_compute_owner_fields',
        store=True,
    )
    owner_vat = fields.Char(
        string='ID',
        compute='_compute_owner_fields',
        store=True,
    )
    
    vehicle_image = fields.Image(
        string='Vehicle Image',
        related='model_id.vehicle_image',
        store=True,
    )

    @api.depends('log_contracts', 'log_contracts.insurer_id', 'log_contracts.state')
    def _compute_owner_fields(self):
        for vehicle in self:
            # Get the most recent running contract that has an insurer
            contract = self.env['fleet.vehicle.log.contract'].search([
                ('vehicle_id', '=', vehicle.id),
                ('insurer_id', '!=', False),
                ('state', 'in', ['open', 'running']),
            ], order='date desc', limit=1)

            # Fallback: any contract with insurer if no running one found
            if not contract:
                contract = self.env['fleet.vehicle.log.contract'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('insurer_id', '!=', False),
                ], order='date desc', limit=1)

            if contract and contract.insurer_id:
                vehicle.owner_id = contract.insurer_id
                vehicle.owner_mobile = contract.insurer_id.phone or False
                vehicle.owner_vat = contract.insurer_id.vat or False
            else:
                vehicle.owner_id = False
                vehicle.owner_mobile = False
                vehicle.owner_vat = False
                
    @api.depends('model_id')
    def _compute_color(self):
        for vehicle in self:
            # لو فيه لون متخزن، سيبه؛ لو لأ، خليه فاضي
            if not vehicle.color or vehicle.color == '#FFFFFF':
                vehicle.color = False