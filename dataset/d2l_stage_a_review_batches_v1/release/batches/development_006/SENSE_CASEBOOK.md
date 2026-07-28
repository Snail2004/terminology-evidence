# Stage A sense casebook: development_006

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. minibatch size

- `sense_id`: `d2lce_152a9bcc9b8b5f6cc5586c54`
- Split: `development`
- Model definition: the number of examples contained in one minibatch during training
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_dc5cb3bfdafeb7c4a403e8a9`: With a minibatch size of 2, we only get 3 minibatches.
- `ctx_78da4af66f0cedb5ae1b160d`: The shape of the features in each minibatch tells us both the minibatch size and the number of input features.
- `ctx_7fc6f12ab12ca9a7f0af8274`: Hence, training on 1024 GPUs with a minibatch size of, say 32 images per batch amounts to an aggregate minibatch of about 32000 images.
- `ctx_a212b34897ea9058b36ef4f4`: A minibatch size of 10 is more efficient than stochastic gradient descent; a minibatch size of 100 even outperforms GD in terms of runtime.
- `ctx_c15f9d27aeea9362be91cca2`: Let the minibatch size be one, and the sequence of the text be "machine".

### Backup contexts

- `ctx_d6ab75565ebd010dfbf7b992`: This can be achieved by setting the minibatch size to 1500 (i.e., to the total number of examples).
- `ctx_1e4dd1bfa6ccb1046784076e`: With 8 GPUs per server and 16 servers we already arrive at a minibatch size of 128.
- `ctx_39af2ece89443cd7fa86dfc2`: On a 16-GPU server this can increase the minibatch size considerably and we may have to increase the learning rate accordingly.

### Contrastive contexts

- `ctxx_5191a23f7110b644d4202364`: [Synthetic] The minibatch size stayed fixed at 32, but the minibatch contents changed every iteration.

### Definition evidence

- `ctx_78da4af66f0cedb5ae1b160d`: The shape of the features in each minibatch tells us both the minibatch size and the number of input features.
- `ctx_d6ab75565ebd010dfbf7b992`: This can be achieved by setting the minibatch size to 1500 (i.e., to the total number of examples).
- `ctx_a212b34897ea9058b36ef4f4`: A minibatch size of 10 is more efficient than stochastic gradient descent; a minibatch size of 100 even outperforms GD in terms of runtime.

### Part-of-speech evidence

- `ctx_7fc6f12ab12ca9a7f0af8274`: Hence, training on 1024 GPUs with a minibatch size of, say 32 images per batch amounts to an aggregate minibatch of about 32000 images.
- `ctx_c15f9d27aeea9362be91cca2`: Let the minibatch size be one, and the sequence of the text be "machine".

## 2. minima

- `sense_id`: `d2lce_455f2de181035ca8388c30b0`
- Split: `development`
- Model definition: Points or values where a function reaches a minimum, especially on an optimization or loss surface.
- Model POS: `noun`

### Primary contexts

- `ctx_9fe845c8f1250f89a8604169`: ### Local Minima
- `ctx_005ac3ba6b11534979ff46ad`: In fact, this is one of the beneficial properties of minibatch stochastic gradient descent where the natural variation of gradients over minibatches is able to dislodge the parameters from local minima.
- `ctx_2023e0a03e715e57f08e87ce`: However, for more complicated models, like deep networks, the loss surfaces contain many minima.
- `ctx_245348373fcf03e11c87da71`: * The optimization problems may have many local minima.
- `ctx_3edadaa9e9bdcfa46667a9cc`: Some of the most vexing ones are local minima, saddle points, and vanishing gradients.

### Backup contexts

- `ctx_14e7d3c859708f8f0ea7212c`: Besides local minima, saddle points are another reason for gradients to vanish.
- `ctx_eef3a0e3a150b78b03b45d89`: This makes saddle points more likely than local minima.
- `ctx_a9e253f896a3bbfcfaf951f0`: The only possible location of minima are at $x = -1, 0, 2$, where the function takes the values $-5,0, -32$ respectively, and thus we can conclude that we minimize our function when $x = 2$.

### Contrastive contexts

- `ctxx_04b9adf8a00921e2e82f00b3`: Synthetic: In typography, minima can refer to the short downward strokes of letters, not optimization points.

### Definition evidence

- `ctx_2023e0a03e715e57f08e87ce`: However, for more complicated models, like deep networks, the loss surfaces contain many minima.
- `ctx_9fe845c8f1250f89a8604169`: ### Local Minima
- `ctx_245348373fcf03e11c87da71`: * The optimization problems may have many local minima.
- `ctx_a9e253f896a3bbfcfaf951f0`: The only possible location of minima are at $x = -1, 0, 2$, where the function takes the values $-5,0, -32$ respectively, and thus we can conclude that we minimize our function when $x = 2$.

### Part-of-speech evidence

- `ctx_2023e0a03e715e57f08e87ce`: However, for more complicated models, like deep networks, the loss surfaces contain many minima.
- `ctx_3edadaa9e9bdcfa46667a9cc`: Some of the most vexing ones are local minima, saddle points, and vanishing gradients.

## 3. MLP

- `sense_id`: `d2lce_0ac8f3308547fb001c31e869`
- Split: `development`
- Model definition: a multilayer perceptron neural network
- Model POS: `proper_noun`

### Primary contexts

- `ctx_e40cd2162abe8f988abaddfb`: Consider a simple MLP with a single hidden layer of, say, $d$ dimensions in the hidden layer and a single output.
- `ctx_c1c142be01a5b299b70337c6`: ```toc :maxdepth: 2 mlp mlp-scratch mlp-concise underfit-overfit weight-decay dropout backprop numerical-stability-and-init environment kaggle-house-price ```
- `ctx_087386cdea1dae5d6dcc3ff7`: Equivalent to :eqref:`eq_additive-attn`, the query and the key are concatenated and fed into an MLP with a single hidden layer whose number of hidden units is $h$, a hyperparameter.
- `ctx_3c67ae78c4b02de37fc6d11f`: They were proposed based on a very simple insight: to use an MLP on the channels for each pixel separately :cite:`Lin.Chen.Yan.2013`.
- `ctx_4a335ba3f1c5504d0ae19024`: In the last chapter, we implemented each component of an MLP from scratch and even showed how to leverage high-level APIs to roll out the same models effortlessly.

### Backup contexts

- `ctx_62a5ada5f1792020bc23cde5`: ```{.python .input} # A simple MLP def get_net(): net = nn.Sequential() net.add(nn.Dense(10, activation='relu'), nn.Dense(1)) net.initialize(init.Xavier()) return net # Square loss loss = gluon.loss.L2Loss() ``` ```{.python .input} #@tab pytorch # Function for initializing the weights of the network def init_weights(m): if type(m) == nn.Linear: nn.init.xavier_uniform_(m.weight) # A simple MLP def get_net(): net = nn.Sequential(nn.Linear(4, 10), nn.ReLU(), nn.Linear(10, 1)) net.apply(init_weights) return net # Note: `MSELoss` computes squared error without the 1/2 factor loss = nn.MSELoss(reduction='none') ``` ```{.python .input} #@tab tensorflow # Vanilla MLP architecture def get_net(): net = tf.keras.Sequential([tf.keras.layers.Dense(10, activation='relu'), tf.keras.layers.Dense(1)]) return net # Note: `MeanSquaredError` computes squared error without the 1/2 factor loss = tf.keras.losses.MeanSquaredError() ``` Now we are ready to [**train the model**].
- `ctx_788a11fa6efa6cbc9a413253`: Because these networks are invariant to the order of the features, we could get similar results regardless of whether we preserve an order corresponding to the spatial structure of the pixels or if we permute the columns of our design matrix before fitting the MLP's parameters.
- `ctx_849b80c6ea299773a2e4a5c4`: For all entries of the reset gate $\mathbf{R}_t$ that are close to 0, the candidate hidden state is the result of an MLP with $\mathbf{X}_t$ as the input.

### Contrastive contexts

- `ctxx_28d8d20b90274cd2c85f8618`: Synthetic: The file extension .mlp here does not refer to an MLP neural network.

### Definition evidence

- `ctx_4a335ba3f1c5504d0ae19024`: In the last chapter, we implemented each component of an MLP from scratch and even showed how to leverage high-level APIs to roll out the same models effortlessly.
- `ctx_62a5ada5f1792020bc23cde5`: ```{.python .input} # A simple MLP def get_net(): net = nn.Sequential() net.add(nn.Dense(10, activation='relu'), nn.Dense(1)) net.initialize(init.Xavier()) return net # Square loss loss = gluon.loss.L2Loss() ``` ```{.python .input} #@tab pytorch # Function for initializing the weights of the network def init_weights(m): if type(m) == nn.Linear: nn.init.xavier_uniform_(m.weight) # A simple MLP def get_net(): net = nn.Sequential(nn.Linear(4, 10), nn.ReLU(), nn.Linear(10, 1)) net.apply(init_weights) return net # Note: `MSELoss` computes squared error without the 1/2 factor loss = nn.MSELoss(reduction='none') ``` ```{.python .input} #@tab tensorflow # Vanilla MLP architecture def get_net(): net = tf.keras.Sequential([tf.keras.layers.Dense(10, activation='relu'), tf.keras.layers.Dense(1)]) return net # Note: `MeanSquaredError` computes squared error without the 1/2 factor loss = tf.keras.losses.MeanSquaredError() ``` Now we are ready to [**train the model**].
- `ctx_087386cdea1dae5d6dcc3ff7`: Equivalent to :eqref:`eq_additive-attn`, the query and the key are concatenated and fed into an MLP with a single hidden layer whose number of hidden units is $h$, a hyperparameter.
- `ctx_e40cd2162abe8f988abaddfb`: Consider a simple MLP with a single hidden layer of, say, $d$ dimensions in the hidden layer and a single output.

### Part-of-speech evidence

- `ctx_4a335ba3f1c5504d0ae19024`: In the last chapter, we implemented each component of an MLP from scratch and even showed how to leverage high-level APIs to roll out the same models effortlessly.
- `ctx_62a5ada5f1792020bc23cde5`: ```{.python .input} # A simple MLP def get_net(): net = nn.Sequential() net.add(nn.Dense(10, activation='relu'), nn.Dense(1)) net.initialize(init.Xavier()) return net # Square loss loss = gluon.loss.L2Loss() ``` ```{.python .input} #@tab pytorch # Function for initializing the weights of the network def init_weights(m): if type(m) == nn.Linear: nn.init.xavier_uniform_(m.weight) # A simple MLP def get_net(): net = nn.Sequential(nn.Linear(4, 10), nn.ReLU(), nn.Linear(10, 1)) net.apply(init_weights) return net # Note: `MSELoss` computes squared error without the 1/2 factor loss = nn.MSELoss(reduction='none') ``` ```{.python .input} #@tab tensorflow # Vanilla MLP architecture def get_net(): net = tf.keras.Sequential([tf.keras.layers.Dense(10, activation='relu'), tf.keras.layers.Dense(1)]) return net # Note: `MeanSquaredError` computes squared error without the 1/2 factor loss = tf.keras.losses.MeanSquaredError() ``` Now we are ready to [**train the model**].

## 4. model parameter

- `sense_id`: `d2lce_ed44d125cc1110c1c39f7b3e`
- Split: `development`
- Model definition: a variable of a model whose value defines the model and is typically initialized and updated during training
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_23b189c0f5c5598741fa92a6`: This weight is not a model parameter and thus it is never updated by backpropagation.
- `ctx_fbb8b66ce00e1ca91661df77`: This module provides various methods for model parameter initialization.
- `ctx_712b9e024f4bb6ad1f3f5876`: where $f(\boldsymbol{\xi}_t, \mathbf{x})$ is the objective function with respect to the training example $\boldsymbol{\xi}_t$ drawn from some distribution at step $t$ and $\mathbf{x}$ is the model parameter.
- `ctx_af69401169f9749c9e888c35`: Generally speaking, when solving an optimization problem, we take update steps for the model parameter, say in the vector form $\mathbf{x}$, in the direction of the negative gradient $\mathbf{g}$ on a minibatch.
- `ctx_7a8590cce9481296230c2d35`: :begin_tab:`tensorflow` The `initializers` module in TensorFlow provides various methods for model parameter initialization.

### Backup contexts

- `ctx_345e280a6afc1f3131a69523`: * TensorFlow's module `initializers` provides various methods for model parameter initialization.
- `ctx_352eb05d2112f610b0c4b6b2`: * MXNet's module `initializer` provides various methods for model parameter initialization.
- `ctx_3c33a18dd04e08da418034a3`: Compare the model parameter sizes of AlexNet, VGG, and NiN with GoogLeNet.

### Contrastive contexts

- `ctxx_c4d879c10574096f39fa32eb`: Synthetic: In the climate model, cloud cover was treated as a fixed model parameter chosen by the researchers.

### Definition evidence

- `ctx_23b189c0f5c5598741fa92a6`: This weight is not a model parameter and thus it is never updated by backpropagation.
- `ctx_af69401169f9749c9e888c35`: Generally speaking, when solving an optimization problem, we take update steps for the model parameter, say in the vector form $\mathbf{x}$, in the direction of the negative gradient $\mathbf{g}$ on a minibatch.
- `ctx_712b9e024f4bb6ad1f3f5876`: where $f(\boldsymbol{\xi}_t, \mathbf{x})$ is the objective function with respect to the training example $\boldsymbol{\xi}_t$ drawn from some distribution at step $t$ and $\mathbf{x}$ is the model parameter.
- `ctx_fbb8b66ce00e1ca91661df77`: This module provides various methods for model parameter initialization.

### Part-of-speech evidence

- `ctx_23b189c0f5c5598741fa92a6`: This weight is not a model parameter and thus it is never updated by backpropagation.
- `ctx_af69401169f9749c9e888c35`: Generally speaking, when solving an optimization problem, we take update steps for the model parameter, say in the vector form $\mathbf{x}$, in the direction of the negative gradient $\mathbf{g}$ on a minibatch.

## 5. momentum

- `sense_id`: `d2lce_addfcc9899bef06c500b6b0e`
- Split: `development`
- Model definition: a parameter or mechanism that uses an exponentially weighted average of past values, especially past gradients, to smooth updates.
- Model POS: `noun`

### Primary contexts

- `ctx_d437426b9a49d27a6fb2a2c3`: It decreases the smoothness of the momentum, the exponentially weighted moving average of past gradients, to take care of the rapid changing gradients because the generator and the discriminator fight with each other.
- `ctx_500ae062c5d8dcb9953ef236`: ```{.python .input} from d2l import mxnet as d2l from mxnet import autograd, np, npx, init from mxnet.gluon import nn npx.set_np() def batch_norm(X, gamma, beta, moving_mean, moving_var, eps, momentum): # Use `autograd` to determine whether the current mode is training mode or # prediction mode if not autograd.is_training(): # If it is prediction mode, directly use the mean and variance # obtained by moving average X_hat = (X - moving_mean) / np.sqrt(moving_var + eps) else: assert len(X.shape) in (2, 4) if len(X.shape) == 2: # When using a fully-connected layer, calculate the mean and # variance on the feature dimension mean = X.mean(axis=0) var = ((X - mean) ** 2).mean(axis=0) else: # When using a two-dimensional convolutional layer, calculate the # mean and variance on the channel dimension (axis=1).
- `ctx_8fa7f6c2ca736e617dfa8130`: ```toc :maxdepth: 2 optimization-intro convexity gd sgd minibatch-sgd momentum adagrad rmsprop adadelta adam lr-scheduler ```
- `ctx_06f4771cf594f1bbed3246e8`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(dim=(0, 2, 3), keepdim=True) var = ((X - mean) ** 2).mean(dim=(0, 2, 3), keepdim=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / torch.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean.data, moving_var.data ```
- `ctx_3630463c4fd1b1974674bd51`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```

### Backup contexts

- `ctx_3ccd2fb56cb762a513ca604f`: ```{.python .input} #@tab pytorch from d2l import torch as d2l import torch from torch import nn def batch_norm(X, gamma, beta, moving_mean, moving_var, eps, momentum): # Use `is_grad_enabled` to determine whether the current mode is training # mode or prediction mode if not torch.is_grad_enabled(): # If it is prediction mode, directly use the mean and variance # obtained by moving average X_hat = (X - moving_mean) / torch.sqrt(moving_var + eps) else: assert len(X.shape) in (2, 4) if len(X.shape) == 2: # When using a fully-connected layer, calculate the mean and # variance on the feature dimension mean = X.mean(dim=0) var = ((X - mean) ** 2).mean(dim=0) else: # When using a two-dimensional convolutional layer, calculate the # mean and variance on the channel dimension (axis=1).
- `ctx_f1d2db847faaa16d40367e41`: ```{.python .input} def train(net, train_iter, valid_iter, num_epochs, lr, wd, devices, lr_period, lr_decay): trainer = gluon.Trainer(net.collect_params(), 'sgd', {'learning_rate': lr, 'momentum': 0.9, 'wd': wd}) num_batches, timer = len(train_iter), d2l.Timer() legend = ['train loss', 'train acc'] if valid_iter is not None: legend.append('valid acc') animator = d2l.Animator(xlabel='epoch', xlim=[1, num_epochs], legend=legend) for epoch in range(num_epochs): metric = d2l.Accumulator(3) if epoch > 0 and epoch % lr_period == 0: trainer.set_learning_rate(trainer.learning_rate * lr_decay) for i, (features, labels) in enumerate(train_iter): timer.start() l, acc = d2l.train_batch_ch13( net, features, labels.astype('float32'), loss, trainer, devices, d2l.split_batch) metric.add(l, acc, labels.shape[0]) timer.stop() if (i + 1) % (num_batches // 5) == 0 or i == num_batches - 1: animator.add(epoch + (i + 1) / num_batches, (metric[0] / metric[2], metric[1] / metric[2], None)) if valid_iter is not None: valid_acc = d2l.evaluate_accuracy_gpus(net, valid_iter, d2l.split_batch) animator.add(epoch + 1, (None, None, valid_acc)) measures = (f'train loss {metric[0] / metric[2]:.3f}, ' f'train acc {metric[1] / metric[2]:.3f}') if valid_iter is not None: measures += f', valid acc {valid_acc:.3f}' print(measures + f'\n{metric[2] * num_epochs / timer.sum():.1f}' f' examples/sec on {str(devices)}') ```
- `ctx_6ac1f400ae1b3195245dc883`: `num_dims`: # 2 for a fully-connected layer and 4 for a convolutional layer def __init__(self, num_features, num_dims, **kwargs): super().__init__(**kwargs) if num_dims == 2: shape = (1, num_features) else: shape = (1, num_features, 1, 1) # The scale parameter and the shift parameter (model parameters) are # initialized to 1 and 0, respectively self.gamma = self.params.get('gamma', shape=shape, init=init.One()) self.beta = self.params.get('beta', shape=shape, init=init.Zero()) # The variables that are not model parameters are initialized to 0 and 1 self.moving_mean = np.zeros(shape) self.moving_var = np.ones(shape) def forward(self, X): # If `X` is not on the main memory, copy `moving_mean` and # `moving_var` to the device where `X` is located if self.moving_mean.ctx != X.ctx: self.moving_mean = self.moving_mean.copyto(X.ctx) self.moving_var = self.moving_var.copyto(X.ctx) # Save the updated `moving_mean` and `moving_var` Y, self.moving_mean, self.moving_var = batch_norm( X, self.gamma.data(), self.beta.data(), self.moving_mean, self.moving_var, eps=1e-12, momentum=0.9) return Y ```

### Contrastive contexts

- `ctxx_7fd22e3f605db0d533d0053f`: Synthetic: The ball’s momentum increased after the collision, which is a physics sense unrelated to optimization.

### Definition evidence

- `ctx_d437426b9a49d27a6fb2a2c3`: It decreases the smoothness of the momentum, the exponentially weighted moving average of past gradients, to take care of the rapid changing gradients because the generator and the discriminator fight with each other.
- `ctx_3630463c4fd1b1974674bd51`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```
- `ctx_06f4771cf594f1bbed3246e8`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(dim=(0, 2, 3), keepdim=True) var = ((X - mean) ** 2).mean(dim=(0, 2, 3), keepdim=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / torch.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean.data, moving_var.data ```

### Part-of-speech evidence

- `ctx_8fa7f6c2ca736e617dfa8130`: ```toc :maxdepth: 2 optimization-intro convexity gd sgd minibatch-sgd momentum adagrad rmsprop adadelta adam lr-scheduler ```
- `ctx_d437426b9a49d27a6fb2a2c3`: It decreases the smoothness of the momentum, the exponentially weighted moving average of past gradients, to take care of the rapid changing gradients because the generator and the discriminator fight with each other.

## 6. MSE

- `sense_id`: `d2lce_ceb82e896665f8c0cd942ed6`
- Split: `development`
- Model definition: Mean squared error; a non-negative metric or loss equal to the average squared difference between an estimate or prediction and the true value.
- Model POS: `symbol`

### Primary contexts

- `ctx_a9382217a06a988f0ecb9234`: $$\mathrm{MSE} (\hat{\theta}_n, \theta) = E[(\hat{\theta}_n - \theta)^2].$$ :eqlabel:`eq_mse_est`
- `ctx_5df9fbccc96715edeb610c55`: Perhaps the simplest metric used to evaluate estimators is the *mean squared error (MSE)* (or $l_2$ loss) of an estimator can be defined as
- `ctx_1a29813f7324a6438bb8baa2`: $$ \begin{aligned} \mathrm{MSE} (\hat{\theta}_n, \theta) &= E[(\hat{\theta}_n - \theta)^2] \\ &= E[(\hat{\theta}_n)^2] + E[\theta^2] - 2E[\hat{\theta}_n\theta] \\ &= \mathrm{Var} [\hat{\theta}_n] + E[\hat{\theta}_n]^2 + \mathrm{Var} [\theta] + E[\theta]^2 - 2E[\hat{\theta}_n]E[\theta] \\ &= (E[\hat{\theta}_n] - E[\theta])^2 + \mathrm{Var} [\hat{\theta}_n] + \mathrm{Var} [\theta] \\ &= (E[\hat{\theta}_n - \theta])^2 + \mathrm{Var} [\hat{\theta}_n] + \mathrm{Var} [\theta] \\ &= (\mathrm{bias} [\hat{\theta}_n])^2 + \mathrm{Var} (\hat{\theta}_n) + \mathrm{Var} [\theta].\\ \end{aligned} $$
- `ctx_fdf0e7090cf0502e217b65eb`: MSE is always non-negative.
- `ctx_426bea20b9dba9336b04c813`: ```{.python .input} # Statistical bias def stat_bias(true_theta, est_theta): return(np.mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(np.mean(np.square(data - true_theta))) ```

### Backup contexts

- `ctx_bc89daf7fd2f4eb40d457f44`: The MSE provides a natural metric, but we can easily imagine multiple different phenomena that might make it large.
- `ctx_591781cd7583666007c98134`: To learn the FM model, we can use the MSE loss for regression task, the cross-entropy loss for classification tasks, and the BPR loss for ranking task.

### Contrastive contexts

- `ctxx_554a2bbe1b9e303caac14fab`: Synthetic: In a company dashboard, MSE could be an internal project code, not mean squared error.

### Definition evidence

- `ctx_5df9fbccc96715edeb610c55`: Perhaps the simplest metric used to evaluate estimators is the *mean squared error (MSE)* (or $l_2$ loss) of an estimator can be defined as
- `ctx_a9382217a06a988f0ecb9234`: $$\mathrm{MSE} (\hat{\theta}_n, \theta) = E[(\hat{\theta}_n - \theta)^2].$$ :eqlabel:`eq_mse_est`
- `ctx_fdf0e7090cf0502e217b65eb`: MSE is always non-negative.
- `ctx_426bea20b9dba9336b04c813`: ```{.python .input} # Statistical bias def stat_bias(true_theta, est_theta): return(np.mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(np.mean(np.square(data - true_theta))) ```

### Part-of-speech evidence

- `ctx_a9382217a06a988f0ecb9234`: $$\mathrm{MSE} (\hat{\theta}_n, \theta) = E[(\hat{\theta}_n - \theta)^2].$$ :eqlabel:`eq_mse_est`
- `ctx_fdf0e7090cf0502e217b65eb`: MSE is always non-negative.

## 7. multi-GPU training

- `sense_id`: `d2lce_6898a7f7f35ca368f75fda48`
- Split: `development`
- Model definition: Training a model using multiple GPUs, typically by splitting work and coordinating gradients or parameters across devices.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_9d1a3070565f618918c563b1`: ### Multi-GPU Training
- `ctx_27e6509f7df6da2429702955`: In what follows we will use a toy network to illustrate multi-GPU training.
- `ctx_b75db9e35adbaaf1637e9f5b`: Now we can implement [**multi-GPU training on a single minibatch**].
- `ctx_e3dc582632a5a667da04879d`: ```{.python .input} def train(num_gpus, batch_size, lr): train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size) devices = [d2l.try_gpu(i) for i in range(num_gpus)] # Copy model parameters to `num_gpus` GPUs device_params = [get_params(params, d) for d in devices] num_epochs = 10 animator = d2l.Animator('epoch', 'test acc', xlim=[1, num_epochs]) timer = d2l.Timer() for epoch in range(num_epochs): timer.start() for X, y in train_iter: # Perform multi-GPU training for a single minibatch train_batch(X, y, device_params, devices, lr) npx.waitall() timer.stop() # Evaluate the model on GPU 0 animator.add(epoch + 1, (d2l.evaluate_accuracy_gpu( lambda x: lenet(x, device_params[0]), test_iter, devices[0]),)) print(f'test acc: {animator.Y[0][-1]:.2f}, {timer.avg():.1f} sec/epoch ' f'on {str(devices)}') ```
- `ctx_dd876433a4a31b49da5e3474`: For efficient multi-GPU training we need two basic operations.

### Backup contexts

- `ctx_d06cbf1985e80a5cb41f32fc`: ```{.python .input} #@tab pytorch def train(num_gpus, batch_size, lr): train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size) devices = [d2l.try_gpu(i) for i in range(num_gpus)] # Copy model parameters to `num_gpus` GPUs device_params = [get_params(params, d) for d in devices] num_epochs = 10 animator = d2l.Animator('epoch', 'test acc', xlim=[1, num_epochs]) timer = d2l.Timer() for epoch in range(num_epochs): timer.start() for X, y in train_iter: # Perform multi-GPU training for a single minibatch train_batch(X, y, device_params, devices, lr) torch.cuda.synchronize() timer.stop() # Evaluate the model on GPU 0 animator.add(epoch + 1, (d2l.evaluate_accuracy_gpu( lambda x: lenet(x, device_params[0]), test_iter, devices[0]),)) print(f'test acc: {animator.Y[0][-1]:.2f}, {timer.avg():.1f} sec/epoch ' f'on {str(devices)}') ```
- `ctx_a790a4f33d4d1ca57797120f`: Right: a variant of multi-GPU training: (1) we compute loss and gradient, (2) all gradients are aggregated on one GPU, (3) parameter update happens and the parameters are re-distributed to all GPUs.](../img/ps.svg) :label:`fig_parameterserver`
- `ctx_190c6414d9d03e42a057ce97`: Unfortunately there is no meaningful speedup to be gained here: the model is simply too small; moreover we only have a small dataset, where our slightly unsophisticated approach to implementing multi-GPU training suffered from significant Python overhead.

### Contrastive contexts

- `ctxx_04d9704fff4fcd51f6f64b7c`: Synthetic: The workshop offered multi-GPU training for new lab technicians learning hardware maintenance.

### Definition evidence

- `ctx_dd876433a4a31b49da5e3474`: For efficient multi-GPU training we need two basic operations.
- `ctx_b75db9e35adbaaf1637e9f5b`: Now we can implement [**multi-GPU training on a single minibatch**].
- `ctx_a790a4f33d4d1ca57797120f`: Right: a variant of multi-GPU training: (1) we compute loss and gradient, (2) all gradients are aggregated on one GPU, (3) parameter update happens and the parameters are re-distributed to all GPUs.](../img/ps.svg) :label:`fig_parameterserver`

### Part-of-speech evidence

- `ctx_27e6509f7df6da2429702955`: In what follows we will use a toy network to illustrate multi-GPU training.
- `ctx_9d1a3070565f618918c563b1`: ### Multi-GPU Training
- `ctx_dd876433a4a31b49da5e3474`: For efficient multi-GPU training we need two basic operations.

## 8. multiple channels

- `sense_id`: `d2lce_ccf7d0a5109d86ee76a75b9c`
- Split: `development`
- Model definition: more than one channel in data or a model, such as multiple input, output, or color channels in convolutional networks.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_516a4df8d34c7a0c4415302b`: Being more general, :eqref:`eq_conv-layer-channels` is the definition of a convolutional layer for multiple channels, where $\mathsf{V}$ is a kernel or filter of the layer.
- `ctx_7a827358f51118bb50e2b2a8`: While we have described the multiple channels that comprise each image (e.g., color images have the standard RGB channels to indicate the amount of red, green and blue) and convolutional layers for multiple channels in :numref:`subsec_why-conv-channels`, until now, we simplified all of our numerical examples by working with just a single input and a single output channel.
- `ctx_3972c87ed9f0cc305dbef415`: When the input data contain multiple channels, we need to construct a convolution kernel with the same number of input channels as the input data, so that it can perform cross-correlation with the input data.
- `ctx_017659fee16b4b1352f9f1b5`: To support multiple channels in both inputs ($\mathsf{X}$) and hidden representations ($\mathsf{H}$), we can add a fourth coordinate to $\mathsf{V}$: $[\mathsf{V}]_{a, b, c, d}$.
- `ctx_3ca9380a219c00402d68c678`: For any one-dimensional input with multiple channels, the convolution kernel needs to have the same number of input channels.

### Backup contexts

- `ctx_7c6a965613332587c6fca111`: ## [**Padding, Strides, and Multiple Channels**]
- `ctx_54f8c3cb816277ace430df97`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.

### Contrastive contexts

- `ctx_ba2a299168416499932ae161`: Typically pairs of memory modules are used to allow for multiple channels.

### Definition evidence

- `ctx_7a827358f51118bb50e2b2a8`: While we have described the multiple channels that comprise each image (e.g., color images have the standard RGB channels to indicate the amount of red, green and blue) and convolutional layers for multiple channels in :numref:`subsec_why-conv-channels`, until now, we simplified all of our numerical examples by working with just a single input and a single output channel.
- `ctx_3972c87ed9f0cc305dbef415`: When the input data contain multiple channels, we need to construct a convolution kernel with the same number of input channels as the input data, so that it can perform cross-correlation with the input data.
- `ctx_516a4df8d34c7a0c4415302b`: Being more general, :eqref:`eq_conv-layer-channels` is the definition of a convolutional layer for multiple channels, where $\mathsf{V}$ is a kernel or filter of the layer.

### Part-of-speech evidence

- `ctx_54f8c3cb816277ace430df97`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_3ca9380a219c00402d68c678`: For any one-dimensional input with multiple channels, the convolution kernel needs to have the same number of input channels.
- `ctx_3972c87ed9f0cc305dbef415`: When the input data contain multiple channels, we need to construct a convolution kernel with the same number of input channels as the input data, so that it can perform cross-correlation with the input data.

## 9. natural language processing

- `sense_id`: `d2lce_609638f74bc5b32d32469bbc`
- Split: `development`
- Model definition: The field of methods for enabling computers to process and work with human language.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_957202f18613badf579e7070`: # Natural Language Processing: Applications :label:`chap_nlp_app`
- `ctx_db7608ae418801ae81a4cf5c`: In just the past five years, deep learning has taken the world by surprise, driving rapid progress in such diverse fields as computer vision, natural language processing, automatic speech recognition, reinforcement learning, and biomedical informatics.
- `ctx_e596c2db961d7da1d125a384`: We have used RNNs to design language models, which are key to natural language processing.
- `ctx_7ce4cad6244e99bb3c578b48`: Despite its pervasive applications in computer vision, batch normalization is usually empirically less effective than layer normalization in natural language processing tasks, whose inputs are often variable-length sequences.
- `ctx_3a53b83e0b10536984dc1341`: # Natural Language Processing: Pretraining :label:`chap_nlp_pretrain`

### Backup contexts

- `ctx_21a455b6628cf522b79a5f32`: In this book, we will teach you the fundamentals of machine learning, and focus in particular on *deep learning*, a powerful set of techniques driving innovations in areas as diverse as computer vision, natural language processing, healthcare, and genomics.
- `ctx_4606fac8f850444f6ad9ec05`: * Language models are key to natural language processing.
- `ctx_f89df5c093f024523f393168`: Similar architectures in which layers are arranged in various repeating patterns are now ubiquitous in other domains, including natural language processing and speech.

### Contrastive contexts

- `ctxx_d87f28982cf81a72d04a6b0d`: Synthetic: The phrase natural language processing here refers to a computing field, not to a person informally polishing everyday speech.

### Definition evidence

- `ctx_db7608ae418801ae81a4cf5c`: In just the past five years, deep learning has taken the world by surprise, driving rapid progress in such diverse fields as computer vision, natural language processing, automatic speech recognition, reinforcement learning, and biomedical informatics.
- `ctx_21a455b6628cf522b79a5f32`: In this book, we will teach you the fundamentals of machine learning, and focus in particular on *deep learning*, a powerful set of techniques driving innovations in areas as diverse as computer vision, natural language processing, healthcare, and genomics.
- `ctx_4606fac8f850444f6ad9ec05`: * Language models are key to natural language processing.
- `ctx_957202f18613badf579e7070`: # Natural Language Processing: Applications :label:`chap_nlp_app`

### Part-of-speech evidence

- `ctx_db7608ae418801ae81a4cf5c`: In just the past five years, deep learning has taken the world by surprise, driving rapid progress in such diverse fields as computer vision, natural language processing, automatic speech recognition, reinforcement learning, and biomedical informatics.
- `ctx_3a53b83e0b10536984dc1341`: # Natural Language Processing: Pretraining :label:`chap_nlp_pretrain`
- `ctx_957202f18613badf579e7070`: # Natural Language Processing: Applications :label:`chap_nlp_app`

## 10. noise words

- `sense_id`: `d2lce_5c270f3b3ebe4f0059649e18`
- Split: `development`
- Model definition: words sampled from a predefined distribution as negative examples, excluding the true context words
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c2cff6800a035ffeaff0c52d`: For this event involving $w_o$, from a predefined distribution $P(w)$ sample $K$ *noise words* that are not from this context window.
- `ctx_20ec226227eb3377a4675027`: The computational cost for training is linearly dependent on the number of noise words at each step.
- `ctx_6c68ff8f58bf4e101cf66d9f`: To sample noise words according to a predefined distribution, we define the following `RandomGenerator` class, where the (possibly unnormalized) sampling distribution is passed via the argument `sampling_weights`.
- `ctx_e871cab6ee40803901bb1ec7`: For a pair of center word and context word, we randomly sample `K` (5 in the experiment) noise words.
- `ctx_8ee1967b4d544ce02f2d1be9`: (index 0 is the # excluded unknown token) in the vocabulary sampling_weights = [counter[vocab.to_tokens(i)]**0.75 for i in range(1, len(vocab))] all_negatives, generator = [], RandomGenerator(sampling_weights) for contexts in all_contexts: negatives = [] while len(negatives) < len(contexts) * K: neg = generator.draw() # Noise words cannot be context words if neg not in contexts: negatives.append(neg) all_negatives.append(negatives) return all_negatives all_negatives = get_negatives(all_contexts, vocab, counter, 5) ```

### Backup contexts

- `ctx_bd85a6abb1abf1675645f0ec`: ```{.python .input} #@tab all #@save def get_negatives(all_contexts, vocab, counter, K): """Return noise words in negative sampling.""" # Sampling weights for words with indices 1, 2, ...
- `ctx_8a60b064bcb2036082395b15`: How can we sample noise words in negative sampling?
- `ctx_fad78fb3a08530724c4b2aef`: After all the center words together with their context words and sampled noise words are extracted, they will be transformed into minibatches of examples that can be iteratively loaded during training.

### Contrastive contexts

- `ctxx_ffaf1f7294086734a7ca9f06`: Synthetic: Here, noise words are sampled negative examples rather than merely messy or misspelled words in a corpus.

### Definition evidence

- `ctx_c2cff6800a035ffeaff0c52d`: For this event involving $w_o$, from a predefined distribution $P(w)$ sample $K$ *noise words* that are not from this context window.
- `ctx_6c68ff8f58bf4e101cf66d9f`: To sample noise words according to a predefined distribution, we define the following `RandomGenerator` class, where the (possibly unnormalized) sampling distribution is passed via the argument `sampling_weights`.
- `ctx_8ee1967b4d544ce02f2d1be9`: (index 0 is the # excluded unknown token) in the vocabulary sampling_weights = [counter[vocab.to_tokens(i)]**0.75 for i in range(1, len(vocab))] all_negatives, generator = [], RandomGenerator(sampling_weights) for contexts in all_contexts: negatives = [] while len(negatives) < len(contexts) * K: neg = generator.draw() # Noise words cannot be context words if neg not in contexts: negatives.append(neg) all_negatives.append(negatives) return all_negatives all_negatives = get_negatives(all_contexts, vocab, counter, 5) ```

### Part-of-speech evidence

- `ctx_c2cff6800a035ffeaff0c52d`: For this event involving $w_o$, from a predefined distribution $P(w)$ sample $K$ *noise words* that are not from this context window.
- `ctx_bd85a6abb1abf1675645f0ec`: ```{.python .input} #@tab all #@save def get_negatives(all_contexts, vocab, counter, K): """Return noise words in negative sampling.""" # Sampling weights for words with indices 1, 2, ...
