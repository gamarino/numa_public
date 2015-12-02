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
    
    sol = fields.Many2one('sale.order.line', 'Sale order line')
    
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    options = fields.One2many('product.configurator.option', 'sol', 'Options')

    show_log = fields.Boolean("Show log")
    log_registry = fields.Text('Log registry')

    category = fields.Many2one('product.category', 'Category')
    
    @api.onchange('category')
    @api.multi
    def onchange_category(self):
        if self.category:
            domain = {'product_template': [('categ_id', 'child_of', [self.category.id])],
                      'category': [('parent_id', '=', self.category.id)]}
            if not self.product_template:
                domain['product_id'] = [('categ_id', 'child_of', [self.category.id])]
            return {'domain': domain}
        else:
            return {'domain': {'product_template': [], 'category': []}}

    @api.one
    def logMsg(self, msg, *args):
        if args:
            full_msg = msg % args
        else:
            full_msg = msg

        _logger.info(u"Configurator log: %s" % full_msg)

        previous_lines = self.log_registry.split('\n')
        self.log_registry = "%s\n%s" % ('\n'.join(previous_lines[-20:]), full_msg)

    @api.one
    @api.depends('product_attributes')
    def _get_product_attributes_count(self):
        self.product_attributes_count = len(self.options)

    @api.multi
    def _get_product_description(self, template, product, attribute_values):
        name = product and \
                   (product.description_sale or product.description or product.name) or \
                   (template.description_sale or template.description or template.name)
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
        sol = self
        self.product_id = False
        if sol.product_template:
            new_options = [(0, 0, od) for od in sol.product_template.get_options_dict()]
            self.options = new_options
            self.product_attributes_count = len(new_options)
            self.product_id = sol.product_template.get_variant(self.options)
            if not self.product_id:
                name = self.product_template.name
                description = ", ".join([o.selection and o.selection.name or o.display_value or '0.0' for o in self.options])
                self.name = "%s (%s)" % (name, description) 
            else:
                self.name = self._get_product_description(
                                self.product_id.product_tmpl_id, 
                                self.product_id, 
                                self.product_id.attribute_value_ids)
            return {'domain': {'product_id': [('product_tmpl_id', '=', sol.product_template.id)]}}
        else:
            self.options = []
            self.name = False
            return {'domain': {'product_id': []}}        

    @api.multi
    def product_id_change(
            self, pricelist, product_id, qty=0, uom=False, qty_uos=0,
            uos=False, name='', partner_id=False, lang=False, update_tax=True,
            date_order=False, packaging=False, fiscal_position=False,
            flag=False):
        res = super(SaleOrderLine, self).product_id_change(
            pricelist, product_id, qty=qty, uom=uom, qty_uos=qty_uos, uos=uos,
            name=name, partner_id=partner_id, lang=lang, update_tax=update_tax,
            date_order=date_order, packaging=packaging,
            fiscal_position=fiscal_position, flag=flag)
        if res and 'value' in res and 'product_attributes' in res['value']:
            res['value'].pop('product_attributes')
        if 'domain' not in res:
            res['domain'] = {}
        if product_id:
            product_obj = self.env['product.product']
            product = product_obj.browse(product_id)
            res['value']['options'] = [(0, 0, od) for od in product.get_options_dict()]
            res['value']['name'] = self._get_product_description(
                product.product_tmpl_id, product, product.attribute_value_ids)
            res['domain']['category'] = [('parent_id', '=', [product.categ_id.id])]
        else:
            res['value']['name'] = False
            res['domain']['category'] = []
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
                self.update_price_unit()
            else:
                self.name = self.product_id.name_get()[0][1]

    @api.one
    def _check_line_confirmability(self):
        sol = self
        
        def raiseWarning(option):
            raise exceptions.Warning(
                _("You can not confirm before configuring all attribute "
                  "values. Option %s is empty") % option.attribute.name)
        
        if sol.product_id:
            return
        if not sol.product_template:
            raise exceptions.Warning(
                _("You can not confirm a line without product and no template! Please check it"))
            
        for option in sol.options:
            if not option.required:
                continue
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

    @api.multi
    def button_confirm(self):
        for line in self:
            if not line.product_id:
                line._check_line_confirmability()

                line.product_id = line.product_template.create_variant(line.options)
                if not line.product_id:
                    raise exceptions.Warning(
                        _("Variant could not be created! Product %s. Please check it") %
                         line.product_template.name_get()[0][1])
                line.name = self._get_product_description(
                                line.product_id.product_tmpl_id, 
                                line.product_id, 
                                line.product_id.attribute_value_ids)
                line.product_template.action_on_variant_creation(line.product_id)

        super(SaleOrderLine, self).button_confirm()

    @api.multi
    def update_price_unit(self):
        self.ensure_one()
        if not self.product_id:
            price_extra = 0.0
            for attr_line in self.options:
                price_extra += attr_line.price_extra
            self.price_unit = self.order_id.pricelist_id.with_context(
                {
                    'uom': self.product_uom.id,
                    'date': self.order_id.date_order,
                    'price_extra': price_extra,
                }).template_price_get(
                self.product_template.id, self.product_uom_qty or 1.0,
                self.order_id.partner_id.id)[self.order_id.pricelist_id.id]

