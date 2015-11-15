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


from openerp.osv.orm import Model, TransientModel
from openerp.osv import fields, orm, osv 
from openerp.loglevels import ustr
import datetime
import openerp
import sys
import traceback
import inspect
import functools
import logging
_logger=logging.getLogger(__name__)
from openerp.tools.translate import _
from openerp.addons import web
from openerp.http import request
from openerp import http
import openerp.modules.registry

SUPERUSER_ID = 1
DT_FORMAT = "%Y-%m-%d %H:%M:%S"

class variable_value(Model):
    _name = "base.variable_value"
    
    _columns = {
        'frame': fields.many2one('base.frame', 'Frame', on_delete="cascade"),
        'sequence': fields.integer('Sequence'),
        'name': fields.char('Name', size=64, readonly=True),
        'value': fields.text('Value', readonly=True),
    }

class frame(Model):
    _name = "base.frame"
    
    _columns = {
        'gexception': fields.many2one('base.general_exception', 'Exception', on_delete="cascade"),
        'src_code': fields.text('Source code', readonly=True),
        'line_number': fields.integer('Line number', readonly=True),
        'file_name': fields.text('File name', readonly=True),
        'locals': fields.one2many('base.variable_value', 'frame', 'Local variables'),
    }

    def name_get(self, cr, uid, ids, context=None):
        res = []
        for f in self.browse(cr, uid, ids, context=context):
            res.append((f.id, "%s,%d" % (f.file_name, f.line_number)))
        return res
    
    def name_search(self, cr, uid, 
                     name, args=None, operator='ilike', 
                     context=None, limit=80):
        context = context or {}
        
        ids = self.search(cr, uid, 
                          ['|', ('file_name', operator, name), ('line_number', operator,name)], 
                          limit=limit, context=context)
                          
        return self.name_get(cr, uid, ids, context=context)

    
class general_exception (Model):
    _name = "base.general_exception"
    _order = "timestamp desc"
    
    _columns = {
        'name': fields.char('ID', size=32, readonly=True),
        'service': fields.char('Service', readonly=True),
        'exception': fields.text('Exception', readonly=True),
        'request': fields.text('Request', readonly=True),
        'timestamp': fields.datetime('Timestamp', readonly=True),
        'do_not_purge': fields.boolean('Do not purge?', readonly=True),
        'user': fields.many2one('res.users', 'User', readonly=True, on_delete='null'),
        'frames': fields.one2many('base.frame', 'gexception', 'Frames', readonly=True),
    }
    
    def create(self, cr, uid, vals, context=None):
        vals = vals or {}
        vals['name'] = self.pool.get('ir.sequence').get(cr, uid, 'base.general_exception') or '/'
        vals['timestamp'] = datetime.datetime.now().strftime(DT_FORMAT)
        return super(general_exception, self).create(cr, uid, vals, context=context)
        
    def action_frames(self, cr, uid, ids, context=None):
        assert ids and len(ids)==1, 'One at the time'
        
        ge = self.browse(cr, uid, ids[0], context=context)
        return {
            'name':_("Frames"),
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'base.frame',
            'type': 'ir.actions.act_window',
            'domain': [('gexception','=',ge.id)],
            'context': dict(context,default_gexception=ge.id),
            'nodestroy': True,
            'context': context or {},
        }
        
    def action_clean(self, cr, uid, ids=[], arg=None, context=None):
        today = datetime.datetime.utcnow()
        one_month_before_dt = today - datetime.timedelta(days=30)
        one_month_before = one_month_before_dt.strftime(DT_FORMAT)
        to_delete_ids = self.search(cr, SUPERUSER_ID, [('do_not_purge','!=',True),
                                                       ('timestamp','<',one_month_before)],
                                                      context=context)
        _logger.info("Cleaning old exceptions. %d eligible exceptions found" % len(to_delete_ids))
        if to_delete_ids:
            self.unlink(cr, SUPERUSER_ID, to_delete_ids, context=context)
        
        return True

def register_exception(db_name, model, uid, e, service, req):
    db = openerp.sql_db.db_connect(db_name)
    cr = db.cursor()
    registry = openerp.registry(cr.dbname)
    ename = "<unknown>"
    if "base.general_exception" in registry:
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
                    output += "\nEXCEPTION DURING PROCESSING: %s" % ustr(process_exception)
                    
                frames.append((0,0, {'file_name': frame.f_code.co_filename,
                                     'line_number': frame.f_lineno,
                                     'src_code': output,
                                     'locals': local_vars}))
                count += 1
                tb = tb.tb_next
            frames.reverse()
            
            ge_obj = registry["base.general_exception"]
            vals = {
                'service': service,
                'exception': unicode(e),
                'request': ustr(req),
                'do_not_purge': False,
                'user': uid,
                'frames': frames,
            }
            ge_id = ge_obj.create(cr, SUPERUSER_ID, vals)
            ge = ge_obj.browse(cr, SUPERUSER_ID, ge_id)
            ename = ge.name
            cr.commit()
    cr.close()
    
    return ename

old_jsonRequest = http.JsonRequest
old_dispatch = http.JsonRequest.dispatch
def new_dispatch(self):
    try:
        if self.jsonp_handler:
            return self.jsonp_handler()
        result = self._call_function(**self.params)
        return self._json_response(result)
    except osv.except_osv, oe:
        return self._handle_exception(oe)
    except Exception, e:
        ename = register_exception(self.session.db,
                                   self.jsonrequest['params'].get('model',''), 
                                   self.session.uid, 
                                   e, 
                                   unicode(self.httprequest), 
                                   unicode(self.jsonrequest))
        return self._handle_exception(
                    osv.except_osv(_('Error!'),
                                   _('Please contact your system administrator, exception ID [%s]') % ename))

http.JsonRequest.dispatch = new_dispatch

    
