# %% Global parameters
#Our variables:
YoussefPathModel= '/home/youssef/EPFL/MA1/Machine learning/MLProject2/ML2/youssefserver.modeldict'
Youssefdatapath = '/home/youssef/EPFL/MA1/Machine learning/MLProject2/Data'
YoussefServerPathModel= '/home/saied/ML/ML2/youssefServer4.modeldict'
YoussefServerdatapath = '/data/mgeiger/gg2/data'
YoussefServerPicklingPath = '/home/saied/ML/ML2/'

#Global variables:
use_saved_model =1
save_trained_model=1
train_or_not =1
epochs =2
PicklingPath=YoussefServerPicklingPath
PathModel= YoussefServerPathModel
datapath = YoussefServerdatapath
proportion_traindata = 0.01 # the proportion of the full dataset used for training

# %% Import Dataset and create trainloader 
import datasetY as dataset
import torch
import importlib
from sampler import *
import itertools
import numpy as np
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
#importlib.reload(module)


full_dataset = dataset.GG2(datapath)

train_size = int(proportion_traindata * len(full_dataset))
test_size = len(full_dataset) - train_size



# To split the full_dataset

indices, sets = random_splitY(full_dataset, [train_size, test_size])
[trainset, testset]=sets
print(len(trainset))

# Dataloaders
batch_sizev=8 # 32>*>8
test_batch_size = 300

trainset_labels = full_dataset.get_labels()[indices[:train_size]] 
testset_labels= full_dataset.get_labels()[indices[train_size:]] 

samplerv= BalancedBatchSampler2(trainset)
samplertest = BalancedBatchSampler2(testset)

trainloader = torch.utils.data.DataLoader(trainset,sampler = samplerv , batch_size= batch_sizev, num_workers=2)
testloader = torch.utils.data.DataLoader(testset,sampler = samplertest , batch_size= test_batch_size, num_workers=2)

# %% Import Neural network

net = torch.hub.load('rwightman/gen-efficientnet-pytorch', 'efficientnet_b0',
 pretrained=True)

# Change First and Last Layer
net.conv_stem = torch.nn.Conv2d(4, 32, kernel_size=(3, 3), stride=(2, 2),
 padding=(1, 1), bias=False)
net.classifier = torch.nn.Linear(1280, 1)
net.to(device)

if not torch.cuda.is_available() : #ie if NOT on the server
    print(net)


# %% Train Neural network

import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F

momentumv=0.90
lrv=0.01


# To calculate accuracy
from sampler import accuracy

def train_accuracy(net):
    return accuracy(net, loader= trainloader,device="cpu")

def test_accuracy(net):
    return accuracy(net, loader= testloader,device="cpu")


#Option to use a saved model parameters
if use_saved_model:
    import os
    if os.path.isfile(PathModel):
        if os.stat(PathModel).st_size > 0:
            net.load_state_dict(torch.load(PathModel,map_location=torch.device(device   )))
            print("Loading model...")
        else: 
            print("Empty file...")

#Training starts

criterion = nn.SoftMarginLoss()
optimizer = optim.SGD(net.parameters(), lr=lrv, momentum=momentumv)

net.train()

if train_or_not:
    print("Starting training...")
    train_accuracy_list = np.array([])
    test_accuracy_list = []
    for epoch in range(epochs):  # loop over the dataset multiple times
        running_loss = 0.0
        for i, data in enumerate(trainloader, 0):
            # get the inputs; data is a list of [inputs, labels]
            inputs, labels = data[0].to(device), data[1].to(device)
            labels = torch.unsqueeze(labels, dim =1)
            labels = labels.float()
            
            # zero the parameter gradients
            optimizer.zero_grad()

            # forward + backward + optimize
            outputs = net(inputs)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            # print statistics
            running_loss += loss.item()
            if i % 2000 == 1999:    # print every 5 mini-batches
                print('[%5d, %5d] loss: %.6f ' %
                        (epoch+1, i + 1, running_loss/2000) )
                running_loss = 0.0
        
        # save predictions and labels for ROC curve calculation
        print("Saving predictions and calculating accuracies...")
        predictions = []
        labels = []
        for k, testset_partial in enumerate(testloader):
            if k <3:
                testset_partial_I , testset_partial_labels = testset_partial[0].to(device), testset_partial[1].to(device)
                predictions += [net(image[None]).item() for image in testset_partial_I ]
                labels += testset_partial_labels.tolist()
            else:
                break
        file_name= PicklingPath+"PredictionsAndLabelsTrial1Epoch"+str(i)
        if os.path.exists(file_name):  # checking if there is a file with this name
            os.remove(file_name)  # deleting the file
        import pickle
        with open(file_name, 'wb') as pickle_file:
            pickle.dump([predictions,labels],pickle_file)
            pickle_file.close()
        print("Pickling done...")

        # calculate and save accuracy and stop if test accuracy increases 
        net.eval()
        test_accuracyv = test_accuracy(net)
        print("Test accuracy: %5f"%test_accuracyv)
        if test_accuracyv< np.min(train_accuracy_list):
            break
        train_accuracy_list = np.concatenate((train_accuracy_list, np.array([test_accuracyv])))
        net.train()

    print('Finished Training')
    if save_trained_model:
        if os.path.exists(PathModel):  # checking if there is a file with this name
            os.remove(PathModel)  # deleting the file
        torch.save(net.state_dict(), PathModel)
        print("Saving model...")

if torch.cuda.is_available() : #ie if on the server
    net.eval()
    test_accuracyv = test_accuracy(net)
    print("Test accuracy: %5f"%test_accuracyv)
    train_accuracyv = train_accuracy(net)
    print("Train accuracy: %5f"%train_accuracyv)
    import sys
    sys.exit()

# %% Metrics

# Testing mode for net
net.eval()

test_accuracyv = test_accuracy(net)
print("Test accuracy: %5f"%test_accuracyv)
from sklearn import metrics

# ROC curve calculation
testset_partial= iter(testloader).next()
testset_partial_I , testset_partial_labels = testset_partial[0], testset_partial[1] 
predictions = [net(image[None]).item() for image in testset_partial_I ]


fpr, tpr, thresholds = metrics.roc_curve(testset_partial_labels, predictions)

# importing the required module 
import matplotlib.pyplot as plt 
  
# x axis and y axis values 
x ,y = fpr, tpr

# plotting the points  
plt.plot(x, y,marker='x') 
plt.plot(x, x,marker='x')
  
# naming the x axis 
plt.xlabel('False Positive Rate') 
# naming the y axis 
plt.ylabel('True Positive Rate') 
  
# giving a title to my graph 
plt.title('Reciever operating characteristic curve') 
  
# function to show the plot 
plt.show()
# %%
# Commands for server: 
# grun *.py
# -t tmux a
# nvidia smi

# %% Optimisation of hyperparameters

import numpy as np

listOfBatchSizes = [8,16,24,32]
listOflr = np.logspace(-6,-1, num=10)

for i,lr, batchSize in enumerate( zip(listOflr,listOfBatchSizes)):
    print('starting test number %5d'%i)
    #pseudo: initialise net? train, save results and net, finaly return best
    

