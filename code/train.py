"""Training script for the DeepLab-ResNet network on the PASCAL VOC dataset
   for semantic image segmentation.

This script trains the model using augmented PASCAL VOC,
which contains approximately 10000 images for training and 1500 images for validation.


### 2017-02-21: steps to change deep_resnet to deep interactive segmentation
  -- step 1: create new image_reader.py, it should support read tiff file.
             update train.py, the new input interface depends on placeholder.

  -- step 2: create new model with input channel = 5, output channel = ???, and load pretrained model

  -- step 3: update inference.py, to implement inference over new model.
"""

from __future__ import print_function

import argparse
# from datetime import datetime
import os
# import os.path as osp
# import sys
import time
import pdb
import tensorflow as tf
# import numpy as np

from deeplab_resnet.image_reader import BatchDataset
from deeplab_resnet import DeepLabResNetModel,image_reader, prepare_label
from deeplab_resnet import cfg


BATCH_SIZE = 7
NUM_EPOCH = 10
LEARNING_RATE = 1e-5
POWER = 0.9
MOMENTUM = 0.9
WEIGHT_DECAY = 2.5e-4

#RESTORE_FROM   = '../../../image-annotator-master/deep_interactive/model/PASCAL/pos_neg/model.ckpt-80000'
RESTORE_FROM = './snapshots/model.ckpt-167000'
SAVE_NUM_IMAGES = 2
SAVE_PRED_EVERY = 1000
SNAPSHOT_DIR = 'snapshots/'


def get_arguments():
    """Parse all the arguments provided from the CLI.

    Returns:
      A list of parsed arguments.
    """
    parser = argparse.ArgumentParser(description="DeepLab-ResNet Network")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help="Number of images sent to the network in one step.")
    parser.add_argument("--is-training", action="store_true",
                        help="Whether to updates the running means and variances during the training.")
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE,
                        help="Base learning rate for training with polynomial decay.")
    parser.add_argument("--momentum", type=float, default=MOMENTUM,
                        help="Momentum component of the optimiser.")
    parser.add_argument("--num-epochs", type=int, default=NUM_EPOCH,
                        help="Number of training steps.")
    parser.add_argument("--power", type=float, default=POWER,
                        help="Decay parameter to compute the learning rate.")
    parser.add_argument("--random-scale", action="store_true",
                        help="Whether to randomly scale the inputs during the training.")
    parser.add_argument("--restore-from", type=str, default=RESTORE_FROM,
                        help="Where restore model parameters from.")
    parser.add_argument("--save-num-images", type=int, default=SAVE_NUM_IMAGES,
                        help="How many images to save.")
    parser.add_argument("--save-pred-every", type=int, default=SAVE_PRED_EVERY,
                        help="Save summaries and checkpoint every often.")
    parser.add_argument("--snapshot-dir", type=str, default=SNAPSHOT_DIR,
                        help="Where to save snapshots of the model.")
    parser.add_argument("--weight-decay", type=float, default=WEIGHT_DECAY,
                        help="Regularisation parameter for L2-loss.")
    return parser.parse_args()

def save(saver, sess, logdir, step):
   '''Save weights.

   Args:
     saver: TensorFlow Saver object.
     sess: TensorFlow session.
     logdir: path to the snapshots directory.
     step: current training step.
   '''
   model_name = 'model.ckpt'
   checkpoint_path = os.path.join(logdir, model_name)

   if not os.path.exists(logdir):
      os.makedirs(logdir)
   saver.save(sess, checkpoint_path, global_step=step)
   print('The checkpoint has been created.')

def load(saver, sess, ckpt_path):
    '''Load trained weights.

    Args:
      saver: TensorFlow Saver object.
      sess: TensorFlow session.
      ckpt_path: path to checkpoint file with parameters.
    '''
    saver.restore(sess, ckpt_path)
    print("Restored model parameters from {}".format(ckpt_path))

def main():
    """Create the model and start the training."""
    args = get_arguments()

    # Load reader.
    h, w = map(int, cfg.INPUT_SIZE.split(','))
    c = 4 if cfg.ONLY_POS else 5
    reader_option = {"resize":True, "resize_size":[h,w]}
    train_dataset_reader = BatchDataset(reader_option)
    num_file  = train_dataset_reader.get_image_number()
    num_steps = args.num_epochs * num_file

    # Create network.
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'

    image_batch  = tf.placeholder(tf.float32, shape=[args.batch_size, h, w, c], name='input')
    label_batch  = tf.placeholder(tf.uint8, shape=[args.batch_size, h, w, 1], name='label')

    net = DeepLabResNetModel({'data': image_batch}, is_training=args.is_training)
    # For a small batch size, it is better to keep
    # the statistics of the BN layers (running means and variances)
    # frozen, and to not update the values provided by the pre-trained model.
    # If is_training=True, the statistics will be updated during the training.
    # Note that is_training=False still updates BN parameters gamma (scale) and beta (offset)
    # if they are presented in var_list of the optimiser definition.

    # Predictions.
    raw_output = net.layers['fc1_voc12']
    # Which variables to load. Running means and variances are not trainable,
    # thus all_variables() should be restored.
    restore_var = tf.global_variables()
    all_trainable = [v for v in tf.trainable_variables() if 'beta' not in v.name and 'gamma' not in v.name]
    fc_trainable = [v for v in all_trainable if 'fc' in v.name] # lr * 10.0
    conv1_trainable = [v for v in all_trainable if 'conv1' in v.name] # lr * 20.0
    conv_trainable = [v for v in all_trainable if 'fc' not in v.name and 'conv1' not in v.name] # lr * 1.0
    assert(len(all_trainable) == len(fc_trainable) + len(conv1_trainable) + len(conv_trainable))

    # Predictions: ignoring all predictions with labels greater or equal than n_classes
    raw_prediction = tf.reshape(raw_output, [-1, cfg.num_classes])
    label_proc = prepare_label(label_batch, tf.stack(raw_output.get_shape()[1:3]), one_hot=False) # [batch_size, h, w]
    raw_gt = tf.reshape(label_proc, [-1,])
    raw_prediction = tf.reshape(raw_prediction, [-1,])
    gt = tf.cast(raw_gt, tf.float32)
    prediction = tf.cast(raw_prediction, tf.float32)


    # Pixel-wise softmax loss.
    # loss = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=prediction, labels=gt)
    loss = tf.nn.weighted_cross_entropy_with_logits(targets=gt, logits=prediction, pos_weight=5, name='weighted_sigmoid')
    l2_losses = [args.weight_decay * tf.nn.l2_loss(v) for v in tf.trainable_variables() if 'weights' in v.name]
    reduced_loss = tf.reduce_mean(loss)*20 + tf.add_n(l2_losses)

    '''
    # Processed predictions: for visualisation.
    raw_output_up = tf.image.resize_bilinear(raw_output, tf.shape(image_batch)[1:3,])
    raw_output_up = tf.argmax(raw_output_up, dimension=3)
    pred = tf.expand_dims(raw_output_up, dim=3)

    # Image summary.
    images_summary = tf.py_func(inv_preprocess, [image_batch, args.save_num_images], tf.uint8)
    labels_summary = tf.py_func(decode_labels, [label_batch, args.save_num_images], tf.uint8)
    preds_summary = tf.py_func(decode_labels, [pred, args.save_num_images], tf.uint8)


    total_summary = tf.summary.image('images',
                                     tf.concat([images_summary, labels_summary, preds_summary], axis=2),
                                     max_outputs=args.save_num_images) # Concatenate row-wise.
    summary_writer = tf.summary.FileWriter(args.snapshot_dir)
    '''

    # Define loss and optimisation parameters.
    base_lr = tf.constant(args.learning_rate)
    step_ph = tf.placeholder(dtype=tf.float32, shape=())
    learning_rate = tf.scalar_mul(base_lr, tf.pow(args.power,  step_ph // num_steps))

    opt_conv  = tf.train.MomentumOptimizer(learning_rate*1, args.momentum)
    opt_fc    = tf.train.MomentumOptimizer(learning_rate*5.0, args.momentum)
    opt_conv1 = tf.train.MomentumOptimizer(learning_rate*5.0, args.momentum)

    grads = tf.gradients(reduced_loss, conv_trainable + fc_trainable  + conv1_trainable)
    grads_conv  = grads[:len(conv_trainable)]
    grads_fc    = grads[len(conv_trainable) : (len(conv_trainable) + len(fc_trainable))]
    grads_conv1 = grads[(len(conv_trainable) + len(fc_trainable)):]

    train_op_conv  = opt_conv.apply_gradients(zip(grads_conv, conv_trainable))
    train_op_fc    = opt_fc.apply_gradients(zip(grads_fc, fc_trainable))
    train_op_conv1 = opt_conv1.apply_gradients(zip(grads_conv1, conv1_trainable))

    train_op = tf.group(train_op_conv, train_op_fc, train_op_conv1)

    # evaluation
    # yjl::check the update operation
    pred = tf.argmax(raw_predictions, axis=-1)
    mIoU, update_op = tf.contrib.metrics.streaming_mean_iou(pred, raw_gt, num_classes=n_classes, weights=weights)


    # Set up tf session and initialize variables.
    config = tf.ConfigProto(allow_soft_placement=True)
    config.gpu_options.allow_growth = True
    sess = tf.Session(config=config)
    init = tf.global_variables_initializer()

    sess.run(init)

    # Saver for storing checkpoints of the model.
    saver = tf.train.Saver(var_list=restore_var, max_to_keep=2)#keep_checkpoint_every_n_hours=1.0)

    # Load variables if the checkpoint is provided.
    # load_var_list = [v for v in restore_var if ('conv1' not in v.name) and ('fc1_voc12' not in v.name)]
    if args.restore_from is not None:
        loader = tf.train.Saver(var_list=restore_var)
        # loader = tf.train.Saver(var_list=load_var_list)
        load(loader, sess, args.restore_from)

    pdb.set_trace()

    for step in range(num_steps):
        start_time = time.time()
        images, labels = train_dataset_reader.next_batch(args.batch_size)
        feed_dict = {image_batch:images, label_batch:labels, step_ph:step}
        #feed_dict = {step_ph:step}
        if step % args.save_pred_every == 0:
            # loss_value, preds, summary = sess.run([reduced_loss,  pred, total_summary], feed_dict=feed_dict)
            # summary_writer.add_summary(summary, step)
            loss_value = sess.run([reduced_loss], feed_dict=feed_dict)
            save(saver, sess, args.snapshot_dir, step)
        loss_value, inf_loss, l2_loss, _ = sess.run([reduced_loss, loss, l2_losses, train_op], feed_dict=feed_dict)
        duration = time.time() - start_time
        epoch = (int)(step*args.batch_size/num_file)
        print('epoch {:d} /step {:d} \t loss = {:.3f},  ({:.3f} sec/step)'.format(epoch, step, loss_value, duration))

if __name__ == '__main__':
    main()
