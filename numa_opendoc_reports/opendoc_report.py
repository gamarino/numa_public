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
from openerp.osv.osv import except_osv
from openerp.osv.fields import float as float_field, function as function_field, datetime as datetime_field

from datetime import datetime, timedelta, date
import time
from openerp import exceptions as oe_exceptions
import openerp
import sys
import logging
_logger=logging.getLogger(__name__)
from openerp.tools.translate import _
from openerp.tools.safe_eval import safe_eval
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT

import zipfile
import StringIO
from lxml import etree
from lxml.etree import tostring
from itertools import chain
import re
import base64
import pdb

import pytz


SUPERUSER_ID = 1
DT_FORMAT = "%Y-%m-%d %H:%M:%S"
LOOP_TAGS = ['{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row',
             '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}section',
             '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}body']

class LoopSkip(oe_exceptions.AccessError):
    pass

class GeneratorSkip(oe_exceptions.AccessError):
    pass

def get_date_length(date_format=DEFAULT_SERVER_DATE_FORMAT):
    return len((datetime.now()).strftime(date_format))

def open_template(template):
    f = []
    sio = StringIO.StringIO(base64.b64decode(template))
    z = zipfile.ZipFile(sio)
    for name in z.namelist():
        zf = z.open(name)
        f.append((name, zf.read()))
    return f

open_field = re.compile("\[\[")
close_field = re.compile("\]\]")
text_tags = [
    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}span',
    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}text',
]

class IndirectBoolean(object):
    def __init__(self, initialValue = False):
        self.flag = initialValue

    def setTrue(self):
        self.flag = True

    def setFalse(self):
        self.flag = False

    def getValue(self):
        return self.flag


def process_element(ix, objects, remove_function, repeat_function, context=None):
    ox = etree.Element(ix.tag, nsmap=ix.nsmap)

    eval_context = context.copy()
    eval_context['objects'] = objects
    eval_context['repeatIn'] = repeat_function
    eval_context['removeParentNode'] = remove_function

    def full_text(node):
        return ((node.text or '') +
                ''.join(full_text(c) for c in node) +
                (node.tail or ''))
                
    def apply_eval(text, obj, eval_context):
        parts = open_field.split(text)
        
        otext = parts[0]
        parts.pop(0)
        while len(parts) > 0:
            ep = close_field.split(parts[0])
            parts.pop(0)
            expression = ep[0]
            _logger.debug("Evaluando: [%s], con eval_context=[%s]" % (expression, unicode(eval_context)))
            try:
                output = unicode(safe_eval(expression, 
                                           locals_dict=eval_context))
                otext += output
                _logger.debug("Resultado: %s" % output)

            except LoopSkip:
                raise
            except GeneratorSkip:
                raise
            except Exception, e:
                otext += unicode(e)
                _logger.info("Unexpected exception [%s]" % unicode(e))
            if len(ep) > 1:
                otext += ep[1]
        return otext

    # Copy attributes

    for name in ix.keys():
        ox.attrib[name] = apply_eval(ix.get(name), objects, eval_context)

    tparts = open_field.split(ix.text or '')
    if len(tparts) > 1:
        xtext = full_text(ix)
        ox.text = apply_eval(xtext, objects, eval_context)
    else:
        if ix.text:
            ox.text = apply_eval(ix.text, objects, eval_context)
        if ix.tail:
            ox.tail = apply_eval(ix.tail, objects, eval_context)
    
        # Copy/generate children
        children = list(ix)
        for index in range(len(children)):
            se = children[index]
            try:
                def removeParentNode(endingTag):
                    tagToCompare = {
                        'para': 'p',
                        'row': 'row',
                        'table': 'table',
                    }.get(endingTag, 'text')
                    if se.tag.endswith(tagToCompare):
                        raise GeneratorSkip()
                    else:
                        remove_function(endingTag)
                    return ''
    
                def repeatIn(record_list, name):
                    if se.tag not in LOOP_TAGS:
                        if repeat_function:
                            repeat_function(record_list, name)
                        return ''
                    else:
                        for loop_element in record_list:
                            eval_context[name] = loop_element
                            def runRepeatIn(record_list, name):
                                return ''                
                            ox.append(process_element(se, objects, removeParentNode, runRepeatIn, eval_context))
                        raise LoopSkip('Loop')
                if se.tag in text_tags and len(open_field.split(se.text or '')) > 1:
                    # Join remaining children's text
                    ox1 = etree.Element(se.tag, nsmap=se.nsmap)
                    for name in se.keys():
                        ox1.attrib[name] = apply_eval(se.get(name), objects, eval_context)
                    parts = [full_text(c) for c in children[index:]]
                    xtext = ''.join(parts)
                    ox1.text = (apply_eval(xtext, objects, eval_context) or '')
                    ox.append(ox1)
                    break
                else:
                    ox.append(process_element(se, objects, removeParentNode, repeatIn, eval_context))
            except LoopSkip:
                if se.tag not in LOOP_TAGS:
                    raise
                break
            except GeneratorSkip:
                continue
            except Exception:
                raise

    return ox

def process_file(infile, objects, context=None):
    context = context or {}
    rcontext = context.copy()

    isio = StringIO.StringIO(infile)

    ox_string = isio.getvalue()
    if len(ox_string) > 10:
        ix_tree = etree.parse(isio)
        ox = process_element(ix_tree.getroot(), objects, None, None, context=context)
        ox_tree = etree.ElementTree(ox)
        ox_string = etree.tostring(ox_tree)

    return ox_string

def process_files(self, cr, uid, ids, input_files, context={}):
    objects = self.browse(cr, uid, ids, context=context)

    of = []
    for infile in input_files:
        name, data = infile
        if name.endswith('.xml'):
            of.append((name, process_file(data, objects, context=context)))
        else:
            of.append((name, data))
    return of

def generate_output(output_files):
    osio = StringIO.StringIO()
    zo = zipfile.ZipFile(osio, 'w')

    for name, output_data in output_files:
        zo.writestr(name, output_data)

    zo.close()
    return osio.getvalue()

class report_opendoc(object):

    def __init__(self, template, model, tr, name, context=None):
        self.template = template
        self.model = model
        self.tr = tr
        self.name = name
        self.localcontext = context or {}
        self._lang_cache = {}
        self.lang_dict = {}
        self.default_lang = {}
        self.lang_dict_called = False
        self._transl_regex = re.compile('(\[\[.+?\]\])')

    def create(self, cr, uid, res_ids, data, context):
        if not self.template:
            raise except_osv(_('Error!'), 
                             _('Empty template. No report could be generated! Please check it'))

        self.localcontext = context.copy() or {}

        eval_context = context.copy()

        currency_obj = self.tr.pool['res.currency']
        user_obj = self.tr.pool['res.users']
        user = user_obj.browse(cr, uid, uid, context=context)

        # Utility functions

        def _get_lang_dict():
            pool_lang = self.tr.pool['res.lang']
            lang = self.localcontext.get('lang', 'en_US') or 'en_US'
            lang_ids = pool_lang.search(cr,uid,[('code','=',lang)])
            if not lang_ids:
                lang_ids = pool_lang.search(cr,self.uid,[('code','=','en_US')])
            lang_obj = pool_lang.browse(cr,uid,lang_ids[0])
            self.lang_dict.update({'lang_obj':lang_obj,'date_format':lang_obj.date_format,'time_format':lang_obj.time_format})
            self.default_lang[lang] = self.lang_dict.copy()
            return True

        def display_address(address_browse_record):
            return self.tr.pool['res.partner']._display_address(self.cr, uid, address_browse_record)

        def get_digits(obj=None, f=None, dp=None):
            d = DEFAULT_DIGITS = 2
            if dp:
                decimal_precision_obj = self.tr.pool['decimal.precision']
                d = decimal_precision_obj.precision_get(cr, uid, dp)
            elif obj and f:
                res_digits = getattr(obj._columns[f], 'digits', lambda x: ((16, DEFAULT_DIGITS)))
                if isinstance(res_digits, tuple):
                    d = res_digits[1]
                else:
                    d = res_digits(cr)[1]
            elif (hasattr(obj, '_field') and\
                    isinstance(obj._field, (float_field, function_field)) and\
                    obj._field.digits):
                    d = obj._field.digits[1] or DEFAULT_DIGITS
            return d

        def formatLang(value, 
                        digits=None, 
                        date=False, 
                        date_time=False, 
                        grouping=True, 
                        monetary=False, 
                        dp=False, 
                        currency_obj=False):
            """
                Assuming 'Account' decimal.precision=3:
                    formatLang(value) -> digits=2 (default)
                    formatLang(value, digits=4) -> digits=4
                    formatLang(value, dp='Account') -> digits=3
                    formatLang(value, digits=5, dp='Account') -> digits=5
            """
            if digits is None:
                if dp:
                    digits = get_digits(dp=dp)
                else:
                    digits = get_digits(value)

            if isinstance(value, (str, unicode)) and not value:
                return ''

            if not self.lang_dict_called:
                _get_lang_dict()
                self.lang_dict_called = True

            if date or date_time:
                if not str(value):
                    return ''

                date_format = self.lang_dict['date_format']
                parse_format = DEFAULT_SERVER_DATE_FORMAT
                if date_time:
                    value = value.split('.')[0]
                    date_format = date_format + " " + self.lang_dict['time_format']
                    parse_format = DEFAULT_SERVER_DATETIME_FORMAT
                if isinstance(value, basestring):
                    # FIXME: the trimming is probably unreliable if format includes day/month names
                    #        and those would need to be translated anyway.
                    date = datetime.strptime(value[:get_date_length(parse_format)], parse_format)
                elif isinstance(value, time.struct_time):
                    date = datetime(*value[:6])
                else:
                    date = datetime(*value.timetuple()[:6])
                if date_time:
                    # Convert datetime values to the expected client/context timezone
                    date = datetime_field.context_timestamp(cr, uid,
                                                            timestamp=date,
                                                            context=self.localcontext)
                return date.strftime(date_format.encode('utf-8'))

            res = self.lang_dict['lang_obj'].format('%.' + str(digits) + 'f', value, grouping=grouping, monetary=monetary)
            if currency_obj:
                if currency_obj.position == 'after':
                    res='%s %s'%(res,currency_obj.symbol)
                elif currency_obj and currency_obj.position == 'before':
                    res='%s %s'%(currency_obj.symbol, res)
            return res

        def set_html_image(id,model=None,field=None,context=None):
            if not id :
                return ''
            if not model:
                model = 'ir.attachment'
            try :
                ids = [int(id)]
                res = self.tr.pool[model].read(self.cr,uid,ids)[0]
                if field :
                    return res[field]
                elif model =='ir.attachment' :
                    return res['datas']
                else :
                    return ''
            except Exception:
                return ''

        def format(text, oldtag=None):
            return text.strip()

        def setCompany(new_company):
            return ''

        def setLang(newLang):
            return ''

        def removeParentNode():
            return ''

        def setTag():
            return ''

        _transl_regex = re.compile('(\[\[.+?\]\])')

        def _translate(text):
            lang = self.localcontext['lang']
            if lang and text and not text.isspace():
                transl_obj = self.tr.pool['ir.translation']
                piece_list = _transl_regex.split(text)
                for pn in range(len(piece_list)):
                    if not _transl_regex.match(piece_list[pn]):
                        source_string = piece_list[pn].replace('\n', ' ').strip()
                        if len(source_string):
                            translated_string = transl_obj._get_source(cr, uid, self.name, ('report', 'rml'), lang, source_string)
                            if translated_string:
                                piece_list[pn] = piece_list[pn].replace(source_string, translated_string)
                text = ''.join(piece_list)
            return text

        def _ellipsis(char, size=100, truncation_str='...'):
            if not char:
                return ''
            if len(char) <= size:
                return char
            return char[:size-len(truncation_str)] + truncation_str

        def _strip_name(name, maxlen=50):
            return _ellipsis(name, maxlen)

        def _value_set(dict, name, value):
            dict[name] = value
            return value

        eval_context.update({
            'user': user,
            'data': data or {},
            'datetime': datetime,
            'timedelta': timedelta,
            #'today': fields.date.context_today(self, cr, uid, context=context),
            'now': datetime.now(tz=pytz.timezone('UTC')).strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'self': self,
            'cr': cr,
            'context': context,
            'tr': self.tr,
            'pdb': pdb,
            'user_values': {},

            'setCompany': setCompany,
            'setLang': setLang,
            'setTag': setTag,
            'setValue': _value_set,
            'removeParentNode': removeParentNode,
            'format': format,
            'formatLang': formatLang,
            'lang' : user.company_id.partner_id.lang,
            'translate' : _translate,
            'setHtmlImage' : set_html_image,
            'strip_name' : _strip_name,
            'time' : time,
            'display_address': display_address,
        })

        pool = openerp.registry(cr.dbname)
        input_model = pool[self.model]
        input_files = open_template(self.template)
        report_context = context.copy()
        report_context.update(data)
        output_files = process_files(input_model, cr, uid, res_ids, input_files, context=eval_context)
        output_file = generate_output(output_files)
        return output_file

class opendoc_report(Model):
    _inherit = "ir.actions.report.xml"

    def _get_report_type_list(self, cr, uid, context=None):
        return self.get_report_type_list(cr, uid, context=None)

    _columns = {
        'report_type': fields.selection(_get_report_type_list, 'Report Type', 
                                        required=True, 
                                        help="HTML will open the report directly in your browser, "
                                             "PDF will use wkhtmltopdf to render the HTML into a PDF file and let you download it, "
                                             "Controller allows you to define the url of a custom controller outputting any kind of report, "
                                             "Opendoc let you use a template to generate an opendoc standard file (text, calc sheet or presentation)"),
        'template_name': fields.char('Template name', size=256),
        'template_file': fields.binary('Template file', filters="*.od*", filename='template_name'),
    }

    def get_report_type_list(self, cr, uid, context=None):
        return [('qweb-pdf', 'PDF'),
                ('qweb-html', 'HTML'),
                ('controller', 'Controller'),
                ('pdf', 'RML pdf (deprecated)'),
                ('sxw', 'RML sxw (deprecated)'),
                ('webkit', 'Webkit (deprecated)'),
                ('opendoc', 'OpenDoc Template to OpenDoc File')]

    def _lookup_report(self, cr, name, template_file=None):
        cr.execute("SELECT * FROM ir_act_report_xml WHERE name=%s", (name,))
        r = cr.dictfetchone()
        if r:
            if r['report_type'] in ['opendoc']:
                return report_opendoc(template_file or r['template_file'], r['model'], self, name)

        # If we are here, it is not handled by this module
        return super(opendoc_report, self)._lookup_report(cr, name)

    def render_report(self, cr, uid, res_ids, name, data, template_file=None, context=None):
        """
        Look up a report definition and render the report for the provided IDs.
        """
        ids = self.search(cr, uid, [('name','=',name)], context=context)
        if ids:
            new_report = self._lookup_report(cr, name, template_file=template_file)
            data = new_report.create(cr, uid, res_ids, data, context)
            return data, 'opendoc'
        else:
            return super(opendoc_report, self).render_report(cr, uid, res_ids, name, data, context=context)

    def action_test(self, cr, uid, ids, context=None):
        assert ids and len(ids)==1, 'One at the time'
        
        return {
            'name':_("Test"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'base.test_report',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'context': context or {},
        }
        


class test_report(TransientModel):
    _name = "base.test_report"

    _columns = {
        'selected_ids': fields.text('Selected ids', 
                                    help="List of ids separated by comma, or leave it blank for all"),
        'report_name': fields.char('Report name'),
        'report': fields.binary('Report',filename='report_name'),
        'data': fields.text('Data', help="Data as serialized pyhton dictionary"),
    }

    _defaults = {
        'data': '{}',
        'report_name': 'test_report.odt',
    }

    def action_get_report(self, cr, uid, ids, context=None):
        assert ids and len(ids)==1, 'One at the time'
        context = context or {}
        report_obj = self.pool['ir.actions.report.xml']

        tr = self.browse(cr, uid, ids[0], context=context)

        report_id = context.get('active_id')
        report = report_obj.browse(cr, uid, report_id, context=context)
        if tr.selected_ids:
            sids = tr.selected_ids.split(',')
            s_ids = [long(s) for s in sids]
        else:
            s_ids = self.pool[report.model].search(cr, uid, [], context=context)

        if tr.data:
            data = safe_eval(tr.data, locals_dict=context)
        else:
            data = context

        report_instance = report_obj._lookup_report(cr, report.report_name)
        if report_instance:
            report_content = report_instance.create(cr, uid, s_ids, data, context=context)
            if report_content:
                template_extension = report.template_name and report.template_name.split('.')[-1] or 'odt'
                rns = (tr.report_name or 'test_report.odt').split('.')
                if len(rns) > 1:
                    rns[-1] = template_extension
                else:
                    rns.append(template_extension)
                tr.write({'report_name': '.'.join(rns),
                          'report': base64.b64encode(report_content)})
            else:
                raise except_osv(_('Error!'), 
                                 _('No report content! Please check it'))
        else:
            raise except_osv(_('Error!'), 
                             _('No report instance! Please check it'))

        return True

if __name__ == "__main__":
    import sys

    args = sys.argv

    if len(args) < 3:
        print "Usage:"
        print "  %s <input_file> <output_file> [<vars> ...]" % args[0]
        exit(-1)

    inputFileName = args[1]
    outputFileName = args[2]
    
    values = {}
    for argument in args[3:]:
        a_splitted = argument.split("=")
        if len(a_splitted) >= 2:
            values[a_splitted[0]] = safe_eval(a_splitted[1])
        else:
            values[a_splitted[0]] = True

    ifile = open(inputFileName, 'rb')

    input_files = open_template(base64.b64encode(ifile.read()))
    output_files = process_files(None, None, None, [], input_files, context=values)
    output_file = generate_output(output_files)

    outFile = open(outputFileName, 'wb')
    outFile.write(output_file)
    outFile.close()

    exit(0)
