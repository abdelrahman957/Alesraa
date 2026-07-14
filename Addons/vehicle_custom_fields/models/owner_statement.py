from odoo import fields, models, api
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta
from calendar import monthrange


class FleetContractRentCost(models.Model):
    _name = 'fleet.contract.rent.cost'
    _description = 'Fleet Contract Rent Cost Period'

    contract_id = fields.Many2one(
        'fleet.vehicle.log.contract',
        string='Fleet Contract',
        required=True,
        ondelete='cascade',
    )
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    rent_amount = fields.Float(string='Rent Amount', required=True)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError("'To' date must be after 'From' date.")


class OwnerStatementLine(models.Model):
    _name = 'owner.statement.line'
    _description = 'Owner Statement Line'
    _order = 'date'

    line_type = fields.Selection(
        selection=[
            ('rent_cost', 'Rent Cost'),
            ('service', 'Service'),
        ],
        string='Type',
        required=True,
        default='rent_cost',
    )
    date = fields.Date(string='Month', required=True)
    amount = fields.Float(string='Amount')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')
    owner_id = fields.Many2one('res.partner', string='Owner')
    contract_id = fields.Many2one(
        'fleet.vehicle.log.contract',
        string='Fleet Contract',
        ondelete='cascade',
    )
    service_id = fields.Many2one(
        'fleet.vehicle.log.services',
        string='Service Report',
        ondelete='cascade',
    )
    rent_cost_id = fields.Many2one(
        'fleet.contract.rent.cost',
        string='Source Period',
        ondelete='cascade',
    )

class FleetVehicleLogContract(models.Model):
    _inherit = 'fleet.vehicle.log.contract'

    rent_cost_ids = fields.One2many(
        'fleet.contract.rent.cost',
        'contract_id',
        string='Rent Cost Periods',
    )
    owner_statement_ids = fields.One2many(
        'owner.statement.line',
        'contract_id',
        string='Owner Statement Lines',
    )
    owner_statement_count = fields.Integer(
        string='Statement Count',
        compute='_compute_owner_statement_count',
    )

    def _compute_owner_statement_count(self):
        for contract in self:
            contract.owner_statement_count = len(contract.owner_statement_ids)

    def _generate_owner_statement_lines(self):
        """يفكّ فترات Rent Cost لسطور شهرية (مع نسبة الأيام للشهور الناقصة)."""
        for contract in self:
            # امسح السطور القديمة من نوع rent_cost بس
            old_lines = contract.owner_statement_ids.filtered(
                lambda l: l.line_type == 'rent_cost'
            )
            old_lines.unlink()

            new_lines = []
            for period in contract.rent_cost_ids:
                if not period.date_from or not period.date_to or not period.rent_amount:
                    continue
                new_lines += self._split_period_to_months(contract, period)

            if new_lines:
                self.env['owner.statement.line'].create(new_lines)

    def _split_period_to_months(self, contract, period):
        """يقسّم فترة واحدة لسطور شهرية بنسبة الأيام."""
        lines = []
        monthly_amount = period.rent_amount
        current = period.date_from
        end = period.date_to

        while current <= end:
            # أول وآخر يوم في الشهر الحالي
            days_in_month = monthrange(current.year, current.month)[1]
            month_first = current.replace(day=1)
            month_last = current.replace(day=days_in_month)

            # بداية ونهاية الاستخدام في الشهر ده
            used_start = max(current, month_first)
            used_end = min(end, month_last)

            # عدد أيام الاستخدام (inclusive)
            used_days = (used_end - used_start).days + 1

            # النسبة: أيام الاستخدام ÷ إجمالي أيام الشهر
            ratio = used_days / days_in_month
            amount = monthly_amount * ratio

            # الـ Owner من insurer_id بتاع العقد
            owner = contract.insurer_id.id if contract.insurer_id else False
            vehicle = contract.vehicle_id.id if contract.vehicle_id else False

            lines.append({
                'line_type': 'rent_cost',
                'date': month_last,
                'amount': amount,
                'vehicle_id': vehicle,
                'owner_id': owner,
                'contract_id': contract.id,
                'rent_cost_id': period.id,
            })

            # روح لأول الشهر اللي بعده
            current = month_first + relativedelta(months=1)

        return lines
    
    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        contracts._generate_owner_statement_lines()
        return contracts

    def write(self, vals):
        res = super().write(vals)
        # لو اتعدّلت الفترات أو العربية أو المالك، أعِد توليد السطور
        if 'rent_cost_ids' in vals or 'vehicle_id' in vals or 'insurer_id' in vals:
            self._generate_owner_statement_lines()
        return res

    def action_view_owner_statement(self):
        """Smart Button — يفتح سطور العربية دي بس."""
        self.ensure_one()
        return {
            'name': 'Owner Statement',
            'type': 'ir.actions.act_window',
            'res_model': 'owner.statement.line',
            'view_mode': 'list',
            'domain': [('contract_id', '=', self.id)],
            'context': {'search_default_group_vehicle': 1},
        }