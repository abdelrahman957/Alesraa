from odoo import fields, models


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    vehicle_image = fields.Image(string='Vehicle Image')