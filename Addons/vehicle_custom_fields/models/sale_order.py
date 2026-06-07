from odoo import fields, models, api
from odoo.exceptions import ValidationError


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

    sale_order_contract_ids = fields.One2many(
        'car.rental.contract',
        'sale_order_id',
        string='Rental Contracts',
    )
    rental_contract_count = fields.Integer(
        string='Rental Contracts',
        compute='_compute_rental_contract_count',
    )
    has_rental_contract = fields.Boolean(
        string='Has Rental Contract',
        compute='_compute_rental_contract_count',
        store=True,
    )

    @api.depends('rental_date_from', 'rental_date_to')
    def _compute_rental_duration(self):
        for order in self:
            if order.rental_date_from and order.rental_date_to:
                delta = order.rental_date_to - order.rental_date_from
                order.rental_duration = delta.days
            else:
                order.rental_duration = 0

    @api.depends('sale_order_contract_ids')
    def _compute_rental_contract_count(self):
        for order in self:
            contracts = order.sale_order_contract_ids
            order.rental_contract_count = len(contracts)
            order.has_rental_contract = bool(contracts)

    @api.constrains('rental_date_from', 'rental_date_to')
    def _check_rental_dates(self):
        for order in self:
            if order.rental_date_from and order.rental_date_to:
                if order.rental_date_to < order.rental_date_from:
                    raise ValidationError("End date cannot be before start date.")

    def action_view_rental_contracts(self):
        return {
            'name': 'Rental Contracts',
            'type': 'ir.actions.act_window',
            'res_model': 'car.rental.contract',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
        }