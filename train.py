from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import numpy as np
import os
import random
import tensorflow as tf
import time

import loader
import network
import utils

tf.flags.DEFINE_string("config", "configs/cinc_config.json",
                       "Configuration file for training.")
FLAGS = tf.flags.FLAGS

def run_epoch(model, data_loader, session, summarizer):
    summary_op = tf.merge_all_summaries()

    for batch in data_loader.batches(data_loader.train):
        ops = [model.train_op, model.avg_loss,
               model.avg_acc, model.it, summary_op]
        res = session.run(ops, feed_dict=model.feed_dict(*batch))
        _, loss, acc, it, summary = res
        summarizer.add_summary(summary, global_step=it)
        if it == 50:
            model.set_momentum(session)
        if it % 100 == 0:
            msg = "Iter {}: AvgLoss {:.3f}, AvgAcc {:.3f}"
            print(msg.format(it, loss, acc))

def run_validation(model, data_loader, session, summarizer):
    it = model.it.eval(session)
    results = []
    for batch in data_loader.batches(data_loader.val):
        ops = [model.acc, model.loss]
        feed_dict = model.feed_dict(batch[0], batch[1], test=True)
        res = session.run(ops, feed_dict=feed_dict)
        results.append(res)
    acc, loss = np.mean(zip(*results), axis=1)
    summary = utils.make_summary("Dev Accuracy", float(acc))
    summarizer.add_summary(summary, global_step=it)
    summary = utils.make_summary("Dev Loss", float(loss))
    summarizer.add_summary(summary, global_step=it)
    msg = "Validation: Loss {:.3f}, Acc {:.3f}"
    print(msg.format(loss, acc))

def main(argv=None):

    with open(FLAGS.config) as fid:
        config = json.load(fid)

    random.seed(config['seed'])
    epochs = config['optimizer']['epochs']
    data_loader = loader.Loader(config['data']['path'],
                                config['model']['batch_size'],
                                seed=config['data']['seed'])

    model = network.Model()

    save_path = config['io']['save_path']
    if not os.path.exists(save_path):
        os.mkdir(save_path)

    config['model']['output_dim'] = data_loader.output_dim
    with open(os.path.join(save_path, "config.json"), 'w') as fid:
        json.dump(config, fid)

    with tf.Graph().as_default(), tf.Session() as sess:
        tf.set_random_seed(config['seed'])
        model.init_inference(config['model'])
        model.init_loss()
        model.init_train(config['optimizer'])
        tf.global_variables_initializer().run()
        saver = tf.train.Saver(tf.global_variables())
        summarizer = tf.train.SummaryWriter(save_path, sess.graph)
        for e in range(epochs):
            start = time.time()
            run_epoch(model, data_loader, sess, summarizer)
            saver.save(sess, os.path.join(save_path, "model"))
            print("Epoch {} time {:.1f} (s)".format(e, time.time() - start))
            run_validation(model, data_loader, sess, summarizer)

if __name__ == '__main__':
    tf.app.run()
