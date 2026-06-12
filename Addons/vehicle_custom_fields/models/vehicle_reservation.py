from odoo import fields, models, api
from odoo.exceptions import ValidationError


class VehicleReservation(models.Model):
    _name = 'vehicle.reservation'
    _description = 'Vehicle Future Reservation'

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        domain=[('state', 'in', ['sale', 'done'])],
        required=True,
    )
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='sale_order_id.partner_id',
        readonly=True,
        store=True,
    )
    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)

    _sql_constraints = [
        ('unique_vehicle_reservation',
         'unique(vehicle_id)',
         'This vehicle already has a reservation!'),
    ]

    @api.constrains('date_from', 'date_to', 'vehicle_id')
    def _check_dates(self):
        for rec in self:
            # تاريخ نهاية العقد الـ running الحالي
            running_contract = self.env['car.rental.contract'].search([
                ('vehicle_id', '=', rec.vehicle_id.id),
                ('state', '=', 'running'),
            ], order='rent_end_date desc', limit=1)

            if running_contract and rec.date_from <= running_contract.rent_end_date:
                raise ValidationError(
                    "The current contract ends on %s. The reservation must start after this date."
                    % running_contract.rent_end_date.strftime('%d/%m/%Y')
                )

            if rec.date_to < rec.date_from:
                raise ValidationError("End date cannot be before start date.")