import pandas as pd
import random
from gurobipy import *
import networkx as nx  
import copy


networkID = 0
product = 1

options = pd.read_csv('../1product_new/options_1product_new.csv')
forbidden = pd.read_csv('../1product_new/forbidden_1product_new.csv')

optionList = []
price = {}
for opt in options['Option']:
    optionList += [int(opt)]
    [price_opt] = options.loc[options['Option']==opt,'Price']
    price[int(opt)] = float(price_opt)
    
for (networkID,repNum) in [(1,10),(6,10),(7,10)]:#[(2,50),(3,50),(4,50),(5,50),(8,50)]:
    
    lines = pd.read_csv('../lines/lines_%s.csv'%networkID)
    
    netArray = []
    repArray = []
    methodArray = []
    optArray = []
    timeArray = []
    bbArray = []
    infArray = []
    
    for rep in range(repNum):
        nodes = pd.read_csv('../1product_new/nodes_%s_%s.csv'%(networkID,rep))
        
        G = nx.Graph()
        for u in nodes['Node']:
            G.add_node(u)
        for l in lines['Line']:
            [source_l] = lines.loc[lines['Line']==l,'Source']
            [target_l] = lines.loc[lines['Line']==l,'Target']
            G.add_edge(int(source_l),int(target_l))
    
        confG = nx.Graph()
        for u in G.nodes():
            for q in optionList:
                confG.add_node((u,q))
            for q1 in optionList:
                for q2 in optionList:
                    if q1 < q2:
                        confG.add_edge((u,q1),(u,q2))
                        
        for (u,v) in G.edges():
            for pair in forbidden['Pair']:
                [source_pair] = forbidden.loc[forbidden['Pair'] == pair,'Source']
                [target_pair] = forbidden.loc[forbidden['Pair'] == pair,'Target']
                confG.add_edge((u,source_pair),(v,target_pair))
                confG.add_edge((u,target_pair),(v,source_pair))
            
        confG_nodes = copy.deepcopy(list(confG.nodes()))
        
        for (u,q) in confG_nodes:
            [val_u] = nodes.loc[nodes['Node']==u,'Value1']
            val_u = float(val_u)
            if val_u < price[q]:
                confG.remove_node((u,q))
    
        # ILP Model
        model = Model('Independent set model')
        
        ## Employ Variables
        x_vars = []
        x_names = []
        for (u,q) in confG.nodes():
            x_vars += [(u,q)]
            x_names += ['X[%s,%s]'%(u,q)]
        X = model.addVars(x_vars, vtype = GRB.BINARY, name = x_names)
        
        for ((u,q),(v,p)) in confG.edges():
            LHS = [(1,X[u,q]),(1,X[v,p])]
            model.addConstr(LinExpr(LHS)<=1, name='Eq.Conflict(%s,%s,%s,%s)'%(u,q,v,p))
            
        objTerms = []
        for (u,q) in confG.nodes():
            objTerms += [(price[q],X[u,q])]
       
        model.setObjective(LinExpr(objTerms), GRB.MAXIMIZE)
        
        # update and solve the model
        model.update()
        model.optimize()
     
        varNameArray = []
        varValueArray = []
        solution = []
        for v in model.getVars():
            varNameArray += [v.varname]
            varValueArray += [v.x]
            if v.varname[0] == 'X' and v.x > 1 - 0.0001:
                varName = v.varname.split(',')
                u = int(varName[0][2:])
                q = int(varName[-1][:-1])
                solution += [(u,q)]
                
        subG = confG.subgraph(solution)
    
        infeasibility = len(subG.edges())
        print('infeasibility=',infeasibility)
        print(len(subG.nodes()))
        print(subG.nodes())
        
        netArray += [networkID]
        repArray += [rep]
        methodArray += ['MILP']
        optArray += [model.objVal]
        timeArray += [model.Runtime]
        bbArray += [model.NodeCount]
        infArray += [infeasibility]
        
        milp = pd.DataFrame(list(zip(netArray,repArray,methodArray,optArray,timeArray,bbArray,infArray)),columns = ['Network','Rep','Method','Opt','Time','Count','Infeasibility'])
        milp.to_csv(r'milp_%s.csv'%(networkID), index = False)#Check
        
        
            
            