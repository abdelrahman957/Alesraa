from odoo import fields, models, api


class CarRentalContract(models.Model):
    _inherit = 'car.rental.contract'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain=[('state', 'in', ['sale', 'done'])],
    )
    delivery_location = fields.Char(string='Delivery Location')

    image = fields.Binary(related='vehicle_id.vehicle_image')

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            self.customer_id = self.sale_order_id.partner_id
            self.rent_start_date = self.sale_order_id.rental_date_from
            self.rent_end_date = self.sale_order_id.rental_date_to
            self.delivery_location = self.sale_order_id.delivery_location


    rental_period_days = fields.Integer(
        string='Rental Period (Days)',
        compute='_compute_rental_period_days',
    )

    @api.depends('rent_start_date', 'rent_end_date')
    def _compute_rental_period_days(self):
        for contract in self:
            if contract.rent_start_date and contract.rent_end_date:
                contract.rental_period_days = (contract.rent_end_date - contract.rent_start_date).days
            else:
                contract.rental_period_days = 0 