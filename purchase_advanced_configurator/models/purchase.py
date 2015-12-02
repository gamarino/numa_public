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

from openerp import models, fields, api, exceptions
from openerp.tools.translate import _

import logging
_logger = logging.getLogger(__name__)

class ProductConfiguratorOption(models.TransientModel):
    _inherit = "product.configurator.option"
    
    pol = fields.Many2one('purchase.order.line', 'Purchase order line')

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    
    @api.multi
    def wkf_confirm_order(self):
        for order in self:
            for line in order.order_line:
                if not line.product_id:
                    line._check_line_confirmability()

                    line.product_id = line.product_template.create_variant(line.options)
                    if not line.product_id:
                        raise exceptions.Warning(
                            _("Variant could not be created! Product %s. Please check it") %
                             line.product_template.name_get()[0][1])
                    line.name = line._get_product_description(
                                    line.product_id.product_tmpl_id, 
                                    line.product_id, 
                                    line.product_id.attribute_value_ids)
                    line.product_template.action_on_variant_creation(line.product_id)

        super(PurchaseOrder, self).wkf_confirm_order()

class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    options = fields.One2many('product.configurator.option', 'pol', 'Options')

    show_log = fields.Boolean("Show log")
    log_registry = fields.Text('Log registry')

    @api.one
    def logMsg(self, msg, *args):
        if args:
            full_msg = msg % args
        else:
            full_msg = msg

        _logger.info(u"Configurator log: %s" % full_msg)

        previous_lines = self.log_registry.split('\n')
        self.log_registry = "%s\n%s" % ('\n'.join(previous_lines[-20:]), full_msg)

    @api.multi
    def _get_product_description(self, template, product, attribute_values):
        name = product and \
                   (product.description_purchase or product.description or product.name) or \
                   (template.description_purchase or template.description or template.name)
                   
        group = self.env.ref(
            'sale_product_variants.group_product_variant_extended_description')
        #extended = group in self.env.user.groups_id
        extended = True
        if not attribute_values and product:
            attribute_values = product.attribute_value_ids
        if extended:
            description = "\n".join(attribute_values.mapped(
                lambda x: "%s: %s" % (x.attribute_id.name, x.name)))
        else:
            description = ", ".join([o.name for o in attribute_values])
        if not description:
            return name
        return ("%s\n%s" if extended else "%s (%s)") % (name, description)

    @api.multi
    @api.onchange('product_template')
    def onchange_product_template(self):
        self.ensure_one()
        pol = self
        self.product_id = False
        if pol.product_template:
            new_options = [(0, 0, od) for od in pol.product_template.get_options_dict()]
            self.options = new_options
            self.product_id = pol.product_template.get_variant(self.options)
            if not self.product_id:
                name = self.product_template.name
                description = ", ".join([o.selection and o.selection.name or o.display_value or '0.0' for o in self.options])
                self.name = "%s (%s)" % (name, description) 
            else:
                self.name = self._get_product_description(
                                self.product_id.product_tmpl_id, 
                                self.product_id, 
                                self.product_id.attribute_value_ids)
            return {'domain': {'product_id': [('product_tmpl_id', '=', pol.product_template.id)]}}
        else:
            self.options = []
            self.name = False
            return {'domain': {'product_id': []}}        

    @api.multi
    def onchange_product_id(
            self, pricelist_id, product_id, qty, uom_id, partner_id,
            date_order=False, fiscal_position_id=False, date_planned=False,
            name=False, price_unit=False, state='draft'):
        res = super(PurchaseOrderLine, self).onchange_product_id(
            pricelist_id, product_id, qty, uom_id, partner_id,
            date_order=date_order, fiscal_position_id=fiscal_position_id,
            date_planned=date_planned, name=name, price_unit=price_unit,
            state=state)
        if res and 'value' in res and 'product_attributes' in res['value']:
            res['value'].pop('product_attributes')
        if product_id:
            product_obj = self.env['product.product']
            product = product_obj.browse(product_id)
            res['value']['options'] = [(0, 0, od) for od in product.get_options_dict()]
            res['value']['name'] = self._get_product_description(
                product.product_tmpl_id, product, product.attribute_value_ids)
        else:
            res['value']['name'] = False
        return res

    @api.one
    @api.onchange('options')
    def onchange_product_options(self):
        self.product_id = False        
        if self.product_template:
            self.product_id = self.product_template.get_variant(self.options)
            if not self.product_id:
                name = self.product_template.name
                description = ", ".join([o.selection and o.selection.name or o.display_value or '0.0' for o in self.options])
                self.name = "%s (%s)" % (name, description) 
            else:
                self.name = self.product_id.name_get()[0][1]

    @api.multi
    def _check_line_confirmability(self):
        pol = self
        
        def raiseWarning(option):
            raise exceptions.Warning(
                _("You can not confirm before configuring all attribute "
                  "values. Option %s is empty") % option.attribute.name)

        if pol.product_id:
            return
        if not pol.product_template:
            raise exceptions.Warning(
                _("You can not confirm a line without product and no template! Please check it"))
            
        for option in pol.options:
            if option.attr_type == 'string' and not option.string_value:
                raiseWarning(option)
            elif option.attr_type == 'range' and \
                 (option.numeric_value < option.attribute.min_range or \
                  option.numeric_value > option.attribute.max_range):
                raiseWarning(option)
            elif option.attr_type == 'select' and not option.selection:
                raiseWarning(option)
            elif option.attr_type == 'product' and not option.product:
                raiseWarning(option)
            elif option.attr_type == 'variant' and not option.variant:
                raiseWarning(option)
            elif option.attr_type == 'category' and not option.category: 
                raiseWarning(option)

