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

    consumed_km = fields.Integer(
        string='Consumed KM',
        compute='_compute_extra_km_fields',
    )
    km_per_day = fields.Integer(
        string='KM Per Day',
        compute='_compute_km_settings',
        readonly=False,
        store=True,
    )
    extra_km_price = fields.Float(
        string='Extra KM Price',
        compute='_compute_km_settings',
        readonly=False,
        store=True,
    )
    extra_km = fields.Integer(
        string='Extra KM',
        compute='_compute_extra_km_fields',
    )
    total_ex_km_amount = fields.Float(
        string='Total EX KM Amount',
        compute='_compute_extra_km_fields',
    )

    insurance_amount = fields.Float(
        string='Insurance',
        related='contract_id.insurance_amount',
    )
    extra_days = fields.Integer(
        string='Extra Days',
        compute='_compute_insurance_calc',
    )
    ex_km_deduction = fields.Float(
        string='Total EX KM',
        compute='_compute_insurance_calc',
    )
    estimated_cost_deduction = fields.Float(
        string='Estimated Cost',
        compute='_compute_insurance_calc',
    )
    net_insurance = fields.Float(
        string='Net Insurance',
        compute='_compute_insurance_calc',
    )

    @api.depends('insurance_amount', 'total_ex_km_amount', 'estimated_cost', 'has_damages', 'actual_return_date')
    def _compute_insurance_calc(self):
        for wizard in self:
            # Total EX KM بالسالب
            wizard.ex_km_deduction = -(wizard.total_ex_km_amount or 0)
            # Estimated Cost بالسالب لو فيه تلفيات، صفر لو لأ
            if wizard.has_damages == 'yes':
                wizard.estimated_cost_deduction = -(wizard.estimated_cost or 0)
            else:
                wizard.estimated_cost_deduction = 0.0

            # عدد الأيام الزيادة (حساب مبدئي - هنرجعله)
            extra_days = 0
            contract = wizard.contract_id
            if wizard.actual_return_date and contract and contract.rent_end_date:
                diff = (wizard.actual_return_date - contract.rent_end_date).days
                extra_days = diff if diff > 0 else 0
            wizard.extra_days = extra_days

            # Net = Insurance + الخصومات السالبة
            wizard.net_insurance = (wizard.insurance_amount or 0) + wizard.ex_km_deduction + wizard.estimated_cost_deduction

    @api.depends('contract_id')
    def _compute_km_settings(self):
        for wizard in self:
            km_per_day = 0
            price = 0.0
            if wizard.contract_id and wizard.contract_id.vehicle_id:
                model = wizard.contract_id.vehicle_id.model_id
                # دوّر على سطر فيه موديل العربية
                line = self.env['fleet.extra.km'].search([
                    ('model_ids', 'in', model.id),
                ], limit=1)
                # لو ملقاش، دوّر على السطر الفاضي (الافتراضي العام)
                if not line:
                    line = self.env['fleet.extra.km'].search([
                        ('model_ids', '=', False),
                    ], limit=1)
                if line:
                    km_per_day = line.km_per_day
                    price = line.extra_km_price
            wizard.km_per_day = km_per_day
            wizard.extra_km_price = price

    @api.depends('return_km', 'actual_return_date', 'km_per_day', 'extra_km_price', 'contract_id')
    def _compute_extra_km_fields(self):
        for wizard in self:
            contract = wizard.contract_id
            exit_km = contract.exit_km if contract else 0
            # Consumed KM = Return KM - Exit KM, لو سالب يبقى 0
            consumed = (wizard.return_km or 0) - exit_km
            consumed = consumed if consumed > 0 else 0
            wizard.consumed_km = consumed

            # Rent Days = Actual Return Date - Rent Start Date
            rent_days = 0
            if wizard.actual_return_date and contract and contract.rent_start_date:
                rent_days = (wizard.actual_return_date - contract.rent_start_date).days

            # Extra KM = Consumed - (KM Per Day * Rent Days), لو سالب يبقى 0
            allowed = wizard.km_per_day * rent_days
            extra = consumed - allowed
            wizard.extra_km = extra if extra > 0 else 0

            # Total = Extra KM * Extra KM Price
            wizard.total_ex_km_amount = wizard.extra_km * wizard.extra_km_price

    def action_confirm(self):
        self.ensure_one()
        # لو فيه تلفيات لازم بيان التلفيات
        if self.has_damages == 'yes' and not self.damage_description:
            raise ValidationError("Damage Description is required when there are damages.")
        # احفظ كل القيم على العقد
        self.contract_id.write({
            'return_km': self.return_km,
            'actual_return_date': self.actual_return_date,
            'has_damages': self.has_damages,
            'estimated_cost': self.estimated_cost,
            'damage_description': self.damage_description,
            'consumed_km': self.consumed_km,
            'km_per_day': self.km_per_day,
            'extra_km': self.extra_km,
            'extra_km_price': self.extra_km_price,
            'total_ex_km_amount': self.total_ex_km_amount,
        })
        # انقل الحالة لـ checking فقط لو الثلاثة كلهم متملّيين
        if self.return_km and self.actual_return_date and self.has_damages:
            return self.contract_id.force_checking()
        return True