from odoo import fields, models, api


class CarRentalContract(models.Model):
    _inherit = 'car.rental.contract'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain=[('state', 'in', ['sale', 'done'])],
    )
    delivery_location = fields.Char(string='Delivery Location')

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            self.customer_id = self.sale_order_id.partner_id
            self.rent_start_date = self.sale_order_id.rental_date_from
            self.rent_end_date = self.sale_order_id.rental_date_to
            self.delivery_location = self.sale_order_id.delivery_location