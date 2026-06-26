from odoo import fields, models, api
from odoo.exceptions import ValidationError


class FleetExtraKm(models.Model):
    _name = 'fleet.extra.km'
    _description = 'Extra KM Configuration'

    model_ids = fields.Many2many(
        'fleet.vehicle.model',
        string='Model',
    )
    km_per_day = fields.Integer(string='KM Per Day', required=True)
    extra_km_price = fields.Float(string='Extra KM Price', required=True)

    @api.constrains('model_ids')
    def _check_unique_model(self):
        for record in self:
            for model in record.model_ids:
                # دوّر على أي سطر تاني فيه نفس الموديل
                other = self.search([
                    ('id', '!=', record.id),
                    ('model_ids', 'in', model.id),
                ], limit=1)
                if other:
                    raise ValidationError(
                        "Model '%s' already exists in another line." % model.display_name
                    )