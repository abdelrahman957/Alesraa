from odoo import fields, models, api


class FleetVehicleOdometer(models.Model):
    _inherit = 'fleet.vehicle.odometer'

    tracking_type = fields.Selection(
        selection=[
            ('rent', 'Rent Contract'),
            ('service', 'Service'),
        ],
        string='Type',
    )
    responsible_id = fields.Many2one(
        'res.partner', string='Responsible')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')

    # روابط المصدر - لمنع التكرار وللربط
    rental_contract_id = fields.Many2one(
        'car.rental.contract', string='Rental Contract', ondelete='cascade')
    service_id = fields.Many2one(
        'fleet.vehicle.log.services', string='Service', ondelete='cascade')

    @api.model
    def _rebuild_tracking(self):
        """يبني سجلات العداد من العقود والصيانات (بدون تكرار)."""

        # 1) عقود الإيجار (Done)
        contracts = self.env['car.rental.contract'].search([('state', '=', 'done')])
        for contract in contracts:
            # هل السجل موجود؟
            existing = self.search([('rental_contract_id', '=', contract.id)], limit=1)
            if existing:
                continue
            if not contract.vehicle_id:
                continue
            # قيمة العداد لو موجودة، غير كده صفر
            value = getattr(contract, 'return_km', 0) or 0
            self.create({
                'vehicle_id': contract.vehicle_id.id,
                'value': value,
                'date': contract.rent_end_date or fields.Date.today(),
                'tracking_type': 'rent',
                'date_from': contract.rent_start_date,
                'date_to': contract.rent_end_date,
                'rental_contract_id': contract.id,
                'responsible_id': contract.customer_id.id if contract.customer_id else False,
            })

        # 2) الصيانات (Done)
        services = self.env['fleet.vehicle.log.services'].search([('state', '=', 'done')])
        for service in services:
            existing = self.search([('service_id', '=', service.id)], limit=1)
            if existing:
                continue
            if not service.vehicle_id:
                continue
            value = 0
            if service.odometer_id:
                value = service.odometer_id.value
            self.create({
                'vehicle_id': service.vehicle_id.id,
                'value': value,
                'date': service.date or fields.Date.today(),
                'tracking_type': 'service',
                'date_from': False,
                'date_to': False,
                'service_id': service.id,
                'responsible_id': service.purchaser_id.id if service.purchaser_id else False,
            })

    @api.model
    def action_open_tracking(self):
        """يبني ثم يفتح الـ list (من الـ menu)."""
        self._rebuild_tracking()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vehicle Odometer',
            'res_model': 'fleet.vehicle.odometer',
            'view_mode': 'list',
            'views': [(self.env.ref('vehicle_custom_fields.fleet_odometer_tracking_list').id, 'list')],
            'search_view_id': [self.env.ref('vehicle_custom_fields.fleet_odometer_tracking_search').id],
            'domain': [('tracking_type', '!=', False)],
            'target': 'current',
        }

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        # ابنِ أول ما الشاشة تتحمّل - مرة واحدة لكل request
        if not self.env.context.get('_odo_built'):
            self.with_context(_odo_built=True)._rebuild_tracking()
            self = self.with_context(_odo_built=True)
        return super().web_search_read(
            domain, specification, offset=offset, limit=limit,
            order=order, count_limit=count_limit,
        )