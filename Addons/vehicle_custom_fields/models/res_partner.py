from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    driving_license_no = fields.Char(string='Driving License No')