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

    estimated_cost = fields.Float(string='Estimated Cost')
    damage_description = fields.Text(string='Damage Description')
    from_fleet = fields.Boolean(string='From Fleet', default=False)

    def action_confirm(self):
        self.ensure_one()
        # لو فيه تلفيات لازم بيان التلفيات
        if self.has_damages == 'yes' and not self.damage_description:
            raise ValidationError("Damage Description is required when there are damages.")
        # احفظ أي قيم مدخلة (حتى لو ناقصة)
        self.contract_id.write({
            'return_km': self.return_km,
            'actual_return_date': self.actual_return_date,
            'has_damages': self.has_damages,
            'estimated_cost': self.estimated_cost,
            'damage_description': self.damage_description,
        })
        # انقل الحالة لـ checking فقط لو الثلاثة كلهم متملّيين
        if self.return_km and self.actual_return_date and self.has_damages:
            return self.contract_id.force_checking()
        return True