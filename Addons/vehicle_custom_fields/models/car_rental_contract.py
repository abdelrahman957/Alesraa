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
        # لما العقد يوصل لحالة invoice، خلي rent_end_date = actual_return_date
        if vals.get('state') == 'invoice':
            for contract in self:
                if contract.actual_return_date:
                    contract.rent_end_date = contract.actual_return_date
                # سجّل تاريخ رد التأمين (دخول invoice + يومين) لو لسه متسجّلش
                if not contract.insurance_refund_date:
                    from datetime import timedelta
                    contract.insurance_refund_date = fields.Date.context_today(self) + timedelta(days=2)
        if 'rent_end_date' in vals or 'state' in vals or 'first_invoice_created' in vals:
            self.mapped('vehicle_id')._compute_rental_status()
        return res
    
    def action_verify(self):
        res = super().action_verify()
        for contract in self:
            if contract.actual_return_date:
                contract.rent_end_date = contract.actual_return_date
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
    insurance_amount = fields.Float(
        string='Insurance',
        compute='_compute_charge_amounts',
        store=True,
    )
    full_coverage_amount = fields.Float(
        string='Full Coverage Insurance',
        compute='_compute_charge_amounts',
    )
    paid_deposit_amount = fields.Float(
        string='Paid Deposit',
        compute='_compute_paid_deposit',
    )

    @api.depends('sale_order_id', 'sale_order_id.invoice_ids', 'sale_order_id.invoice_ids.payment_state')
    def _compute_paid_deposit(self):
        for contract in self:
            total = 0.0
            if contract.sale_order_id:
                # فواتير الـ down payment المدفوعة بالكامل
                downpayment_invoices = contract.sale_order_id.invoice_ids.filtered(
                    lambda inv: inv.payment_state == 'paid'
                    and any(line.is_downpayment for line in inv.invoice_line_ids)
                )
                total = sum(downpayment_invoices.mapped('amount_total'))
            contract.paid_deposit_amount = total

    net_requested_charge = fields.Float(
        string='Net Requested Charge',
        compute='_compute_charge_amounts',
    )

    @api.constrains('state', 'return_km', 'actual_return_date', 'has_damages', 'damage_description')
    def _check_return_fields(self):
        for contract in self:
            if contract.state in ('checking', 'invoice', 'done'):
                if not contract.return_km or not contract.actual_return_date or not contract.has_damages:
                    raise ValidationError(
                        "Return KM, Actual Return Date, and Has Damages are required."
                    )
                if contract.has_damages == 'yes' and not contract.damage_description:
                    raise ValidationError(
                        "Damage Description is required when there are damages."
                    )
                
    def _default_checklist_line(self):
        tools = self.env['car.tools'].search([
            ('name', 'in', ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges', 'Refundable Insurance', 'Full Coverage Insurance']),
        ])
        return [(0, 0, {'name': tool.id, 'price': 0.0}) for tool in tools]

    @api.depends('rent_start_date', 'rent_end_date')
    def _compute_rental_period_days(self):
        for contract in self:
            if contract.rent_start_date and contract.rent_end_date:
                contract.rental_period_days = (contract.rent_end_date - contract.rent_start_date).days
            else:
                contract.rental_period_days = 0

    @api.depends('checklist_line', 'checklist_line.price', 'checklist_line.name', 'paid_deposit_amount')
    def _compute_charge_amounts(self):
        for contract in self:
            rent = pickup = dropoff = insurance = full_cov = 0.0
            for line in contract.checklist_line:
                name = line.name.name if line.name else ''
                if name == 'Rent Fees':
                    rent += line.price
                elif name == 'Pick Up Charges':
                    pickup += line.price
                elif name == 'Drop Off Charges':
                    dropoff += line.price
                elif name == 'Refundable Insurance':
                    insurance += line.price
                elif name == 'Full Coverage Insurance':
                    full_cov += line.price
            contract.rent_fees_amount = rent
            contract.pickup_charge_amount = pickup
            contract.dropoff_charge_amount = dropoff
            contract.insurance_amount = insurance
            contract.full_coverage_amount = full_cov
            contract.total_requested_charge = rent + pickup + dropoff + insurance + full_cov
            contract.net_requested_charge = contract.total_requested_charge - contract.paid_deposit_amount

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            self.customer_id = self.sale_order_id.partner_id
            self.rent_start_date = self.sale_order_id.rental_date_from
            self.rent_end_date = self.sale_order_id.rental_date_to
            self.pickup_location = self.sale_order_id.pickup_location
            self.dropoff_location = self.sale_order_id.dropoff_location

            # التأكد من وجود البنود الـ 3 الأساسية، وإضافة الناقص
            required_names = ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges', 'Refundable Insurance', 'Full Coverage Insurance']
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

    @api.constrains('sale_order_id')
    def _check_unique_sale_order(self):
        for contract in self:
            if contract.sale_order_id:
                other = self.search([
                    ('sale_order_id', '=', contract.sale_order_id.id),
                    ('id', '!=', contract.id),
                ], limit=1)
                if other:
                    raise ValidationError(
                        "This Sale Order is already linked to another contract."
                    )   
                
    allowed_model_ids = fields.Many2many(
        'fleet.vehicle.model',
        string='Allowed Models',
        compute='_compute_allowed_models',
    )

    @api.depends('sale_order_id', 'sale_order_id.order_line.product_id')
    def _compute_allowed_models(self):
        all_models = self.env['fleet.vehicle.model'].search([])
        for contract in self:
            if contract.sale_order_id:
                vehicle_lines = contract.sale_order_id.order_line.filtered(
                    lambda l: l.product_id.is_vehicle
                )
                models = vehicle_lines.mapped('product_id.product_tmpl_id.fleet_model_id')
                contract.allowed_model_ids = models if models else all_models
            else:
                contract.allowed_model_ids = all_models

    @api.constrains('vehicle_id', 'state')
    def _check_vehicle_availability(self):
        for contract in self:
            if contract.state in ('running', 'checking') and contract.vehicle_id:
                other = self.search([
                    ('vehicle_id', '=', contract.vehicle_id.id),
                    ('id', '!=', contract.id),
                    ('state', 'in', ['running', 'checking']),
                ], limit=1)
                if other:
                    raise ValidationError(
                        "This vehicle is already rented in another active contract."
                    )
                
    @api.constrains('exit_km', 'state')
    def _check_exit_km(self):
        for contract in self:
            if contract.state in ('reserved', 'running', 'checking', 'invoice', 'done'):
                if not contract.exit_km or contract.exit_km <= 0:
                    raise ValidationError(
                        "Exit KM is required and must be greater than zero."
                    )
    
    consumed_km = fields.Integer(string='Consumed KM')
    km_per_day = fields.Integer(string='KM Per Day')
    extra_km = fields.Integer(string='Extra KM')
    extra_km_price = fields.Float(string='Extra KM Price')
    total_ex_km_amount = fields.Float(string='Total EX KM Amount')

    extra_days = fields.Integer(string='Extra Days')
    extra_days_amount = fields.Float(string='Extra Days Amount')
    day_rate = fields.Float(string='Day Rate')
    net_insurance_refund = fields.Float(
        string='Net Insurance Refund',
        compute='_compute_net_insurance_refund',
        store=True,
    )
    total_paid_amount = fields.Float(
        string='Total Paid',
        compute='_compute_total_paid',
    )
    balance_due = fields.Float(
        string='Balance Due',
        compute='_compute_total_paid',
    )
    final_net_payable = fields.Float(
        string='Net Payable by Customer',
        compute='_compute_net_insurance_refund',
    )
    insurance_refund_done = fields.Boolean(
        string='Insurance Refund Done',
        default=False,
        copy=False,
    )
    total_deductions = fields.Float(
        string='Total Deductions',
        compute='_compute_total_deductions',
        store=True,
    )
    insurance_refund_date = fields.Date(
        string='Insurance Refund Date',
        copy=False,
    )
    insurance_overdue = fields.Boolean(
        string='Insurance Overdue',
        compute='_compute_insurance_overdue',
        search='_search_insurance_overdue',
    )

    @api.depends('insurance_amount', 'net_insurance_refund')
    def _compute_total_deductions(self):
        for contract in self:
            contract.total_deductions = (contract.insurance_amount or 0) - (contract.net_insurance_refund or 0)

    @api.depends('insurance_refund_date', 'insurance_refund_done')
    def _compute_insurance_overdue(self):
        today = fields.Date.context_today(self)
        for contract in self:
            contract.insurance_overdue = bool(
                contract.insurance_refund_date
                and not contract.insurance_refund_done
                and contract.insurance_refund_date < today
            )

    def _search_insurance_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        # نرجّع domain للعقود المتأخرة
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [
                ('insurance_refund_date', '<', today),
                ('insurance_refund_done', '=', False),
            ]
        else:
            return ['|',
                ('insurance_refund_date', '>=', today),
                ('insurance_refund_done', '=', True),
            ]

    def action_open_insurance_refund(self):
        self.ensure_one()
        direction = 'Refund to Customer' if self.net_insurance_refund > 0 else ('Collect from Customer' if self.net_insurance_refund < 0 else 'Settled')
        return {
            'name': 'Refund Insurance',
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.refund.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_contract_id': self.id,
                'default_insurance_amount': self.insurance_amount,
                'default_extra_km_amount': self.total_ex_km_amount,
                'default_extra_days_amount': abs(self.extra_days_amount or 0),
                'default_damages_amount': self.estimated_cost if self.has_damages == 'yes' else 0.0,
                'default_net_amount': self.net_insurance_refund,
                'default_direction': direction,
            },
        }

    @api.depends('sale_order_id', 'sale_order_id.invoice_ids',
                 'sale_order_id.invoice_ids.payment_state',
                 'total_requested_charge')
    def _compute_total_paid(self):
        for contract in self:
            paid = 0.0
            # مدفوعات فواتير العقد
            contract_invoices = self.env['account.move'].search([
                ('fleet_rent_id', '=', contract.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ])
            for inv in contract_invoices:
                paid += (inv.amount_total - inv.amount_residual)
            # مدفوعات الـ down payment على الـ SO
            if contract.sale_order_id:
                dp_invoices = contract.sale_order_id.invoice_ids.filtered(
                    lambda i: i.state == 'posted'
                    and any(l.is_downpayment for l in i.invoice_line_ids)
                )
                for inv in dp_invoices:
                    paid += (inv.amount_total - inv.amount_residual)
            contract.total_paid_amount = paid
            contract.balance_due = contract.total_requested_charge - paid

    @api.depends('insurance_amount', 'total_ex_km_amount', 'estimated_cost',
                 'has_damages', 'extra_days_amount', 'balance_due')
    def _compute_net_insurance_refund(self):
        for contract in self:
            deductions = (contract.total_ex_km_amount or 0)
            if contract.has_damages == 'yes':
                deductions += (contract.estimated_cost or 0)
            deductions += abs(contract.extra_days_amount or 0)
            net_refund = (contract.insurance_amount or 0) - deductions
            contract.net_insurance_refund = net_refund
            contract.final_net_payable = net_refund - contract.balance_due

    def action_print_settlement(self):
        self.ensure_one()
        return self.env.ref(
            'vehicle_custom_fields.action_report_customer_settlement'
        ).report_action(self)

    def action_invoice_create(self):
        res = super().action_invoice_create()
        for contract in self:
            # هات الفاتورة اللي اتعملت
            invoice = contract.first_payment_inv
            if not invoice:
                continue

            # منتج الخدمة والحساب (نفس اللي بيستخدمه الأصلي)
            product_id = self.env['product.product'].browse(
                self.env.ref('fleet_rental.fleet_service_product').id)
            if product_id.property_account_income_id.id:
                income_account = product_id.property_account_income_id.id
            elif product_id.categ_id.property_account_income_categ_id.id:
                income_account = product_id.categ_id.property_account_income_categ_id.id
            else:
                continue

            # امسح السطور القديمة (سطر الـ first_payment الفاضي)
            invoice.invoice_line_ids.unlink()

            # ابني السطور المنفصلة
            lines = []
            charge_items = [
                ('Rent Fees', contract.rent_fees_amount),
                ('Pick Up Charges', contract.pickup_charge_amount),
                ('Drop Off Charges', contract.dropoff_charge_amount),
                ('Full Coverage Insurance', contract.full_coverage_amount),
            ]
            for label, amount in charge_items:
                if amount and amount > 0:
                    lines.append((0, 0, {
                        'name': label,
                        'price_unit': amount,
                        'quantity': 1.0,
                        'account_id': income_account,
                        'product_id': product_id.id,
                        'move_id': invoice.id,
                    }))

            # سطر Refundable Insurance على حساب الـ Liability (مش الإيراد)
            if contract.insurance_amount and contract.insurance_amount > 0:
                liability_account = self.env['account.account'].search([
                    ('code', '=', '212001'),
                ], limit=1)
                if liability_account:
                    lines.append((0, 0, {
                        'name': 'Refundable Insurance',
                        'price_unit': contract.insurance_amount,
                        'quantity': 1.0,
                        'account_id': liability_account.id,
                        'product_id': product_id.id,
                        'move_id': invoice.id,
                    }))

            # سطر الـ Paid Deposit بالسالب (خصم)
            if contract.paid_deposit_amount and contract.paid_deposit_amount > 0:
                lines.append((0, 0, {
                    'name': 'Paid Deposit (Down Payment)',
                    'price_unit': -contract.paid_deposit_amount,
                    'quantity': 1.0,
                    'account_id': income_account,
                    'product_id': product_id.id,
                    'move_id': invoice.id,
                }))

            if lines:
                invoice.write({'invoice_line_ids': lines})
        return res
    
                     
class CarTools(models.Model):
    _inherit = 'car.tools'

    def unlink(self):
        protected_names = ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges', 'Refundable Insurance', 'Full Coverage Insurance']
        for tool in self:
            if tool.name in protected_names:
                raise ValidationError(
                    "You cannot delete the default items (Rent Fees, Pick Up Charges, Drop Off Charges, Refundable Insurance, Full Coverage Insurance)."
                )
        return super().unlink()
    
class CarRentalChecklist(models.Model):
    _inherit = 'car.rental.checklist'

    def unlink(self):
        protected_names = ['Rent Fees', 'Pick Up Charges', 'Drop Off Charges',
                           'Refundable Insurance', 'Full Coverage Insurance']
        for line in self:
            tool_name = line.name.name if line.name else ''
            if tool_name in protected_names:
                raise ValidationError(
                    "You cannot delete the default charge items from the contract."
                )
        return super().unlink()