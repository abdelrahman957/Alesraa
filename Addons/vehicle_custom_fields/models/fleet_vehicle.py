from odoo import fields, models

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