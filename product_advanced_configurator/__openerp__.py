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
    "name": "Product advanced configurator",
    "version": "1.0",
    "depends": [
        "product", 
        "product_variants_no_automatic_creation",
    ],
    "author": "NUMA Extreme Systems",
    "contributors": [
        "Gustavo Marino <gamarino@numaes.com>",
    ],
    'description': """
Product Advanced Configurator
=============================

This module expands Product Template to add several features to the basic product template of Odoo.

First, it expand the template to a hierarchy of templates in order to be able to transfer product attributes
from parents to children. In this way, it is not necessary to reimplement a product attribute set in every
single product of a family. It is defined in a base product template and automatically this attributes
will be inherit by all template children.

Second, it adds a product configurator with enables the configuration of specific products (variants of the template)
with a set expanded product attributes. Attributes could be expressed as options (the classic type), numeric values,
ranges and string values (open strings or numeric values). Additional an attribute could be represented by
another product variant, a template or a product category.

Third, it provides a programable configurator with the possiblity of help messages for the configuration
process at the product, attribute and option level.

Fourth, it creates an event system with user programable code to act on attribute change, product configuration
and product creation, based on the template. A this level, any code could be called on configuration and
product creation, and in the case of onchange the limitations of normal onchange applies(you cannot write
to DB)

Fifth, it adds a series of images and html fields to be shown on actual configuration. The image could
anything you think it can help the user to understand the consequences of attribute setting and the html
text could be used to compute dynamically generated information on the setting currently chosen, even 
SVG diagrams with drawings and diagrams

""",
    "category": "Product Management",
    "website": "http://www.numaes.com",
    'data': [
        "views/product_view.xml",
    ],
    'installable': True,
}
