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

import logging
_logger = logging.getLogger(__name__)


class MasterSharedModel(models.Model):
    _name = 'dbsynch.shared_model'
    _rec_name = 'model'
    
    model = fields.Many2one('ir.model', 'Odoo Model')
    no_upload = fields.Boolean('Do not upload')
    shared_fields = fields.One2many('dbsynch.shared_field', 'shared_model', 'Shared fields',
                                    help='List of allowed fields to be synched. If empty, all fields will be synched')
    
    _sql_constraints = [
        ('obj_name_uniq', 'unique (model)', 'Each model could be selected only once!'),
    ]


class MasterSharedField(models.Model):
    _name = 'dbsynch.shared_field'
    _rec_name = 'field'
    
    shared_model = fields.Many2one('dbsynch.shared_model', 'Model', on_delete="cascade")
    field = fields.Many2one('ir.model.fields', 'Odoo Model Field')

    _sql_constraints = [
        ('obj_name_uniq', 'unique (shared_model,field)', 'Each field could only be specified once!'),
    ]

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


class Server(models.AbstractModel):
    _name = 'dbsynch.server'

    def addInstance(self, instance):
        modelName = instance._name

        if modelName not in self.modelsCache:
            modelObj = self.env[modelName]
            allFields = modelObj.fields_get()
            smObj = self.env['dbsynch.shared_model']
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

        # Do not add the same instance twice to the current response
        if self.sessionState.hasInstance(instance):
            return True

        # Do not add the instance if it was already synched in previous synch sessions
        if self.limitDate and instance.write_date < self.limitDate:
            return True
            
        # Check for recursion errors
        if self.sessionState.hasBeenVisited(instance):
            #_logger.info("Model %s, instance %d already visited!" % (modelName, instance.id))
            return False

        self.sessionState.setVisited(instance)

        # Preorder exploration of the instance (Be sure many2one fields are there before sending to remote)
        fieldsData = {}
        scndStepFields = {}
        secondStep = False
        for fieldName in allFields.keys():
            fieldType = allFields[fieldName]['type']
            
            if fieldType == 'many2one':
                comodelInstance = instance[fieldName]
                if comodelInstance:
                    self.sessionState.push()
                    try:
                        #_logger.info("On model %s, instance %d, field %s, field instance %d" % (modelName, instance.id, fieldName, comodelInstance.id))
                        if not self.addInstance(comodelInstance):
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
                            secondStep = True
                            self.sessionState.pop()
                        else:
                            fieldsData[fieldName] = comodelInstance.id
                            self.sessionState.commit()
                    except except_orm, e:
                        # Ignore recursion errors on non required fields
                        scndStepFields[fieldName] = comodelInstance
                        secondStep = True
                        self.sessionState.pop()
                        pass
                else:
                    fieldsData[fieldName] = 0 
            elif fieldType in ['one2many','many2many']:
                secondStep = True
                continue
            else:
                fieldsData[fieldName] = instance[fieldName] or False 

        _logger.debug("Collecting Master model %s, instance id %d" % (modelName, instance.id))

        # Add to response list to keep preorder
        self.sessionState.appendCommand({
            'command': 'update',
            'model': modelName,
            'id': instance.id,
            'values': fieldsData,
        })

        # Add the instance to the current response set
        self.sessionState.setInstance(instance)

        # Post order exploration of the instance. Process 2one fields
        if secondStep:
            fieldsData = {}

            for fieldName in allFields.keys():
                fieldType = allFields[fieldName]['type']
    
                if fieldType == 'many2one' and \
                   fieldName in scndStepFields and \
                   scndStepFields[fieldName]:
                    relationInstance = instance[fieldName]
                    #_logger.info("On 2nd step, model %s, instance %d, field %s, field instance %d" % (
                    #              modelName, instance.id, fieldName, relationInstance.id))
                    if not self.addInstance(relationInstance):
                        raise except_orm(_('Error'),
                                         _('Recursion error on model %s, instance %d, many2one field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                          (modelName, instance.id, fieldName, relationInstance._name, relationInstance.id))

                    fieldsData[fieldName] = relationInstance.id
                elif fieldType in ['one2many','many2many']:
                    for relationInstance in instance[fieldName]:
                        if not self.addInstance(relationInstance):
                            raise except_orm(_('Error'),
                                             _('Recursion error on model %s, instance %d, field %s, relation model %s, relation instance %d! Please check DBSynch Master configuration') % \
                                              (modelName, instance.id, fieldType, fieldName, relationInstance._name, relationInstance.id))
                    fieldsData[fieldName] = [i.id for i in instance[fieldName]]    
    
            # Send an updated of initial record

            if fieldsData:
                self.sessionState.appendCommand({
                    'command': 'update',
                    'model': modelName,
                    'id': instance.id,
                    'values': fieldsData,
                })
                _logger.debug("Updating relation fields on model %s, id %d, data %s" % (modelName, instance.id, unicode(fieldsData)))
        
        # Remove current instance from visited stack
        self.sessionState.removeVisited(instance)
        return True
            
    def addModel(self, modelName, selectList):
        modelObj = self.env[modelName]
        if self.limitDate:
            selectList.extend([('write_date','>=',self.limitDate)])
        instances = modelObj.search(selectList)
        for instance in instances:
            self.addInstance(instance)

    @api.model
    def get_synch_data(self, command):
        if command['protocolVersion'] == '1.0':
            self.modelsCache = {}
            self.sessionState = SessionState()

            self.limitDate = command['sinceTime']
            offset = command.get('offset', 0)
            limit = command.get('limit', 0)

            _logger.info("Collecting data for remote, cmds %s" % unicode(command.get('objectsToSend', [])))

            try:
                for cmd in command.get('objectsToSend', []):
                    requestedModel, selectList = cmd
                    self.addModel(requestedModel, selectList)
            except Exception, e:
                _logger.info("Exception collecting data %s" % unicode(e))
                raise
            commands = self.sessionState.getCommands()

            ret = {
                'count': len(commands),
                'lang': self.env.context.get('lang', 'en_US'),
                'company_id': self.env.user.company_id.id,
            }

            _logger.info("Collecting data for remote, returning %d commands, from %d, limit %d, lang %s" %
                         (ret['count'], offset, limit, ret['lang']))

            if limit:
                ret['data'] = commands[offset: offset+limit]
            else:
                ret['data'] = commands[offset:]

            #for cmd in ret['data']:
            #    _logger.info("Sending model %s, id %d" % (cmd['model'], cmd['id']))

            return ret
        else:
            return {
                'error': 'Protocol version not supported'            
            }
        
    def updateInstance(self, instanceData):
        reference = instanceData['reference']
        modelName = instanceData['model']
        instanceId = instanceData.get('id', False)
        fieldsData = instanceData['fields']
        operation = instanceData['operation']

        if modelName not in self.modelsCache:
            modelObj = self.env[modelName]
            fieldsDef = modelObj.fields_get()
            self.modelsCache[modelName] = (modelObj, fieldsDef)
        else:
            modelObj, fieldsDef = self.modelsCache[modelName]

        for fieldName, value in fieldsData.items():
            fieldType = fieldsDef[fieldName]['type']
            if fieldType in ['one2many', 'many2many']:
                fieldsData[fieldName] = [(4, ri) for ri in value]
            
        if operation == 'create':
            _logger.debug("Creating model %s with %s" % (modelName, fieldsData))

            if 'id' in fieldsData:
                del fieldsData['id']

            newInstance = modelObj.with_context(DBSYNCH_Update=True).create(fieldsData)
            self.response.append({
                'reference': reference,
                'model': modelName,
                'id': newInstance.id
            })
        elif operation == 'write':
            _logger.debug("Updating model %s, id %d with %s" % (modelName, instanceId, fieldsData))
            br = modelObj.browse(instanceId)
            br.with_context(DBSYNCH_Update=True     ).write(fieldsData)
                
    @api.model
    def remote_update(self, updateRequest):
        if updateRequest['protocolVersion'] == '1.0':
            self.modelsCache = {}
            self.response = []
            self.visited = {}
            self.instances = {}
                    
            # TODO Loggear excepciones
                    
            for instanceData in updateRequest['updateCommands']:
                self.updateInstance(instanceData)
    
            ret = {
                'createdIds': self.response,        
            }
    
            return ret
        else:
            return {
                'error': 'Protocol version not supported',            
            }
