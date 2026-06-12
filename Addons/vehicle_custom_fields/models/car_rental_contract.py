from odoo import fields, models, api
from odoo.exceptions import ValidationError


class CarRentalContract(models.Model):
    _inherit = 'car.rental.contract'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain=[('state', 'in', ['sale', 'done'])],
    )

    pickup_location = fields.Char(string='Pick Up Location')
    dropoff_location = fields.Char(string='Drop Off Location')

    image = fields.Binary(related='vehicle_id.vehicle_image')

    exit_fuel = fields.Float(string='Exit Fuel (%)')

    rental_period_days = fields.Integer(
        string='Rental Period (Days)',
        compute='_compute_rental_period_days',
    )

    checklist_line = fields.One2many(
        default=lambda self: self._default_checklist_line(),
    )

    rent_fees_amount = fields.Float(
        string='Rent Fees',
        compute='_compute_charge_amounts',
    )
    pickup_charge_amount = fields.Float(
        string='Pick Up Charge',
        compute='_compute_charge_amounts',
    )
    dropoff_charge_amount = fields.Float(
        string='Drop Off Charge',
        compute='_compute_charge_amounts',
    )
    total_requested_charge = fields.Float(
        string='Total Requested Charge',
        compute='_compute_charge_amounts',
    )

    def _default_checklist_line(self):
        tools = self.env['car.tools'].search([
            ('name', 'in', ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges'])
        ])
        return [(0, 0, {'name': tool.id, 'price': 0.0}) for tool in tools]

    @api.depends('rent_start_date', 'rent_end_date')
    def _compute_rental_period_days(self):
        for contract in self:
            if contract.rent_start_date and contract.rent_end_date:
                contract.rental_period_days = (contract.rent_end_date - contract.rent_start_date).days
            else:
                contract.rental_period_days = 0

    @api.depends('checklist_line', 'checklist_line.price', 'checklist_line.name')
    def _compute_charge_amounts(self):
        for contract in self:
            rent = pickup = dropoff = 0.0
            for line in contract.checklist_line:
                name = line.name.name if line.name else ''
                if name == 'Rent Fees':
                    rent += line.price
                elif name == 'Pick Up Charges':
                    pickup += line.price
                elif name == 'Drop Off Charges':
                    dropoff += line.price
            contract.rent_fees_amount = rent
            contract.pickup_charge_amount = pickup
            contract.dropoff_charge_amount = dropoff
            contract.total_requested_charge = rent + pickup + dropoff

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            self.customer_id = self.sale_order_id.partner_id
            self.rent_start_date = self.sale_order_id.rental_date_from
            self.rent_end_date = self.sale_order_id.rental_date_to
            self.pickup_location = self.sale_order_id.pickup_location
            self.dropoff_location = self.sale_order_id.dropoff_location

            # ملء البنود من سطور الـ SO
            for line in self.checklist_line:
                line.price = 0.0  # تصفير القيمة الأول
                tool_name = line.name.name
                if tool_name == 'Rent Fees':
                    vehicle_lines = self.sale_order_id.order_line.filtered(
                        lambda l: l.product_id.is_vehicle
                    )
                    if vehicle_lines:
                        line.price = sum(vehicle_lines.mapped('price_subtotal'))
                else:
                    matching = self.sale_order_id.order_line.filtered(
                        lambda l: l.product_id.name == tool_name
                    )
                    if matching:
                        line.price = matching[0].price_subtotal


class CarTools(models.Model):
    _inherit = 'car.tools'

    def unlink(self):
        protected_names = ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges']
        for tool in self:
            if tool.name in protected_names:
                raise ValidationError(
                    "You cannot delete the default items (Rent Fees, Pick Up Charges, Drop Off Charges)."
                )
        return super().unlink()