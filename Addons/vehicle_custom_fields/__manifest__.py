{
    'name': 'Vehicle Custom Fields',
    'version': '19.0.1.0.0',
    'category': 'Fleet',
    'summary': 'Add custom fields to Fleet Vehicle',
    'depends': ['fleet', 'sale'],
    'data': [
    'views/fleet_vehicle_views.xml',
    'security/ir.model.access.csv',
    'views/sale_order_views.xml',
    'reports/sale_order_report.xml',
],
    'installable': True,
    'auto_install': False,
}