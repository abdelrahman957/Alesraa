from odoo import fields, models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    rental_date_from = fields.Date(string='From')
    rental_date_to = fields.Date(string='To')
    rental_duration = fields.Integer(
        string='Duration',
        compute='_compute_rental_duration',
        store=True,
    )
    delivery_location = fields.Text(string='Delivery Location')

    @api.depends('rental_date_from', 'rental_date_to')
    def _compute_rental_duration(self):
        for order in self:
            if order.rental_date_from and order.rental_date_to:
                delta = order.rental_date_to - order.rental_date_from
                order.rental_duration = delta.days
            else:
                order.rental_duration = 0