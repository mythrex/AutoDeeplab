import torch
import torch.nn as nn
import numpy as np
from operations import *
from torch.autograd import Variable
from genotypes import PRIMITIVES
from genotypes import Genotype


class MixedOp (nn.Module):
    '''
    Makes a list of operation
    Methods
    _______
    forward: apply weights of each operation and sums it sum(w * op(x))
    '''

    def __init__(self, C, stride):
        super(MixedOp, self).__init__()
        self._ops = nn.ModuleList()
        for primitive in PRIMITIVES:
            op = OPS[primitive](C, stride, False)
            if 'pool' in primitive:
                op = nn.Sequential(op, nn.BatchNorm2d(C, affine=False))
            self._ops.append(op)

    def forward(self, x, weights):
        return sum(w * op(x) for w, op in zip(weights, self._ops))


class Cell(nn.Module):
    '''
    Makes a cell structure
    '''

    def __init__(self, steps, multiplier, C_prev_prev, C_prev, C, rate):
        '''
        Parameters
        ----------
        steps : int
                        Value of B i.e. B=5
        multiplier : int
                        Description of parameter `x`.
        C_prev_prev : int
                        h^(l-2) hidden state.
                        if -1 is supplied means that there is no such hidden state
        C_prev : int
                        h^(l-1) hidden state.
                        if -1 is supplied means that there is no such hidden state
        C : int
                        h^(l) hidden state.
                        if -1 is supplied means that there is no such hidden state

        '''
        super(Cell, self).__init__()
        self.C_out = C
        if C_prev_prev != -1:
            self.preprocess0 = ReLUConvBN(
                C_prev_prev, C, 1, 1, 0, affine=False)

        if rate == 2:
            self.preprocess1 = FactorizedReduce(C_prev, C, affine=False)
        elif rate == 0:
            self.preprocess1 = FactorizedIncrease(C_prev, C)
        else:
            self.preprocess1 = ReLUConvBN(C_prev, C, 1, 1, 0, affine=False)
        self._steps = steps
        self._multiplier = multiplier
        self._ops = nn.ModuleList()
        # if C_prev_prev is present
        if C_prev_prev != -1:
            for i in range(self._steps):
                for j in range(2+i):
                    stride = 1
                    op = MixedOp(C, stride)
                    self._ops.append(op)
        else:
            for i in range(self._steps):
                for j in range(1+i):
                    stride = 1
                    op = MixedOp(C, stride)
                    self._ops.append(op)
        # apply ReLU , Convolution and Batch Normalisation to the cell
        self.ReLUConvBN = ReLUConvBN(
            self._multiplier * self.C_out, self.C_out, 1, 1, 0)

    def forward(self, s0, s1, weights):
        if s0 is not None:
            s0 = self.preprocess0(s0)
        s1 = self.preprocess1(s1)
        if s0 is not None:
            states = [s0, s1]
        else:
            states = [s1]
        offset = 0
        # ! this is supicious, why i is not used
        for i in range(self._steps):
            s = sum(self._ops[offset+j](h, weights[offset+j])
                    for j, h in enumerate(states))
            offset += len(states)
            states.append(s)

        concat_feature = torch.cat(states[-self._multiplier:], dim=1)
        return self.ReLUConvBN(concat_feature)


if __name__ == "__main__":
    # k = no of alphas
    k = sum(1 for i in range(5) for n in range(2+i))
    num_ops = len(PRIMITIVES)
    alphas_cell = torch.tensor(1e-3*torch.randn(k, num_ops))
    x = torch.tensor(torch.ones(1, k, 1, num_ops))
    op = MixedOp(20, 1)
    print("---k---", k)
    print("---op---", op)
    #   print("---x---", x)
    print(op.forward(x, alphas_cell))
    #   print(op.applyop(x, 1))
