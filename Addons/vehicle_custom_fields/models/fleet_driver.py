from odoo import fields, models

class FleetDriver(models.Model):
    _name = "fleet.driver"
    _description = "Driver"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)