#import os
import os.path as osp
from easydict import EasyDict as edict

__C = edict()


cfg = __C

# Maximum margin to pick up samples around objects
__C.D = 30


# strategy3 margin
__C.NEG3_MARGIN = 10


# margin size for candidate pixels
__C.D_MARGIN = 8

# Ratio factor for determine the distance among pixels
__C.RATIO_FACTOR = 2.


# INPUT DataSet Attribute
# __C.TXT_PATH = '/home/yuanjial/NeuralNetwork/FilePreprocess/coco/train.txt'
# __C.BASE_DIR = '/home/yuanjial/DataSet/COCO/coco2014_train'

__C.TXT_PATH = '/media/wenxuan/LargeDisk/yjl_dataset/CVPPP/train.txt'
__C.BASE_DIR = '/media/wenxuan/LargeDisk/yjl_dataset/CVPPP'

__C.IMG_DIR = 'JPEGImages'
__C.IMG_EXT = '.jpg'

__C.INSTANCEANN_DIR = 'SegmentationObjectFilledDenseCRF'
__C.GT_EXT = '.png'

# directory to store converted tiff files
__C.OUT_PATH = 'CVPPP/converted'
__C.OUT_FNAME = 'train_converted_cvppp.txt'

# Number of positive sampels
__C.N_POS = 2

# Number of negative samples
__C.N_NEG = 8

# Number of pairs
__C.N_PAIRS = 5

# Energy scale in distrance transform
__C.ENERGY_SCALE = 5

# Training phase configures
__C.TRAIN = edict()


# Test Configures
__C.TEST = edict()

# Project Root
__C.ROOT_DIR = osp.abspath(osp.join(osp.dirname(__file__), '..', '..'))


# GPU ID
__C.GPU_ID = 0

# Small Number
__C.EPS = 1e-14






