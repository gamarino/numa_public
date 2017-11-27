# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems.
#  
#    Copyright (C) 2013 NUMA Extreme Systems (<http:www.numaes.com>).
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
    'name': 'NUMA Exceptions',
    'author' : 'Numa Extreme Systems',
    'category' : 'Specific Numa Applications',
    'description': """
Extended exception processing.
==============================

    * Exception information will be stored in a model in database
    * Every exception records not only the stack frames, but also parameters and locals values and remote call parameters
    * Exception information purge, unless configured, every month to limit space consuption
    * User is informed of problem with a link that can be copied and emailed to the system administration
    * Exception information can be consulted online without server access by the system administrator

""",
	'summary': "Exception Information Database",
    'version': '1.0',
    'depends': ['base'],
    'data': ['security/ir.model.access.csv','security/security.xml','views/exceptions_view.xml','data/exceptions_data.xml',],
    'auto_install': False,
    'application': True,
}
