import os
import pandas as pd
import networkx as nx
import copy
import time
import itertools
import openpyxl
from gurobipy import GRB, quicksum, Model, LinExpr
import random
from dimod import BinaryQuadraticModel
from dwave.samplers import SimulatedAnnealingSampler
import datetime

def constructGraphs(nodes, lineList, optionList, forbiddenList, price):
    # We only care about nodes that generate revenue.
    # By filtering here, we skip millions of unnecessary edges.
    node_values = dict(zip(nodes['Node'], nodes['Value1']))
    revenueFunction = {}
    confG = nx.Graph()

    # 1. Add Nodes and Internal Conflicts simultaneously
    for u, val_u in node_values.items():
        # Only track options this user can actually afford
        affordable_options = []
        for q in optionList:
            rev = price[q] if val_u >= price[q] else 0.0
            if rev > 0:
                revenueFunction[u, q] = rev
                confG.add_node((u, q), Revenue=rev)
                affordable_options.append((u, q))
        
        # Internal conflicts: A user can only pick one affordable option
        if len(affordable_options) > 1:
            confG.add_edges_from(itertools.combinations(affordable_options, 2))

    # 2. Add Network Conflicts (Line Conflicts)
    # Instead of building a massive list of tuples, add them in smaller chunks
    # or directly if memory is extremely tight.
    for u, v in lineList:
        for q, r in forbiddenList:
            # Only add the edge if BOTH nodes are in our revenue-generating graph
            if (u, q) in confG and (v, r) in confG:
                confG.add_edge((u, q), (v, r))
            if (u, r) in confG and (v, q) in confG:
                confG.add_edge((u, r), (v, q))
            
    return confG, revenueFunction

def LS(bestRevenue, is_sol, indNbr, redConfG, revenueFunction, timeTheory, subproblems):
    improve = False
    
    # PHASE 1: Greedy Additions (The "Free Money" Phase)
    for (u, q) in redConfG.nodes():
        if is_sol[u, q] == 0 and len(indNbr[u, q]) == 0:
            improve = True
            is_sol[u, q] = 1
            bestRevenue += revenueFunction[u, q]
            
            # Update blockers for neighbors
            for (v, r) in redConfG.neighbors((u, q)):
                indNbr[v, r].append((u, q))
    
    # PHASE 2: 1-for-N Swaps (The "Trading Up" Phase)
    # We iterate over a list of keys to avoid "dictionary changed size during iteration" errors
    current_nodes = [node for node, active in is_sol.items() if active == 1]
    
    for (u, q) in current_nodes:
        # 1. Identify neighbors blocked ONLY by this node
        theNeighbors = [nbr for nbr in redConfG.neighbors((u, q)) if len(indNbr[nbr]) == 1]
        
        if not theNeighbors:
            continue
            
        # 2. Solve the mini-optimization
        subConfG = redConfG.subgraph(theNeighbors)
        # num_v = subConfG.number_of_nodes()
        # num_e = subConfG.number_of_edges()
        # print(f"--> Solving Subgraph for {u,q}: Nodes={num_v}, Edges={num_e}")
        model = MILP(subConfG, revenueFunction)
        timeTheory += model.Runtime
        subproblems += 1
        # print('model runtime: ',model.Runtime)
        
        # 3. If the new group is better, perform the swap
        if model.objVal > revenueFunction[u, q]:
            improve = True
            
            # --- REMOVE OLD ---
            is_sol[u, q] = 0
            bestRevenue -= revenueFunction[u, q]
            # Remove (u,q) from all its neighbors' blocker lists
            for (v, r) in redConfG.neighbors((u, q)):
                indNbr[v, r].remove((u, q))
            
            # --- ADD NEW ---
            # updateSolution now modifies is_sol IN-PLACE (no deepcopy!)
            newly_added = []
            for v in model.getVars():
                if v.varname.startswith('X') and v.x > 0.99:
                    # Parsing node/option from Gurobi variable name
                    varName = v.varname.split(',')
                    node_id = int(varName[0][2:])
                    opt_id = int(varName[-1][:-1])
                    
                    is_sol[node_id, opt_id] = 1
                    bestRevenue += revenueFunction[node_id, opt_id]
                    newly_added.append((node_id, opt_id))
            
            # Update blockers for the newly added group
            for (new_u, new_q) in newly_added:
                for (v, r) in redConfG.neighbors((new_u, new_q)):
                    indNbr[v, r].append((new_u, new_q))

            # print(bestRevenue)
                    
    return bestRevenue, is_sol, indNbr, improve, timeTheory, subproblems


def QLS(bestRevenue, is_sol, indNbr, redConfG, revenueFunction, timeTheory, subproblems,sampler,numRuns):
    improve = False
    
    # PHASE 1: Greedy Additions (The "Free Money" Phase)
    for (u, q) in redConfG.nodes():
        if is_sol[u, q] == 0 and len(indNbr[u, q]) == 0:
            improve = True
            is_sol[u, q] = 1
            bestRevenue += revenueFunction[u, q]
            
            # Update blockers for neighbors
            for (v, r) in redConfG.neighbors((u, q)):
                indNbr[v, r].append((u, q))
    
    # PHASE 2: 1-for-N Swaps (The "Trading Up" Phase)
    # We iterate over a list of keys to avoid "dictionary changed size during iteration" errors
    current_nodes = [node for node, active in is_sol.items() if active == 1]
    
    for (u, q) in current_nodes:
        # 1. Identify neighbors blocked ONLY by this node
        theNeighbors = [nbr for nbr in redConfG.neighbors((u, q)) if len(indNbr[nbr]) == 1]
        
        if not theNeighbors:
            continue
            
        # 2. Solve the mini-optimization
        subConfG = redConfG.subgraph(theNeighbors)
        # num_v = subConfG.number_of_nodes()
        # num_e = subConfG.number_of_edges()
        # print(f"--> Solving Subgraph for {u,q}: Nodes={num_v}, Edges={num_e}")
        sampleset, runtime = qubo(subConfG,revenueFunction,sampler,numRuns)
        best_value = - sampleset.first.energy
        
        timeTheory += runtime
        subproblems += 1
        # print('model runtime: ',model.Runtime)
        
        # 3. If the new group is better, perform the swap
        if best_value > revenueFunction[u, q]:
            improve = True
            
            # --- REMOVE OLD ---
            is_sol[u, q] = 0
            bestRevenue -= revenueFunction[u, q]
            # Remove (u,q) from all its neighbors' blocker lists
            for (v, r) in redConfG.neighbors((u, q)):
                indNbr[v, r].remove((u, q))
            
            # --- ADD NEW ---
            # updateSolution now modifies is_sol IN-PLACE (no deepcopy!)
            newly_added = []
            for (u,p) in subConfG.nodes():
                xVal_u_p = sampleset.first.sample['X[%s,%s]' % (u, p)]
                if xVal_u_p > 1 - 0.0001:
                    newly_added += [(u,p)]
                    bestRevenue += revenueFunction[u,p]
                    is_sol[u,p] = 1
            
            # Update blockers for the newly added group
            for (new_u, new_q) in newly_added:
                for (v, r) in redConfG.neighbors((new_u, new_q)):
                    indNbr[v, r].append((new_u, new_q))

            # print(bestRevenue)
                    
    return bestRevenue, is_sol, indNbr, improve, timeTheory, subproblems


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



def qubo(subConfG,revenueFunction,sampler,numRuns):
    # Create arrays for problem variables        
    Q1 = {}
    Q2 = {}
         
    bigM = 1
    for (u,p) in subConfG.nodes():
        price_p = revenueFunction[u,p]
        Q1['X[%s,%s]'%(u,p)] = - float(price_p)
        bigM += float(price_p)
        
    for ((u,p),(v,q)) in subConfG.edges():
        Q2['X[%s,%s]'%(u,p),'X[%s,%s]'%(v,q)] = bigM
        
    bqm = BinaryQuadraticModel(Q1, Q2, 0.0,'BINARY')
    ticqubo = time.time()
    sampleset = sampler.sample(bqm, num_reads=numRuns, chain_strength = bigM)
    tocqubo = time.time()
    
    return sampleset, tocqubo - ticqubo


def singleOption(nodes):

    bestPrice = -1
    bestRevenue = 0
    bestOption = -1
    
    # We can pre-calculate the revenue for all options at once
    prices = [i * 100 for i in range(1, 7)]
    revenues = []

    for i, singlePrice in enumerate(prices, 1):
        # Vectorized check: (Series >= scalar) returns a boolean mask
        # .sum() counts how many are True. Then multiply by the price.
        singleRevenue = (nodes['Value1'] >= singlePrice).sum() * singlePrice
        revenues.append(singleRevenue)
        
        if singleRevenue > bestRevenue:
            bestRevenue = singleRevenue
            bestPrice = singlePrice
            bestOption = i
            
    avgRevenue = sum(revenues) / len(revenues)
        
    return bestPrice, bestRevenue, avgRevenue, bestOption 


def solveGlobalOptimal(confG, revenueFunction, seconds_limit=300):
    model = Model('Global_Optimal_MIS')
    
    # --- Performance Parameters ---
    model.setParam('OutputFlag', 1)
    model.setParam('TimeLimit', seconds_limit) # Stop after X seconds
    model.setParam('MIPGap', 0.0001)           # Stop if within 0.01% of optimal
    
    nodes_options = list(confG.nodes())
    X = model.addVars(nodes_options, vtype=GRB.BINARY, name="X")
    
    for (node1, node2) in confG.edges():
        if node1 in X and node2 in X:
            model.addConstr(X[node1] + X[node2] <= 1)
            
    obj = quicksum(revenueFunction[u, q] * X[u, q] for (u, q) in nodes_options)
    model.setObjective(obj, GRB.MAXIMIZE)
    
    model.optimize()
    
    # Capture results even if Time Limit was hit
    current_best_sol = 0
    if model.SolCount > 0:
        current_best_sol = model.objVal
        
    # BestBound represents the best possible value mathematically achievable
    return current_best_sol, model.ObjBound, model.Runtime


# main code starts here
## parameter setting
product = 1
networkID = 0
rep = 0

# 1. Options: Convert directly to a dictionary and list
options = pd.read_csv('../1product_new/options_1product_new.csv')
optionList = options['Option'].tolist()
price = dict(zip(options['Option'], options['Price'].astype(float)))

# 2. Forbidden Pairs: Zip columns directly into a list of tuples
forbidden = pd.read_csv('../1product_new/forbidden_1product_new.csv')
forbiddenList = list(zip(forbidden['Source'], forbidden['Target']))

# 3. Lines: Zip columns directly into a list of tuples
lines = pd.read_csv('../yt_20260224/yt/yt_lines.csv')
lineList = list(zip(lines['Source'], lines['Target']))

# 4. Nodes: Load as normal
nodes = pd.read_csv('../yt_20260224/yt/yt_nodes_value1.csv')

## initial solution: the best single option
bestPrice, bestRevenue, avgRevenue, bestOption = singleOption(nodes)
print('initial revenue =',bestRevenue)

## construct graphs (Directly building the reduced version)
confG, revenueFunction = constructGraphs(nodes, lineList, optionList, forbiddenList, price)
print(f'Graph created with {confG.number_of_nodes()} active nodes')


numInstances = 10
for rep in range(numInstances):
    print('### rep =',rep)
    print(datetime.datetime.now())
    # NO DEEPCOPY NEEDED. Use confG directly.
    # redConfG = confG 

    nodes = pd.read_csv('../yt_20260224/yt/yt_nodes_value1_%s.csv'%(rep))
    
    ## initial solution: the best single option
    bestPrice, bestRevenue, avgRevenue, bestOption = singleOption(nodes)
    print('initial revenue =',bestRevenue)
    
    ## construct graphs (Directly building the reduced version)
    redConfG, revenueFunction = constructGraphs(nodes, lineList, optionList, forbiddenList, price)
    print(f'Graph created with {confG.number_of_nodes()} active nodes')
    
    ## 2. Fast is_sol initialization (Dictionary Comprehension)
    # We initialize everyone to 0, and only the bestOption to 1
    is_sol = {node: (1 if node[1] == bestOption else 0) for node in redConfG.nodes()}
    
    # Recalculate based on only the nodes that survived pruning
    bestRevenue = sum(revenueFunction[node] for node, active in is_sol.items() if active == 1)
    
    ## 3. Fast indNbr initialization
    # Initialize empty lists for everyone
    indNbr = {node: [] for node in redConfG.nodes()}
    
    # Forward Update: Only loop over nodes that are IN the solution
    active_nodes = [node for node, status in is_sol.items() if status == 1]
    
    for active_node in active_nodes:
        # Tell all neighbors of this active node that they are now blocked
        for neighbor in redConfG.neighbors(active_node):
            indNbr[neighbor].append(active_node)
    
    print('Indicators initialized successfully.')
    
    ## local search
    improve = True
    tic = time.time()
    timeTheory = 0.0
    subproblems = 0
    print('starting search')
    while improve == True:
        numRuns = 8
        bestRevenue,is_sol,indNbr,improve, timeTheory, subproblems = QLS(bestRevenue,is_sol,indNbr,redConfG,revenueFunction,timeTheory, subproblems, SimulatedAnnealingSampler(),numRuns)
        print('### improve =',improve)
        print('### bestRevenue =',bestRevenue)
        print(datetime.datetime.now())
    toc = time.time()
    elapse = toc - tic    
        
    finalRevenue = 0
    theSolution = []
    for (u,q) in redConfG.nodes():
        if is_sol[u,q] == 1:
            finalRevenue += revenueFunction[u,q]
            theSolution += [(u,q)]
            
    # Run the global solver
    # optRevenue, bestBound, optTime = solveGlobalOptimal(redConfG, revenueFunction, seconds_limit=600)
    
    # Constraint Density: Actual Edges / Possible Edges
    # Possible Edges = (N * (N-1)) / 2
    num_nodes_conf = redConfG.number_of_nodes()
    num_edges_conf = redConfG.number_of_edges()
    density = (2 * num_edges_conf) / (num_nodes_conf * (num_nodes_conf - 1)) if num_nodes_conf > 1 else 0
            
    print('finalRevenue =',finalRevenue)
    print('infeasibility =',len(redConfG.subgraph(theSolution).edges()))   
    print('elapse =',elapse)
    print('timeTheory =',timeTheory)         
    
    
    # 1. Organize your data into a single-row dictionary
    output_row = {
        'Network_ID': [networkID],
        'Rep_ID': [rep],
        'Users': [len(nodes)],
        'Conflict_Nodes': [num_nodes_conf],
        'Conflict_Edges': [num_edges_conf],
        'Conflict_Density': [round(density, 5)],
        # 'Opt_Revenue': [optRevenue],
        # 'Opt_Time': [optTime],
        'LS_Revenue': [finalRevenue],
        'LS_Time': [elapse],
        'LS_Subproblems': [subproblems],
        # 'Best_Theoretical_Bound': [bestBound],
        'Theoretical_Time_Sec': [timeTheory],
        'Infeasibility_Count': [len(redConfG.subgraph(theSolution).edges())],
        'Timestamp': [time.strftime("%Y-%m-%d %H:%M:%S")]
    }
    
    df_new_row = pd.DataFrame(output_row)
    output_file = 'Recursive_yt_Pandas_Log_QUBO_numRuns%s_rep%s.xlsx'%(numRuns,rep)
    
    df_new_row.to_excel(output_file, index=False)
    
    print(f"--> Results appended to {output_file}")

             
    






    
    