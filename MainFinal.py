# %% Global parameters

#Our variables:
YoussefPathModel= '/home/youssef/EPFL/MA1/Machine learning/MLProject2/ML2/youssefServer4.modeldict' # Path of the weights of the model
Youssefdatapath = '/home/youssef/EPFL/MA1/Machine learning/MLProject2/Data' # Path of data
YoussefServerPathModel= '/home/saied/ML/ML2/youssefServer22.modeldict' # Path of weights of the Model
YoussefServerdatapath = '/data/mgeiger/gg2/data' # Path of data
YoussefPathDataset= '/home/youssef/EPFL/MA1/Machine learning/MLProject2/traintestsets.pckl' # Path of training and test dataset
YoussefServerPathDataset= '/home/saied/ML/ML2/traintestsets.pckl' # Path of training and test dataset

import os 
dir_path = os.path.dirname(os.path.realpath(__file__))


#Global variables (booleans):
transfer_learning=0
init_batchnormv =1
use_parallelization=1
simple =0
data_augmentation =1
use_saved_model =1
save_trained_model=1
train_or_not =0
epochs =20


# PLEASE INSERT YOUR PATH HERE
PathModel= dir_path+'/youssefServer22.modeldict'
PathDataset = dir_path +'/traintestsets.pckl'
datapath = dir_path+'/Data' #YoussefServerdatapath

proportion_traindata = 0.8 # the proportion of the full dataset used for training
printevery = 1000

# %% Import Dataset and create trainloader 
import datasetY as dataset
import torch
import importlib
from datasetY import BalancedBatchSampler, BalancedBatchSampler2, random_splitY, accuracy, load_GG2_imagesTransfer, load_GG2_images2
import itertools
import numpy as np

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

# Pickling datasets

from datasetY import MakingDatasets
trainloader, testloader, ROCloader = MakingDatasets(transfer_learning=transfer_learning, PathDataset=PathDataset
                                            ,data_augmentation=data_augmentation,batch_sizev=8,test_batch_size=8,
                                             proportion_traindata=proportion_traindata)
# %% Import Neural network

if simple:
    net = torch.hub.load('rwightman/gen-efficientnet-pytorch', 'tf_mobilenetv3_small_minimal_100',
    pretrained=False)

    # Change First and Last Layer
    if not transfer_learning:
        net.conv_stem = torch.nn.Conv2d(4,16,kernel_size=(2,2),bias=False)
    net.classifier = torch.nn.Linear(1024, 1)
else: 
    net = torch.hub.load('rwightman/gen-efficientnet-pytorch', 'efficientnet_b0',
    pretrained=True)

    # Change First and Last Layer
    if not transfer_learning:
        net.conv_stem = torch.nn.Conv2d(4, 32, kernel_size=(3, 3), stride=(2, 2), padding=(1, 1), bias=False)
    net.classifier = torch.nn.Linear(1280, 1)


if not torch.cuda.is_available() : #ie if NOT on the server
    print(net)


from datasetY import init_batchnorm

net.to(device)
#Converts model with init_batchnorm
if not transfer_learning and init_batchnormv:
        init_batchnorm(net)


#Option to parallelize
print("There are", torch.cuda.device_count(), "GPUs!")
if torch.cuda.device_count() > 1 and use_parallelization:
    import torch.nn as nn
    print("Let's use", torch.cuda.device_count(), "GPUs!")
    net = nn.DataParallel(net)
net.to(device)


# %% Train Neural network

import torch.optim as optim
import torch.nn as nn
import torch.nn.functional as F

momentumv=0.90
lrv=10**-2

print("Learning rate= "+str(lrv))


# To calculate accuracy
from sampler import accuracy

def train_accuracy(net):
    return accuracy(net, loader= trainloader,device=device)

def test_accuracy(net):
    return accuracy(net, loader= testloader,device=device)

def ROC_accuracy(net):
    return accuracy(net, loader= ROCloader,device=device)


#Option to use a saved model parameters
if use_saved_model:
    import os
    if os.path.isfile(PathModel):
        if os.stat(PathModel).st_size > 0:
            net.load_state_dict(torch.load(PathModel,map_location=torch.device(device   )))
            print("Loading model...")
        else: 
            print("Empty file...")
        print("Using saved model...")


#Training starts

criterion = nn.SoftMarginLoss()

if not transfer_learning:
    optimizer = optim.SGD(net.parameters(), lr=lrv, momentum=momentumv)
else:
    optimizer = optim.SGD(net.classifier.parameters(), lr=lrv, momentum=momentumv)
    for param in net.parameters():
        param.requires_grad = False
    for param in net.classifier.parameters():
        param.requires_grad = True
    
    
# Decay LR by a factor of 0.1 every 7 epochs
from torch.optim import lr_scheduler
exp_lr_scheduler = lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.1)

net.train()

if train_or_not:
    print("Starting training...")
    train_auc_list = np.array([0])
    test_auc_list = []
    for epoch in range(epochs):  # loop over the dataset multiple times
        exp_lr_scheduler.step()
        print("Starting epoch %d"%(epoch+1))
        print("Learning rate= "+str(lrv))
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
            if i % printevery == printevery-1:    # print every n mini-batches
                print('[%5d, %5d] loss: %.6f ' %
                        (epoch+1, i + 1, running_loss/printevery) )
                running_loss = 0.0
        
        # save predictions and labels for ROC curve calculation
        print("Calculating AUROC...")

        # AUC for ROC curve, stop if test AUROC decreases significantly 
        
        #net.eval()
        net.train()
        from sklearn import metrics
        predictions = []
        labels = []
        with torch.no_grad():
            if True:
                for k, testset_partial in enumerate(testloader):
                    if k <1000:
                        testset_partial_I , testset_partial_labels = testset_partial[0].to(device), testset_partial[1].to(device)
                        predictions += [p.item() for p in net(testset_partial_I) ]
                        labels += testset_partial_labels.tolist()
                    else: break

                auc = metrics.roc_auc_score(labels, predictions)
                test_auc_list = np.concatenate((train_auc_list, np.array([auc])))
                if auc < np.max(test_auc_list)-0.04:
                    break
                print("Test auc: %5f"%auc)

        net.train()
    
    print('Finished Training')
    if save_trained_model:
        import os
        if os.path.exists(PathModel):  # checking if there is a file with this name
            os.remove(PathModel)  # deleting the file
        torch.save(net.state_dict(), PathModel)
        print("Saving model...")


import sys
sys.exit()



