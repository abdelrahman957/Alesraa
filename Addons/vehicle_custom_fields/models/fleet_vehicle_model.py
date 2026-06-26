from odoo import fields, models, api


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    vehicle_image = fields.Image(string='Vehicle Image')
    model_year = fields.Selection(required=True)

    @api.depends('name', 'brand_id', 'model_year')
    def _compute_display_name(self):
        for model in self:
            name = model.name or ''
            if model.brand_id:
                name = f"{model.brand_id.name}/{name}"
            if model.model_year:
                name = f"{name} ({model.model_year})"
            model.display_name = name