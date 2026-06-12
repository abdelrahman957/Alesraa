from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    driving_license_no = fields.Char(string='Driving License No')
    vat_valid_to = fields.Date(string='Valid Till')
    driving_license_valid_to = fields.Date(string='Valid Till')