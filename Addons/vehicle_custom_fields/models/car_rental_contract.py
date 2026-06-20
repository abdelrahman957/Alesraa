from odoo import fields, models, api
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError


class CarRentalContract(models.Model):
    _inherit = 'car.rental.contract'

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain=[('state', 'in', ['sale', 'done'])],
    )

    pickup_location = fields.Char(string='Pick Up Location')
    dropoff_location = fields.Char(string='Drop Off Location')

    vehicle_image_display = fields.Image(
        string='Vehicle Image',
        compute='_compute_vehicle_image_display',
        store=True,
    )

    def unlink(self):
        for contract in self:
            if contract.state not in ('draft', 'cancel'):
                raise UserError(
                    "You cannot delete a confirmed contract. "
                    "Please cancel it instead."
                )
        return super().unlink()

    def write(self, vals):
        res = super().write(vals)
        # لو اتغيّر تاريخ النهاية أو الحالة، حدّث الـ Return Date على العربية
        if 'rent_end_date' in vals or 'state' in vals:
            self.mapped('vehicle_id')._compute_rental_status()
        return res

    def action_confirm(self):
        res = super().action_confirm()
        for contract in self:
            already_set = contract.name and (contract.name.startswith('CORP/') or contract.name.startswith('RET/'))
            if not already_set:
                if contract.contract_type == 'corporate':
                    contract.name = self.env['ir.sequence'].next_by_code('car.rental.contract.corporate')
                elif contract.contract_type == 'retail':
                    contract.name = self.env['ir.sequence'].next_by_code('car.rental.contract.retail')
        return res

    @api.depends('vehicle_id', 'vehicle_id.vehicle_image')
    def _compute_vehicle_image_display(self):
        for contract in self:
            contract.vehicle_image_display = contract.vehicle_id.vehicle_image if contract.vehicle_id else False 

    @api.depends('vehicle_id', 'vehicle_id.vehicle_image')
    def _compute_contract_image(self):
        for contract in self:
            contract.image = contract.vehicle_id.vehicle_image if contract.vehicle_id else False
            
    exit_fuel = fields.Float(string='Exit Fuel (%)')

    exit_km = fields.Integer(string='Exit KM')

    return_km = fields.Float(string='Return KM')
    actual_return_date = fields.Date(string='Actual Return Date')
    has_damages = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Has Damages')
    estimated_cost = fields.Float(string='Estimated Cost')
    damage_description = fields.Text(string='Damage Description')
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

    @api.constrains('state', 'return_km', 'actual_return_date', 'has_damages')
    def _check_return_fields(self):
        for contract in self:
            if contract.state in ('checking', 'invoice', 'done'):
                if not contract.return_km or not contract.actual_return_date or not contract.has_damages:
                    raise ValidationError(
                        "Return KM, Actual Return Date, and Has Damages are required."
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

            # التأكد من وجود البنود الـ 3 الأساسية، وإضافة الناقص
            required_names = ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges']
            existing_names = self.checklist_line.mapped('name.name')
            for tool_name in required_names:
                if tool_name not in existing_names:
                    tool = self.env['car.tools'].search([('name', '=', tool_name)], limit=1)
                    if tool:
                        self.checklist_line = [(0, 0, {'name': tool.id, 'price': 0.0})]

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

    contract_type = fields.Selection(
        selection=[
            ('corporate', 'Corporate'),
            ('retail', 'Retail'),
        ],
        string='Contract Type',
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.contract_type == 'corporate':
                record.name = self.env['ir.sequence'].next_by_code('car.rental.contract.corporate')
            elif record.contract_type == 'retail':
                record.name = self.env['ir.sequence'].next_by_code('car.rental.contract.retail')
        return records

    @api.model
    def action_create_corporate(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'car.rental.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_contract_type': 'corporate'},
        }

    @api.model
    def action_create_retail(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'car.rental.contract',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_contract_type': 'retail'},
        }
    
    def action_open_return_wizard(self):
        self.ensure_one()
        return {
            'name': 'Vehicle Return',
            'type': 'ir.actions.act_window',
            'res_model': 'car.rental.return.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_return_km': self.return_km,
                'default_actual_return_date': self.actual_return_date,
                'default_has_damages': self.has_damages,
                'default_estimated_cost': self.estimated_cost,
                'default_damage_description': self.damage_description,
            },
        }       
                     
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