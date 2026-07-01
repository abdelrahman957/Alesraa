from odoo import fields, models, api
from odoo.exceptions import UserError


class InsuranceRefundWizard(models.TransientModel):
    _name = 'insurance.refund.wizard'
    _description = 'Insurance Refund Wizard'

    contract_id = fields.Many2one('car.rental.contract', string='Contract', required=True)
    insurance_amount = fields.Float(string='Refundable Insurance', readonly=True)
    extra_km_amount = fields.Float(string='Extra KM Charges', readonly=True)
    extra_days_amount = fields.Float(string='Extra Days Charges', readonly=True)
    damages_amount = fields.Float(string='Damages', readonly=True)
    net_amount = fields.Float(string='Net Amount', readonly=True)
    direction = fields.Char(string='Direction', readonly=True)
    journal_id = fields.Many2one(
        'account.journal',
        string='Payment Method (Cash/Bank)',
        required=True,
        domain="[('type', 'in', ['cash', 'bank'])]",
    )

    def action_confirm_refund(self):
        self.ensure_one()
        contract = self.contract_id
        if contract.insurance_refund_done:
            raise UserError("Insurance has already been refunded for this contract.")

        # الحسابات
        liab_212001 = self.env['account.account'].search([('code', '=', '212001')], limit=1)
        liab_212002 = self.env['account.account'].search([('code', '=', '212002')], limit=1)
        product = self.env['product.product'].browse(self.env.ref('fleet_rental.fleet_service_product').id)
        income_account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        cash_account = self.journal_id.default_account_id

        if not (liab_212001 and liab_212002 and income_account and cash_account):
            raise UserError("Please check the accounts configuration (212001, 212002, income, journal).")

        insurance = contract.insurance_amount
        extra_income = (contract.total_ex_km_amount or 0) + abs(contract.extra_days_amount or 0)
        damages = contract.estimated_cost if contract.has_damages == 'yes' else 0.0
        net = contract.net_insurance_refund  # موجب = نرجّع، سالب = نحصّل

        lines = []
        # Debit التأمين بالكامل (نقفل الالتزام)
        lines.append((0, 0, {
            'account_id': liab_212001.id,
            'name': 'Refundable Insurance Settlement',
            'debit': insurance,
            'credit': 0.0,
        }))
        # Credit الإيراد (Extra KM + Days)
        if extra_income > 0:
            lines.append((0, 0, {
                'account_id': income_account.id,
                'name': 'Extra KM & Days Income',
                'debit': 0.0,
                'credit': extra_income,
            }))
        # Credit الـ Damages liability
        if damages > 0:
            lines.append((0, 0, {
                'account_id': liab_212002.id,
                'name': 'Repair Deductions',
                'debit': 0.0,
                'credit': damages,
            }))
        # الكاش: نرجّع (credit) لو net موجب، نحصّل (debit) لو سالب
        if net > 0:
            lines.append((0, 0, {
                'account_id': cash_account.id,
                'name': 'Insurance Refund to Customer',
                'debit': 0.0,
                'credit': net,
            }))
        elif net < 0:
            lines.append((0, 0, {
                'account_id': cash_account.id,
                'name': 'Insurance Collection from Customer',
                'debit': abs(net),
                'credit': 0.0,
            }))

        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'ref': 'Insurance Refund - %s' % contract.name,
            'line_ids': lines,
        })
        move.action_post()

        contract.insurance_refund_done = True
        return {'type': 'ir.actions.act_window_close'}