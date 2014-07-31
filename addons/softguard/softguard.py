# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT
from openerp import netsvc
from datetime import datetime
import base64
import csv
try:
    import cStringIO as StringIO
except:
    import StringIO

def takeone(l, alt=False):
    if l and len(l) > 0:
        return l[0]
    else:
        return alt

def update(o, d):
    dn = {}
    for k,v in d.items():
        v = v[0] if isinstance(v, tuple) else v
        v = o[k] if not v and o[k] else v
        dn[k] = v
    for k,v in o.items():
        if not k in dn:
            dn[k] = v
    return dn

class softguard_import_line(osv.osv):
    _name = 'softguard.import.line'

    # cue_cIdExtendido.

    _columns = {
        'import_id': fields.many2one('softguard.import', 'Softguard Import'),
        'RowNumber': fields.integer('Row number'),
        'cue_iid': fields.integer('cue_iid'),
        'cue_clinea': fields.char('cue_clinea'),
        'cue_ncuenta': fields.char('cue_ncuenta'),
        'cue_cnombre': fields.char('Name Account'),
        'cue_ccalle': fields.char('Street Account'),
        'cue_clocalidad': fields.char('Locality Account'),
        'cue_cprovincia': fields.integer('State Code'),
        'cue_provincia': fields.char('State Account'),
        'cue_ccodigopostal': fields.char('Postal Code Account'),
        'Situacion': fields.char('Situation'),
        'cue_cLatLng': fields.char('Position'),
        'sta_cultimaalarma': fields.char('sta_cultimaalarma'),
        'sta_dfechautimaalarma': fields.char('sta_dfechautimaalarma'),
        'sta_dfechaultimotst': fields.char('sta_dfechautimotst'),
        'cod_cdescripcion': fields.char('Description'),
        'cod_nColorLetra': fields.integer('cod_nColorLetra'),
        'cod_ncolor': fields.integer('Color'),
        'sta_nestado': fields.integer('STA State'),
        'act_nestado': fields.integer('ACT State'),
        'tip_ccodigo': fields.char('Code Account'),
        'tip_cdescripcion': fields.char('TIP Description'),
        'tip_curlimagen': fields.char('TIP Urlimag'),
        'tip_cservicio': fields.char('TIP Service'),
        'tip_nTipo': fields.integer('TIP Type'),
        'tip_nCondicion': fields.integer('TIP Condition'),
        'tip_idKey': fields.char('TIP Id Key'),
        'sta_nEnFalloDeAC': fields.integer('STA AC Fail'),
        'cue_nEfectiva': fields.integer('CUE Efective'),
        'cue_cIdExtendido': fields.char('CUE Cid Extended'),
        'cue_iZonaHoraria': fields.integer('CUE Time Zone'),
        'cue_cPartitionInfo': fields.char('CUE Partition Info'),
        'cue_nparticion': fields.integer('CUE Partition Number'),
    }

    def do_import(self, cr, uid, ids, context=None):
        par_obj = self.pool.get('res.partner')
        cou_obj = self.pool.get('res.country')
        sta_obj = self.pool.get('res.country.state')
        con_obj = self.pool.get('account.analytic.account')
        
        for line in self.browse(cr, uid, ids, context=context):
            par_key = line.cue_cIdExtendido.strip()
            par_ids = par_obj.search(cr, uid, [ '|', '|',
                ('ref','=','%s' % par_key),
                ('ref','=','%s.0' % par_key),
                ('category_id','=','E-%s' % par_key),
            ])

            values = {
                'ref': line.cue_ncuenta,
                'name': line.cue_cnombre.title(),
                'street': line.cue_ccalle,
                'street2': '',
                'city': line.cue_clocalidad.title(),
                'state_id': takeone(sta_obj.search(cr, uid, [('name','ilike',line.cue_provincia)])),
                'country_id': takeone(cou_obj.search(cr, uid, [('name','ilike','argentina')])),
                'zip': line.cue_ccodigopostal,
            }

            # If more than one partner for this reference, we send a message to advise.
            if len(par_ids) > 1:
                msg =  _('<b>Processing row %i, we found duplicated partner. Please check which partner must be deleted</b>') % line.RowNumber
                par_obj.message_post(cr, uid, par_ids, body=msg, context=context)
                continue

            elif len(par_ids) == 1:
                keep_values = par_obj.read(cr, uid, par_ids, [
                    'name',
                    'street',
                    'street2',
                    'city',
                    'state_id',
                    'country_id',
                    'zip',
                ])[0]
                values = update(values, keep_values)
                del values['id']
                par_obj.write(cr, uid, par_ids, values)
                msg =  _('<b>Updated from row %i using softguard import %s</b>') % (line.RowNumber, line.import_id.name)
                par_obj.message_post(cr, uid, par_ids, body=msg, context=context)

            else:
                par_ids = [ par_obj.create(cr, uid, values) ]
                msg =  _('<b>Created from row %i using softguard import %s</b>') % (line.RowNumber, line.import_id.name)
                par_obj.message_post(cr, uid, par_ids, body=msg, context=context)

            # Update and create contract.
            con_ids = con_obj.search(cr, uid, [('name','=',line.cue_ncuenta)])

            values = {
                'name': line.cue_ncuenta,
                'use_utilities': True,
                'state': 'draft',
                'partner_id': par_ids[0],
                'partner_invoice_id': par_ids[0],
                'partner_shipping_id': par_ids[0],
            }

            if len(con_ids) > 1:
                msg =  _('<b>Processing row %i, we found duplicated contract. Please check which contract must be deleted</b>') % line.RowNumber
                con_obj.message_post(cr, uid, con_ids, body=msg, context=context)
                continue

            elif len(con_ids) == 1:
                keep_values = con_obj.read(cr, uid, par_ids, [
                    'state',
                    'partner_id',
                    'partner_invoice_id',
                    'partner_shipping_id',
                ])
                values = update(values, keep_values)
                del values['id']
                con_obj.write(cr, uid, con_ids, values)
                msg =  _('<b>Updated from row %i using softguard import %s</b>') % (line.RowNumber, line.import_id.name)
                con_obj.message_post(cr, uid, con_ids, body=msg, context=context)

            else:
                con_ids = [ con_obj.create(cr, uid, values) ]
                msg =  _('<b>Created from row %i using softguard import %s</b>') % (line.RowNumber, line.import_id.name)
                con_obj.message_post(cr, uid, con_ids, body=msg, context=context)

            #if par_ids and con_ids:
           #     pass

        pass

softguard_import_line()

class softguard_import(osv.osv):
    _name = 'softguard.import'

    _columns = {
        'name': fields.char('Importation Name'),
        'date_load': fields.datetime('Load date'),
        'date_update': fields.datetime('Update date'),
        'data': fields.binary('Data File'),
        'line_ids': fields.one2many('softguard.import.line', 'import_id', 'Lines'),
    }

    def do_load(self, cr, uid, ids, context=None):
        for imp in self.browse(cr, uid, ids, context=context):
            if imp.line_ids:
                continue
            data = StringIO.StringIO(base64.decodestring(imp.data))
            import_lines = [ (0,0,values) for values in csv.DictReader(data) ]
            self.write(cr, uid, imp.id, { 'line_ids': import_lines })
        return True

    def do_import(self, cr, uid, ids, context=None):
        implin_obj = self.pool.get('softguard.import.line')
        for imp in self.browse(cr, uid, ids, context=context):
            if imp.line_ids:
                implin_obj.do_import(cr, uid, [line.id for line in imp.line_ids], context=context)
        return True

softguard_import()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
