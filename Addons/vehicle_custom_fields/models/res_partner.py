from odoo import fields, models, api
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    driving_license_no = fields.Char(string='Driving License No')
    vat_valid_to = fields.Date(string='Valid To')
    driving_license_valid_to = fields.Date(string='Valid To')
    name_arabic = fields.Char(string='Arabic Name')

    @api.constrains('name_arabic')
    def _check_name_arabic(self):
        for partner in self:
            if partner.name_arabic:
                # يسمح بالحروف العربية والمسافات فقط
                if not re.fullmatch(r'[\u0600-\u06FF\s]+', partner.name_arabic):
                    raise ValidationError("الاسم بالعربي يجب أن يحتوي على حروف عربية فقط.")