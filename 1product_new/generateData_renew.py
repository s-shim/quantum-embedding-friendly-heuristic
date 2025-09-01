#from gurobipy import *
import pandas as pd
#import networkx as nx
#import time
import random as rd
import math

repNumber = 10
prodNumber = 1
frequency = 25

for (networkID,repNum) in [(0,50),(1,10),(2,50),(3,50),(4,50),(5,50),(7,10),(8,50)]:#[1,6,7]:#[0,2,3,4,5,8,9]:#[0,1,2,3,4,5,6,7,8,9]:
    for rep in range(repNum):
        nodes = pd.read_csv('new/nodes_%s_%s.csv'%(networkID,rep))
        nodes = nodes.drop('Time',axis=1)
        nodes = nodes.drop('Elapse',axis=1)
        nodes = nodes.drop('Batch',axis=1)
        
        avg = []
        for u in nodes['Node']:
            [val_u] = nodes.loc[nodes['Node']==u,'Value1']
            avg += [val_u * rd.random()]
            
        nodes['avgValue'] = avg
                
        nodes = nodes.sort_values(by='avgValue', ascending=False)
        
        fColumn = []
        elapseTime = 0
        rtColumn = []
        etColumn = []
        partColumn = []
        for node in nodes['Node']:
            fColumn += [frequency]
            rdProb = rd.uniform(0,1)
            rdTime = - math.log(rdProb) / frequency
            elapseTime += rdTime
            rtColumn += [rdTime]
            etColumn += [elapseTime]
            partColumn += [int(elapseTime)]
            
        nodes['Lambda'] = fColumn
        nodes['Time'] = rtColumn
        nodes['Elapse'] = etColumn
        nodes['Batch'] = partColumn
    
        nodes.to_csv(r'nodes_%s_%s.csv'%(networkID,rep), index = False)#Check
    
        
    

















