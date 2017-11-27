##############################################################################
#
# Copyright (c) 2008-2012 Alistek Ltd (http://www.alistek.com) All Rights Reserved.
#                    General contacts <info@alistek.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 3
# of the License, or (at your option) any later version.
#
# This module is GPLv3 or newer and incompatible
# with OpenERP SA "AGPL + Private Use License"!
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from odoo import models, fields, exceptions
from odoo.tools import convert_xml_import
from odoo.tools.translate import _
import base64
import lxml.etree
import zipfile
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

class report_aeroo_import(models.TransientModel):
    _name = 'aeroo.report_import'
    _description = 'Aeroo report import wizard'
    
    name = fields.Char('Name')
    file = fields.Binary('Aeroo report file', filters='*.aeroo', required=True)
    info = fields.Text('Info', readonly=True)
    state = fields.Selection([
            ('draft','Draft'),
            ('info','Info'),
            ('done','Done'),
        ],'State', index=True, readonly=True, default='draft')

    def default_get(self, fields_list=[]):
        values = {'state': 'draft'}
        default_ids = self.env.context.get('default_ids')
        if default_ids:
            this = self.read(default_ids, ['name','state','file','info'])[0]
            del this['id']
            values.update(this)
        return values

    def install_report(self):
        self.ensure_one()
        report_obj = self.env.get('ir.actions.report.xml')
        this = self
        if report_obj.search([('report_name','=',this.name)]):
            raise exceptions.UserError(_('Report with service name "%s" already exist in system!') % this.name)
        fd = StringIO()
        fd.write(base64.decodestring(this.file))
        fd.seek(0)
        convert_xml_import(cr, 'report_aeroo', fd, {}, 'init', noupdate=True)
        fd.close()
        this.state = 'done'
        report = report_obj.search([('report_name','=',this.name)])[-1]
        event_id = self.env.get('ir.values').set_action(report.report_name, 'client_print_multi', report.model, 'ir.actions.report.xml,%d' % report.id)
        if report.report_wizard:
            report._set_report_wizard(report.id)

        mod_obj = self.env.get('ir.model.data')
        act_obj = self.env.get('ir.actions.act_window')

        mod = mod_obj.search([('name', '=', 'action_aeroo_report_xml_tree')])[0]
        res_id = mod_obj.read(mod.id, ['res_id'])['res_id']
        act_win = act_obj.read(res_id, [])
        act_win['domain'] = [('id','=',report.id)]
        return act_win

    def next(self):
        self.ensure_one()
        this = self
        file_data = base64.decodestring(this.file)
        zip_stream = StringIO()
        zip_stream.write(file_data)
        zip_obj = zipfile.ZipFile(zip_stream, mode='r', compression=zipfile.ZIP_DEFLATED)
        if zipfile.is_zipfile(zip_stream):
            report_obj = self.env.get('ir.actions.report.xml')
            self.env.context['allformats'] = True
            mimetypes = dict(report_obj._get_in_mimetypes(cr, uid, context=context))
            styles_select = dict(report_obj._columns['styles_mode'].selection)
            if 'data.xml' in zip_obj.namelist():
                data = zip_obj.read('data.xml')
            else:
                raise exceptions.UserError(_('Aeroo report file is invalid!'))
            tree = lxml.etree.parse(StringIO(data))
            root = tree.getroot()
            info = ''
            report = root.xpath("//data/record[@model='ir.actions.report.xml']")[0]
            style = root.xpath("//data/record[@model='report.stylesheets']")[0]
            rep_name = report.find("field[@name='name']").text
            rep_service = report.find("field[@name='report_name']").text
            rep_model = report.find("field[@name='model']").text
            rep_format = eval(report.find("field[@name='out_format']").attrib['search'], {})[0][2]
            rep_charset = report.find("field[@name='charset']").text
            parser_state = report.find("field[@name='parser_state']").text
            styles_mode = report.find("field[@name='styles_mode']").text
            tml_source = report.find("field[@name='tml_source']").text

            info += "Name: %s\n" % rep_name
            info += "Object: %s\n" % rep_model
            info += "Service Name: %s\n" % rep_service
            info += "Format: %s\n" % mimetypes.get(rep_format,'oo-odt')
            info += "Template: %s\n" % (tml_source=='parser' and 'defined by parser' or 'static')
            if rep_format=='genshi-raw':
                info += "Charset: %s\n" % rep_charset
            info += "Parser: %s\n" % (parser_state in ('def','loc') and 'customized' or 'default')
            info += "Stylesheet: %s%s\n" % (styles_select[styles_mode].lower(), style is not None and " (%s)" % style.find("field[@name='name']").text)
            this.write({'name':rep_service,'info':info,'state':'info','file':base64.encodestring(data)})
        else:
            raise exceptions.UserError(_('Is not Aeroo report file.'))

        mod_obj = self.env.get('ir.model.data')
        act_obj = self.env.get('ir.actions.act_window')

        mod = mod_obj.search([('name', '=', 'action_aeroo_report_import_wizard')])[0]
        res_id = mod_obj.read(mod.id, ['res_id'])['res_id']
        act_win = act_obj.read(res_id, [])
        act_win['domain'] = [('id','in',[this.id])]
        act_win['context'] = {'default_ids':[this.id]}
        return act_win
