# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2015
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################


{
    'name': 'NUMA Services',
    'version': '1.0',
    'category': 'Product Management',
    'description': """
NUMA Services
=============

Services Management

Services can be offered to your customers as normal part of your portfolio.
This module implements the concept of Service Orders as an internal unit
to control the proper execution and assignement to service groups
Additionally, any product defined as service, can be set to define an
external service, which will be grouped by sale order to create a corresponding
service order.
Service orders can be configured to generate invoices on service completion,
in a similar behavior as pickings
Services can be bought or produced. In the first case an external subcontrator
is assumed, and consequently a draft Purchase Order is created on Service order
confirmation.
An internally produced service order will be delivered by a service class 
group, with a predefined capacity. 
A service category group could not deliver more than a number of simultaneous 
service orders. This is known as its capacity.
Service orders can be scheduled for a certain service class group and timeframe.
Delayed or rescheduled Service Orders can be put under the control af a service
manager, who is the only authorized to assign, reschedule or cancel a Service
Order.
In order to close a service order, customer confirmation is needed. As a result
of service delivery, some products could be consumed (like spare parts or 
small accesories). This can be added to the service order as additional items
 
""",
    'author': 'NUMA Extreme Systems',
    'website': 'http://www.numaes.com',
    'depends': [
        'base',
        'product',
        'procurement',
        'sale',
        'purchase',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'report_serviceorder.xml',
        'service_report.xml',
        'services_view.xml',
        'data.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': True,
    'active': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
