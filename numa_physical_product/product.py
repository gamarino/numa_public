# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA Extreme Systems (www.numaes.com)
#    Copyright (C) 2017
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

from odoo import models, fields, api, tools, _
from odoo.exceptions import UserError, ValidationError
import odoo.addons.decimal_precision as dp

from itertools import chain

import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    weight_kind = fields.Selection([
                                ('normal', 'Normal'),
                                ('length', 'Length based'),
                                ('width', 'Width based'),
                                ('height', 'Height based'),
                                ('surface', 'Surface based'),
                                ('volume', 'Volume based')], 
                            'Product weight computation', 
                            required=True,
                            default='normal',                            
                            help="It computes weight automatically based on length, width, surface, volume, etc")
    weight_factor = fields.Float('Weight per unit [kg/unit]', 
                                 digits=dp.get_precision('Stock Weight'),
                                 help="Weight factor to apply")
    width = fields.Float('Width [m]',
                         digits=dp.get_precision('Stock Length'))
    height = fields.Float('Height [m]', 
                          digits=dp.get_precision('Stock Length'))
    length = fields.Float('Length [m]', 
                          digits=dp.get_precision('Stock Length'))
    surface = fields.Float('Surface [m2]',
                          digits=dp.get_precision('Stock Surface'))

    @api.onchange('width','height','length')
    def onchange_dimensions(self):
        self.surface = self.length * self.width
        self.volume = self.length * self.width * self.height
        return False

    @api.onchange('weight_kind','surface','width','height','length','volume')
    def onchange_weight(self):
        p = self
        
        if p.weight_kind == 'length':
            p.weight = p.weight_factor * p.length
        elif p.weight_kind == 'width':
            p.weight = p.weight_factor * p.width
        elif p.weight_kind == 'height':
            p.weight = p.weight_factor * p.height
        elif p.weight_kind == 'surface':
            p.weight = p.weight_factor * p.surface
        elif p.weight_kind == 'volume':
            p.weight = p.weight_factor * p.volume
        return False


class ProductProduct(models.Model):
    _inherit = 'product.product'

    weight_factor = fields.Float('Weight Factor [kg/unit]',
                           compute="get_weight_factor", inverse="set_weight_factor",
                           digits=dp.get_precision('Stock Weight'),
                           help="The weight factor")
    weight = fields.Float('Weight [kg]',
                           compute="get_weight", inverse="set_weight",
                           digits=dp.get_precision('Stock Weight'),
                           help="The weight of the contents in Kg, not including any packaging, etc.")
    volume = fields.Float('Volume [m3]',
                           compute="get_volume", inverse="set_volume",
                           digits=dp.get_precision('Stock Volume'))
    surface = fields.Float('Surface [m2]',
                           compute="get_surface", inverse="set_surface",
                           digits=dp.get_precision('Stock Surface'))
    width = fields.Float('Width [m]',
                         compute="get_width", inverse="set_width",
                         digits=dp.get_precision('Stock Length'))
    height = fields.Float('Height [m]',
                          compute="get_height", inverse="set_height",
                          digits=dp.get_precision('Stock Length'))
    length = fields.Float('Length [m]',
                          compute="get_length", inverse="set_length",
                          digits=dp.get_precision('Stock Length'))

    variant_weight_factor = fields.Float('Weight Factor [kg/unit]')
    variant_weight = fields.Float('Weight [kg]')
    variant_volume = fields.Float('Volume [m3]')
    variant_surface = fields.Float('Surface [m2]')
    variant_width = fields.Float('Width [m]')
    variant_height = fields.Float('Height [m]')
    variant_length = fields.Float('Length [m]')

    def get_weight_factor(self):
        for product in self:
            product.weight_factor = product.variant_weight_factor if product.variant_weight_factor != 0 else \
                             product.product_tmpl_id.weight_factor

    def set_weight_factor(self):
        for product in self:
            product.variant_weight_factor = product.weight_factor


    def get_weight(self):
        for product in self:
            product.weight = product.variant_weight if product.variant_weight != 0 else \
                             product.product_tmpl_id.weight

    def set_weight(self):
        for product in self:
            product.variant_weight = product.weight


    def get_volume(self):
        for product in self:
            product.volume = product.variant_volume if product.variant_volume != 0 else \
                             product.product_tmpl_id.volume

    def set_volume(self):
        for product in self:
            product.variant_volume = product.volume


    def get_surface(self):
        for product in self:
            product.surface = product.variant_surface if product.variant_surface != 0 else \
                              product.product_tmpl_id.surface

    def set_surface(self):
        for product in self:
            product.variant_surface = product.surface


    def get_length(self):
        for product in self:
            product.length = product.variant_length if product.variant_length != 0 else \
                             product.product_tmpl_id.length

    def set_length(self):
        for product in self:
            product.variant_length = product.length


    def get_width(self):
        for product in self:
            product.width = product.variant_width if product.variant_width != 0 else \
                            product.product_tmpl_id.width

    def set_width(self):
        for product in self:
            product.variant_width = product.width


    def get_height(self):
        for product in self:
            product.height = product.variant_height if product.variant_height != 0 else \
                            product.product_tmpl_id.height

    def set_height(self):
        for product in self:
            product.variant_height = product.height

    @api.onchange('width','height','length')
    @api.depends('width','height','length')
    def onchange_variant_dimensions(self):
        self.variant_surface = self.length * self.width
        self.variant_volume = self.length * self.width * self.height
        self.onchange_variant_weight()
        self.get_volume()
        self.get_weight()
        self.get_surface()
        return False

    @api.onchange('weight_kind','weight_factor','surface','width','height','length','volume')
    @api.depends('weight_kind','weight_factor','surface','width','height','length','volume')
    def onchange_variant_weight(self):
        p = self
        
        if p.weight_kind == 'length':
            p.variant_weight = p.weight_factor * p.length
        elif p.weight_kind == 'width':
            p.variant_weight = p.weight_factor * p.width
        elif p.weight_kind == 'height':
            p.variant_weight = p.weight_factor * p.height
        elif p.weight_kind == 'surface':
            p.variant_weight = p.weight_factor * p.surface
        elif p.weight_kind == 'volume':
            p.variant_weight = p.weight_factor * p.volume
        return False


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    base = fields.Selection(selection_add=[
        ('volume', 'Volume, price per m3'),
        ('surface', 'Surface, price per m2'),
        ('weight', 'Weight, price per kg'),
        ('length', 'Length, price per m'),
        ('width', 'Width, price per m'),
        ('height', 'Height, price per m'),
    ])

    @api.one
    @api.depends('categ_id', 'product_tmpl_id', 'product_id', 'compute_price', 'fixed_price', \
        'pricelist_id', 'percent_price', 'price_discount', 'price_surcharge')
    def _get_pricelist_item_name_price(self):
        if self.categ_id:
            self.name = _("Category: %s") % (self.categ_id.display_name)
        elif self.product_tmpl_id:
            self.name = self.product_tmpl_id.name
        elif self.product_id:
            self.name = self.product_id.display_name.replace('[%s]' % self.product_id.code, '')
        else:
            self.name = _("All Products")

        if self.compute_price == 'fixed':
            self.price = ("%s %s") % (self.fixed_price, self.pricelist_id.currency_id.name)
        elif self.compute_price == 'percentage':
            self.price = _("%s %% discount") % (self.percent_price)
        else:
            self.price = _("%s %% discount and %s surcharge") % (self.price_discount, self.price_surcharge)



class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    @api.multi
    def action_show_items(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Pricelist items for %s") % self.name,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'product.pricelist.item',
            'domain': [('pricelist_id', '=', self.id)],
            'context': {'default_pricelist_id': self.id},
        }

