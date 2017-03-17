
import numpy as np
import tensorflow as tf

MOMENTUM_INIT = 0.5

class Model:

    def init_inference(self, config):
        raise NotImplemented("Your model must implement this function.")

    def init_loss(self):
        self.mask = tf.placeholder(tf.float32,
                        shape=(self.batch_size, None))
        total_inv = (1.0 / tf.reduce_sum(self.mask))

        self.labels = tf.placeholder(tf.int64, shape=(self.batch_size, None))
        losses = tf.nn.sparse_softmax_cross_entropy_with_logits(
                    self.logits, self.labels)
        losses = self.mask * losses
        self.loss =  total_inv * tf.reduce_sum(losses)

        correct = tf.equal(tf.argmax(self.logits, 2), self.labels)
        correct = self.mask * tf.cast(correct, tf.float32)
        self.acc = total_inv * tf.reduce_sum(correct)

    def init_train(self, config):

        l2_weight = config.get('l2_weight', None)
        if l2_weight is not None:
            # *NB* assumes we want an l2 penalty for all trainable variables.
            l2s = [tf.nn.l2_loss(p) for p in tf.trainable_variables()]
            self.loss += l2_weight * tf.add_n(l2s)

        self.momentum = config['momentum']
        self.mom_var = tf.Variable(MOMENTUM_INIT, trainable=False,
                                   dtype=tf.float32)
        ema = tf.train.ExponentialMovingAverage(0.95)
        ema_op = ema.apply([self.loss, self.acc])
        self.avg_loss = ema.average(self.loss)
        self.avg_acc = ema.average(self.acc)

        tf.scalar_summary("Loss", self.loss)
        tf.scalar_summary("Accuracy", self.acc)

        self.it = tf.Variable(0, trainable=False, dtype=tf.int64)

        learning_rate = tf.train.exponential_decay(float(config['learning_rate']),
                            self.it, config['decay_steps'],
                            config['decay_rate'], staircase=True)

        optimizer = tf.train.MomentumOptimizer(learning_rate, self.mom_var)

        gvs = optimizer.compute_gradients(self.loss)

        # Gradient clipping
        clip_norm = config.get('clip_norm', None)
        if clip_norm is not None:
            tf.clip_by_global_norm([g for g, _ in gvs], clip_norm=clip_norm)

        train_op = optimizer.apply_gradients(gvs, global_step=self.it)
        with tf.control_dependencies([train_op]):
            self.train_op = tf.group(ema_op)

    def set_momentum(self, session):
        self.mom_var.assign(self.momentum).eval(session=session)

    def feed_dict(self, inputs, labels=None):
        """
        Generates a feed dictionary for the model's place-holders.
        *NB* inputs and labels are assumed to all be of the same
        lenght.
        Params:
            inputs : List of 1D arrays of wave segments
            labels (optional) : List of lists of integer labels
        Returns:
            feed_dict (use with feed_dict kwarg in session.run)
        """
        feed_dict = {self.inputs : np.vstack(inputs)}
        if labels is not None:
            feed_dict[self.labels] = np.vstack(labels)
            feed_dict[self.mask] = np.ones((len(labels), len(labels[0])))
        return feed_dict

