import pandas as pd
import random as rd
import math

numProducts = 3
retail = 700

for (networkID,numReps) in [(0,50),(1,10),(2,50),(3,50),(4,50),(5,50),(6,10),(7,10),(8,50),(9,50)]:
    
    for rep in range(numReps):
        
        nodes = pd.read_csv('base/nodes_%s_%s.csv'%(networkID,rep))
        nodes = nodes.drop('Value', axis=1)
        nodes0 = pd.read_csv('../../onlineQuantum_revised/onlineQuantum_revised/nodes_3products_time_new/nodes_%s_%s.csv'%(networkID,rep))
        
        timeArray = []
        logArray = []                     
        elapseArray = []
        partitionArray = []
        for u in nodes['Node']:
            [time_u] = nodes0.loc[nodes0['Node']==u,'Time']
            [elapse_u] = nodes0.loc[nodes0['Node']==u,'Elapse']
            [partition_u] = nodes0.loc[nodes0['Node']==u,'Partition']
            [log_u] = nodes0.loc[nodes0['Node']==u,'Lambda']

            timeArray += [time_u]
            logArray += [log_u]                     
            elapseArray += [elapse_u]
            partitionArray += [partition_u]

        nodes['Lambda'] = logArray
        nodes['Time'] = timeArray
        nodes['Elapse'] = elapseArray
        nodes['Batch'] = partitionArray            

        nodes = nodes.sort_values(by=['Elapse'])

        nodes.to_csv(r'nodes_%s_%s.csv'%(networkID,rep), index = False)#Check
        
        
        
        
        
        
        
        
