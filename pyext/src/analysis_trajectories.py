#!/usr/bin/env python

'''
Tools to analyze PMI MC runs
'''

from __future__ import division

import sys
import os
import math
import glob
import random
import itertools
import pandas as pd
import numpy as np
import multiprocessing as mp
from scipy import stats
from equilibration import *

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pylab as pl
import matplotlib.gridspec as gridspec
import matplotlib.cm as cmx
import matplotlib.colors as colors
mpl.rcParams.update({'font.size': 8})

import seaborn as sns
import hdbscan

class AnalysisTrajectories(object):
    def __init__(self,
                 out_dirs,
                 dir_name = 'run_', 
                 analysis_dir = 'analys/',
                 nproc=6):

        self.out_dirs = out_dirs
        self.dir_name = dir_name
        self.analysis_dir = analysis_dir
        self.nproc = nproc
        self.restraint_names = {}
        self.all_fields = []

        self.th = 50
        
        # For multiprocessing
        self.manager = mp.Manager()
        self.S_all = self.manager.dict()
        self.S_files = self.manager.dict()
        self.S_dist_all = self.manager.dict()
        self.XLs_nuis = self.manager.dict()
        
        # Sample stat file
        stat_files = np.sort(glob.glob(self.out_dirs[0]+'stat.*.out'))
        self.stat2_dict = self.get_keys(stat_files[0])

        # Define with restraints to analyze
        self.Connectivity_restraint = False
        self.Excluded_volume_restraint = False
        self.XLs_restraint = False
        self.XLs_restraint_nuisances = False
        self.Multiple_XLs_restraints = False
        self.atomic_XLs_restraint = False
        self.atomic_XLs_restraint_nuisances = False
        self.Multiple_atomic_XLs_restraints = False
        
        self.EM_restraint = False
        self.Distance_restraint = False
        self.Binding_restraint = False
        self.Occams_restraint = False
        self.Occams_restraint_nuisances = False
        self.Occams_positional_restraint = False
        self.Occams_positional_nuisances = False
        self.pEMAP_restraint = False
        self.DOPE_restraint = False
        self.MembraneExclusion_restraint = False
        self.MembraneSurfaceLocation_restraint = False

        # By default, add restraints of same type
        self.sum_Connectivity_restraint = True
        self.sum_Excluded_volume_restraint = True
        self.sum_Binding_restraint = True
        self.sum_Distance_restraint =  True
        self.sum_XLs_restraint = True
        self.sum_Occams_positional_restraint = True
        self.sum_atomic_XLs_restraint = True
        self.sum_DOPE_restraint = True
        self.sum_MembraneExclusion_restraint = True
        self.sum_MembraneSurfaceLocation_restraint = True
        
        self.select_XLs_satisfaction =  False
        self.select_EM_score = False
        self.select_Total_score = False
        self.Multiple_psi_values = False

        # Separate trajectories into two halves
        self.dir_halfA = np.sort(self.out_dirs)[::2]
        self.dir_halfB = np.sort(self.out_dirs)[1::2]

    def set_analyze_XLs_restraint(self,
                                  get_nuisances = True,
                                  Multiple_XLs_restraints =  False,
                                  ambiguous_XLs_restraint = False,
                                  XLs_cutoffs = {'DSSO':30.0}):
        self.XLs_restraint = True
        self.select_XLs_satisfaction = True
        self.ambiguous_XLs_restraint = False
        if get_nuisances:
            self.XLs_restraint_nuisances = True
        if Multiple_XLs_restraints:
            self.Multiple_XLs_restraints = True
            self.sum_XLs_restraint = False
        if ambiguous_XLs_restraint:
            self.ambiguous_XLs_restraint = True
            
        self.XLs_cutoffs = XLs_cutoffs
        

    def set_analyze_atomic_XLs_restraint(self,
                                         get_nuisances = True,
                                         Multiple_atomic_XLs_restraints =  False,
                                         atomic_XLs_cutoffs = {'DSSO':30.0}):
        self.atomic_XLs_restraint = True
        self.select_atomic_XLs_satisfaction = True
        if get_nuisances:
            self.atomic_XLs_restraint_nuisances = True
        if Multiple_atomic_XLs_restraints:
            self.Multiple_atomic_XLs_restraints = True
            self.sum_atomic_XLs_restraint = False
        self.atomic_XLs_cutoffs = atomic_XLs_cutoffs
    
    def set_analyze_Connectivity_restraint(self):
        self.Connectivity_restraint = True    
       
    def set_analyze_Excluded_volume_restraint(self):
        self.Excluded_volume_restraint = True
 
    def set_analyze_EM_restraint(self):
        self.EM_restraint = True

    def set_analyze_Distance_restraint(self):
        self.Distance_restraint = True

    def set_analyze_Binding_restraint(self):
        self.Binding_restraint = True
        
    def set_analyze_Occams_restraint(self):
         self.Occams_restraint = True
         
    def set_analyze_Occams_positional_restraint(self):
        self.Occams_positional_restraint = True
        self.Occams_positional_nuisances = True
    
    def set_analyze_pEMAP_restraint(self):
        self.pEMAP_restraint = True

    def set_analyze_DOPE_restraint(self):
        self.DOPE_restraint = True

    def set_analyze_MembraneExclusion_restraint(self):
        self.MembraneExclusion_restraint = True

    def set_analyze_MembraneSurfaceLocation_restraint(self):
        self.MembraneSurfaceLocation_restraint = True
        
    def set_select_by_Total_score(self, score_cutoff):
        self.select_Total_score = True
        self.cutoff_Total_score = score_cutoff

    def set_select_by_EM_score(self, score_cutoff):
        self.select_EM_score = True
        self.cutoff_EM_score = score_cutoff
        
    def get_restraint_fields(self):
        '''
        Gather information to retrieve from
        stat file for each trajectory
        '''
    
        # Get the field number for fframe and total score
        self.rmf_file_field = self.get_field_id(self.stat2_dict, 'rmf_file')
        rmf_frame_index = self.get_field_id(self.stat2_dict, 'rmf_frame_index')
        fframe = self.get_field_id(self.stat2_dict, 'MonteCarlo_Nframe')
        Total_score = self.get_field_id(self.stat2_dict, 'Total_Score')
    
        # Restraint names
        self.all_fields = fframe+rmf_frame_index+Total_score
        self.restraint_names[0] = 'MC_frame'
        self.restraint_names[1] = 'rmf_frame_index'
        self.restraint_names[2] = 'Total_score'
        self.name_i = 3

        # Percent satisfaction fields
        self.percent_satisfied = []
        
        # All possible restraints
        if self.Excluded_volume_restraint:
            self.get_fields('ExcludedVolumeSphere', 'EV')
           
        if self.Connectivity_restraint:
            self.get_fields('ConnectivityRestraint', 'CR')

        if self.XLs_restraint:
            self.get_fields('CrossLinkingMassSpectrometryRestraint_Data_Score', 'XLs')
            self.get_fields('CrossLinkingMassSpectrometryRestraint_PriorPsi_Score', 'XLs_psi')
            
            # Other quantities associated to XLs (distances and nuisances)
            XLs_dist = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if ('CrossLinkingMassSpectrometryRestraint_Distance_' in self.stat2_dict[k])}
            self.XLs_info = XLs_dist
            if self.XLs_restraint_nuisances:
                XLs_nuis = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if ('CrossLinkingMassSpectrometryRestraint_Psi_' in self.stat2_dict[k] and 'MonteCarlo_' not in self.stat2_dict[k])}
                self.psi_head = self.get_str_match(list(XLs_nuis.keys()))
                for k, v in XLs_nuis.items():
                    self.restraint_names[self.name_i] = 'Psi_vals_'+k.split('CrossLinkingMassSpectrometryRestraint_Psi_')[-1]
                    self.name_i += 1
                self.all_fields += XLs_nuis.values()

                if len(XLs_nuis.keys())> 1:
                    self.Multiple_psi_values = True
                self.XLs_info.update(XLs_nuis)
                mm = sorted(list([v for v in XLs_nuis.keys()]))
                ss = sorted(list([v+'_std' for v in XLs_nuis.keys()]))
                self.DF_XLs_psi = pd.DataFrame(columns=['Trajectory']+mm+ss)
            self.xls_fields = self.XLs_info.values()
            
        # Atomic XLs restraint
        if self.atomic_XLs_restraint:
            self.get_fields('AtomicXLRestraint_Score', 'atomic_XLs')
            
            # Get Psi score
            Psi_score = self.get_field_id(self.stat2_dict,'AtomicXLRestraint_psi_Score')
            self.restraint_names[name_i] = 'atomic_Psi_score'
            self.name_i += 1
            self.all_fields += Psi_score
            
            # Other quantities associated to XLs (distances and nuisances)
            atomic_XLs_dist = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if ('AtomicXLRestraint_' in self.stat2_dict[k] and 'BestDist' in self.stat2_dict[k])}
            self.atomic_XLs_info = atomic_XLs_dist
            if self.atomic_XLs_restraint_nuisances:
                atomic_XLs_nuis = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if ('AtomicXLRestraint_psi_Score' in self.stat2_dict[k] and 'MonteCarlo_' not in self.stat2_dict[k])}
                if len(atomic_XLs_nuis.keys())> 1:
                   self.Multiple_atomic_psi_values = True
                self.atomic_XLs_info.update(atomic_XLs_nuis)
                mm = sorted(list([v for v in atomic_XLs_nuis.keys()]))
                ss = sorted(list([v+'_std' for v in atomic_XLs_nuis.keys()]))
                self.DF_atomic_XLs_psi = pd.DataFrame(columns=['Trajectory']+mm+ss)

        # XLs info    
        self.XLs_names = self.XLs_info.keys()
        self.XLs_fields = [self.XLs_info[k] for k in self.XLs_names]
        if self.ambiguous_XLs_restraint == True:
            self.ambiguous_XLs_dict = self.check_XLs_ambiguity(self.XLs_names)
            
        if self.EM_restraint:
            self.get_fields('GaussianEMRestraint_EM', 'EM3D')
            
        if self.Occams_restraint:
            self.get_fields('OccamsRestraint_Score', 'OccCon')
            
            # Percent of restraints satisfied
            self.Occams_satif = self.get_field_id(self.stat2_dict, 'OccamsRestraint_satisfied')

        if self.Occams_restraint:
            self.get_fields('OccamsPositionalRestraint_Score', 'OccPos')
            
        if self.pEMAP_restraint:
            self.get_fields('SimplifiedPEMAP_Score_None', 'pEMAP')
            
            # Percent of restraints satisfied
            self.pEMAP_satif = self.get_field_id(self.stat2_dict, 'SimplifiedPEMAP_Satisfied')
            # All pE-MAP distances
            pEMAP_dist = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if ('SimplifiedPEMAP_Distance_' in self.stat2_dict[k])}
            
            # Get target distance from stat file
            d_pEMAP = []
            v_pEMAP = []
            for k, val in pEMAP_dist.items():
                d_pEMAP.append(float(k.split('_')[-1]))        
                v_pEMAP.append(val)

        if self.Distance_restraint:
            self.get_fields('DistanceRestraint_Score', 'DR')
            
        if self.Binding_restraint:
            self.get_fields('ResidueBindingRestraint_score', 'BR')
            
        if self.DOPE_restraint:
            self.get_fields('DOPE_Restraint_score', 'DOPE')
            
        if self.MembraneExclusion_restraint:
            self.get_fields('MembraneExclusionRestraint', 'MEX')
            
        if self.MembraneSurfaceLocation_restraint:
            self.get_fields('MembraneSurfaceLocation', 'MSL')
            
    def get_fields(self, name_stat_file, short_name):
        '''
        For each restraint, get the stat file field number
        '''
        RES = {self.stat2_dict[k]: k for k in self.stat2_dict.keys() if (name_stat_file in self.stat2_dict[k])}
        if len(RES) == 1:
            self.restraint_names[self.name_i] = short_name+'_sum'
            self.name_i += 1
        else:
            for k, v in RES.items():
                self.restraint_names[self.name_i] = short_name+'_'+k.split(name_stat_file + '_')[-1]
                self.name_i += 1
        self.all_fields += RES.values()
        
            
    def read_DB(self, db_file):
        ''' Read database '''
        DB = {}
        i = 0
        for line in open(db_file):
            vals =  line.split()
            DB[str(i)] = vals
            i  += 1
        return DB

    def get_keys(self, stat_file):
        ''' Get all keys in stat file '''
        for line in open(stat_file).readlines():
            d = eval(line)
            klist = list(d.keys())
            # check if it is a stat2 file
            if "STAT2HEADER" in klist:
                import operator
                isstat2 = True
                for k in klist:
                    if "STAT2HEADER" in str(k):
                        del d[k]
                stat2_dict = d
                # get the list of keys sorted by value
                kkeys = [k[0]
                         for k in sorted(stat2_dict.items(), key=operator.itemgetter(1))]
                klist = [k[1]
                         for k in sorted(stat2_dict.items(), key=operator.itemgetter(1))]
                invstat2_dict = {}
                for k in kkeys:
                    invstat2_dict.update({stat2_dict[k]: k})
            else:
                isstat1 = True
                klist.sort()
            break
        
        return stat2_dict

    def read_stat_files(self):
        
        # Split directories
        ND = int(np.ceil(len(self.out_dirs)/float(self.nproc)))
        out_dirs_dict = {}
        for k in range(self.nproc-1):
            out_dirs_dict[k] = list(self.out_dirs[(k*ND):(k*ND+ND)])
        out_dirs_dict[self.nproc-1] = list(self.out_dirs[((self.nproc-1)*ND):(len(self.out_dirs))])

        # Define an output queue
        output = mp.Queue()
        
        # Setup a list of processes that we want to run
        processes = [mp.Process(target=self.read_traj_info, args=((out_dirs_dict[x],))) for x in range(self.nproc)]

        # Run processes
        for p in processes:
            p.start()
            
        # Exit the completed processes
        for p in processes:
            p.join()

    def read_stats_detailed(self, traj, stat_files, query_fields, dist_fields, satif_fields, query_rmf_file):
        """
        Detailed reading of stats files that includes
        the rmf in which the frame is.
        To be used when using rmf_slice
        """
        
        S_scores = []
        S_dist = []
        P_satif = []
        #frames_dic = {}
        for file in stat_files:
            line_number=0
            for line in open(file).readlines():
                line_number += 1
                try:
                    d = eval(line)
                except:
                    print("# Warning: skipped line number " + str(line_number) + " not a valid line")
                    break 

                if line_number > 1:
                    frmf = [d[field] for field in query_rmf_file][0]
                    s0 = [float(d[field]) for field in self.all_fields]+[traj, frmf]
                    S_scores.append(s0)
                    if self.XLs_restraint or  self.atomic_XLs_restraint:
                        d0 = [s0[0]] + [float(d[field]) for field in self.xls_fields]
                        S_dist.append(d0)
                    if satif_fields:
                        p0 = [s0[0]] + [float(d[field]) for field in satif_fields]
                        P_satif.append(p0)
                    
        # Sort based on frame
        S_scores.sort(key=lambda x: float(x[0]))
        
        # Convert into pandas DF
        column_names = [self.restraint_names[x] for x in sorted(self.restraint_names.keys())] + ['traj', 'rmf3_file']
        DF = pd.DataFrame(S_scores, columns = column_names)
        
        # If some restraints need to be added
        if self.XLs_restraint and self.sum_XLs_restraint:
            XLs_sum = pd.Series(self.add_restraint_type(DF, 'XLs_'))
            DF = DF.assign(XLs_sum=XLs_sum.values)

        if self.atomic_XLs_restraint and self.sum_atomic_XLs_restraint:
            atomic_XLs_sum = pd.Series(self.add_restraint_type(DF, 'atomic_XLs_'))
            DF = DF.assign(atomic_XLs_sum=atomic_XLs_sum.values)
       
        if self.Excluded_volume_restraint and self.sum_Excluded_volume_restraint:
            EV_sum = pd.Series(self.add_restraint_type(DF, 'EV_'))
            DF = DF.assign(EV_sum=EV_sum.values)
 
        if self.Connectivity_restraint and self.sum_Connectivity_restraint:
            CR_sum = pd.Series(self.add_restraint_type(DF, 'CR_'))
            DF = DF.assign(CR_sum=CR_sum.values)
            
        if self.Binding_restraint and self.sum_Binding_restraint:
            BR_sum = pd.Series(self.add_restraint_type(DF, 'BR_'))
            DF = DF.assign(BR_sum=BR_sum.values)
            
        if self.Distance_restraint and self.sum_Distance_restraint:
            DR_sum = pd.Series(self.add_restraint_type(DF, 'DR_'))
            DF = DF.assign(DR_sum=DR_sum.values)

        if self.MembraneExclusion_restraint and self.sum_MembraneExclusion_restraint:
            MEX_sum = pd.Series(self.add_restraint_type(DF, 'MEX_'))
            DF = DF.assign(MEX_sum=MEX_sum.values)

        if self.MembraneExclusion_restraint and self.sum_MembraneExclusion_restraint:
            MSL_sum = pd.Series(self.add_restraint_type(DF, 'MSL_'))
            DF = DF.assign(MSL_sum=MSL_sum.values)
    
        # Get distance fields
        if self.XLs_restraint:
            S_dist = np.array(S_dist)
            S_dist = S_dist[S_dist[:,0].argsort()]
            # Convert in DF
            column_names_XLs = ['MC_frame'] + list(self.XLs_info.keys())
            DF_XLs = pd.DataFrame(S_dist, columns = column_names_XLs)
        if self.atomic_XLs_restraint:
            S_dist = np.array(S_dist)
            S_dist = S_dist[S_dist[:,0].argsort()]
            # Convert in DF
            column_names_XLs = ['MC_frame'] + list(self.atomic_XLs_info.keys())
            DF_atomic_XLs = pd.DataFrame(S_dist, columns = column_names_XLs)
     
        if satif_fields:  
            P_satif = np.array(P_satif)
            P_satif = P_satif[P_satif[:,0].argsort()]

        #return DF, DF_XLs, P_satif, frames_dic
        if self.XLs_restraint:
            return DF, DF_XLs, P_satif
        elif self.atomic_XLs_restraint:
            return DF, DF_atomic_XLs, P_satif
        elif satif_fields:
            return DF, None, P_satif
        else:
            return DF, None, None

    def add_restraint_type(self, DF, key_id):
        temp_fields = [v for v in DF.columns.values if key_id in v]
        DF_t = DF[temp_fields]
        DF_s = DF_t.sum(axis=1)
        return DF_s
    
    def read_traj_info(self, out_dirs_sel):
        # Dictionary to put the scores of all the trajectories
        # files_dic: keys: frames, values: rmf3 file

        #rmf_file = get_field_id(stat2_dict, 'rmf_file')
        #rmf_frame_index = get_field_id(stat2_dict, 'rmf_frame_index')

        if isinstance(out_dirs_sel, str):
            out_dirs_sel = [out_dirs_sel]
        
        for out in out_dirs_sel:
            if self.dir_name in out:
                traj = [x for x in out.split('/') if self.dir_name in x][0]
                traj_number = int(traj.split(self.dir_name)[1])
            else:
                traj = 0
                traj_number = 0
            stat_files = np.sort(glob.glob(out+'stat.*.out'))
            #if self.XLs_restraint:
            #    S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
            #                                                             stat_files,
            #                                                             self.all_fields,
            #                                                             self.XLs_info.values(),
            #                                                             None,
            #                                                             self.rmf_file_field)
                
                
            if self.atomic_XLs_restraint and not self.pEMAP_restraint and not self.Occams_restraint:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         self.atomic_XLs_info.values(),
                                                                         None,
                                                                         self.rmf_file_field)
                
            elif self.pEMAP_restraint and not self.XLs_restraint:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         None,
                                                                         self.pEMAP_satif,
                                                                         self.rmf_file_field)
    
            elif self.pEMAP_restraint and self.XLs_restraint:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         self.XLs_info.values(),
                                                                         self.pEMAP_satif,
                                                                         self.rmf_file_field)
            elif self.Occams_restraint  and not self.XLs_restraint:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         None,
                                                                         self.Occams_satif,
                                                                         self.rmf_file_field)
    
            elif self.Occams_restraint and self.XLs_restraint:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         self.XLs_info.values(),
                                                                         self.Occams_satif,
                                                                         self.rmf_file_field)

            
                
            else:
                S_tot_scores, S_dist, P_satif = self.read_stats_detailed(traj,
                                                                         stat_files,
                                                                         self.all_fields,
                                                                         None,
                                                                         None,
                                                                         self.rmf_file_field)


            print('The mean score, min score, and n frames are: ', traj_number,
                  np.mean(S_tot_scores['Total_score'].iloc[self.th:]),
                  np.min(S_tot_scores['Total_score'].iloc[self.th:]),
                  len(S_tot_scores))
                
            # Selection of just sums (default)
            sel_entries = ['Total_score']+[v for v in S_tot_scores.columns.values if 'sum' in v]
            
            # If specified by user, can look at individual contributions
            if self.Connectivity_restraint== True and self.sum_Connectivity_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'CR_' in v and 'sum' not in v]
            if self.Excluded_volume_restraint== True and self.sum_Excluded_volume_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'EV_' in v and 'sum' not in v]
            if self.Binding_restraint == True and self.sum_Binding_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'BR_' in v and 'sum' not in v]
            if self.Distance_restraint ==  True and self.sum_Distance_restraint ==  False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'DR_' in v and 'sum' not in v]
            if self.XLs_restraint == True and self.sum_XLs_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'XLs_' in v and 'sum' not in v]
            if self.atomic_XLs_restraint == True and self.sum_atomic_XLs_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'atomic_XLs_' in v and 'sum' not in v]
            if self.DOPE_restraint == True and self.sum_DOPE_restraint == False:
                sel_entries += [v for v in S_tot_scores.columns.values if 'DOPE_' in v and 'sum' not in v]

            # Also add nuisances parameter
            sel_entries += [v for v in S_tot_scores.columns.values if 'Psi' in v and 'sum' not in v]
            
            # Detect equilibration time
            ts_eq = []
            for r in sel_entries:
                try:
                    [t, g, N] = detectEquilibration(np.array(S_tot_scores[r].loc[self.th:]), nskip=5, method='multiscale')
                    ts_eq.append(t)
                except:
                    ts_eq.append(0)
            print('Trajectory, ts_eqs: ',traj, ts_eq)
            ts_max = np.max(ts_eq)+self.th
        
            # Plot the scores and restraint satisfaction
            file_out = 'plot_scores_%s.pdf'%(traj_number)               
            self.plot_scores_restraints(S_tot_scores[['MC_frame']+sel_entries], ts_eq, file_out)
        
            if self.pEMAP_restraint:
                file_out_pemap = 'plot_pEMAP_%s.pdf'%(traj_number) 
                self.plot_pEMAP_distances(P_satif, file_out_pemap)

            if self.Occams_restraint:
                file_out_occams = 'plot_Occams_satisfaction_%s.pdf'%(traj_number) 
                self.plot_Occams_satisfaction(P_satif, file_out_occams)
                
            # Check how many XLs are satisfied
            if self.XLs_restraint:
                S_tot_scores, S_dist = self.analyze_trajectory_XLs(S_tot_scores,
                                                                   S_dist,
                                                                   atomic_XLs = False,
                                                                   traj_number = traj_number,
                                                                   ts_max = ts_max)
                
            if self.atomic_XLs_restraint:
                S_tot_scores, S_dist = self.analyze_trajectory_XLs(S_tot_scores,
                                                                   S_dist,
                                                                   atomic_XLs = True,
                                                                   traj_number = traj_number,
                                                                   ts_max = ts_max)
                                                                                                 
            # Add half info
            if out in self.dir_halfA:
                S_tot_scores = S_tot_scores.assign(half = pd.Series(['A']*len(S_tot_scores), index=S_tot_scores.index).values)
            elif out in self.dir_halfB:
                S_tot_scores = S_tot_scores.assign(half = pd.Series(['B']*len(S_tot_scores), index=S_tot_scores.index).values)
            else:
                S_tot_scores = S_tot_scores.assign(half = pd.Series([0]*len(S_tot_scores), index=S_tot_scores.index).values)

            self.S_all[out] = S_tot_scores[ts_max:]
            if self.XLs_restraint:
                self.S_dist_all[out] = S_dist[ts_max:]
            if self.atomic_XLs_restraint:
                self.S_dist_all[out] = S_dist[ts_max:]
                
    def get_field_id(self, dict,val):
        ''' 
        For single field, get number of fields in stat file 
        '''
        return [k for k in dict.keys() if dict[k]==val]
    
    def plot_scores_restraints(self, selected_scores, ts_eq, file_out):
        '''
        For each trajectory plot all restraint scores
        '''
        n_bins=20
        ts_max = np.max(ts_eq)
        n_res = len(selected_scores.columns.values)-1
    
        fig, ax = pl.subplots(figsize=(2.0*n_res, 4.0), nrows=2, ncols=n_res)
        axes = ax.flatten()
        for i, c in enumerate(selected_scores.columns.values[1:]):
            axes[i].plot(selected_scores['MC_frame'].loc[self.th::10], selected_scores[c].loc[self.th::10], color='b',alpha=0.5)
            axes[i].axvline(ts_eq[i], color='grey')
            axes[i].set_title(c, fontsize=14)
            axes[i].set_xlabel('Step',fontsize=12)
            if i == 0:
                axes[i].set_ylabel('Score (a.u.)',fontsize=12)
        
        for i, c in enumerate(selected_scores.columns.values[1:]):
            axes[i+n_res].hist(selected_scores[c].loc[ts_eq[i]::10], n_bins, histtype='step',fill=False, color='orangered',alpha=0.9)
            axes[i+n_res].hist(selected_scores[c].loc[ts_max::10], n_bins, histtype='step',fill=False, color='gold',alpha=0.9)
            axes[i+n_res].set_xlabel('Score (a.u.)',fontsize=12)
            if i == 0:
                axes[i+n_res].set_ylabel('Density',fontsize=12)

        pl.tight_layout(pad=0.5, w_pad=0.1, h_pad=2.0)
        fig.savefig(self.analysis_dir+file_out)
       
    def write_models_info(self):
        ''' Write info of all models after equilibration'''
       
        for k, T in self.S_all.items():
            kk = k.split(self.dir_name)[-1].split('/')[0]
            T.to_csv(self.analysis_dir+'all_info_'+str(kk)+'.csv')

    def read_models_info(self, XLs_cutoffs= None):
        ''' Read info of all models after equilibration'''
        if XLs_cutoffs:
            self.XLs_cutoffs = XLs_cutoffs        

        info_files = glob.glob(self.analysis_dir+'all_info_*.csv')
        for f in info_files:
            k = f.split('all_info_')[-1].split('.csv')[0]
            df = pd.read_csv(f)
            self.S_all[k] = df
        
        xls_all_file = glob.glob(self.analysis_dir+'XLs_info_all.csv')
        if len(xls_all_file)>0:
            self.S_comb_dist = pd.read_csv(xls_all_file[0])
            self.ambiguous_XLs_restraint = True
            XLs_names = self.S_comb_dist.columns.values
            self.ambiguous_XLs_dict =  self.check_XLs_ambiguity(XLs_names)
        else:
            print('No files with XLs info found')
            
       
    def hdbscan_clustering(self,
                           selected_scores,
                           min_cluster_size=150,
                           min_samples=5,
                           skip=1):

        '''
        DO HDBSCAN clustering for selected restraint and/or nuisance parameters
        '''

        all_dfs = [self.S_all[dd] for dd in np.sort(self.S_all.keys())]
        S_comb = pd.concat(all_dfs)
        
        S_comb_sel = S_comb[selected_scores].iloc[::skip]
        S_comb_all = S_comb.iloc[::skip]       

        hdbsc = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size,
                                min_samples=min_samples).fit(S_comb_sel)
        labels = hdbsc.labels_

        # Add clusters labels
        S_comb_sel = S_comb_sel.assign(cluster = pd.Series(hdbsc.labels_, index=S_comb_sel.index).values)
        S_comb_all = S_comb_all.assign(cluster = pd.Series(hdbsc.labels_, index=S_comb_all.index).values)

        # Add cluster labels also to XLs info if available
        if self.XLs_restraint == True:
            all_dist_dfs = [self.S_dist_all[dd] for dd in np.sort(self.S_dist_all.keys())]
            S_comb_dist = pd.concat(all_dist_dfs).iloc[::skip]
            self.S_comb_dist = S_comb_dist.assign(cluster = pd.Series(hdbsc.labels_, index=S_comb_dist.index).values)
            self.S_comb_dist.to_csv(self.analysis_dir+'/XLs_info_all.csv', index=False)
            
 
        print('Number of unique clusters: ', len(np.unique(hdbsc.labels_)))
        
        # Write and plot info from clustering
        self.plot_hdbscan_clustering(S_comb_sel, selected_scores)
        self.write_hdbscan_clustering(S_comb_all)

        S_comb_sel = S_comb_sel.assign(half = pd.Series(S_comb_all['half'],index=S_comb_sel.index).values)
        self.write_summary_hdbscan_clustering(S_comb_sel)

    def write_summary_hdbscan_clustering(self, S_comb_sel):

        ''' 
        Write clustering summary information 
        (i.e. cluster number, average scores, number of models)
        '''
        
        clusters = list(set(S_comb_sel['cluster']))
        
        out = open(self.analysis_dir+'summary_hdbscan_clustering.dat', 'w')
        out.write(' '.join(S_comb_sel.columns.values) +' n_models n_A n_B \n')
        for cl in clusters:
            cluster_info = np.array(S_comb_sel[S_comb_sel['cluster']==cl].mean().values).astype('str')
            n_models = len(S_comb_sel[S_comb_sel['cluster']==cl])
            n_A = len(S_comb_sel[(S_comb_sel['cluster']==cl) & (S_comb_sel['half']=='A')])
            n_B = len(S_comb_sel[(S_comb_sel['cluster']==cl) & (S_comb_sel['half']=='B')])
            out.write(' '.join(cluster_info.astype('str'))+' '+str(n_models)+' '+str(n_A)+' '+str(n_B) +'\n')
            print('Cluster number, number of models: ', cl, n_models)
        out.close()

    def plot_hdbscan_trajectories_info(self, cluster):
        # TO DO
        return 0

    def write_hdbscan_clustering(self, S_comb):

        ''' 
        Write the frames information for each cluster
        '''

        print('Selecting and writing models to extract ...')
        clusters = list(set(S_comb['cluster']))
        clusters = [cl for cl in clusters if cl >=0]
        
        clus_sel = 0
        for cl in clusters:
            HH_cluster = S_comb[S_comb['cluster'] == cl]
            # Select two-halves
            HA = HH_cluster[(HH_cluster['half']=='A')]
            HB = HH_cluster[(HH_cluster['half']=='B')]
            if len(HA['half'].values) >= 10 and len(HB['half'].values) >= 10:
                clus_sel += 1
                n = self.plot_scores_distributions(HA, HB, cl)
            
                out_A = open(self.analysis_dir+'selected_models_A_cluster'+str(cl)+'.dat', 'w')
                out_B = open(self.analysis_dir+'selected_models_B_cluster'+str(cl)+'.dat', 'w')
                for row in HH_cluster.itertuples():
                    if row.half=='A':
                        out_A.write('h1_'+row.traj+'_'+str(int(row.MC_frame))+'.rmf3 \n')
                    if row.half=='B':
                        out_B.write('h2_'+row.traj+'_'+str(int(row.MC_frame))+'.rmf3 \n')

                out_A.close()
                out_B.close()

                out_A_det = open(self.analysis_dir+'selected_models_A_cluster'+str(cl)+'_detailed.dat', 'w')
                out_B_det = open(self.analysis_dir+'selected_models_B_cluster'+str(cl)+'_detailed.dat', 'w')
                for row in HH_cluster.itertuples():
                    if row.half=='A':
                        out_A_det.write('h1_'+row.traj+'_'+str(int(row.MC_frame))+'.rmf3 '+row.traj+' '+row.rmf3_file+' '+str(int(row.MC_frame))+' '+str(int(row.rmf_frame_index))+'\n')
                    if row.half=='B':
                        out_B_det.write('h2_'+row.traj+'_'+str(int(row.MC_frame))+'.rmf3 '+row.traj+' '+row.rmf3_file+' '+str(int(row.MC_frame))+' '+str(int(row.rmf_frame_index))+'\n')

                out_A_det.close()
                out_B_det.close()

                # Write to csv
                HA.to_csv(self.analysis_dir+'selected_models_A_cluster'+str(cl)+'_detailed.csv')
                HB.to_csv(self.analysis_dir+'selected_models_B_cluster'+str(cl)+'_detailed.csv')

                # Select n model from
                if int(n) < 30000 and len(HH_cluster) < 30000:
                    HH_sel = HH_cluster
                    HH_sel_A = HH_sel[(HH_sel['half']=='A')]
                    HH_sel_B = HH_sel[(HH_sel['half']=='B')]
                else:
                    HH_sel = HH_cluster.sample(n=29999)
                    HH_sel_A = HH_sel[(HH_sel['half']=='A')]
                    HH_sel_B = HH_sel[(HH_sel['half']=='B')]
                    
                HH_sel_A.to_csv(self.analysis_dir+'selected_models_A_cluster'+str(cl)+'_random.csv')
                HH_sel_B.to_csv(self.analysis_dir+'selected_models_B_cluster'+str(cl)+'_random.csv')
                
        if clus_sel == 0:
            print('WARNING: No models were selected because the simulations are not converged.')
                
    def plot_hdbscan_clustering(self, S_comb_sel, selected_scores):

        print('Generating HDBSCAN clustering plot ...')
        num_sel = len(S_comb_sel)-2

        palette = sns.color_palette("deep", len(np.unique(S_comb_sel['cluster']))).as_hex()
        cluster_colors = [palette[col] for col in S_comb_sel['cluster']]

        n_sel = len(selected_scores)
        fig = pl.figure(figsize=(2*n_sel,2*n_sel))
        gs = gridspec.GridSpec(n_sel, n_sel)
        i = 0
        for s1, s2 in itertools.product(selected_scores, repeat=2):
            ax = pl.subplot(gs[i])
            if s1 == s2:
                ax.hist(S_comb_sel[s1], 20, histtype='step',color='b', alpha=0.5)
            else:
                ax.scatter(S_comb_sel[s2],S_comb_sel[s1], c=np.array(cluster_colors),s=3.0,alpha=0.3)
        
            i += 1
                
        # Add horizontal labels (top plots)
        for i in range(n_sel):
            fig.get_axes()[i].set_title('%s'%(selected_scores[i]),
                                        fontsize=12)
        # Add vertical labels
        fig.get_axes()[0].set_ylabel('%s'%(selected_scores[0]),
                                     fontsize=12)
        k = 1 
        for i in range(n_sel,n_sel*n_sel,n_sel):
            fig.get_axes()[i].set_ylabel('%s'%(selected_scores[k]),
                                         fontsize=12)
            k += 1
            
            
        pl.tight_layout(pad=1.2, w_pad=1.5, h_pad=2.5)
        fig.savefig(self.analysis_dir+'plot_clustering_scores.png') 
        pl.close()
        
    def do_extract_models(self, gsms_info, filename, gsms_dir):

        self.scores = self.manager.list()
        
        # Split the DF
        df_array = np.array_split(gsms_info, self.nproc)

        # Define an output queue
        output = mp.Queue()
        
        # Setup a list of processes that we want to run
        processes = [mp.Process(target=self.extract_models, args=(df_array[x], filename, gsms_dir)) for x in range(self.nproc)]

        # Run processes
        for p in processes:
            p.start()
            
        # Exit the completed processes
        for p in processes:
            p.join()

        # Write scores to file
        np.savetxt(gsms_dir+'.txt', np.array(self.scores))
    
    def write_GSMs_info(self, gsms_info, filename):
        restraint_cols = gsms_info.columns.values
        gsms_info.to_csv(self.analysis_dir+filename, index=False)

    def get_models_to_extract(self, file):
        # Get models to extract from file
        DD  = pd.read_csv(file)
        return DD
        
    def get_sample_of_models_to_extract(self, file_A, file_B):
        DD_A = pd.read_csv(file_A)
        DD_B = pd.read_csv(file_B)

        # Take samples and see when it plateaus
        
    def extract_models(self, gsms_info, filename, gsms_dir):
        '''
        Use rmf_slice to extract the GSMs
        '''
        for row in gsms_info.itertuples():
            id = row.traj
            fr = int(row.MC_frame)
            fr_rmf = int(row.rmf_frame_index)
            file = row.rmf3_file
            os.system('rmf_slice '+ id+'/'+file + ' '+gsms_dir+'/'+filename+'_'+str(id)+'_'+str(fr)+'.rmf3 --frame '+str(fr_rmf) )
            
            # Collect scores
            self.scores.append(row.Total_score)
            
    def create_gsms_dir(self, dir):
        '''
        Create directories for GSM.
        If already present, rename old one
        '''
        
        if not os.path.isdir(dir):
            os.makedirs(dir)
        else:
            os.system('mv '+dir + ' '+dir+'.old_'+str(random.randint(0,100)))
            os.makedirs(dir)

    def plot_scores_distributions(self, HA, HB, cl):
        '''
        Plot distribution of GSMs of both halves
        '''
        
        n_bins = 20
 
        scores_A = HA['Total_score']
        scores_B = HB['Total_score']

        fig = pl.figure(figsize=(8,4))
        gs = gridspec.GridSpec(1, 2,
                               width_ratios = [0.5,0.5],
                               height_ratios = [1.0])
    
        # Plot distributions
        ax= pl.subplot(gs[0])
        ax.hist(scores_A,  n_bins, histtype='step', stacked=True, fill=False, color='orangered')
        ax.hist(scores_B,  n_bins, histtype='step', stacked=True, fill=False, color='blue')
        ax.set_xlabel('Total scores (a.u.)')
        ax.set_ylabel('Density')

        # Plot expected score from random set
        nn = len(scores_A) + len(scores_B)
       
        M = np.arange(int(min(len(scores_A),len(scores_B))/20.), min(len(scores_A),len(scores_B)),int(nn/20.))
        if len(M)<=10.0:
            M = np.arange(int(min(len(scores_A),len(scores_B))/10.), min(len(scores_A),len(scores_B)),int(min(len(scores_A),len(scores_B))/10.))
    
        RH1 = []
        RH2 = []
        for m in M[1:]:
            D1 = []
            D2 = []
            for d in range(20):
                D1.append(min(random.sample(list(scores_A),m)))
                D2.append(min(random.sample(list(scores_B),m)))
            RH1.append((m,np.mean(D1),np.std(D1)))
            RH2.append((m,np.mean(D2),np.std(D2)))
        
        RH1 = np.array(RH1)
        RH2 = np.array(RH2)

        hits = 0
        n = 0
        for s in range(len(RH1)-1):
            dA = RH1[s,1]-RH1[s+1,1]
            dB = RH2[s,1]-RH2[s+1,1]
            if dA < RH1[s+1,2] and dB < RH2[s+1,1]:
                hits += 1
            if hits == 4:
                n = RH1[s+1,0]
                continue
        
        ax = pl.subplot(gs[1])
        ax.errorbar(RH1[:,0], RH1[:,1], yerr=RH1[:,2], c='orangered',fmt='o')
        ax.errorbar(RH2[:,0], RH2[:,1], yerr=RH2[:,2], c='blue',fmt='o')
        ax.axvline(n, color='grey')
        ax.set_xlim([0.8*M[0],1.1*M[-1]])
        ax.set_xlabel('Number of models')
        ax.set_ylabel('Minimum score (a.u.)')

        fig.savefig(self.analysis_dir+'plot_scores_convergence_cluster'+str(cl)+'.pdf') 
        pl.close()

        return n
     
    def check_XLs_ambiguity(self, all_keys):
        '''
        Input: DF with XLs distances
        Output: Dictionary of XLs that should be treated as ambiguous
        '''
        xls_ids = {}

        if self.Multiple_XLs_restraints:
            for type_XLs in self.XLs_cutoffs.keys():
                xls_ids[type_XLs] = {}
                for i, xl in enumerate(all_keys):
                    if ('Distance_' in xl) and (type_XLs in xl):
                        vals = xl.split('|')
                        id = vals[2].split('.')[0]
                        p1 = vals[3].split('.')[0]
                        r1 = vals[4]
                        p2 = vals[5].split('.')[0]
                        r2 = vals[6]
                        if id in xls_ids[type_XLs].keys():
                            xls_ids[type_XLs][id].append(xl)
                        else:
                            xls_ids[type_XLs][id] = [xl]
        else:        
            for i, xl in enumerate(all_keys):
                if ('Distance_' in xl):
                    vals = xl.split('|')
                    id = vals[2].split('.')[0]
                    p1 = vals[3].split('.')[0]
                    r1 = vals[4]
                    p2 = vals[5].split('.')[0]
                    r2 = vals[6]
                    if id in xls_ids.keys():
                        xls_ids[id].append(xl)
                    else:
                        xls_ids[id] = [xl]
        return xls_ids

    def get_Psi_stats(self, atomic_XLs = False):
        '''
        Organize Psi values into DataFrame
        Get mean value for extracting models 
        (Does not work for atomic XLs restraint)
        '''
        if atomic_XLs:
            DF_XLs_psi  =  self.DF_atomic_XLs_psi
        else:
            DF_XLs_psi  =  self.DF_XLs_psi

        
        for k,v in self.XLs_nuis.items():
            DF_XLs_psi = DF_XLs_psi.append(pd.Series([k]+v, index = DF_XLs_psi.columns.values), ignore_index=True) 

        DF_XLs_psi.to_csv(self.analysis_dir+'XLs_all_Psi.csv')

        psi_cols =  DF_XLs_psi.columns.values[1:]
        psi_vals = DF_XLs_psi[psi_cols]
        if self.Multiple_XLs_restraints or self.Multiple_psi_values:
            self.psi_mean = psi_vals.mean()
        else:
            self.psi_mean = psi_vals.mean().mean()
           
        print('The average XLs Psi parameter is: ', self.psi_mean)

    def analyze_trajectory_XLs(self, S_tot_scores, S_dist, atomic_XLs, traj_number, ts_max):

        sel_nuis = [v for v in S_dist.columns.values if 'Psi' in v]
                
        # Get XLS satisfaction, append to S_dist
        XLs_satif_fields = []
        if self.Multiple_XLs_restraints:
            for type_XLs in self.XLs_cutoffs.keys():
                XLs_satif = self.get_XLs_satisfaction(S_dist, atomic_XLs, type_XLs = type_XLs)
                temp_name = 'XLs_satif_'+type_XLs.rstrip()
                S_tot_scores = S_tot_scores.assign(XLs_satif=pd.Series(XLs_satif))
                S_tot_scores.rename(columns={'XLs_satif':temp_name}, inplace=True)
                XLs_satif_fields.append(temp_name)
        elif self.Multiple_psi_values:
            all_psis = [v.split(self.psi_head)[1] for v in  self.DF_XLs_psi.columns.values[1:] if 'std' not in v]
            for type_psi in all_psis:
                XLs_satif = self.get_XLs_satisfaction(S_dist, atomic_XLs, type_psi = type_psi)
                temp_name = 'XLs_satif_'+type_psi
                S_tot_scores = S_tot_scores.assign(XLs_satif=pd.Series(XLs_satif))
                S_tot_scores.rename(columns={'XLs_satif':temp_name}, inplace=True)
                XLs_satif_fields.append(temp_name)
        else:
            XLs_satif = self.get_XLs_satisfaction(S_dist, atomic_XLs)
            S_tot_scores = S_tot_scores.assign(XLs_satif=pd.Series(XLs_satif))
            XLs_satif_fields.append('XLs_satif')

        file_out_xls = 'plot_XLs_%s.pdf'%(traj_number)
        self.plot_XLs_satisfaction(S_tot_scores['MC_frame'].values, S_tot_scores[XLs_satif_fields], S_dist[sel_nuis], ts_max, file_out_xls)
        
        # Add percent of satisfied XLs to DF
        if self.XLs_restraint_nuisances:
            nuis_mean = []
            nuis_std = []
            nuis_fields = sorted([n for n in S_dist.columns.values if 'Psi' in n])
            for nuis in sorted(nuis_fields):
                # Create df instead of dict
                nuis_mean.append(np.mean(S_dist[nuis].loc[ts_max:]))
                nuis_std.append(np.std(S_dist[nuis].loc[ts_max:]))
            self.XLs_nuis[traj_number] = list(nuis_mean) + list(nuis_std)

        return S_tot_scores, S_dist

    def get_XLs_satisfaction(self, S_dist, atomic_XLs, type_XLs = None, type_psi = None):
        
        if type_XLs and not type_psi:
            dist_columns = [x for x in S_dist.columns.values if ('Distance_' in x and type_XLs in x)]
            cutoff = self.XLs_cutoffs[type_XLs]
        elif type_psi and not type_XLs:
            dist_columns = [x for x in S_dist.columns.values if ('Distance_' in x and type_psi in x)]
            cutoff = list(self.XLs_cutoffs.values())[0]
        elif type_XLs and type_psi:
            dist_columns = [x for x in S_dist.columns.values if ('Distance_' in x and type_XLs in x and type_psi in x)]
            cutoff = self.XLs_cutoffs[type_XLs]
        elif atomic_XLs:
            dist_columns = [x for x in S_dist.columns.values if ('BestDist' in x)]
            cutoff = list(self.XLs_cutoffs.values())[0]
        else:
            dist_columns = [x for x in S_dist.columns.values if 'Distance_' in x]
            cutoff = list(self.XLs_cutoffs.values())[0]

        # Only distance columns
        XLs_dists = S_dist[dist_columns]

        # Check for ambiguity
        if self.ambiguous_XLs_restraint == True:
            min_XLs = pd.DataFrame()
            if self.Multiple_XLs_restraints:
                for k, v in self.ambiguous_XLs_dict[type_XLs].items():
                    min_XLs[k] = XLs_dists[v].min(axis=1)
            else:
                 for k, v in self.ambiguous_XLs_dict.items():
                     min_XLs[k] = XLs_dists[v].min(axis=1)   
            perc_per_step = list(min_XLs.apply(lambda x: sum(x<=cutoff)/len(x), axis=1))
            
        else:
            perc_per_step = list( XLs_dists.apply(lambda x: sum(x<=cutoff)/len(x), axis=1))

        return perc_per_step

    def summarize_XLs_info(self):
        unique_clusters = np.sort(list(set(self.S_comb_dist['cluster'])))
        print('unique_clusters', unique_clusters)
        if self.Multiple_XLs_restraints:
            for type_XLs in self.XLs_cutoffs.keys():
                cutoff = self.XLs_cutoffs[type_XLs]
                for cl in unique_clusters[1:]:
                    # Boxplot XLs distances
                    self.boxplot_XLs_distances(cluster = cl, type_XLs = type_XLs, cutoff = cutoff, file_out = 'plot_XLs_distances_cl'+str(cl)+'_'+type_XLs+'.pdf')
                    # XLs satisfaction data
                    self.get_XLs_details(cluster = cl, type_XLs = type_XLs)
        else:
            cutoff = self.XLs_cutoffs.values()[0]
            for cl in unique_clusters[1:]:
                # Boxplot XLs distances
                self.boxplot_XLs_distances(cluster = cl, cutoff = cutoff, file_out = 'plot_XLs_distances_cl'+str(cl)+'.pdf')
                # XLs satisfaction data
                self.get_XLs_details(cluster = cl)
                
        # XLs satisfaction data for all models
        self.get_XLs_details(cluster = 'All')
    
    def get_XLs_details(self, cluster=0, type_XLs = None):
        '''
        For GSM, determine for each XLs how often it is satisfied.
        '''

        if type_XLs:
            dist_columns = [v for v in self.S_comb_dist.columns.values if 'Distance' in v and type_XLs in v]
            cutoff = [v for k,v in self.XLs_cutoffs.items() if type_XLs in k][0]
        else:
            dist_columns = [v for v in self.S_comb_dist.columns.values if 'Distance' in v]
            cutoff = list(self.XLs_cutoffs.values())[0]

        if cluster != 'All':
            dXLs_cluster = self.S_comb_dist.loc[self.S_comb_dist['cluster'] == cluster, dist_columns]
        else:
            dXLs_cluster = self.S_comb_dist.loc[:, dist_columns]
            
        stats_XLs = pd.DataFrame()
        stats_XLs['mean'] = dXLs_cluster.mean()
        stats_XLs['std'] = dXLs_cluster.std()
        stats_XLs['min'] = dXLs_cluster.min()
        stats_XLs['max'] = dXLs_cluster.max()
        stats_XLs['perc_satif'] = dXLs_cluster.apply(lambda x: float(len(x[x<cutoff]))/float(len(x)), axis = 0)

        if type_XLs:
            stats_XLs.to_csv(self.analysis_dir+'XLs_satisfaction_'+type_XLs+'_cluster_'+str(cluster)+'.csv')
            dXLs_cluster.to_csv(self.analysis_dir+'XLs_distances_'+type_XLs+'_cluster_'+str(cluster)+'.csv')
        else:
            stats_XLs.to_csv(self.analysis_dir+'XLs_satisfaction_cluster_'+str(cluster)+'.csv')
            dXLs_cluster.to_csv(self.analysis_dir+'XLs_distances_cluster_'+str(cluster)+'.csv')
         
    def plot_XLs_satisfaction(self, t, perc_per_step, nuis_vals, ts_max, file_out):
        
        c = ['gold', 'orange', 'red', 'blue', 'green']
        n_bins = 20
        
        fig, ax = pl.subplots(figsize=(10.0, 4.0), nrows=1, ncols=3)
        axes = ax.flatten()
        for i, c in enumerate(perc_per_step.columns.values):
            label = c
            axes[0].plot(t[::10], perc_per_step[c].loc[::10], label=label)
        axes[0].set_title('XLs restraint satisfaction', fontsize=14)
        axes[0].set_xlabel('Step',fontsize=12)
        axes[0].set_ylabel('Percent Satisfied',fontsize=12)
        handles, labels = ax[0].get_legend_handles_labels()
        ax[0].legend(handles[::-1], labels[::-1])

        for i, c in enumerate(nuis_vals.columns.values):
            label = c.split('CrossLinkingMassSpectrometryRestraint_')[-1]
            axes[1].plot(t[::100], nuis_vals[c].loc[::100], label=label)
        axes[1].set_title('Psi nuisance parameters', fontsize=14)
        axes[1].set_xlabel('Step',fontsize=12)
        axes[1].set_ylabel('Psi',fontsize=12)
        handles, labels = ax[1].get_legend_handles_labels()
        ax[1].legend(handles[::-1], labels[::-1])

        for i,c in enumerate(nuis_vals.columns.values):
            label = c.split('CrossLinkingMassSpectrometryRestraint_')[-1]
            axes[2].hist(nuis_vals[c].loc[ts_max:],n_bins, histtype='step',fill=False, label=label)
            
        axes[2].set_title('Psi nuisance parameters', fontsize=14)
        axes[2].set_xlabel('Psi',fontsize=12)
        axes[2].set_ylabel('Density',fontsize=12)
        handles, labels = ax[1].get_legend_handles_labels()
        ax[2].legend(handles[::-1], labels[::-1])
        
        pl.tight_layout(pad=1.0, w_pad=1.0, h_pad=1.5)
        fig.savefig(self.analysis_dir+file_out)

    def boxplot_XLs_distances(self, cluster = 0, type_XLs = None, cutoff = 30.0, file_out = 'plot_XLs_distance_distributions.pdf'):

        if type_XLs:
            dist_columns = [x for x in self.S_comb_dist.columns.values if ('Distance_' in x) and (type_XLs in x)]
        else:
            dist_columns = [x for x in self.S_comb_dist.columns.values if 'Distance_' in x]
        dXLs_cluster = self.S_comb_dist.loc[self.S_comb_dist['cluster'] == cluster, dist_columns]
    
        dXLs_unique = pd.DataFrame()
        if self.ambiguous_XLs_restraint == True:
            if type_XLs:
                for k, v in self.ambiguous_XLs_dict[type_XLs].items():
                    XLs_sele = dXLs_cluster.loc[:,v].mean()
                    XLs_min = XLs_sele.idxmin()
                    dXLs_unique[XLs_min] =  dXLs_cluster[XLs_min]
            else:
                for k, v in self.ambiguous_XLs_dict.items():
                    XLs_sele = dXLs_cluster.loc[:,v].mean()
                    XLs_min = XLs_sele.idxmin()
                    dXLs_unique[XLs_min] =  dXLs_cluster[XLs_min]
        else:
            dXLs_unique = dXLs_cluster    
    
        # Get distances and order based on the mean
        columns = ['entry', 'mean', 'id']
        XLs_ids = pd.DataFrame(columns = columns)
        for i, v in enumerate(dXLs_unique.columns.values):
            m = np.mean(dXLs_unique[v])
            ll = v.split('_|')[1]
            label = '|'.join(ll.split('|')[2:6])
            XLs_ids = XLs_ids.append(pd.Series([int(i),m,label], index=columns), ignore_index=True)
        XLs_ids = XLs_ids.sort_values(by=['mean'])
        labels_ordered = XLs_ids['id'].values

        # For plot layout
        S_sorted = np.array(dXLs_unique)[:, XLs_ids['entry'].values.astype('int')]
        n_xls = len(labels_ordered)
        n_plots = int(math.ceil(n_xls/50.0))
        n_frac = int(math.ceil(n_xls/float(n_plots)))

        # Generate plot
        fig, ax = pl.subplots(figsize=(12, 6.0*n_plots), nrows=n_plots, ncols=1)
        if n_plots == 1: ax = [ax] 
        for i in range(n_plots):
            if i == n_plots-1:
                bb1 = ax[i].boxplot(S_sorted[:,(i*n_frac):-1],patch_artist=True, showfliers=False)
                ax[i].set_xticklabels(labels_ordered[(i*n_frac):-1],rotation='vertical',fontsize=10)
                max_y = np.max(S_sorted[:, -1]) + 25
                ax[i].set_ylim([0, (max_y - (max_y % 25))])
            else:
                bb1 = ax[i].boxplot(S_sorted[:,(i*n_frac):((i+1)*n_frac)],patch_artist=True, showfliers=False)
                ax[i].set_xticklabels(labels_ordered[(i*n_frac):((i+1)*n_frac)],rotation='vertical',fontsize=10)
                ax[i].set_ylim([0,np.max(S_sorted[:,(i+1)*n_frac])+20.0])
            ax[i].axhline(y=cutoff, color='forestgreen', linestyle='-', linewidth=1.5)
            ax[i].set_xticks(range(1,n_frac+1))
            
            ax[i].set_ylabel('XLs distances (A)')
            ax[i].set_title('XLs distance distributions')

        pl.tight_layout()
        fig.savefig(self.analysis_dir+file_out)
                    
    def plot_pEMAP_distances(self, pEMAP_satif, file_out):
        n_bins = 20
        fig, ax = pl.subplots(figsize=(4.0, 4.0), nrows=1, ncols=1)
    
        ax.plot(pEMAP_satif[::10,0], pEMAP_satif[::10,1], color='orangered',alpha=0.8)
        ax.set_title('pE-MAP restraint', fontsize=14)
        ax.set_xlabel('Step',fontsize=12)
        ax.set_ylabel('Percent satisfied',fontsize=12)
        
        pl.tight_layout(pad=1.2, w_pad=1.5, h_pad=2.5)
        fig.savefig(self.analysis_dir+file_out)

    def plot_Occams_satisfaction(self, Occams_satif, file_out):
        n_bins = 20
        fig, ax = pl.subplots(figsize=(4.0, 4.0), nrows=1, ncols=1)
        
        
        ax.plot(Occams_satif[::10,0], Occams_satif[::10,1], color='orangered',alpha=0.8)
        ax.set_title('Occams restraint', fontsize=14)
        ax.set_xlabel('Step',fontsize=12)
        ax.set_ylabel('Percent satisfied',fontsize=12)
        
        pl.tight_layout(pad=1.2, w_pad=1.5, h_pad=2.5)
        fig.savefig(self.analysis_dir+file_out)
        
    def substrings(self, s):
        for i in range(len(s)):
            for j in range(i, len(s)):
                yield s[i:j+1]
        
    def get_str_match(self, strs):
        if len(strs) > 1:
            intersect = set(self.substrings(strs[0])) & set(self.substrings(strs[1]))
            return max(intersect, key = len)
        else:
            return strs[0]


        
