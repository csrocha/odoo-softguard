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

    def _get_related_ids(self, cr, uid, ids, field_name, arg, context):
        par_obj = self.pool.get('res.partner')
        con_obj = self.pool.get('account.analytic.account')
        r = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            par_key = line.cue_cIdExtendido.strip()
            par_ids = par_obj.search(cr, uid, [ '|', '|',
                ('ref','=','%s' % par_key),
                ('ref','=','%s.0' % par_key),
                ('category_id','=','E-%s' % par_key),
            ])
            con_ids = con_obj.search(cr, uid, [('name','=',line.cue_ncuenta)])
            msg = "%s, %s" % (
                (len(par_ids) == 0 and 'No Partner') or
                (len(par_ids) >  1 and 'Error: Multiple Partners') or
                (len(par_ids) == 1 and 'Partner Ok'),
                (len(con_ids) == 0 and 'No Contract') or
                (len(con_ids) >  1 and 'Error: Multiple Contract') or
                (len(con_ids) == 1 and 'Contract Ok'),
            )
            r[line.id] = {
                'rel_partner_ids': par_ids,
                'rel_contract_ids': con_ids,
                'message': msg,
            }

        return r

    _columns = {
        'import_id': fields.many2one('softguard.import', 'Softguard Import', ondelete="cascade", required=True),
        'rel_partner_ids': fields.function(_get_related_ids, type='many2many', obj='res.partner', string='Related Partners', method=True, multi='related'),
        'rel_contract_ids': fields.function(_get_related_ids, type='many2many', obj='account.analytic.account', string='Related Contracts', method=True, multi='related'),
        'message': fields.function(_get_related_ids, type='char', string='Message', multi='related'),
        'state': fields.selection([('draft', 'Draft'),('hold','Hold'),('open','Open'),('done','Done')], 'State'),

        'name': fields.char('Row number'),
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

    _defaults = {
        'state': 'open',
    }

    def do_draft(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'draft'})
        return True
    
    def do_open(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'open'})
        return True

    def do_hold(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'hold'})
        return True

    def do_done(self, cr, uid, ids, context=None):
        par_obj = self.pool.get('res.partner')
        cou_obj = self.pool.get('res.country')
        sta_obj = self.pool.get('res.country.state')
        con_obj = self.pool.get('account.analytic.account')

        hold_ids = []
        done_ids = []

        for line in self.browse(cr, uid, ids):
            pars = line.rel_partner_ids
            cons = line.rel_contract_ids

            if line.state != 'open':
                continue

            if len(pars) > 1 or len(cons) > 1:
                hold_ids.append(line.id)
                continue

            par_ids = [ p.id for p in  pars ]

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

            if len(par_ids) == 1:
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
                msg =  _('<b>Updated from row %s using softguard import %s</b>') % (line.name, line.import_id.name)
                par_obj.message_post(cr, uid, par_ids, body=msg, context=context)

            else:
                par_ids = [ par_obj.create(cr, uid, values) ]
                msg =  _('<b>Created from row %s using softguard import %s</b>') % (line.name, line.import_id.name)
                par_obj.message_post(cr, uid, par_ids, body=msg, context=context)

            con_ids = [ c.id for c in  cons ]

            values = {
                'name': line.cue_ncuenta,
                'use_utilities': True,
                'state': 'draft',
                'partner_id': par_ids[0],
                'partner_invoice_id': par_ids[0],
                'partner_shipping_id': par_ids[0],
            }

            if len(con_ids) == 1:
                keep_values = con_obj.read(cr, uid, con_ids, [
                    'state',
                    'partner_id',
                    'partner_invoice_id',
                    'partner_shipping_id',
                ])[0]
                values = update(values, keep_values)
                del values['id']
                con_obj.write(cr, uid, con_ids, values)
                msg =  _('<b>Updated from row %s using softguard import %s</b>') % (line.name, line.import_id.name)
                con_obj.message_post(cr, uid, con_ids, body=msg, context=context)

            else:
                con_ids = [ con_obj.create(cr, uid, values) ]
                msg =  _('<b>Created from row %s using softguard import %s</b>') % (line.name, line.import_id.name)
                con_obj.message_post(cr, uid, con_ids, body=msg, context=context)

            done_ids.append(line.id)

        self.write(cr, uid, hold_ids, {'state':'hold'})
        self.write(cr, uid, done_ids, {'state':'done'})
        return True

    def open_partners(self, cr, uid, ids, context=None):
        line = self.browse(cr, uid, ids)[0]
        return  {
            'domain':[('id','in',[ p.id for p in line.rel_partner_ids ])],
            'name':_('Partners'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'res.partner',
            'type':'ir.actions.act_window',
        }

    def open_contracts(self, cr, uid, ids, context=None):
        line = self.browse(cr, uid, ids)[0]
        return  {
            'domain':[('id','in',[ p.id for p in line.rel_contract_ids ])],
            'name':_('Partners'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'account.analytic.account',
            'type':'ir.actions.act_window',
        }

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
        def _update_(d):
            d['name'] = d.pop('RowNumber')
            return d
        for imp in self.browse(cr, uid, ids, context=context):
            if imp.line_ids:
                continue
            data = StringIO.StringIO(base64.decodestring(imp.data))
            import_lines = [ (0,0,_update_(values)) for values in csv.DictReader(data) ]
            self.write(cr, uid, imp.id, { 'line_ids': import_lines })
        return True

    def do_import(self, cr, uid, ids, context=None):
        implin_obj = self.pool.get('softguard.import.line')
        for imp in self.browse(cr, uid, ids, context=context):
            if imp.line_ids:
                implin_obj.do_done(cr, uid, [line.id for line in imp.line_ids], context=context)
        return  {
            'domain':[('state','=','hold')],
            'name':_('Hold Lines'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'softguard.import.line',
            'type':'ir.actions.act_window',
        }

    def do_list_all(self, cr, uid, ids, context=None):
        return  {
            'domain':[('import_id','in',ids)],
            'name':_('Lines'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'softguard.import.line',
            'type':'ir.actions.act_window',
        }

    def do_list_hold(self, cr, uid, ids, context=None):
        return  {
            'domain':[('state','=','hold'),('import_id','in',ids)],
            'name':_('Hold Lines'),
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'softguard.import.line',
            'type':'ir.actions.act_window',
        }





softguard_import()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
