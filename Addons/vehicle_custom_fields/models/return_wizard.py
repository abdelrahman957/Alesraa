from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CarRentalReturnWizard(models.TransientModel):
    _name = 'car.rental.return.wizard'
    _description = 'Car Rental Return Wizard'

    contract_id = fields.Many2one('car.rental.contract', string='Contract', required=True)
    return_km = fields.Float(string='Return KM')
    actual_return_date = fields.Date(string='Actual Return Date')
    has_damages = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Has Damages')

def action_confirm(self):
        self.ensure_one()
        # احفظ أي قيم مدخلة (حتى لو ناقصة)
        self.contract_id.write({
            'return_km': self.return_km,
            'actual_return_date': self.actual_return_date,
            'has_damages': self.has_damages,
        })
        # انقل الحالة لـ checking فقط لو الثلاثة كلهم متملّيين
        if self.return_km and self.actual_return_date and self.has_damages:
            return self.contract_id.force_checking()
        # غير كده اقفل الـ Wizard من غير ما يحصل حاجة
        return True