from odoo import fields, models, api
from odoo.exceptions import UserError


class OwnerStatementReport(models.Model):
    _name = 'owner.statement.report'
    _description = 'Owner Statement Report'
    _order = 'create_date desc'

    name = fields.Char(
        string='Reference',
        default='New',
        copy=False,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
    )
    owner_id = fields.Many2one(
        'res.partner',
        string='Owner',
        compute='_compute_owner',
        store=True,
    )
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
        ],
        string='Status',
        default='draft',
        copy=False,
    )
    line_ids = fields.One2many(
        'owner.statement.report.line',
        'report_id',
        string='Lines',
    )
    total_amount = fields.Float(
        string='Total',
        compute='_compute_total',
        store=True,
    )
    bill_id = fields.Many2one(
        'account.move',
        string='Vendor Bill',
        readonly=True,
        copy=False,
    )
    payment_state = fields.Selection(
        related='bill_id.payment_state',
        string='Payment Status',
        store=True,
    )
    is_paid = fields.Boolean(
        string='Paid',
        compute='_compute_is_paid',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    pending_warning = fields.Text(
        string='Pending Warning',
        readonly=True,
        copy=False,
    )

    @api.depends('bill_id', 'bill_id.payment_state')
    def _compute_is_paid(self):
        for report in self:
            paid = bool(
                report.bill_id and report.bill_id.payment_state in ('paid', 'in_payment')
            )
            report.is_paid = paid
            # حدّث حالة السطور الأصلية
            source_lines = report.line_ids.filtered(
                lambda l: l.source_line_id
            ).mapped('source_line_id')
            if source_lines:
                if paid:
                    source_lines.filtered(lambda l: l.state == 'confirmed').write({'state': 'paid'})
                else:
                    source_lines.filtered(lambda l: l.state == 'paid').write({'state': 'confirmed'})

    @api.depends('vehicle_id')
    def _compute_owner(self):
        for report in self:
            report.owner_id = report.vehicle_id.owner_id.id if report.vehicle_id else False

    @api.depends('line_ids', 'line_ids.amount')
    def _compute_total(self):
        for report in self:
            report.total_amount = sum(report.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('owner.statement.report') or 'New'
        return super().create(vals_list)

    def action_compute(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Compute is only allowed in Draft state.")
        if not self.vehicle_id or not self.date_from or not self.date_to:
            raise UserError("Please set Vehicle, From and To dates first.")

        # امسح كل السطور المولّدة (غير اليدوية)
        self.line_ids.filtered(lambda l: not l.is_manual).unlink()

        # هات سطور الأصل للعربية في الفترة
        source_lines = self.env['owner.statement.line'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', '=', 'open'),
        ])

        # اعمل سطور جديدة من الأصل
        for src in source_lines:
            self.env['owner.statement.report.line'].create({
                'report_id': self.id,
                'source_line_id': src.id,
                'line_type': src.line_type,
                'date': src.date,
                'amount': src.amount,
                'description': src.description,
                'is_manual': False,
            })
        # فحص الصيانات اللي مسؤوليتها Pending
        pending_services = self.env['fleet.vehicle.log.services'].search([
            ('vehicle_id', '=', self.vehicle_id.id),
            ('state', '=', 'done'),
            ('has_pending_responsibility', '=', True),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])

        if pending_services:
            details = []
            for srv in pending_services:
                ref = srv.display_name or ('#%s' % srv.id)
                date_str = srv.date.strftime('%d/%m/%Y') if srv.date else '-'
                details.append('%s (%s)' % (ref, date_str))
            details_str = ' , '.join(details)
            self.pending_warning = (
                "Maintenance with undefined responsibility in this period: %s\n"
                "يوجد صيانة لم تُحدَّد مسؤوليتها في هذه الفترة: %s"
            ) % (details_str, details_str)
        else:
            self.pending_warning = False

        return True
        

    def action_confirm(self):
        self.ensure_one()
        # السطور الأصلية المرتبطة بالتقرير
        source_lines = self.line_ids.filtered(lambda l: l.source_line_id).mapped('source_line_id')

        # امنع لو أي سطر بقى confirmed في مكان تاني
        already_confirmed = source_lines.filtered(lambda l: l.state == 'confirmed')
        if already_confirmed:
            raise UserError(
                "Some lines are already confirmed in another report. "
                "Please run Compute again to refresh, then confirm."
            )

        if not self.owner_id:
            raise UserError("Owner is required to create the vendor bill.")
        if not self.line_ids:
            raise UserError("No lines to confirm.")

        # اعمل فاتورة المورد
        self._create_vendor_bill()

        # أكّد السطور الأصلية
        source_lines.write({'state': 'confirmed'})
        self.state = 'confirmed'

    def _create_vendor_bill(self):
        """يعمل Vendor Bill للمالك بسطور الإيجار والصيانة."""
        self.ensure_one()

        # هات الحسابات
        rent_account = self.env['account.account'].search([
            ('code', '=', '500001'),
        ], limit=1)
        service_account = self.env['account.account'].search([
            ('code', '=', '500002'),
        ], limit=1)

        if not rent_account:
            raise UserError("Account 500001 (Car Rent Cost) not found.")
        if not service_account:
            raise UserError("Account 500002 (Car Service Cost) not found.")

        invoice_lines = []
        for line in self.line_ids:
            # اختار الحساب حسب النوع
            if line.line_type == 'service':
                account = service_account
            else:
                account = rent_account

            invoice_lines.append((0, 0, {
                'name': line.description or dict(
                    line._fields['line_type'].selection
                ).get(line.line_type, 'Line'),
                'account_id': account.id,
                'quantity': 1,
                'price_unit': line.amount,
            }))

        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.owner_id.id,
            'invoice_date': self.date_to,
            'date': self.date_to,
            'ref': self.name,
            'invoice_line_ids': invoice_lines,
        })
        bill.action_post()
        self.bill_id = bill.id
        return bill

    def action_view_bill(self):
        self.ensure_one()
        if not self.bill_id:
            raise UserError("No vendor bill for this report.")
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.bill_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_set_draft(self):
        self.ensure_one()
        if self.is_paid:
            raise UserError("Cannot set to draft: the bill is already paid.")
        # لغِ الفاتورة لو موجودة
        if self.bill_id:
            self.bill_id.button_draft()
            self.bill_id.button_cancel()
        # رجّع السطور الأصلية لـ open
        source_lines = self.line_ids.filtered(lambda l: l.source_line_id).mapped('source_line_id')
        source_lines.write({'state': 'open'})
        self.state = 'draft'

    def unlink(self):
        for report in self:
            if report.state == 'confirmed':
                raise UserError("Cannot delete a confirmed report.")
        return super().unlink()


class OwnerStatementReportLine(models.Model):
    _name = 'owner.statement.report.line'
    _description = 'Owner Statement Report Line'
    _order = 'date'

    report_id = fields.Many2one(
        'owner.statement.report',
        string='Report',
        required=True,
        ondelete='cascade',
    )
    source_line_id = fields.Many2one(
        'owner.statement.line',
        string='Source Line',
        ondelete='set null',
    )
    is_manual = fields.Boolean(string='Manual', default=True)
    line_type = fields.Selection(
        selection=[
            ('rent_cost', 'Rent Cost'),
            ('service', 'Service'),
            ('other', 'Other'),
        ],
        string='Type',
        default='other',
    )
    date = fields.Date(string='Date')
    description = fields.Char(string='Description')
    amount = fields.Float(string='Amount')