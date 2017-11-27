# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'NUMA CRM Process',
    'version': '1.0',
    'category': 'Sales',
    'sequence': 5,
    'summary': 'Lead processes',
    'description': """
NUMA CRM Process
================

""",
    'website': 'https://www.numaes.com',
    'depends': [
        'base_action_rule',
        'base_setup',
        'mail',
        'fetchmail',
        'crm',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'views/crm_process_views.xml',
        'views/crm_menues.xml',
    ],
    'demo': [
        'data/demo.xml',
    ],
    'css': ['static/src/css/crm.css'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
