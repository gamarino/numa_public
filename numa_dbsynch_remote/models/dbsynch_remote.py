# -*- coding: utf-8 -*-
##############################################################################
#
#    NUMA
#    Copyright (C) 2017 NUMA Extreme Systems (<http:www.numaes.com>).
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
from openerp.exceptions import except_orm

from openerp.tools.translate import _
from openerp.tools.safe_eval import safe_eval as eval

import xmlrpclib
import sys, traceback

import logging
_logger = logging.getLogger(__name__)

PRIVATE_FIELDS = [
    'id',
    'write_date',
    'write_uid',
    'create_date',
    'create_uid',
    'parent_rigth',
    'parent_left',
]

class CommandsNode(object):
    def __init__(self, previous=None):
        self.commands = []
        self.previous = previous

    def getCommands(self):
        ret = [cmd for cmd in self.commands]
        if self.previous:
            ret.extend(self.previous.getCommands())
        return ret

    def appendCommand(self, cmd):
        self.commands.append(cmd)

    def commit(self):
        if self.previous:
            self.previous.commands.extend(self.commands)
            return self.previous
        else:
            return self

class InstancesNode(object):
    def __init__(self, previous=None):
        self.instances = {}
        self.previous = previous

    def hasInstance(self, oo):
        if oo._name in self.instances:
            if oo.id in self.instances[oo._name]:
                return True
        if self.previous:
            return self.previous.hasInstance(oo)
        else:
            return False

    def setInstance(self, oo):
        if oo._name not in self.instances:
            self.instances[oo._name] = set()
        self.instances[oo._name].add(oo.id)

    def commit(self):
        if self.previous:
            p = self.previous
            for modelName in self.instances.keys():
                if modelName not in p.instances:
                    p.instances[modelName] = self.instances[modelName]
                else:
                    p.instances[modelName].update(self.instances[modelName])
            return p
        else:
            return self

class VisitedNode(object):
    def __init__(self, previous=None):
        self.visited = {}
        self.previous = previous

    def hasBeenVisited(self, oo):
        if oo._name in self.visited:
            if oo.id in self.visited[oo._name]:
                return True
        if self.previous:
            return self.previous.hasBeenVisited(oo)
        else:
            return False

    def setVisited(self, oo):
        if oo._name not in self.visited:
            self.visited[oo._name] = set()
        self.visited[oo._name].add(oo.id)

    def removeVisited(self, oo):
        self.visited[oo._name].remove(oo.id)

    def commit(self):
        if self.previous:
            p = self.previous
            for modelName in self.visited.keys():
                if modelName not in p.visited:
                    p.visited[modelName] = self.visited[modelName]
                else:
                    p.visited[modelName].update(self.visited[modelName])
            return p
        else:
            return self

class SessionState(object):
    def __init__(self):
        self.visited = VisitedNode()
        self.instances = InstancesNode()
        self.commands = CommandsNode()

    def setVisited(self, oo):
        self.visited.setVisited(oo)

    def hasBeenVisited(self, oo):
        return self.visited.hasBeenVisited(oo)

    def checkAndSetVisited(self, oo):
        if not self.hasBeenVisited(oo):
            self.setVisited(oo)

    def removeVisited(self, oo):
        self.visited.removeVisited(oo)

    def hasInstance(self, oo):
        return self.instances.hasInstance(oo)

    def setInstance(self, oo):
        return self.instances.setInstance(oo)

    def push(self):
        self.visited = VisitedNode(self.visited)
        self.instances = InstancesNode(self.instances)
        self.commands = CommandsNode(self.commands)

    def commit(self):
        self.visited = self.visited.commit()
        self.instances = self.instances.commit()
        self.commands = self.commands.commit()

    def pop(self):
        self.visited = self.visited.previous if self.visited else None
        self.instances = self.instances.previous if self.instances else None
        self.commands = self.commands.previous if self.commands else None

    def appendCommand(self, cmds):
        self.commands.appendCommand(cmds)

    def getCommands(self):
        return self.commands.getCommands()


class LevelInfo(object):
    pass

class RemoteSharedModel(models.Model):
    _name = 'dbsynch.remote_shared_model'
    _rec_name = 'model'
    
    remote_server = fields.Many2one('dbsynch.remote_server', 'Remote Server')
    model = fields.Many2one('ir.model', 'Odoo Model')
    no_upload = fields.Boolean('Do not upload')
    shared_fields = fields.One2many('dbsynch.remote_shared_field', 'shared_model', 'Shared fields')
    
    _sql_constraints = [
        ('obj_name_uniq', 'unique (remote_server,model)', 'Each model could be selected only once per remote server!'),
    ]
    
class RemoteSharedField(models.Model):
    _name = 'dbsynch.remote_shared_field'
    _rec_name = 'field'
    
    shared_model = fields.Many2one('dbsynch.remote_shared_model', 'Model', on_delete="cascade")
    field = fields.Many2one('ir.model.fields', 'Odoo Model Field')

    _sql_constraints = [
        ('obj_name_uniq', 'unique (shared_model,field)', 'Each field could only be specified once per model!'),
    ]

class RemoteMapping(models.Model):
    _name = 'dbsynch.remote_mapping'
    _rec_name = 'model'
    
    remote_server = fields.Many2one('dbsynch.remote_server', 'Remote Server')
    model = fields.Char('Model name', select=1)
    remote_id = fields.Integer('Remote ID', select=1)
    local_id = fields.Integer('Local ID', select=1)
    base_vals = fields.Text('Base values')
    local_modified_vals = fields.Text('Locally modified values since last synch')
    synch_timestamp = fields.Datetime('Last synch timestamp')

class RemoteObjects(models.Model):
    _name = 'dbsynch.remote_object'
    _rec_name = 'model'
    _order = 'remote_server desc, sequence, id'

    sequence = fields.Integer('Sequence')
    remote_server = fields.Many2one('dbsynch.remote_server', 'Remote Server',
                                    on_delete='cascade')
    model = fields.Many2one('ir.model', 'Odoo Model')
    selection = fields.Text('Selection expression', default='[]')
    
class LocalObjects(models.Model):
    _name = 'dbsynch.local_object'
    _rec_name = 'model'
    _order = 'remote_server desc, sequence, id'

    sequence = fields.Integer('Sequence')
    remote_server = fields.Many2one('dbsynch.remote_server', 'Remote Server',
                                    on_delete='cascade')
    model = fields.Many2one('ir.model', 'Odoo Model')
    selection = fields.Text('Selection expression', default='[]')
    
class RemoteServer(models.Model):
    _name = 'dbsynch.remote_server'

    @api.model
    def _get_master_type_selection(self):
        return self.get_master_type_selection()
    
    name = fields.Char('Remote name', required=True)
    shared_models = fields.One2many('dbsynch.remote_shared_model', 'remote_server', 'Models shared with Master')
    mappings = fields.One2many('dbsynch.remote_mapping', 'remote_server', 'Remote instances Mapping')
    master_objects = fields.One2many('dbsynch.remote_object', 'remote_server', 'Objects to be asked to Master')
    local_objects = fields.One2many('dbsynch.local_object', 'remote_server', 'Objects to be sent to Master')

    state = fields.Selection([
                ('draft', 'Draft'),
                ('active', 'Active'),
                ('synching', 'Synching'),
                ('suspended', 'Suspended'),
            ], string="State", default='draft')

    master_type = fields.Selection(_get_master_type_selection, string='Master type', 
                                   required=True, default='normal')
    
    url = fields.Char('Remote URL',
                      required=True,
                      help="Remote URL, including protocol, address and port")
    remote_dbname = fields.Char('Remote DB name',
                         required=True)
    login = fields.Char('Remote login',
                         required=True)
    password = fields.Char('Remote password')
    
    last_synched_on = fields.Datetime("Last synch on")
    local_changes_since = fields.Datetime("Local changes since",
                                          help="For the next synch, consider local changes from here on")

    synch_job = fields.Many2one('res.background_job', 'Synch job')
    synch_state = fields.Selection([
                                ('init', 'Initializing'),
                                ('started', 'Started'),
                                ('ended', 'Ended'),
                                ('aborted', 'Aborted'),
                            ], string="Synch state",
                            related=['synch_job', 'state'])
    synch_current_status = fields.Char('Synch current status',
                              related=['synch_job','current_status'])    
    synch_completion_rate = fields.Integer('Synch completion rate',
                              related=['synch_job','completion_rate'])    
    synch_on = fields.Datetime('Synched on',
                              related=['synch_job','initialized_on'])    
    synch_ended_on = fields.Datetime('Synched ended on',
                              related=['synch_job','ended_on'])    
    synch_error = fields.Text('Last synch error msg',
                              related=['synch_job','error'])    

    _sql_constraints = [
        ('obj_name_uniq', 'unique (name)', 'Remote name should be unique!'),
    ]

    @api.multi
    def get_master_type_selection(self):
        # To be extended by subclases
        return [('normal', _('Normal'))]

    @api.multi
    def action_synch(self):
        self.ensure_one()
        
        if self.state == 'synching':
            self.remote_server.action_abort_synch()

        self.state = 'synching'
        self.synch_job = self.env["res.background_job"].create({
                                'name': _('DBSYNCH %s') % self.name,
                                'model': self._model,
                                'res_id': self.id,
                                'method': 'action_perform_synch',
                          })

        return True

    @api.multi
    def openSession(self, bkJob):
        sock_common = xmlrpclib.ServerProxy ('%s/xmlrpc/common' % self.url)
        self.uid = sock_common.login(
                        self.remote_dbname, 
                        self.login,
                        self.password)
        self.sock = xmlrpclib.ServerProxy('%s/xmlrpc/object' % self.url)
                                   
    @api.multi
    def getModifiedFields(self, instance, baseValuesText):
        modifiedFields = {}
        modelObj = self.env[instance._name]
        fieldsDef = modelObj.fields_get()
        
        baseValues = eval(baseValuesText)
        for fieldName in baseValues.keys():
            fieldType = fieldsDef[fieldName]
            if fieldType in ['one2many', 'many2many']:
                relatedInstances = set([i.id for i in instance[fieldName]])
                baseRelatedInstances = set(baseValues)
                if relatedInstances != baseRelatedInstances:
                    modifiedFields[fieldName] = instance[fieldName]
            else:
                if instance[fieldName] != baseValues[fieldName]:
                    modifiedFields[fieldName] = instance[fieldName]
                
        return modifiedFields

    @api.multi
    def getBaseFields(self, instance, baseValues):
        modifiedFields = {}
        modelObj = self.env[instance._name]
        fieldsDef = modelObj.fields_get()

        for fieldName in baseValues.keys():
            fieldType = fieldsDef[fieldName]['type']
            if fieldType =='many2one':
                modifiedFields[fieldName] = instance[fieldName].id or False
            elif fieldType in ['one2many', 'many2many']:
                modifiedFields[fieldName] = [ri.id or False for ri in instance[fieldName]]
            else:
                modifiedFields[fieldName] = instance[fieldName]

        return modifiedFields

    @api.multi
    def getMappingByRemoteID(self, modelName, remoteId):
        instanceMappingObj = self.env['dbsynch.remote_mapping']
        
        return instanceMappingObj.search([
                    ('remote_server', '=', self.id), 
                    ('model', '=', modelName), 
                    ('remote_id', '=', remoteId)])

    @api.multi
    def getMappingByLocalID(self, modelName, localId):
        instanceMappingObj = self.env['dbsynch.remote_mapping']
        
        return instanceMappingObj.search([
                    ('remote_server', '=', self.id), 
                    ('model', '=', modelName), 
                    ('local_id', '=', localId)])

    @api.multi
    def getMasterObjects(self, bkJob):
        return [(mo.model.model, eval(mo.selection) if mo.selection else []) for mo in self.master_objects]

    # To be overloaded 
    # Try to create an instance.
    # if it is special, return the "created" or "refernced" object
    # if None or False, a normal create on the model will be used
    @api.multi
    def processSpecialModels(self, modelName, defaultVals):
        return None

    def requestMasterForObjects(self, objectsToRequest, sinceTime, offset=0, limit=0):
        '''
        Get Master objects to update locally

        @param objectsToRequest is a list of tuples of [<modelName>, <selection expression>],
                                where selection expression is a normal search selection
                                argument list
        @param sinceTime        is a time in YYYY-MM-DD HH:MM:SS format used as time since 
                                modifications should be sent. An empty value means since 
                                begining of time
        @param offset
        @param limit            are used to restrict the response to a window of deltas
                                They are optional
        '''
        
        cmd = {
            'protocolVersion': '1.0',
            'objectsToSend': objectsToRequest,
            'sinceTime': sinceTime,
            'offset': offset,
            'limit': limit,
        }
        result = self.sock.execute(
                    self.remote_dbname,
                    self.uid,
                    self.password,
                    'dbsynch.server',
                    'get_synch_data',
                    cmd)

        if not result:
            raise except_orm(_('Error'),
                             _(u'Error in MASTER: no data received'))
        if result.get('error'):
            raise except_orm(_('Error'),
                             _(u'Error in MASTER command execution: %s') % result['error'])

        return result
        
    @api.multi
    def getFromMaster(self, bkJob):
        bkJob.update_status(rate=0, status_msg=_('Starting synching'))
        
        moreToAsk = True
        offset = 0
        CHUNK_SIZE = 100
        total = CHUNK_SIZE
        
        cmdCount = 0

        master_objects = self.getMasterObjects(bkJob)
        _logger.info("Getting the following master objects: %s" % unicode(master_objects))

        try:
            while moreToAsk:
                if bkJob.was_aborted():
                    self.env.cr.rollback()
                    return

                _logger.info("Asking remote objects from offset %d, limit %d" % (offset, CHUNK_SIZE))

                result = self.requestMasterForObjects(master_objects,
                                                      self.last_synched_on,
                                                      offset,
                                                      CHUNK_SIZE)

                bkJob.update_status(rate=40, status_msg=_('Master data received. Updating local DB'))

                modelCache = {}

                def getInstanceByRemoteId(mName, remoteId):
                    if mName not in modelCache:
                        mc = {}
                        modelCache[mName] = mc
                    else:
                        mc = modelCache[mName]

                    if remoteId in mc:
                        localId = mc[remoteId]
                    else:
                        mapping = self.getMappingByRemoteID(mName, remoteId)

                        if not mapping:
                            return None

                        localId = mapping.local_id
                        mc[remoteId] = localId

                    try:
                        instanceObj = self.env[mName]
                    except:
                        raise except_orm(_('Error'),
                                         _('No model found for name %s, remote id %d! Please check modules and setup') % \
                                          (mName, remoteId))

                    instance = instanceObj.browse(localId)
                    if not instance.exists():
                        mapping.unlink()
                        return None

                    return instance

                total = result['count']
                self.lang = result.get('lang', 'en_US')

                previousCompany = self.env.user.company_id

                companyObj = self.env['res.company']
                company_id = result['company_id']
                companyMapping = self.getMappingByRemoteID('res.company', company_id)
                if not companyMapping:
                    # This is the first synch, no remote company was created yet
                    # It is assumed that during the first synch this data will be updated
                    vals = {
                        'name': 'Remote unnamed',
                    }
                    remoteCompany = companyObj.create(vals)
                    mappings = [(0, 0, {'model': 'res.company',
                                        'remote_id': company_id,
                                        'local_id': remoteCompany.id,
                                        'base_vals': {},
                                        'local_modified_vals': {},
                                        'synch_timestamp': self.current_synch_on})]
                    self.write({'mappings': mappings})

                    self.env.user.write({
                        'company_ids': [(4, remoteCompany.id)],
                        'company_id': remoteCompany.id,
                    })

                else:
                    remoteCompany = companyObj.browse(companyMapping.local_id)
                    self.env.user.company_id = remoteCompany.id

                self.remoteCompany = remoteCompany

                for cmdItem in result['data']:
                    modelName = cmdItem['model']
                    remoteInstanceId = cmdItem['id']
                    instanceData = cmdItem['values']
                    #_logger.info("Procesando comando: model %s, instancia %d" % (modelName, remoteInstanceId))

                    modelObj = self.env[modelName]
                    fieldsDef = modelObj.fields_get()

                    vals = {}
                    for fieldName in instanceData:
                        fieldDef = fieldsDef[fieldName]
                        if fieldDef['type'] == 'many2one':
                            relatedInstanceId = instanceData[fieldName]
                            if relatedInstanceId:
                                relatedInstance = getInstanceByRemoteId(fieldDef['relation'], relatedInstanceId)
                                if not relatedInstance:
                                    raise except_orm(_('Error'),
                                                     _('On model %s, remote id %d could not be mapped to a local instance!') % \
                                                      (fieldDef['relation'], instanceData[fieldName]))
                                vals[fieldName] = relatedInstance.id
                            else:
                                vals[fieldName] = False
                        elif fieldDef['type'] == 'many2many':
                            localIds = []
                            for remoteRelatedId in instanceData[fieldName]:
                                relatedInstance = getInstanceByRemoteId(fieldDef['relation'], remoteRelatedId)
                                if not relatedInstance:
                                    raise except_orm(_('Error'),
                                                     _('On model %s, remote id %d could not be mapped to a local instance!') % \
                                                      (fieldDef['relation'], remoteRelatedId))
                                localIds.append(relatedInstance.id)
                            vals[fieldName] = [(6, 0, localIds)]
                        elif fieldDef['type'] == 'one2many':
                            localIds = []
                            for remoteRelatedId in instanceData[fieldName]:
                                relatedInstance = getInstanceByRemoteId(fieldDef['relation'], remoteRelatedId)
                                if not relatedInstance:
                                    raise except_orm(_('Error'),
                                                     _('On model %s, remote id %d could not be mapped to a local instance!') % \
                                                      (fieldDef['relation'], remoteRelatedId))
                                localIds.append(relatedInstance.id)
                            vals[fieldName] = [(6, 0, localIds)]
                        else:
                            vals[fieldName] = instanceData[fieldName]

                    instance = getInstanceByRemoteId(modelName, remoteInstanceId)
                    if instance:
                        currentMapping = self.getMappingByRemoteID(modelName, remoteInstanceId)
                        if not currentMapping:
                            raise except_orm(_('Error'),
                                             _('On model %s, remote id %d could not be mapped to a local instance!') % \
                                              (modelName, remoteInstanceId))

                        localModifiedFields = None
                        if currentMapping.synch_timestamp < instance.write_date:
                            # Do not update fields that were modified locally
                            localModifiedFields = self.getModifiedFields(instance, currentMapping.base_vals)

                        # Update base vals
                        baseVals = eval(currentMapping.base_vals)
                        baseVals.update(self.getBaseFields(instance, vals))

                        currentMapping.write({
                                    'base_vals': unicode(baseVals),
                                    'local_modified_vals': unicode(localModifiedFields),
                                    'synch_timestamp': self.current_synch_on})


                        _logger.info("DBSYNCH: Updating model %s, local id %d, remote id %d" % \
                                    (modelName, instance.id, remoteInstanceId))

                        # The create_product_variant parameters avoids the auto creation of variants in products

                        instance.with_context(
                            DBSYNCH_Update=True,
                            lang=self.lang,
                            create_product_variant=True,
                            company_id=self.remoteCompany.id).write(vals)

                    else:
                        if 'id' in vals:
                            del vals['id']

                        newVals = modelObj.default_get(modelObj.fields_get().keys())
                        newVals.update(vals)

                        _logger.info("DBSYNCH: Creating model %s, remote id %d" %
                                     (modelName, remoteInstanceId))

                        newInstance = self.processSpecialModels(modelName, newVals)

                        if not newInstance:
                            # The create_product_variant parameter avoids the auto creation of variants in products

                            newInstance = modelObj.with_context(
                                DBSYNCH_Update=True,
                                lang=self.lang,
                                create_product_variant=True,
                                company_id=self.remoteCompany.id).create(newVals)

                        if modelName not in modelCache:
                            modelCache[modelName] = {}
                        modelCache[modelName][remoteInstanceId] = newInstance.id

                        self.env['dbsynch.remote_mapping'].create({
                            'remote_server': self.id,
                            'model': modelName,
                            'remote_id': remoteInstanceId,
                            'local_id': newInstance.id,
                            'base_vals': self.getBaseFields(newInstance, newVals),
                            'local_modified_vals': unicode({}),
                            'synch_timestamp': self.current_synch_on})

                    cmdCount += 1
                    if cmdCount == total or \
                       cmdCount % 10 == 0:
                        bkJob.update_status(rate=40 + (20 * cmdCount / total),
                                            status_msg=_('Master data received. Updating local DB. (%d/%d)') % \
                                                        (cmdCount, total))

                self.env.user.company_id = previousCompany.id

                if len(result['data']) != CHUNK_SIZE:
                    moreToAsk = False
                offset += len(result['data'])

            self.env.cr.commit()

        except Exception, e:
            self.env.cr.rollback()
            _logger.info("Getting from master unexpected exception %s" % repr(e))
            raise e

    @api.multi
    def updateRemoteInstance(self, instance):
        modelName = instance._name

        if modelName not in self.modelsCache:
            modelObj = self.env[modelName]
            allFields = modelObj.fields_get()
            smObj = self.env['dbsynch.remote_shared_model']
            modelDef = smObj.search([('model.model','=',modelName)], limit=1)
            if modelDef:
                allowedFieldNames = [msf.field.name for msf in modelDef.shared_fields]

                allFields = {f:allFields[f] for f in allowedFieldNames}
                self.modelsCache[modelName] = (modelDef.no_upload, allFields)
            else:                                    
                allFields = {f:allFields[f] for f in allFields.keys() if f not in PRIVATE_FIELDS and \
                                                                         f[0] != '_'}
                self.modelsCache[modelName] = (False, allFields)
                
        noUpload, allFields = self.modelsCache[modelName]

        # If a model should not be upload, just return
        if noUpload:
            return True
            
        # Create new steps if necesary or just get the current one
        if self.currentLevel > len(self.updateSteps):
            currentStep = LevelInfo()
            currentStep.sessionState = SessionState()
            self.updateSteps.append(currentStep)
        else:
            currentStep = self.updateSteps[self.currentLevel - 1]
            
        # Was it changed in the current time frame?
        # If not, it should not be updated in Master
        if self.local_changes_since and \
           instance.write_date < self.local_changes_since:
           return True

        # Do not add the same instance twice to the current response
        if currentStep.sessionState.hasInstance(instance):
            return True

        # Check for recursion errors
        if currentStep.sessionState.hasBeenVisited(instance):
            _logger.info("Model %s, instance %d already visited!" % (modelName, instance.id))
            return False

        currentStep.sessionState.setVisited(instance)

        # Preorder exploration of the instance (Be sure related fields are there before sending to remote)
        fieldsData = {}
        scndStepFields = {}
        secondStep = False

        mapping = self.getMappingByLocalID(modelName, instance.id)

        for fieldName in allFields.keys():
            fieldType = allFields[fieldName]['type']

            if fieldType == 'many2one':
                comodelInstance = instance[fieldName]
                if comodelInstance:
                    currentStep.sessionState.push()
                    try:
                        relatedMapping = self.getMappingByLocalID(comodelInstance._name, comodelInstance.id)
                        if relatedMapping:
                            if not self.updateRemoteInstance(comodelInstance):
                                required = allFields[fieldName]['required']
                                if required:
                                    raise except_orm(
                                        _('Error'),
                                        _('Recursion error on model %s, instance %d, REQUIRED many2one field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                         (modelName,
                                          instance.id,
                                          fieldName,
                                          comodelInstance._name,
                                          comodelInstance.id))

                                scndStepFields[fieldName] = comodelInstance
                                currentStep.sessionState.pop()
                            else:
                                fieldsData[fieldName] = relatedMapping.remote_id
                                currentStep.sessionState.commit()
                        else:
                            self.currentLevel += 1
                            if not self.updateRemoteInstance(comodelInstance):
                                required = allFields[fieldName]['required']
                                if required:
                                    raise except_orm(
                                        _('Error'),
                                        _('Recursion error on model %s, instance %d, REQUIRED many2one field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                         (modelName,
                                          instance.id,
                                          fieldName,
                                          comodelInstance._name,
                                          comodelInstance.id))

                                scndStepFields[fieldName] = comodelInstance
                                currentStep.sessionState.pop()
                            else:
                                fieldsData[fieldName] = (comodelInstance._name, comodelInstance.id)
                                currentStep.sessionState.commit()
                            self.currentLevel -= 1
                    except except_orm, e:
                        # Ignore recursion errors on non required fields
                        scndStepFields[fieldName] = comodelInstance
                        secondStep = True
                        currentStep.sessionState.pop()
                        pass
                else:
                    fieldsData[fieldName] = 0 
            elif fieldType in ['one2many','many2many']:
                if not mapping:
                    secondStep = True
                continue
            else:
                fieldsData[fieldName] = instance[fieldName] or False

        if secondStep:
            savedStep = currentStep
            self.currentLevel += 1
            if self.currentLevel > len(self.updateSteps):
                currentStep = LevelInfo()
                currentStep.sessionState = SessionState()
                self.updateSteps.append(currentStep)
            else:
                currentStep = self.updateSteps[self.currentLevel - 1]

        _logger.info("Uploading model %s, instance id %d" % (modelName, instance.id))

        if not mapping:
            cmd = (modelName, 'create', instance.id, fieldsData)
        else:
            cmd = (modelName, 'write', mapping.remote_id, fieldsData)
        currentStep.sessionState.appendCommand(cmd)

        # Add the instance to the current response set
        currentStep.sessionState.setInstance(instance)

        if secondStep:
            self.currentLevel -= 1
            currentStep = savedStep
            
        if secondStep:
            fieldsData = {}
            for fieldName in allFields.keys():
                fieldType = allFields[fieldName]['type']
    
                if fieldType == 'many2one' and \
                   fieldName in scndStepFields and \
                   scndStepFields[fieldName]:
                    relationInstance = scndStepFields[fieldName]
                    if not self.addInstance(relationInstance):
                        raise except_orm(_('Error'),
                                         _('Recursion error on model %s, instance %d, many2one field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                          (modelName, instance.id, fieldName, relationInstance._name, relationInstance.id))
                    fieldsData[fieldName] = relationInstance.id
                elif fieldType in ['one2many','many2many']:
                    for relationInstance in instance[fieldName]:
                        self.updateRemoteInstance(relationInstance)
                    ids = []
                    for relationInstance in instance[fieldName]:
                        relatedMapping = self.getMappingByLocalID(relationInstance._name, 
                                                                  relationInstance.id)
                        if relatedMapping:
                            if not self.updateRemoteInstance(relationInstance):
                                raise except_orm(_('Error'),
                                                 _('Recursion error on model %s, instance %d, %s field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                                  (modelName, instance.id, fieldType, fieldName, relationInstance._name, relationInstance.id))
                            ids.append(relatedMapping.remote_id)
                        else:
                            self.currentLevel += 1
                            if not self.updateRemoteInstance(relationInstance):
                                raise except_orm(_('Error'),
                                                 _('Recursion error on model %s, instance %d, %s field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                                  (modelName, instance.id, fieldType, fieldName, relationInstance._name, relationInstance.id))
                            ids.append((relationInstance._name, relationInstance.id))
                            self.currentLevel -= 1
                    fieldsData[fieldName] = ids    
                else:
                    continue
    
            if fieldsData:
                if mapping:
                    cmd = (modelName, 'write', mapping.remote_id, fieldsData)
                else:
                    # Remote record is to going to be created in a previous step
                    cmd = (modelName, 'write', (modelName, instance.id), fieldsData)
                    
                currentStep.sessionState.appendCommand(cmd)

        # Remove current instance from visited stack
        currentStep.sessionState.removeVisited(instance)

        return True
        
    @api.multi
    def getLocalObjects(self, bkJob):
        return [(mo.model.model, eval(mo.selection) if mo.selection else []) for mo in self.local_objects]

    def prepareLocalChanges(self, bkJob):
        local_objects = self.getLocalObjects(bkJob)

        self.updateSteps = []
        self.instances = {}
        self.visited = {}
        self.modelsCache = {}
        self.currentLevel = 1

        modelCount = 0
        for modelName, searchCondition in local_objects:
            modelObj = self.env[modelName]

            if self.local_changes_since:
                searchCondition.append(('write_date','>=',self.local_changes_since))

            instances = modelObj.search(searchCondition)
            for instance in instances:
                self.updateRemoteInstance(instance)
            modelCount += 1

            bkJob.update_status(rate=50 + 10 * (modelCount/len(local_objects)), 
                                  status_msg=_('Collectiong local changes since last synch (%d/%d)') % \
                                            (modelCount, len(local_objects)))


    def executeCommandsInMaster(self, commands):
        '''
        Execute update commands in Master

        To be overloaded in cases where a diferent protocol is needed 
        
        @param commands is a list of dictionaries, where:
            'command': 'update' is for now the only command given
            'model':   model name of the object to update
            'id':      master instance id
            'values':  a dictionary of fields values
                       keys will be the local field names of the model
                       many2one values provides a master id
                       one2many and many2many provides a list of master ids
        
        '''
        
        updateRequest = {
            'protocolVersion': '1.0',
            'updateCommands': commands,
        }
        
        result = self.sock.execute(
                    self.remote_dbname, 
                    self.uid, 
                    self.password, 
                    'dbsynch.server', 
                    'remote_update', 
                    updateRequest)
                    
        if not result:
            raise except_orm(_('Error'),
                             _(u'Error in MASTER: no data received'))
        if result.get('error'):
            raise except_orm(_('Error'),
                             _(u'Error in MASTER command execution: %s') % result['error'])

        return result
        
    @api.multi
    def updateLocalChanges(self, bkJob):
        instanceMappingObj = self.env['dbsynch.remote_mapping']

        bkJob.update_status(rate=50, status_msg=_('Collectiong local changes since last synch'))

        # Local changes from start of synch till here will not be
        # recognized and sent to Master (in order to prevent a loop!)
        # Only if changes were complete sent to Master
        
        self.local_changes_since = fields.Datetime.now()

        if self.updateSteps:
            bkJob.update_status(rate=60, status_msg=_('Sending local changes to Master'))

            stepCount = 0
            for step in reversed(self.updateSteps):
                stepCount += 1

                commandsToSend = []
                createCommands = {}
                nextReference = 1
                for modelName, command, instanceId, data in step.sessionState.getCommands():
                    
                    # Fix references from previous steps
                    
                    # if the record was already created, discard the changes
                    if command == 'create':
                        mapping = self.getMappingByLocalID(modelName, instanceId)
                        if mapping:
                            continue
                    
                    # if the record was created in previous steps, fixe references
                    fixedFields = {}
                    for fieldName in data:
                        fieldData = data[fieldName]
                        fixedFields[fieldName] = fieldData
                        if isinstance(fieldData, type((0,))):
                            comodelName, localId = fieldData
                            mapping = self.getMappingByLocalID(comodelName, localId)
                            if mapping:
                                fixedFields[fieldName] = mapping.remote_id
                            else:
                                raise except_orm(
                                    _('Error'),
                                    _('Expecting remote id for model %s, local instance %d, but no info found! Please contact your System Administrator') % \
                                     (modelName, localId))
                        elif isinstance(fieldData, type([])):
                            newFieldData = []
                            for item in fieldData:
                                if isinstance(item, type((0,))):
                                    comodelName, localId = item
                                    mapping = self.getMappingByLocalID(comodelName, localId)
                                    if mapping:
                                        newFieldData.append(mapping.remote_id)
                                    else:
                                        raise except_orm(
                                            _('Error'),
                                            _('Expecting remote id for model %s, local instance %d, but no info found! Please contact your System Administrator') % \
                                             (modelName, localId))
                                else:
                                    newFieldData.append(item)
                            fixedFields[fieldName] = newFieldData
                    
                    # if the record was created in previous steps, fix operations
                    # that relies on a still non created record
                    if isinstance(instanceId, type((0,))):
                        comodelName, localId = instanceId
                        mapping = self.getMappingByLocalID(comodelName, localId)
                        if mapping:
                            instanceId = mapping.remote_id
                        else:
                            raise except_orm(
                                _('Error'),
                                _('Expecting remote id for model %s, local instance %d, but no info found! Please contact your System Administrator') % \
                                 (modelName, localId))
                        
                    remoteCommand = {
                        'operation': command,
                        'reference': nextReference,
                        'model': modelName,
                        'id': instanceId,
                        'fields': fixedFields,
                    }
                    if command == 'create':
                        createCommands[nextReference] = remoteCommand
                    commandsToSend.append(remoteCommand)

                    _logger.info("DBSYNCH: Sending local instance: step %d, operation %s, model %s, local id %d, reference %s" % \
                                 (stepCount, command, modelName, instanceId, nextReference))

                    nextReference += 1
    
                # Update master in chunks of CHUNK_SIZE commands

                offset = 0
                CHUNK_SIZE = 100

                while offset < len(commandsToSend):
                    if bkJob.was_aborted():
                        self.env.cr.rollback()
                        return
                        
                    bkJob.update_status(rate=60 + (40 * stepCount/len(self.updateSteps)), 
                                        status_msg=_('Sending local changes to Master. Step %d/%d, offset %d') %\
                                                    (stepCount, len(self.updateSteps), offset))

                    result = self.executeCommandsInMaster(commandsToSend[offset:offset + CHUNK_SIZE])
                                
                    if result:
                        bkJob.update_status(rate=90, status_msg=_('Updating master created objects references'))
        
                        for recordUpdate in result['createdIds']:
                            reference = recordUpdate['reference']
                            modelName = recordUpdate['model']
                            remoteId = recordUpdate['id']

                            ref = createCommands[reference]
                            
                            # Update remote mappings with Master id received
                            mapping = self.getMappingByRemoteID(modelName, remoteId)
                            if not mapping:
                                instanceMappingObj.create({
                                    'remote_server': self.id,
                                    'model': ref['model'],
                                    'remote_id': remoteId,
                                    'local_id': ref['id'],
                                    'base_vals': ref['fields'],
                                    'local_modified_vals': {},
                                    'synch_timestamp': self.current_synch_on,
                                })

                            _logger.info("DBSYNCH: Updating master created instances: model %s, remote id %d, local id %s" % \
                                         (modelName, remoteId, ref['id']))
                                
                    offset += CHUNK_SIZE
                    
        self.env.cr.commit()
        
    @api.multi
    def action_perform_synch(self, bkJob):
        self.ensure_one()
        
        self.current_synch_on = fields.Datetime.now()

        try:
            # Local changes will be collected since last synch till now
            # This is prepared before getting objects from Master 
            # in order to avoid collecting Master received objects
            # as locally changed ones!

            _logger.info("DBSYNCH: Preparing local changes..")
            self.prepareLocalChanges(bkJob)
            
            _logger.info("DBSYNCH: Opening session..")
            self.openSession(bkJob)
            
            _logger.info("DBSYNCH: Asking for remote objects..")
            self.getFromMaster(bkJob)
            
            _logger.info("DBSYNCH: Sending local objects to Master..")
            self.updateLocalChanges(bkJob)
    
            _logger.info("DBSYNCH: Complete..")
            bkJob.update_status(rate=100, status_msg=_('Synch Complete'))
            
            if self.state == 'synching':
                self.last_synched_on = self.current_synch_on
                self.state = 'active'
                self.synch_job.end()
                
            return True

        except Exception, e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            
            _logger.info("DBSYNCH: Unexpected exception")
            traceback.print_exception(exc_type, exc_value, exc_traceback, 
                                      limit=10, file=sys.stdout)

            self.env.cr.rollback()

            msg = u"%s" % (str(e).decode('utf-8'))

            self.state = 'active'
            self.env.cr.commit()

            bkJob.abort(msg)

            raise e
    
    @api.multi
    def action_abort_synch(self):
        self.ensure_one()
        
        if self.state == 'synching' and self.synch_job:
            self.synch_job.abort()
            self.state = 'active'
            
        return True

    @api.multi
    def action_refresh(self):
        return True

    @api.multi
    def action_set_active(self):
        self.ensure_one()
        
        if self.state in ['draft', 'suspended']:
            self.state = 'active'
            
        return True

    @api.multi
    def action_suspend(self):
        self.ensure_one()
        
        if self.state in ['active']:
            self.state = 'suspended'
            
        return True

    @api.multi
    def action_get_mappings(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name':_("Remote mappings for %s") % self.name,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'dbsynch.remote_mapping',
            'domain': [('remote_server','=',self.id)],
            'context': {'default_remote_server': self.id},
        }
        
    @api.multi
    def action_get_rules(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name':_("Model rules for for %s") % self.name,
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'dbsynch.remote_shared_model',
            'domain': [('remote_server','=',self.id)],
            'context': {'default_remote_server': self.id},
        }
        
