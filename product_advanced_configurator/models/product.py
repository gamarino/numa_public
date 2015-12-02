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

from openerp import models, fields, api
from openerp.tools.translate import _
from openerp.exceptions import except_orm

import logging
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = "product.template"

    vc_message = fields.Text('Variant creation message',
                             help="Message to be use by configurators to describe the possible variants")
    
    on_configuration = fields.Text('On configuration',
                                   help="Code triggered on end of configuration. Parameter: <self>, <container>")
    @api.one
    def action_on_configuration(self, options, container=None):
        if self.on_change:
            localdict = {'self': self, 'options': options, 'container': container}
            exec self.on_configuration in globals(), localdict

    on_change = fields.Text('On change',
                            help="Code triggered on any change in configurator. Parameters: <self>, <container>")
    @api.one
    def action_on_change(self, options, container=None):
        for parent in self.parents:
            parent.action_on_change(options, container=None)
        if self.on_change:
            localdict = {'self': self, 'options': options, 'container': container}
            exec self.on_change in globals(), localdict
            
    on_variant_creation = fields.Text('On variant creation',
                                      help="Code triggered on variant creation. Parameters: <self>, <new_variant>")
    @api.one
    def action_on_variant_creation(self, new_variant):
        for parent in self.parents:
            parent.action_on_change(new_variant)
        if self.on_change:
            localdict = {'self': self, 'new_variant': new_variant}
            exec self.on_variant_creation in globals(), localdict
            
    @api.depends('parents','own_attribute_lines','attribute_line_ids')
    @api.multi
    def _getAttributeLines(self):
        for template in self:
            attrs = set()
            for a in template.own_attribute_lines:
                attrs.add(a)
            if template.parents:
                for p in template.parents:
                    for a in p.attribute_line_ids:
                        attrs.add(a)
            template.attribute_line_ids = [(4, a.id) for a in list(attrs)]

    @api.depends('parent_domain', 'parents')            
    @api.multi
    def _getParentDomain(self):
        for template in self:
            parentSet = set()
            if template.parents:
                for p in template.parents:
                    for t in p.parent_domain:
                        parentSet.add(t)
            template.parent_domain = [(6, 0, [p.id for p in list(parentSet)])]
            
    parents = fields.Many2many('product.template', 'product_parents', 'product_id', 'parent_id', 'Parent products')
    parent_domain = fields.One2many('product.template', string='Parents domain',
                                    compute='_getParentDomain')
    attribute_line_ids = fields.One2many('product.attribute.line', string='Product Attributes Lines',
                                          compute='_getAttributeLines', store=False)
    own_attribute_lines = fields.One2many('product.attribute.line', 'product_tmpl_id', 'Own attribute lines')

    @api.multi
    def get_options_dict(self):
        self.ensure_one()
        return self.attribute_line_ids.mapped(
            lambda al: {'attribute_line': al.id,
                        'selection': al.default and al.default.id or False,
                        'display_value': al.default and al.default.name_get()[0][1] or False,
                        'price_extra': al.price_extra,
                        'sequence': al.sequence})
        
    @api.multi
    def get_variant(self, options):
        pav_obj = self.env['product.attribute.value']
        variant_obj = self.env['product.product']
        
        self.ensure_one()

        template = self
        
        idxOptions = {o.attribute: o for o in options}
        
        for al in template.attribute_line_ids:
            if not al.required:
                continue
            option = idxOptions(al.attribute_id)
            if not option or not option.display_value:
                return False
            if al.attr_type == 'string' and not option.string_value:
                return False
            elif al.attr_type == 'range' and \
                 (option.numeric_value < al.attribute.min_range or \
                  option.numeric_value > al.attribute.max_range):
                return False
            elif al.attr_type == 'select' and not option.selection:
                return False
            elif al.attr_type == 'product' and not option.product:
                return False
            elif al.attr_type == 'variant' and not option.variant:
                return False
            elif al.attr_type == 'category' and not option.category: 
                return False

        av_ids = []
        for option in options:
            if option.attr_type == 'select' or option.selection:
                av_ids.append(option.selection.id)
            else:
                if option.attr_type in ['numeric','range']:
                    domain = [('numeric_value', '=', option.numeric_value)]
                elif option.attr_type in ['string']:
                    domain = [('string_value', '=', option.string_value)]
                elif option.attr_type in ['product'] and option.product:
                    domain = [('product', '=', option.product.id)]
                elif option.attr_type in ['variant'] and option.variant:
                    domain = [('variant', '=', option.variant.id)]
                elif option.attr_type in ['category'] and option.category:
                    domain = [('category', '=', option.category.id)]
                elif option.attr_type in ['select'] and option.category:
                    domain = [('value', '=', option.selection.id)]
                else:
                    return False
                values = pav_obj.search([('attribute_id','=',option.attribute.id)] + domain)
                if values:
                    av_ids.append(values[0].id)
                else:
                    return False
                    
        domain = [('product_tmpl_id', '=', template.id)]
        for av_id in av_ids:
            domain.append(('attribute_value_ids', '=', av_id))
        variants = variant_obj.search(domain)
        if variants and isinstance(variants[0], (int, long)):
            variants = variant_obj.browse(variants)
        for variant in variants:
            avFound = True
            for av in variant.attribute_value_ids:
                if av.id not in av_ids:
                    avFound = False
                    break
            if avFound and len(variant.attribute_value_ids) == len(av_ids):
                return variant
                
        return False

    @api.multi
    def create_variant(self, options):
        pav_obj = self.env['product.attribute.value']
        variant_obj = self.env['product.product']
        
        self.ensure_one()

        template = self
        
        idxOptions = {o.attribute: o for o in options}
        
        for al in template.attribute_line_ids:
            if not al.required:
                continue
            option = idxOptions(al.attribute_id)
            if not option or not option.display_value:
                return False
            if al.attr_type == 'string' and not option.string_value:
                return False
            elif al.attr_type == 'range' and \
                 (option.numeric_value < al.attribute.min_range or \
                  option.numeric_value > al.attribute.max_range):
                return False
            elif al.attr_type == 'select' and not option.selection:
                return False
            elif al.attr_type == 'product' and not option.product:
                return False
            elif al.attr_type == 'variant' and not option.variant:
                return False
            elif al.attr_type == 'category' and not option.category: 
                return False

        av_ids = []
        for option in options:
            if option.attr_type == 'select':
                av_ids.append(option.selection.id)
            else:
                name = option.display_value
                if option.attr_type in ['numeric','range']:
                    domain = [('numeric_value', '=', option.numeric_value)]
                    name = str(option.numeric_value)
                elif option.attr_type in ['string']:
                    domain = [('string_value', '=', option.string_value)]
                    name = option.string_value
                elif option.attr_type in ['product'] and option.product:
                    domain = [('product', '=', option.product.id)]
                elif option.attr_type in ['variant'] and option.variant:
                    domain = [('variant', '=', option.variant.id)]
                elif option.attr_type in ['category'] and option.category:
                    domain = [('category', '=', option.category.id)]
                elif option.attr_type in ['select'] and option.category:
                    domain = [('value', '=', option.selection.id)]
                else:
                    return False
                values = pav_obj.search([('attribute_id','=',option.attribute.id)] + domain)
                if values:
                    av_ids.append(values[0].id)
                else:
                    attr_vals = {
                        'name': name,
                        'attribute_id': option.attribute.id,
                        'display_value': option.display_value,
                        'string_value': option.string_value,
                        'numeric_value': option.numeric_value,
                        'product': option.product and option.product.id or False,
                        'variant': option.variant and option.variant.id or False,
                        'category': option.category and option.category.id or False,
                    }
                    new_value = pav_obj.create(attr_vals)
                    av_ids.append(new_value.id)
        domain = [('product_tmpl_id', '=', template.id)]
        domain.append(('attribute_value_ids', 'in', av_ids)) 
        variants = variant_obj.search(domain)
        for variant in variants:
            avFound = True
            for av in variant.attribute_value_ids:
                if av.id not in av_ids:
                    avFound = False
                    break
            if avFound and len(variant.attribute_value_ids) == len(av_ids):
                return variant
        return variant_obj.create({'product_tmpl_id': template.id,
                                   'attribute_value_ids': [(6, 0, av_ids)]})
        
    @api.multi
    def write(self, vals):
        nvals = vals and vals.copy() or {}
        if 'parents' in vals:
            for template in self:
                for command in nvals['parents']:
                    if command[0] == 6:
                        for proposed_parent_id in command[2]:
                            proposed_parent = self.browse(proposed_parent_id)
                            if proposed_parent in template.parent_domain:
                                raise except_orm(_('Error'),
                                                 _('No recursive partners are allowed [template: %(template)s, parent: %(parent)s]! Please check it') \
                                                  % {'template': template.display_name, 
                                                     'parent': proposed_parent.display_name})
                    elif command[0] == 4:
                        proposed_parent = self.browse(command[1])
                        if proposed_parent in template.parent_domain:
                            raise except_orm(_('Error'),
                                             _('No recursive partners are allowed [template: %(template)s, parent: %(parent)s]! Please check it') \
                                              % {'template': template.display_name, 
                                                 'parent': proposed_parent.display_name})
                        
        if 'attribute_line_ids' in nvals:
            new_commands = []
            for command in vals['attribute_line_ids']:
                cmd = command[0]
                cid = command[1]
                vals = command[2] if len(command) > 2 else None

                if cmd in (0, 1, 4, 5, 6):
                    # same action
                    new_commands.append((cmd, cid, vals))
                elif cmd in (2, 3):
                    # Removes only if they belong to the products
                    if cid in [pt.id for pt in self]:
                        new_commands.append((cmd, cid, vals))
            nvals['own_attribute_lines'] = new_commands
                
            del nvals['attribute_line_ids']
        return super(ProductTemplate, self).write(nvals)
        
    @api.multi
    def action_create_variant(self):
        variant_obj = self.env['product.product']
        configurator_obj = self.env['product.configurator']

        p = self
        if p.attribute_line_ids:
            vals = {
                'template': p.id,
                'options': [(0,0,od) for od in p.get_options_dict()]
            }
            configurator = configurator_obj.create(vals)
            return {
                'name': _("Configure product"),
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'product.configurator',
                'res_id': configurator.id,
                'type': 'ir.actions.act_window',
                'target': 'new',
                'nodestroy': False,
            }
        else:
            vals = {
                'product_tmpl_id': p.id,            
            }
            variant = variant_obj.create(vals)
            return {
                'name': _("New variant"),
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'product.product',
                'res_id': variant.id,
                'type': 'ir.actions.act_window',
                'nodestroy': False,
                'context': {},
            }

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.multi
    def get_options_dict(self):
        self.ensure_one()
        
        p = self
        def getAttributeDictionary(al):
            pav = None
            for av in p.attribute_value_ids:
                if av.attribute_id == al.attribute_id:
                    pav = av
                    break
            return {
                'sequence': al.sequence,
                'attribute_line': al.id,
                'attribute': al.attribute_id.id,
                'description': al.attribute_id.description,
                'attribute_image': al.attribute_id.image,
                'attr_type': al.attribute_id.attr_type,
                'required': al.required,
                'price_extra': al.price_extra,
                'display_value': pav and (pav.display_value or pav.name) or False,
                'string_value': pav and pav.string_value or False,
                'numeric_value': pav and pav.numeric_value or 0.0,
                'min_range': al.attribute_id.min_range,
                'max_range': al.attribute_id.max_range,
                'selection_domain': [sav.id for sav in al.value_ids],
                'selection': pav and pav.id or False,
                'selection_description': pav and pav.description or False,
                'selection_image': pav and pav.image or False,
                'product': pav and pav.product and pav.product.id or False,
                'variant': pav and pav.variant and pav.variant.id or False,
                'category': pav and pav.category and pav.category.id or False,
            }
    
        return [getAttributeDictionary(al)
                for al in p.product_tmpl_id.attribute_line_ids]

class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    attr_type = fields.Selection(required=True, selection=[
        ('select', 'Select'),
        ('range', 'Range'),
        ('numeric', 'Numeric'),
        ('string', 'String'),
        ('product', 'Product'),
        ('variant', 'Variant'),
        ('category', 'Category'),
    ], string="Type", default='select')
    min_range = fields.Float('Min', digits=(12, 6))
    max_range = fields.Float('Max', digits=(12, 6))
    
    description = fields.Text('Description')
    image = fields.Binary('Image')

    on_change = fields.Text('On change',
                            help="Code triggered on any change in configurator. Parameters: <self>")
    @api.one
    def action_on_change(self):
        if self.on_change:
            localdict = {'self': self}
            exec self.on_change in globals(), localdict

    _sql_constraints = [
        ('number_uniq', 'unique(name)', _('Attribute Name must be unique!'))]

class ProductAttributeLine(models.Model):
    _inherit = "product.attribute.line"

    sequence = fields.Integer("Sequence")
    required = fields.Boolean('Required')
    default = fields.Many2one('product.attribute.value', 'Default')
    attr_type = fields.Selection(string='Type', store=False,
                                 related='attribute_id.attr_type')
    price_extra = fields.Float('Extra price')
    
    on_change = fields.Text('On change', option=None)
    @api.one
    def action_on_change(self):
        if self.on_change:
            localdict = {'self': self}
            exec self.on_change in globals(), localdict

class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    attr_type = fields.Selection(string='Type',
                                 related='attribute_id.attr_type')
    display_value = fields.Char('Value')
    string_value = fields.Char('String Value')
    numeric_value = fields.Float('Numeric Value', digits=(12, 6))
    product = fields.Many2one('product.template', 'Product')
    variant = fields.Many2one('product.product', 'Variant')
    category = fields.Many2one('product.category', 'Product category')

    description = fields.Text('Description')
    image = fields.Binary('Image')
    
    @api.multi
    def name_get(self):
        res = []
        for value in self:
            res.append([value.id, "%s: %s" % (value.attribute_id.name, value.display_value or value.name)])
        return res

    on_change = fields.Text('On change')
    @api.one
    def action_onchange(self):
        if self.on_change:
            localdict = {'self': self}
            eval(self.on_change, localdict)
    
class ProductConfiguratorOption(models.TransientModel):
    _name = "product.configurator.option"
    _order = 'sequence'
    
    sequence = fields.Integer('Sequence')
    configurator = fields.Many2one('product.configurator', 'Configurator')
    attribute_line = fields.Many2one('product.attribute.line', 'Attribute line')
    attribute = fields.Many2one('product.attribute', 'Attribute',
                                related='attribute_line.attribute_id')
    description = fields.Text('Description',
                              related='attribute_line.attribute_id.description')
    attribute_image = fields.Binary('Attribute Image',
                         related='attribute_line.attribute_id.image')
    attr_type = fields.Selection('Attribute type',
                              related='attribute_line.attribute_id.attr_type')
    required = fields.Boolean('Required',
                              related='attribute_line.required')
    price_extra = fields.Float('Extra price',
                                related='attribute_line.price_extra')

    display_value = fields.Char('Value')

    string_value = fields.Char('String Value')
    
    numeric_value = fields.Float('Numeric value', digits=(12,6))
    min_range = fields.Float('Minimun', digits=(12,6),
                             related='attribute.min_range')
    max_range = fields.Float('Maximun', digits=(12,6),
                             related='attribute.max_range')

    selection_domain = fields.Many2many('product.attribute.value', 'Selection domain',
                                       related='attribute_line.value_ids')
    selection = fields.Many2one('product.attribute.value', 'Selection')
    selection_description = fields.Text('Description',
                                        related='selection.description')
    selection_image = fields.Binary('Image',
                                   related='selection.image')
    product = fields.Many2one('product.template', 'Product')
    variant = fields.Many2one('product.product', 'Variant')
    category = fields.Many2one('product.category', 'Product category')

    @api.onchange('numeric_value', 'selection', 'product', 'variant', 'category', 'string_value')
    @api.one
    def onchange_values(self):
        option = self
        if option.attr_type == 'string':
            display_value = "%s: %s" % (option.attribute.name, option.string_value)
        elif option.attr_type in ['numeric','range']:
            display_value = "%s: %s" % (option.attribute.name, str(option.numeric_value))
        elif option.attr_type == 'select':
            display_value = option.selection and option.selection.name_get()[0][1] or ''
        elif option.attr_type == 'product':
            display_value = option.product and "%s: %s" % (option.attribute.name, option.product.name_get()[0][1]) or ''
        elif option.attr_type == 'variant':
            display_value = option.variant and "%s: %s" % (option.attribute.name, option.variant.name_get()[0][1]) or ''
        elif option.attr_type == 'category':
            display_value = option.category and "%s: %s" % (option.attribute.name, option.category.name_get()[0][1]) or ''
        else:
            display_value = False

        option.display_value = display_value

        if option.attribute:
            option.attribute.action_on_change()
            
        if option.attribute_line:
            option.attribute_line.action_on_change()

class ProductConfigurator(models.TransientModel):
    _name = "product.configurator"
    _rec_name = 'template'    
    
    template = fields.Many2one('product.template', 'Product')
    template_message = fields.Text('Product message',
                                   related="template.vc_message")
    options = fields.One2many('product.configurator.option', 'configurator', 'Options')
    conf_message = fields.Text('Configurator message')
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
    def name_get(self):
        res = []
        for pc in self:
            res.append((pc.id, _('Configurator')))

        return res        

    @api.onchange('options')
    @api.one
    def onchange_options(self):
        pc = self
        if pc.template:
            pc.template.action_on_change(pc.options, pc)

    @api.multi
    def create_variant(self):
        self.ensure_one()
        pc = self

        variant = pc.template.create_variant(pc.options)
        if not variant:
            raise except_orm(_('Error'),
                             _('No variant could be created! Please check it'))
        pc.template.action_on_variant_creation(variant)
        return variant
        
    @api.multi
    def action_select(self):
        self.ensure_one()
        pc = self
        
        pc.template.action_on_configuration(pc.options)
        res = self.create_variant()

        return {
            'name': _("New variant"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'product.product',
            'res_id': res.id,
            'type': 'ir.actions.act_window',
            'nodestroy': False,
            'context': {},
        }
