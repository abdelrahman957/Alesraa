from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    interested_vehicle_ids = fields.Many2many(
        'product.product',
        string='Interested Vehicles',
        domain="[('is_vehicle', '=', True)]",
    )