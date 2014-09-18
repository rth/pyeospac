#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright CNRS 2012
# Roman Yurchak (LULI)
# This software is governed by the CeCILL-B license under French law and
# abiding by the rules of distribution of free software.
import numpy as np

from scipy.constants import physical_constants

from ..base import MaterialBase, TableBase, _pull_tables
from ..quantities import add_quantity

R_CST = physical_constants['molar gas constant'][0]*1e7 # erg.K⁻¹.mol⁻¹

# cf Guardone and Vigevano, 2001

def Pt_DT(self, rho, temp):
    return R_CST*temp*rho/(self['abar']*(1 - rho*self['b'])) - self['a']*rho**2

def Ut_DT(self, rho, temp):
    return R_CST*temp/(self['abar']*self['delta']) - self['a']*rho

def T_DUt(self, rho, eint):
    return self['abar']*self['delta'] * (eint + self['a']*rho)/R_CST

def T_DPt(self, rho, pres):
    return self['abar']*(pres - self['a']*rho**2)*(1./rho - self['b'])/R_CST

def Pt_DSt(self, rho, sint):
    return self['delta']* np.exp(self['delta']*self['abar']*(sint)/R_CST)/(1./rho - self['b'])**(self['delta']+1.0) - self['a']*rho**2

def St_DUt(self, rho, eint):
    return R_CST*np.log((1./rho - self['b'])*(eint + rho*self['a'])**(1./self['delta']))/self['abar']


def St_DT(self, rho, temp):
    # copy past previous lines
    eint = R_CST*temp/(self['abar']*self['delta']) - self['a']*rho
    return R_CST*np.log((1./rho - self['b'])*(eint + rho*self['a'])**(1./self['delta']))/self['abar']

available_tables = {'Pt_DT': Pt_DT, 'Ut_DT': Ut_DT,
                    'T_DUt': T_DUt, 'T_DPt': T_DPt,
                    'Pt_DSt': Pt_DSt, 'St_DUt': St_DUt,
                    'St_DT': St_DT}


class VdwTable(TableBase):
    _original_units = 'cgs'
    def __init__(self, _name, table_handle=None,
            options={'game': None, 'gamc':None, 'abar':None}, units='cgs'):
        self.options = {}
        super(VdwTable, self).__init__(_name, table_handle, options, units)
        for key in ['delta', 'rho_c', 'Pt_c', 'temp_c', 'a', 'b', 'abar']:
            self[key] = options[key] 

    def _interpolate(self, X, Y, kind):
        if kind == 'F':
            Xin, Yin = X*self._X_convert, Y*self._Y_convert
            return available_tables[self._name](self, Xin, Yin)*self._F_convert
        else:
            return self._differentiate(X, Y, kind)



class VdwMaterial(MaterialBase):
    def __init__(self, material=None, tables=None,
            options={'delta': None, 'a': None, 'b': None, 'abar': None},
            spec=['t'], table_handles=None, units='cgs'):
        """
        Parameters:
        -----------
         - material: int: 4 digit SESAME material ID
         - tables: list: ['table1_id', 'table2_id', ..etc]
         - options: 
            abar: atomic mass
            delta: defined as \delta = R / (C_v * A)
            rho_c: critical point density [g/cc]
            Pt_c: critical point pressure [0.1 Pa]
            a: Van der Waals constant [bar*L²/mol²]
            b: Van der Waals constant [L/mol]
            either rho_c and Pt_c or a and b should be provided
        """
        self._backend = 'vdw'
        self.tables = _pull_tables(tables, spec, available_tables.keys())
        self.options = {'delta': None, 'rho_c': None, 'Pt_c': None,
                'a': None, 'b': None, 'abar': None}


        self.options.update(**options)
        options =  self.options
        if options['abar']<1:
            raise ValueError('we should have game > 1')
        if options['delta']<0:
            raise ValueError('we should have delta > 0')
        self._init_base()
        if options['b'] is not None:
            options['b'] = 1e+3*options['b']/options['abar'] # L/mol -> cm³/g
            options['rho_c'] = 1./(3*options['b'])
        else:
            raise ValueError

        if options['a'] is not None:
            options['a'] = 1e6*1e+6*options['a']/options['abar']**2 # bar*L²/mol² -> barie*(cm³/g)²
            options['Pt_c'] = options['a']/(27.*options['b']**2)
        else:
            raise ValueError

        options['temp_c'] = 8*options['a']*options['abar']/(27*options['b']*R_CST)

        for tab_idx, tab_key in enumerate(self.tables):
            setattr(self, tab_key,
                VdwTable(tab_key,
                            None,
                            options=options,
                            units=units))



@add_quantity(name='G3_vdw', args='DT', dependencies=['P{s}_DT'])
def fundemental_derivative(tab, spec, *XYf):
    r"""Fundemental derivative
        Guardnone et al. 2001
        """
    if tab._backend != 'vdw':
        raise ValueError('This derived variable is only compatible with the vdw backend!')
    XYf_DT = XYf[:]
    rho = XYf_DT[0]
    Pt = tab.get_table('P{s}_DT', spec)(*XYf_DT)/tab.Pt_DT._F_convert
    print Pt
    delta = tab.Pt_DT['delta']
    a = tab.Pt_DT['a']
    b = tab.Pt_DT['b']
    P_frac_1 = (Pt + a*rho**2)/(1./rho - b)**2
    P_frac_2 = rho*(Pt + a*rho**2)/(1./rho - b)
    num = (delta+1)*(delta+2) * P_frac_1  - 6*a*rho**4 
    denum = 2*(delta+1)*P_frac_2 - 4*a*rho**4
    return num/denum