import pandas as pd
import networkx as nx
import copy
import time
from gurobipy import *
import random

def constructGraphs(nodes,lineList,optionList,forbiddenList,price):
    G = nx.Graph()
    confG = nx.Graph()
    revenueFunction = {}
    for u in nodes['Node']:
        G.add_node(u)
        [val_u] = nodes.loc[nodes['Node']==u,'Value1']
        for q in optionList:
            confG.add_node((u,q))
            confG.nodes[(u,q)]['Revenue'] = 0.0
            revenueFunction[u,q] = 0.0
            if val_u >= price[q]:
                confG.nodes[(u,q)]['Revenue'] = price[q]
                revenueFunction[u,q] = price[q]
    
        for q in optionList:
            for r in optionList:
                if q < r:
                    confG.add_edge((u,q),(u,r))
    
    for (u,v) in lineList:
        G.add_edge(u,v)
        for (q,r) in forbiddenList:
            confG.add_edge((u,q),(v,r))
            confG.add_edge((u,r),(v,q))
            
    return G, confG, revenueFunction


def LS(bestRevenue,is_sol,indNbr,redConfG,revenueFunction,timeTheory):
    improve = False
    for (u,q) in redConfG.nodes():
        if is_sol[u,q] == 0 and len(indNbr[u,q]) == 0:
            improve = True
            print('### addition',u,q)
            is_sol[u,q] = 1
            bestRevenue += revenueFunction[u,q]
            print(u,q,bestRevenue)
            for (v,r) in redConfG.neighbors((u,q)):
                indNbr[v,r] += [(u,q)]
    
        if is_sol[u,q] == 1:
            theNeighbors = []
            for (v,r) in redConfG.neighbors((u,q)):
                if len(indNbr[v,r]) == 1:
                    theNeighbors += [(v,r)]
            subConfG = redConfG.subgraph(theNeighbors)
            model = MILP(subConfG,revenueFunction)
            timeTheory += model.Runtime
            if model.objVal > revenueFunction[u,q]:
                improve = True
                print('### deletion',u,q)
                bestRevenue = bestRevenue - revenueFunction[u,q] + model.objVal 
                print(bestRevenue)
                sub_is_sol = updateSolution(model,is_sol)
                is_sol = copy.deepcopy(sub_is_sol)
                is_sol[u,q] = 0
                for (v,r) in redConfG.neighbors((u,q)):
                    indNbr[v,r].remove((u,q))
                    if is_sol[v,r] == 1:
                        for (w,t) in redConfG.neighbors((v,r)):
                            indNbr[w,t] += [(v,r)]
                            if is_sol[w,t] == 1:
                                print('error')
    return bestRevenue,is_sol,indNbr, improve, timeTheory


def MILP(subConfG,revenueFunction):
    model = Model('MIS')
    model.setParam('OutputFlag', 0)
    
    x_vars = []
    x_names = []
    for (u,q) in subConfG.nodes():
        x_vars += [(u,q)]
        x_names += ['X[%s,%s]'%(u,q)]
    X = model.addVars(x_vars, vtype = GRB.BINARY, name = x_names)
    
    for ((u,q),(v,r)) in subConfG.edges():
        LHS = [(1,X[u,q]),(1,X[v,r])]
        model.addConstr(LinExpr(LHS)<=1, name='Eq.Conflict(%s,%s,%s,%s)'%(u,q,v,r))
        
    objTerms = []
    for (u,q) in subConfG.nodes():
        objTerms += [(revenueFunction[u,q],X[u,q])]
       
    model.setObjective(LinExpr(objTerms), GRB.MAXIMIZE)
    
    # update and solve the model
    model.update()
    model.optimize()

    return model


def singleOption(nodes):
    bestPrice = -1
    bestRevenue = 0
    avgRevenue = 0
    bestOption = -1
    for i in range(1,6+1):
        singlePrice = i * 100
        singleRevenue = 0
        for u in nodes['Node']:
            [value_u] = nodes.loc[nodes['Node']==u,'Value1']
            if value_u >= singlePrice:
                singleRevenue += singlePrice
                    
        avgRevenue += singleRevenue
        # print(i*100, singleRevenue)
        if bestRevenue < singleRevenue:
            bestRevenue = singleRevenue
            bestPrice = singlePrice
            bestOption = i
            
    avgRevenue = avgRevenue / 6
        
    return bestPrice, bestRevenue, avgRevenue, bestOption  


def updateSolution(model,sub_is_sol):
    for v in model.getVars():
        if v.varname[0] == 'X':
            varName = v.varname.split(',')
            u = int(varName[0][2:])
            q = int(varName[-1][:-1])
            if v.x > 1 - 0.0001:
                sub_is_sol[u,q] = 1
            if v.x < 0 + 0.0001:
                sub_is_sol[u,q] = 0
    return sub_is_sol



# main code starts here
## parameter setting
product = 1
networkID = 0
rep = 0

## read input data
options = pd.read_csv('../1product_new/options_1product_new.csv')
optionList = []
price = {}
for q in options['Option']:
    optionList += [q]
    [price_q] = options.loc[options['Option']==q,'Price']
    price[q] = float(price_q)
forbidden = pd.read_csv('../1product_new/forbidden_1product_new.csv')
forbiddenList = []
for pair in forbidden['Pair']:
    [source_pair] = forbidden.loc[forbidden['Pair']==pair,'Source']
    [target_pair] = forbidden.loc[forbidden['Pair']==pair,'Target']
    forbiddenList += [(source_pair,target_pair)]
lines = pd.read_csv('../lines/lines_%s.csv'%(networkID))
lineList = []
for l in lines['Line']:
    [source_l] = lines.loc[lines['Line']==l,'Source']
    [target_l] = lines.loc[lines['Line']==l,'Target']
    lineList += [(source_l,target_l)]    
nodes = pd.read_csv('../1product_new/nodes_%s_%s.csv'%(networkID,rep))

## initial solution: the best single option
bestPrice, bestRevenue, avgRevenue, bestOption = singleOption(nodes)
print('initial revenue =',bestRevenue)

## construct graphs
G, confG, revenueFunction = constructGraphs(nodes,lineList,optionList,forbiddenList,price)    
redConfG = copy.deepcopy(confG)
for (u,q) in confG.nodes():
    if confG.nodes[(u,q)]['Revenue'] == 0.0:
        redConfG.remove_node((u,q))

## indicators of the initial solution of the best single option
is_sol = {}
for (u,q) in redConfG.nodes():
    is_sol[u,q] = 0
    if q == bestOption:
        is_sol[u,q] = 1
indNbr = {}
for (u,q) in redConfG.nodes():
    indNbr[u,q] = []
    for (v,r) in redConfG.neighbors((u,q)):
        if is_sol[v,r] == 1:
            indNbr[u,q] += [(v,r)]

## local search
improve = True
tic = time.time()
timeTheory = 0.0
while improve == True:
    bestRevenue,is_sol,indNbr,improve, timeTheory = LS(bestRevenue,is_sol,indNbr,redConfG,revenueFunction,timeTheory)
    print('### improve =',improve)
toc = time.time()
elapse = toc - tic    
    
finalRevenue = 0
theSolution = []
for (u,q) in redConfG.nodes():
    if is_sol[u,q] == 1:
        finalRevenue += revenueFunction[u,q]
        theSolution += [(u,q)]
        
print('finalRevenue =',finalRevenue)
print('infeasibility =',len(redConfG.subgraph(theSolution).edges()))   
print('elapse =',elapse)
print('timeTheory =',timeTheory)         
                
                     
            
        
        
        
        
        
        
            
            