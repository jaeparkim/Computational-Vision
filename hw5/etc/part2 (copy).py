import numpy as np
import torch
import os
import sys
import matplotlib.pyplot as plt

import torch.nn as nn
import torch.nn.functional as f
import torch.optim as optim
import torchvision.transforms as transforms
import torchvision.datasets as datasets

from torch.utils.data import Dataset, DataLoader, SubsetRandomSampler
from torch.autograd import Variable
from torchsummary import summary
from PIL import Image


def data_loader(input_min_dim, batch_size):
    # data transformer
    data_transforms = transforms.Compose([
        transforms.Resize(input_min_dim),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5])
    ])

    dataset = datasets.ImageFolder(root="/home/jae/rpi/spring2021/comp_vision/hw5/hw5_data/train", transform=data_transforms)
    test_dataset = datasets.ImageFolder(root="/home/jae/rpi/spring2021/comp_vision/hw5/hw5_data/test", transform=data_transforms)

    # split into training andtesting
    percentage = 0.125
    dataset_size = len(dataset) - 7
    valid_size = int(dataset_size * percentage)
    train_size = dataset_size - valid_size

    # pseudo-random dataset (change seeds in main)
    indices = torch.randperm(len(dataset))
    train_indices = indices[:len(indices) - valid_size][:train_size or None]
    valid_indices = indices[len(indices) - valid_size:] if valid_size else None

    # data loaders - Original 4k, Train 3.5k, Validation 0.5k, Test 1k
    data_loader = DataLoader(dataset, batch_size=dataset_size, shuffle=True,
                             num_workers=4, pin_memory=True)
    train_loader = DataLoader(dataset, pin_memory=True, batch_size=batch_size,
                              sampler=SubsetRandomSampler(train_indices),
                              num_workers=4)
    valid_loader = DataLoader(dataset, pin_memory=True, batch_size=batch_size,
                              sampler=SubsetRandomSampler(valid_indices),
                              num_workers=4)
    test_loader = DataLoader(test_dataset, pin_memory=True, batch_size=batch_size,
                             shuffle=True, num_workers=4)

    return train_loader, valid_loader, test_loader


'''
This function will generate one Unit of Convolution layer (without Maxpool)
'''


class ConvUnit(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(ConvUnit, self).__init__()
        self.conv = nn.Conv2d(in_channels=in_channels, kernel_size=3,
                              out_channels=out_channels, stride=1, padding=1, bias=True)
        self.bn = nn.BatchNorm2d(num_features=out_channels)
        self.relu = nn.ReLU()

    def forward(self, input):
        output = self.conv(input)
        output = self.bn(output)
        output = self.relu(output)

        return output


'''
This function will generate the Convolution Neural Network
'''


class ConvNet(nn.Module):
    def __init__(self, num_classes=5):
        super(ConvNet, self).__init__()

        # Create __ layers of the unit with max pooling in between
        self.unit1 = ConvUnit(in_channels=3, out_channels=32)
        self.unit2 = ConvUnit(in_channels=32, out_channels=64)
        self.unit3 = ConvUnit(in_channels=64, out_channels=128)

        self.maxpool = nn.MaxPool2d(kernel_size=2)
        self.dropoutFC = nn.Dropout(p=0.5)
        self.dropoutCONV = nn.Dropout(p=0.5)

        # Add all the units into the Sequential layer in exact order
        self.net = nn.Sequential(self.unit1,
                                 self.maxpool,
                                 self.unit2,
                                 self.maxpool,
                                 self.unit3,
                                 self.maxpool)

        self.fc1 = nn.Linear(in_features=128 * 7 * 11, out_features=256)
        self.fc2 = nn.Linear(in_features=256, out_features=5)

    def forward(self, input):
        output = self.net(input)
        output = output.view(-1, 128 * 7 * 11)
        output = self.dropoutCONV(output)
        output = self.fc1(output)
        output = self.dropoutFC(output)
        output = self.fc2(output)
        return output


'''
This function will generate Neural Network
'''


class FCNeuralNet(nn.Module):
    def __init__(self, input_size, num_classes):
        super(FCNeuralNet, self).__init__()

        # hidden layers sizes, you can play with it as you wish!
        hidden1 = 512
        hidden2 = 256
        hidden3 = 128

        # layer parameters
        self.fc1 = nn.Linear(input_size, hidden1)
        self.fc2 = nn.Linear(hidden1, hidden2)
        self.fc3 = nn.Linear(hidden2, hidden3)
        self.output = nn.Linear(hidden3, num_classes)

        # activations
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(p=0.5)

    def forward(self, x):
        output = self.fc1(x)
        output = self.relu(output)
        output = self.dropout(output)
        output = self.fc2(output)
        output = self.relu(output)
        output = self.dropout(output)
        output = self.fc3(output)
        output = self.relu(output)
        output = self.dropout(output)
        output = self.output(output)

        return output


'''
This function will perform train/test/split depending on the 'mode' booleans.
If train is set to true, model.train() will be activated and training will be done.
If validation/test is set to true, model.eval() will be activated. No gradients in 
eval() mode. 
This function works both for NN and CNN!
'''


def PERFORM(model, data_loader, device, optimizer, loss_fn, data_size,
            input_shape=None,
            train=False, validation=False, test=False):

    # loss and accuracy containers
    loss_sum = 0.0
    accuracy_sum = 0.0

    # for each mini-batch of data
    for i, (images, labels) in enumerate(data_loader):

        if train:
            # set train mode
            model.train(True)
        else:
            torch.no_grad()
            model.eval()

        # push data and labels to GPU/CPU
        if input_shape is not None:
            images = images.reshape(-1, input_shape).to(device)
        else:
            images = images.to(device)
        labels = labels.to(device)

        # predict classes
        outputs = model(images).to(device)

        # compute loss
        loss = loss_fn(outputs, labels)
        if train:
            # clear all accumulated gradients
            optimizer.zero_grad()

            # backpropagate the loss
            loss.backward()

            # adjust parameters
            optimizer.step()

        # keep track of accumulated loss or accuracy.
        loss_sum += loss.item()
        _, prediction = torch.max(outputs.data, 1)
        accuracy_sum += torch.sum(prediction == labels.data)

        if test:
            c = (prediction == labels).squeeze()
            for j in range(5):
                label = labels[j]
                class_correct[label] += c[j].item()
                class_total[label] += 1



    return accuracy_sum / data_size, loss_sum / data_size, optimizer


if __name__ == "__main__":

    # set seed value
    torch.manual_seed(1)
    torch.cuda.manual_seed(1)
    np.random.seed(1)
    device = 'cuda'  # or cpu

    # test with different variables
    # hyperparameters
    num_classes = 5  # The number of output classes.
    num_epochs = 50  # The number of times entire dataset is trained
    batch_size = 64  # The size of input data took for one iteration
    learning_rate = 1e-3  # The speed of convergence


    # model_name and shape
    model_name = sys.argv[1]

    if model_name == 'NN':
        input_shape = 3 * 60 * 90
        model = FCNeuralNet(input_shape, num_classes).to(device)
    elif model_name == 'CNN':
        input_shape = None
        model = ConvNet(num_classes=5).to(device)
    else:  # wrong input
        print("Usage: python part2.py 'NN or CNN'")
        sys.exit()

    # load data
    train_loader, valid_loader, test_loader = data_loader(input_min_dim=60, batch_size=batch_size)

    class_correct = list(0. for i in range(5))
    class_total = list(0. for i in range(5))

    # optimizer and loss function
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=1e-5)
    loss = nn.CrossEntropyLoss()

    # loss and accuracy container
    training_loss_list = []
    training_accuracy_list = []
    validation_loss_list = []
    validation_accuracy_list = []

    # global values

    global_v_loss = 10.0
    global_v_acc = 0.0
    global_tr_loss = 10.0
    global_tr_acc = 0.0

    # perform (train/validation/test)

    for epoch in range(num_epochs):

        # perform training
        training_accuracy, training_loss, _ = PERFORM(model, data_loader=train_loader,
                                                      device=device, optimizer=optimizer,
                                                      loss_fn=loss, data_size=3500,
                                                      input_shape=input_shape, train=True)
        training_accuracy_list.append(training_accuracy)
        training_loss_list.append(training_loss)

        # perform validation
        validation_accuracy, validation_loss, optimizer = PERFORM(model, data_loader=valid_loader,
                                                                  device=device, optimizer=optimizer,
                                                                  loss_fn=loss, data_size=500,
                                                                  input_shape=input_shape,
                                                                  validation=True)
        validation_accuracy_list.append(validation_accuracy)
        validation_loss_list.append(validation_loss)

        # save best model
        if validation_loss < global_v_loss and validation_accuracy > global_v_acc:
            checkpoint = {
                'state_dict': model.state_dict(),
                'optimizer': optimizer.state_dict()
            }
            torch.save(checkpoint, 'checkpoint.pth')
            global_v_loss = validation_loss
            global_v_acc = validation_accuracy
            global_tr_loss = training_loss
            global_tr_acc = training_accuracy

        # print epoch wise performance
        print(
            f'Epoch[{epoch + 1}/{num_epochs}] Training Accuracy: {training_accuracy:.4f} Training Loss {training_loss:.4f} Validation Accuracy: {validation_accuracy:.4f} Validation Loss: {validation_loss:.4f}')

    # load best model
    checkpoint = torch.load('checkpoint.pth')
    model.load_state_dict(checkpoint['state_dict'])
    for parameter in model.parameters():
        parameter.requires_grad = False

    # perform test
    test_accuracy, _, _ = PERFORM(model, data_loader=test_loader, device=device,
                                  optimizer=optimizer, loss_fn=loss,
                                  data_size=1000, input_shape=input_shape,
                                  test=True)

# PLOTTING
# for total epochs
epoch = [i for i in range(num_epochs)]
plt.plot(epoch, validation_loss_list, '-g', label='Validation Loss')
plt.plot(epoch, training_loss_list, '-r', label='Training Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.title('Training VS Validation Loss')
plt.legend()
# plt.savefig('loss_CNN_60shape.png')
# files.download('loss_CNN_60shape.png')

# PLOTTING
# for total epochs
epoch = [i for i in range(num_epochs)]
plt.plot(epoch, validation_accuracy_list, '-g', label='Validation Accuracy')
plt.plot(epoch, training_accuracy_list, '-r', label='Training Training')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.title('Training VS Validation Accuracy')
plt.legend()
# plt.savefig('acc_CNN_60shape.png')
# files.download('acc_CNN_60shape.png')

print(
    f'Training Loss: {global_tr_loss:.4f} Training Accuracy: {global_tr_acc} Validation Accuracy: {global_v_acc}\
     Validation Loss: {global_v_loss} Test Accuracy: {test_accuracy}')

# PLOTTING
# upto early stopping threshold
epoch = [i for i in range(16)]
plt.plot(epoch, validation_loss_list[:16], '-g', label='Validation Loss')
plt.plot(epoch, training_loss_list[:16], '-r', label='Training Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss')
plt.title('Training VS Validation Loss')
plt.legend()
# plt.savefig('loss_CNN_60shape_15epoch.png')
# files.download('loss_CNN_60shape_15epoch.png')

# PLOTTING
# upto early stopping threshold
epoch = [i for i in range(16)]
plt.plot(epoch, validation_accuracy_list[:16], '-g', label='Validation Accuracy')
plt.plot(epoch, training_accuracy_list[:16], '-r', label='Training Training')
plt.xlabel('Epoch')
plt.ylabel('Accuracy')
plt.title('Training VS Validation Accuracy')
plt.legend()
# plt.savefig('acc_CNN_60shape_15epoch.png')
# files.download('acc_CNN_60shape_15epoch.png')

# Classwise Accuracy
classes = ['Grass', 'Ocean', 'Redcarpet', 'Road', 'Wheatfield']
for i in range(5):
    print('Accuracy of class %5s : %2d %%' % (
        classes[i], 100 * class_correct[i] / class_total[i]))

sys.exit()
