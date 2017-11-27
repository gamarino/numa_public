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


from odoo import models, fields, api, modules, exceptions, SUPERUSER_ID
from odoo.tools.translate import _
from odoo import http
from odoo.loglevels import exception_to_unicode, ustr

import odoo

import datetime
import sys
import inspect

import logging
_logger=logging.getLogger(__name__)

DT_FORMAT = "%Y-%m-%d %H:%M:%S"

class VariableValue(models.Model):
    _name = "base.variable_value"

    frame = fields.Many2one('base.frame', 'Frame',
                            on_delete="cascade")
    sequence = fields.Integer('Sequence')
    name = fields.Char('Name', readonly=True)
    value = fields.Text('Value', readonly=True)

class Frame(models.Model):
    _name = "base.frame"

    gexception = fields.Many2one('base.general_exception', 'Exception',
                                 on_delete="cascade")
    src_code = fields.Text('Source code', readonly=True)
    line_number = fields.Integer('Line number', readonly=True)
    file_name = fields.Char('File name', readonly=True)
    locals = fields.One2many('base.variable_value', 'frame', 'Local variables',
                             readonly=True)

    def name_get(self):
        res = []
        for f in self:
            res.append((f.id, "%s, %d" % (f.file_name, f.line_number)))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', context=None, limit=80):
        frames = self.search(['|', ('file_name', operator, name), ('line_number', operator,name)],
                             limit=limit)
                          
        return frames.name_get()

class GeneralException (models.Model):
    _name = "base.general_exception"
    _order = "timestamp desc"

    name = fields.Char('ID', readonly=True)
    service = fields.Char('Service', readonly=True)
    exception = fields.Text('Exception', readonly=True)
    method = fields.Char('Method', readonly=True)
    params = fields.Text('Params', readonly=True)
    timestamp = fields.Datetime('Timestamp', readonly=True)
    do_not_purge = fields.Boolean('Do not purge?', readonly=True)
    user = fields.Many2one('res.users', 'User', readonly=True, on_delete='null')
    frames = fields.One2many('base.frame', 'gexception', 'Frames', readonly=True)

    @api.model
    def create(self, vals):
        vals = vals or {}
        vals['name'] = self.env['ir.sequence'].next_by_code('base.general_exception') or '/'
        vals['timestamp'] = fields.Datetime.now()
        return super(GeneralException, self).create(vals)
        
    def action_frames(self):
        self.ensure_one()

        ge = self
        return {
            'name':_("Frames"),
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'base.frame',
            'type': 'ir.actions.act_window',
            'domain': [('gexception','=',ge.id)],
            'context': dict(default_gexception=ge.id),
            'nodestroy': True,
            'context': False,
        }
        
    def action_clean(self):
        now = datetime.datetime.utcnow()
        one_month_before_dt = now - datetime.timedelta(days=30)
        one_month_before = one_month_before_dt.strftime(DT_FORMAT)
        to_delete = super(GeneralException, self).search([('do_not_purge','!=',True),
                                         ('timestamp','<',one_month_before)])
        _logger.info("Cleaning old exceptions. %d eligible exceptions found" % len(to_delete))
        if to_delete:
            to_delete.unlink()
        
        return True

def register_exception(service_name, method, params, db, uid, e):

    if not db:
        return None

    registry = modules.registry.RegistryManager.get(db)

    if not registry:
        return None

    cr = registry.cursor()

    if "base.general_exception" in registry:
        with api.Environment.manage():
            env = api.Environment(cr, SUPERUSER_ID, {})
            ge_obj = env["base.general_exception"]

            tb = sys.exc_info()[2]
            if tb:
                frames = []
                count = 0
                while tb:
                    frame = tb.tb_frame
                    local_vars = []
                    output = ''
                    try:
                        if count >= 0:
                            local_vars = [(0,0,{'name': ustr(k), 'value': ustr(v)}) for k,v in frame.f_locals.items()]
                            local_vars.sort(key=lambda x: x[2]['name'])
                            seq = 1
                            for lv in local_vars:
                                lv[2]['sequence'] = seq
                                seq += 1
                            lines, lineno = inspect.getsourcelines(frame)
                            for l in lines:
                                if lineno >= (frame.f_lineno - 10) and lineno <= (frame.f_lineno + 10):
                                    output += u"%s%d: %s" % (frame.f_lineno == lineno and '*' or ' ', lineno, l)
                                lineno += 1
                    except Exception, process_exception:
                        output += "\nEXCEPTION DURING PROCESSING: %s" % exception_to_unicode(process_exception)

                    frames.append((0,0, {'file_name': frame.f_code.co_filename,
                                         'line_number': frame.f_lineno,
                                         'src_code': output,
                                         'locals': local_vars}))
                    count += 1
                    tb = tb.tb_next
                frames.reverse()

                vals = {
                    'service': service_name,
                    'exception': exception_to_unicode(e),
                    'method': method,
                    'params' : unicode(params or []),
                    'do_not_purge': False,
                    'user': uid,
                    'frames': frames,
                }
                _logger.error("About to log exception [%s], on service [%s, %s, %s]" %
                              (exception_to_unicode(e),
                               service_name, method, params))
                try:
                    ge = ge_obj.sudo().create(vals)
                    ename = ge.name
                    cr.commit()
                    cr.close()
                    return ename

                except Exception, loggingException:
                    _logger.error("Error logging exception, exception [%s]" %
                                  exception_to_unicode(loggingException))

    cr.close()
    return None
    
old_dispatch_rpc = odoo.http.dispatch_rpc

def new_dispatch_rpc(service_name, method, params):
    global old_dispatch_rpc

    try:
        return old_dispatch_rpc(service_name, method, params)
    except Exception, e:
        if service_name in ['object', 'report'] and \
           not isinstance(e, exceptions.except_orm):
            (db, uid, passwd) = params[0:3]
            ename = register_exception(
                        'RPC %s' % service_name,
                        method,
                        params,
                        db,
                        uid,
                        e)
            if ename:
                e = exceptions.UserError(_('System error %s. Get in touch with your System Admin') % ename)

        raise e

odoo.http.dispatch_rpc = new_dispatch_rpc

old_json_dispatch = odoo.http.JsonRequest.dispatch

def new_json_dispatch(self):
    global old_json_dispatch

    try:
        return old_json_dispatch(self)

    except Exception, e:
        if not isinstance(e, exceptions.except_orm):
            model = 'JSON %s' % self.params.get('model', 'unknown model')
            method = self.params.get('method', 'unknown method')
            params = self.params.get('args', [])
            db = self.session.db
            uid = self.session.uid

            ename = register_exception(
                        model,
                        method,
                        params,
                        db,
                        uid,
                        e)
            if ename:
                e = exceptions.UserError(_('System error %s. Get in touch with your System Admin') % ename)

        raise e

odoo.http.JsonRequest.dispatch = new_json_dispatch

old_json_handle_exception = odoo.http.JsonRequest._handle_exception

def new_json_handle_exception(self, exception):
    global old_json_handle_exception

    if not isinstance(exception, exceptions.except_orm):
        model = 'JSONE %s' % self.params.get('model', 'unknown model')
        method = self.params.get('method', 'unknown method')
        params = self.params.get('args', [])
        db = self.session.db
        uid = self.session.uid

        ename = register_exception(
                    model,
                    method,
                    params,
                    db,
                    uid,
                    exception)

        if ename:
            exception = exceptions.UserError(_('System error %s. Get in touch with your System Admin') % ename)

    return old_json_handle_exception(self, exception)

odoo.http.JsonRequest._handle_exception = new_json_handle_exception
