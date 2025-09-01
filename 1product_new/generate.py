import pandas as pd
import random

totalWeight = 1 + (1 - 1/2) + (1/2 - 1/3) + (1/3 - 1/4) + (1/4 - 1/5) + (1/5 - 1/6) + 1/6
threshold = {}
threshold[0] = 0
threshold[1] = 1/totalWeight
threshold[2] = (1 + (1 - 1/2))/totalWeight
threshold[3] = (1 + (1 - 1/2) + (1/2 - 1/3))/totalWeight
threshold[4] = (1 + (1 - 1/2) + (1/2 - 1/3) + (1/3 - 1/4))/totalWeight
threshold[5] = (1 + (1 - 1/2) + (1/2 - 1/3) + (1/3 - 1/4) + (1/4 - 1/5))/totalWeight
threshold[6] = (1 + (1 - 1/2) + (1/2 - 1/3) + (1/3 - 1/4) + (1/4 - 1/5) + (1/5 - 1/6))/totalWeight
threshold[7] = (1 + (1 - 1/2) + (1/2 - 1/3) + (1/3 - 1/4) + (1/4 - 1/5) + (1/5 - 1/6) + 1/6)/totalWeight

networkID = 0
product = 1

for (networkID,repNum) in [(1,10),(2,50),(3,50),(4,50),(5,50),(6,10),(7,10),(8,50)]:
    for rep in range(repNum):
        nodes = pd.read_csv('../../InequityAversionPricing/nodes/nodes_%s_%s.csv'%(networkID,rep))
        
        valArray = []
        for u in nodes['Node']:
            rand_u = random.random()
            val_u = 0
            for i in range(1,7+1):
                if rand_u > threshold[i]:
                    print(i,threshold[i])
                    val_u += 100
                else:
                    print(i,threshold[i])
                    val_u += 100 * (rand_u - threshold[i-1]) / (threshold[i] - threshold[i-1])
                    break
            print(u,rand_u,val_u)
            valArray += [val_u]
            
        nodes['Value1'] = valArray
        
        nodes.to_csv(r'nodes_%s_%s.csv'%(networkID,rep), index = False)#Check
        
        
        
        
        
        
        
        
        
        
        
        
        
            
            