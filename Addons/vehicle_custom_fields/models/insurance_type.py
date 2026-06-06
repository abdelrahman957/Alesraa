from odoo import fields, models

class FleetVehicleInsuranceType(models.Model):
    _name = 'fleet.vehicle.insurance.type'
    _description = 'Fleet Vehicle Insurance Type'

    name = fields.Char(string='Insurance Type', required=True)