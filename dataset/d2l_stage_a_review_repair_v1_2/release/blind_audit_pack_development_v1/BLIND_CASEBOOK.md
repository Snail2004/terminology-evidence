# Development-only blind Stage A audit

## Adam

- `ctx_724a58cef32d03f9a90cc4d9`: ```{.python .input}
lr, num_epochs = 0.01, 5
trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr})
loss = gluon.loss.SoftmaxCrossEntropyLoss()
d2l.train_ch13(net, train_iter, test_iter, loss, trainer, num_epochs, devices)
```

- `ctx_c4effad022bd5e216d2eaf51`: ```{.python .input}
def train(net, train_iter, loss, epochs, lr):
    trainer = gluon.Trainer(net.collect_params(), 'adam',
                            {'learning_rate': lr})
    for epoch in range(epochs):
        for X, y in train_iter:
            with autograd.record():
                l = loss(net(X), y)
            l.backward()
            trainer.step(batch_size)
        print(f'epoch {epoch + 1}, '
              f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}')

net = get_net()
train(net, train_iter, loss, 5, 0.01)
```

```{.python .input}
#@tab pytorch
def train(net, train_iter, loss, epochs, lr):
    trainer = torch.optim.Adam(net.parameters(), lr)
    for epoch in range(epochs):
        for X, y in train_iter:
            trainer.zero_grad()
            l = loss(net(X), y)
            l.sum().backward()
            trainer.step()
        print(f'epoch {epoch + 1}, '
              f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}')

net = get_net()
train(net, train_iter, loss, 5, 0.01)
```

```{.python .input}
#@tab tensorflow
def train(net, train_iter, loss, epochs, lr):
    trainer = tf.keras.optimizers.Adam()
    for epoch in range(epochs):
        for X, y in train_iter:
            with tf.GradientTape() as g:
                out = net(X)
                l = loss(y, out)
                params = net.trainable_variables
                grads = g.gradient(l, params)
            trainer.apply_gradients(zip(grads, params))
        print(f'epoch {epoch + 1}, '
              f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}')

net = get_net()
train(net, train_iter, loss, 5, 0.01)
```

## Prediction

Since the training loss is small, we would expect our model to work well.

- `ctx_feb069ef1ecb8e58ef71c482`: Unlike in previous sections, [**our training functions
will rely on the Adam optimizer
(we will describe it in greater detail later)**].

- `ctx_5c812a90177b5b129b327432`: Indeed, anyone content with treating optimization as a black box device to minimize objective functions in a simple setting might well content oneself with the knowledge that there exists an array of incantations of such a procedure (with names such as "SGD" and "Adam").

- `ctx_4a985a7867b0862e601aa744`: This function gets all available GPUs, 
uses Adam as the optimization algorithm,
applies image augmentation to the training dataset,
and finally calls the `train_ch13` function just defined to train and evaluate the model.

- `ctx_3c4a7aaec02b50911df8c766`: ```{.python .input}
#@save
def train_seq2seq(net, data_iter, lr, num_epochs, tgt_vocab, device):
    """Train a model for sequence to sequence."""
    net.initialize(init.Xavier(), force_reinit=True, ctx=device)
    trainer = gluon.Trainer(net.collect_params(), 'adam',
                            {'learning_rate': lr})
    loss = MaskedSoftmaxCELoss()
    animator = d2l.Animator(xlabel='epoch', ylabel='loss',
                            xlim=[10, num_epochs])
    for epoch in range(num_epochs):
        timer = d2l.Timer()
        metric = d2l.Accumulator(2)  # Sum of training loss, no.

- `ctx_58c0a9351bd98055ea39a9a0`: ```{.python .input}
def train(net, data_iter, lr, num_epochs, device=d2l.try_gpu()):
    net.initialize(ctx=device, force_reinit=True)
    trainer = gluon.Trainer(net.collect_params(), 'adam',
                            {'learning_rate': lr})
    animator = d2l.Animator(xlabel='epoch', ylabel='loss',
                            xlim=[1, num_epochs])
    # Sum of normalized losses, no.

## fully-connected layers

- `ctx_8ce751d21f2cb72d502c47b8`: Note that each of the two fully-connected layers is an instance of the `Linear` class
which is itself a subclass of `Module`.

- `ctx_eafeb346f16534dd44c4414d`: ## Parameterization Cost of Fully-Connected Layers
:label:`subsec_parameterization-cost-fc-layers`

- `ctx_f4fa216c07f2cf0249eb37ca`: ```{.python .input}
#@tab mxnet, pytorch
tau = 4
features = d2l.zeros((T - tau, tau))
for i in range(tau):
    features[:, i] = x[i: T - tau + i]
labels = d2l.reshape(x[tau:], (-1, 1))
```

```{.python .input}
#@tab tensorflow
tau = 4
features = tf.Variable(d2l.zeros((T - tau, tau)))
for i in range(tau):
    features[:, i].assign(x[i: T - tau + i])
labels = d2l.reshape(x[tau:], (-1, 1))
```

```{.python .input}
#@tab all
batch_size, n_train = 16, 600
# Only the first `n_train` examples are used for training
train_iter = d2l.load_array((features[:n_train], labels[:n_train]),
                            batch_size, is_train=True)
```

Here we [**keep the architecture fairly simple:
just an MLP**] with two fully-connected layers, ReLU activation, and squared loss.

- `ctx_403adb70f5312a0fa35b95be`: The easiest way to do this is to stack
many fully-connected layers on top of each other.

- `ctx_faa4efe019d52f783381c40a`: # From Fully-Connected Layers to Convolutions
:label:`sec_why-conv`

- `ctx_1f4f955fd892e6791b4aeef3`: These two huge fully-connected layers produce model parameters of nearly 1 GB.

- `ctx_28b17b3a0950632e4ac5d1f9`: Therefore,
what sets attention mechanisms
apart from those fully-connected layers
or pooling layers
is the inclusion of the volitional cues.

- `ctx_58323905b57101ea133ca2d9`: The outputs of two gates
are given by two fully-connected layers
with a sigmoid activation function.

## in place

- `ctx_dd4385b29dac92b049208df2`: Typically, we will want to perform these updates *in place*.

- `ctx_25b94844ba885d1f978af59d`: In general, with activation functions in place,
it is no longer possible to collapse our MLP into a linear model:

- `ctx_b28630d61d9d7f640c9a5483`: Moreover, current purchase habits are often a result
of the recommendation algorithm currently in place,
but learning algorithms do not always take this detail into account.

- `ctx_51b702393d86c10055ec9803`: ```{.python .input}
%matplotlib inline
from d2l import mxnet as d2l
from mxnet import np, npx
npx.set_np()

def init_adadelta_states(feature_dim):
    s_w, s_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1)
    delta_w, delta_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1)
    return ((s_w, delta_w), (s_b, delta_b))

def adadelta(params, states, hyperparams):
    rho, eps = hyperparams['rho'], 1e-5
    for p, (s, delta) in zip(params, states):
        # In-place updates via [:]
        s[:] = rho * s + (1 - rho) * np.square(p.grad)
        g = (np.sqrt(delta + eps) / np.sqrt(s + eps)) * p.grad
        p[:] -= g
        delta[:] = rho * delta + (1 - rho) * g * g
```

- `ctx_f813489a437efb8e7e42d969`: If we do not update in place, other references will still point to
the old memory location, making it possible for parts of our code
to inadvertently reference stale parameters.

- `ctx_3d152d0258e0fc757b4f6fc6`: :begin_tab:`mxnet, pytorch`
Fortunately, (**performing in-place operations**) is easy.

- `ctx_3b646f556dedb3e0fad436ed`: Now that we have all of the parts in place,
we are ready to [**implement the main training loop.**]
It is crucial that you understand this code
because you will see nearly identical training loops
over and over again throughout your career in deep learning.

- `ctx_537ed43953ead18faf55b24e`: Also note that some functions are not supported in the `symbol` module (e.g.,  `asnumpy`) and operations in-place such as `a += b` and `a[:] = a + b` must be rewritten as `a = a + b`.

## CUDA

- `ctx_88d4ac7e32b65e492b2dbc3a`: If your computer has NVIDIA graphics cards and has installed [CUDA](https://developer.nvidia.com/cuda-downloads),
then you should install a GPU-enabled version.

- `ctx_6fcdbf49cf1b09495f5babfd`: ```{.python .input}
#@tab pytorch
with d2l.Benchmark():
    for _ in range(10):
        a = torch.randn(size=(1000, 1000), device=device)
        b = torch.mm(a, a)
    torch.cuda.synchronize(device)
```

- `ctx_7f3025aa974fb8d15e3804a4`: The code [cuda-convnet](https://code.google.com/archive/p/cuda-convnet/)
was good enough that for several years
it was the industry standard and powered
the first couple years of the deep learning boom.

- `ctx_d5e3c3872235604218a2a839`: Then, download the [NVIDIA driver and CUDA](https://developer.nvidia.com/cuda-downloads)
and follow the prompts to set the appropriate path.

- `ctx_df035bcc5db7501785c43a7e`: We now need to find out what version of CUDA you have installed.

- `ctx_f0c64b01d15f034d29c1d6ce`: Assume that you have installed CUDA 10.1,
then you can install with the following command:

- `ctx_dae4dda67205c6e9b5831f82`: You can check this by running `nvcc --version` 
or `cat /usr/local/cuda/version.txt`.

- `ctx_c8b662075f19ab652ddcc0b9`: Optionally: install CUDA or use an AMI with CUDA preinstalled.

## channels

- `ctx_e7ad2905fd773a830f6b4c43`: ```{.python .input}
%matplotlib inline
from d2l import mxnet as d2l
from mxnet import autograd, gluon, init, lr_scheduler, np, npx
from mxnet.gluon import nn
npx.set_np()

net = nn.HybridSequential()
net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'),
        nn.MaxPool2D(pool_size=2, strides=2),
        nn.Conv2D(channels=16, kernel_size=5, activation='relu'),
        nn.MaxPool2D(pool_size=2, strides=2),
        nn.Dense(120, activation='relu'),
        nn.Dense(84, activation='relu'),
        nn.Dense(10))
net.hybridize()
loss = gluon.loss.SoftmaxCrossEntropyLoss()
device = d2l.try_gpu()

batch_size = 256
train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size)

# The code is almost identical to `d2l.train_ch6` defined in the 
# lenet section of chapter convolutional neural networks
def train(net, train_iter, test_iter, num_epochs, loss, trainer, device):
    net.initialize(force_reinit=True, ctx=device, init=init.Xavier())
    animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs],
                            legend=['train loss', 'train acc', 'test acc'])
    for epoch in range(num_epochs):
        metric = d2l.Accumulator(3)  # train_loss, train_acc, num_examples
        for i, (X, y) in enumerate(train_iter):
            X, y = X.as_in_ctx(device), y.as_in_ctx(device)
            with autograd.record():
                y_hat = net(X)
                l = loss(y_hat, y)
            l.backward()
            trainer.step(X.shape[0])
            metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0])
            train_loss = metric[0] / metric[2]
            train_acc = metric[1] / metric[2]
            if (i + 1) % 50 == 0:
                animator.add(epoch + i / len(train_iter),
                             (train_loss, train_acc, None))
        test_acc = d2l.evaluate_accuracy_gpu(net, test_iter)
        animator.add(epoch + 1, (None, None, test_acc))
    print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, '
          f'test acc {test_acc:.3f}')
```

- `ctx_93be4d86c465d785ac0a0ec1`: For now,
we only need to know that
since the sequence length is $n$,
the numbers of input and output channels are both $d$,
the computational complexity of the convolutional layer is $\mathcal{O}(knd^2)$.

- `ctx_79213e2c4e36b995f90f0b30`: A $200\times 200$ color photograph would consist of $200\times200\times3=120000$
numerical values, corresponding to the brightness
of the red, green, and blue channels for each spatial location.

- `ctx_4bb23f20ff0fa67bc6c1be83`: Tensors will become more important when we start working with images,
 which arrive as $n$-dimensional arrays with 3 axes corresponding to the height, width, and a *channel* axis for stacking the color channels (red, green, and blue).

- `ctx_50b02cc418dce008fb37b2ea`: Note that the dataset consists of grayscale images, whose number of channels is 1.

- `ctx_e066da075985b1450c0cd804`: These include the convolutional layers themselves,
nitty-gritty details including padding and stride,
the pooling layers used to aggregate information
across adjacent spatial regions,
the use of multiple channels  at each layer,
and a careful discussion of the structure of modern architectures.

- `ctx_e7437fb0f0bdad9c3645e83b`: Moreover, AlexNet has ten times more convolution channels than LeNet.

## bit

- `ctx_5717eff884f463a81a21a526`: Within RNNs this is a bit trickier, since we first need to decide how and where to add extra nonlinearity.

- `ctx_6bf5da537a25d356b2e5e0ac`: You might think of your neural network
as being a bit like the C programming language.

- `ctx_decede697ad47b1366644611`: ```{.python .input}
#@tab tensorflow
# tf.keras behaves a bit differently.

- `ctx_bc735116b032003b647bf1d5`: Determining which way to move each parameter at each step of an algorithm
requires a little bit of calculus, which will be briefly introduced.

- `ctx_30cb9519a863d7ebe60dd4e0`: To make some progress we need a bit of mathematics.

- `ctx_48fb92c20348628ff3c83349`: In this section,
we will delve a bit more deeply
into the details of backpropagation for sequence models and why (and how) the mathematics works.

- `ctx_a08fef290a47362d440d8409`: Since the softmax and the corresponding loss are so common,
it is worth understanding a bit better how it is computed.

- `ctx_296377e3411a5f06ef38c871`: Reality is a bit more complicated than the most naive interpretations of this intuition since representations are not learned independent but are rather optimized to be jointly useful.

## contexts

- `ctx_ad827e72cc1bfa17dfbdadef`: Note that the word "dimension" tends to get overloaded
in these contexts and this tends to confuse people.

- `ctx_c40b35f077d50245b79ff9f6`: Dot products are useful in a wide range of contexts.

- `ctx_d84189ac843db03cf9cfdc82`: * Once defined, custom layers can be invoked in arbitrary contexts and architectures.

- `ctx_85c155993547287904ebb77e`: For text,
we can train models 
to "fill in the blanks"
by predicting randomly masked words
using their surrounding words (contexts)
in big corpora without any labeling effort :cite:`Devlin.Chang.Lee.ea.2018`!

- `ctx_938a7ef4c625c0fdaa81a1ed`: It is quite difficult to adjust such models to additional contexts,
whereas, deep learning based language models are well suited to
take this into account.

- `ctx_8d01d5c8ba8b22afa8297f86`: For example, the word "bank" has different meanings in contexts “i went to the bank to deposit cash” and “i went to the bank to sit down”.

- `ctx_a703c64944c46d8745b2290e`: Thus, many more recent pretraining models adapt representation of the same token
to different contexts.

- `ctx_a1d30a054504f29bcb20b25b`: ### Cosine Similarity
In ML contexts where the angle is employed
to measure the closeness of two vectors,
practitioners adopt the term *cosine similarity*
to refer to the portion
$$
\cos(\theta) = \frac{\mathbf{v}\cdot\mathbf{w}}{\|\mathbf{v}\|\|\mathbf{w}\|}.

## forward propagation

- `ctx_e3686abbec23ffeb19f2dfef`: Their idea, called *dropout*, involves
injecting noise while computing
each internal layer during forward propagation,
and it has become a standard technique
for training neural networks.

- `ctx_4f8a2ab7305e5e99ddf848a4`: * Generate predictions by calling `net(X)` and calculate the loss `l` (the forward propagation).

- `ctx_18f5c52c0937b1589d8a6782`: Any subclass of it must define a forward propagation function
that transforms its input into output
and must store any necessary parameters.

- `ctx_072a83737808daf5abee6df6`: The forward propagation function
calls the `corr2d` function and adds the bias.

- `ctx_d126e74d5ab3240a96363756`: We will describe deep architectures with
multiple hidden layers,
and discuss the bidirectional design
with both forward and backward recurrent computations.

- `ctx_041277e59fc9e3b32469b673`: ```{.python .input}
class NWKernelRegression(nn.Block):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.params.get('w', shape=(1,))

    def forward(self, queries, keys, values):
        # Shape of the output `queries` and `attention_weights`:
        # (no.

## BatchNorm

- `ctx_2a4b835e03acf05a36784e49`: ```{.python .input}
def down_sample_blk(num_channels):
    blk = nn.Sequential()
    for _ in range(2):
        blk.add(nn.Conv2D(num_channels, kernel_size=3, padding=1),
                nn.BatchNorm(in_channels=num_channels),
                nn.Activation('relu'))
    blk.add(nn.MaxPool2D(2))
    return blk
```

- `ctx_97626c8a07aa5d9bfd5cd128`: ```{.python .input}
#@save
def resnet18(num_classes):
    """A slightly modified ResNet-18 model."""
    def resnet_block(num_channels, num_residuals, first_block=False):
        blk = nn.Sequential()
        for i in range(num_residuals):
            if i == 0 and not first_block:
                blk.add(d2l.Residual(
                    num_channels, use_1x1conv=True, strides=2))
            else:
                blk.add(d2l.Residual(num_channels))
        return blk

    net = nn.Sequential()
    # This model uses a smaller convolution kernel, stride, and padding and
    # removes the maximum pooling layer
    net.add(nn.Conv2D(64, kernel_size=3, strides=1, padding=1),
            nn.BatchNorm(), nn.Activation('relu'))
    net.add(resnet_block(64, 2, first_block=True),
            resnet_block(128, 2),
            resnet_block(256, 2),
            resnet_block(512, 2))
    net.add(nn.GlobalAvgPool2D(), nn.Dense(num_classes))
    return net
```

- `ctx_a112ae80926b023797d45e91`: ```{.python .input}
class G_block(nn.Block):
    def __init__(self, channels, kernel_size=4,
                 strides=2, padding=1, **kwargs):
        super(G_block, self).__init__(**kwargs)
        self.conv2d_trans = nn.Conv2DTranspose(
            channels, kernel_size, strides, padding, use_bias=False)
        self.batch_norm = nn.BatchNorm()
        self.activation = nn.Activation('relu')

    def forward(self, X):
        return self.activation(self.batch_norm(self.conv2d_trans(X)))
```

- `ctx_8f8f50278fcee237079dc232`: We can now [**create a proper `BatchNorm` layer.**]
Our layer will maintain proper parameters
for scale `gamma` and shift `beta`,
both of which will be updated in the course of training.

- `ctx_2bba7bfd16dd89a39a9179f1`: ```{.python .input}
ln = nn.LayerNorm()
ln.initialize()
bn = nn.BatchNorm()
bn.initialize()
X = d2l.tensor([[1, 2], [2, 3]])
# Compute mean and variance from `X` in the training mode
with autograd.record():
    print('layer norm:', ln(X), '\nbatch norm:', bn(X))
```

- `ctx_cc13b838430cc6b65f7256c9`: ```{.python .input}
#@tab tensorflow
class BatchNorm(tf.keras.layers.Layer):
    def __init__(self, **kwargs):
        super(BatchNorm, self).__init__(**kwargs)

    def build(self, input_shape):
        weight_shape = [input_shape[-1], ]
        # The scale parameter and the shift parameter (model parameters) are
        # initialized to 1 and 0, respectively
        self.gamma = self.add_weight(name='gamma', shape=weight_shape,
            initializer=tf.initializers.ones, trainable=True)
        self.beta = self.add_weight(name='beta', shape=weight_shape,
            initializer=tf.initializers.zeros, trainable=True)
        # The variables that are not model parameters are initialized to 0
        self.moving_mean = self.add_weight(name='moving_mean',
            shape=weight_shape, initializer=tf.initializers.zeros,
            trainable=False)
        self.moving_variance = self.add_weight(name='moving_variance',
            shape=weight_shape, initializer=tf.initializers.ones,
            trainable=False)
        super(BatchNorm, self).build(input_shape)

    def assign_moving_average(self, variable, value):
        momentum = 0.9
        delta = variable * momentum + value * (1 - momentum)
        return variable.assign(delta)

    @tf.function
    def call(self, inputs, training):
        if training:
            axes = list(range(len(inputs.shape) - 1))
            batch_mean = tf.reduce_mean(inputs, axes, keepdims=True)
            batch_variance = tf.reduce_mean(tf.math.squared_difference(
                inputs, tf.stop_gradient(batch_mean)), axes, keepdims=True)
            batch_mean = tf.squeeze(batch_mean, axes)
            batch_variance = tf.squeeze(batch_variance, axes)
            mean_update = self.assign_moving_average(
                self.moving_mean, batch_mean)
            variance_update = self.assign_moving_average(
                self.moving_variance, batch_variance)
            self.add_update(mean_update)
            self.add_update(variance_update)
            mean, variance = batch_mean, batch_variance
        else:
            mean, variance = self.moving_mean, self.moving_variance
        output = batch_norm(inputs, moving_mean=mean, moving_var=variance,
            beta=self.beta, gamma=self.gamma, eps=1e-5)
        return output
```

- `ctx_5799f6d95cc38b1ae654394a`: ```{.python .input}
class BatchNorm(nn.Block):
    # `num_features`: the number of outputs for a fully-connected layer
    # or the number of output channels for a convolutional layer.

- `ctx_a70b42d220709405815636f8`: ```{.python .input}
#@tab pytorch
class BatchNorm(nn.Module):
    # `num_features`: the number of outputs for a fully-connected layer
    # or the number of output channels for a convolutional layer.

## Generator

- `ctx_2cc55c7c27ecd856fe623eec`: This allows us to improve the data generator until it generates something that resembles the real data.

- `ctx_ce5770ebbcecab9cd14b31d1`: At their heart, GANs rely on the idea that a data generator is good if we cannot tell fake data apart from real data.

- `ctx_111ebd3664347c4b99a35b2e`: We call this the generator network.

- `ctx_545710fbceae0d3428fd3a00`: The discriminator is a binary classifier to distinguish if the input $x$ is real (from real data) or fake (from the generator).

- `ctx_33e923407e067945b2c17e33`: The generator network attempts to fool the discriminator network.

- `ctx_2aca2894517926700f9e34d1`: This information, in turn is used to improve the generator network, and so on.

## input gate

- `ctx_a7c81a70b68bbf602ecfbeab`: Similarly,
in LSTMs we have two dedicated gates for such purposes: the input gate $\mathbf{I}_t$ governs how much we take new data into account via $\tilde{\mathbf{C}}_t$ and the forget gate $\mathbf{F}_t$ addresses how much of the old memory cell content $\mathbf{C}_{t-1} \in \mathbb{R}^{n \times h}$ we retain.

- `ctx_b2ecc4429423fc36a19369d3`: ```{.python .input}
def get_lstm_params(vocab_size, num_hiddens, device):
    num_inputs = num_outputs = vocab_size

    def normal(shape):
        return np.random.normal(scale=0.01, size=shape, ctx=device)

    def three():
        return (normal((num_inputs, num_hiddens)),
                normal((num_hiddens, num_hiddens)),
                np.zeros(num_hiddens, ctx=device))

    W_xi, W_hi, b_i = three()  # Input gate parameters
    W_xf, W_hf, b_f = three()  # Forget gate parameters
    W_xo, W_ho, b_o = three()  # Output gate parameters
    W_xc, W_hc, b_c = three()  # Candidate memory cell parameters
    # Output layer parameters
    W_hq = normal((num_hiddens, num_outputs))
    b_q = np.zeros(num_outputs, ctx=device)
    # Attach gradients
    params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc,
              b_c, W_hq, b_q]
    for param in params:
        param.attach_grad()
    return params
```

- `ctx_d97ae77a3b700998ac63cadd`: ```{.python .input}
#@tab pytorch
def get_lstm_params(vocab_size, num_hiddens, device):
    num_inputs = num_outputs = vocab_size

    def normal(shape):
        return torch.randn(size=shape, device=device)*0.01

    def three():
        return (normal((num_inputs, num_hiddens)),
                normal((num_hiddens, num_hiddens)),
                d2l.zeros(num_hiddens, device=device))

    W_xi, W_hi, b_i = three()  # Input gate parameters
    W_xf, W_hf, b_f = three()  # Forget gate parameters
    W_xo, W_ho, b_o = three()  # Output gate parameters
    W_xc, W_hc, b_c = three()  # Candidate memory cell parameters
    # Output layer parameters
    W_hq = normal((num_hiddens, num_outputs))
    b_q = d2l.zeros(num_outputs, device=device)
    # Attach gradients
    params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc,
              b_c, W_hq, b_q]
    for param in params:
        param.requires_grad_(True)
    return params
```

- `ctx_ef08148c1866b77ae7d4ed7f`: We refer to this as the *input gate*.

- `ctx_55d21390aec0ff7a7336858a`: Correspondingly, the gates at time step $t$
are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.

- `ctx_6c0d6d0d558005aaf9be6fc3`: If the forget gate is always approximately 1 and the input gate is always approximately 0, the past memory cells $\mathbf{C}_{t-1}$ will be saved over time and passed to the current time step.

- `ctx_6a19e08d950ca7bef8fb4c89`: ### Input Gate, Forget Gate, and Output Gate

- `ctx_9ee60265b7c99b18fa9a46f2`: ![Computing the input gate, the forget gate, and the output gate in an LSTM model.](../img/lstm-0.svg)
:label:`lstm_0`

## Caser

- `ctx_a07c31185d557a9cba947172`: The goal of Caser is to recommend item by considering user general tastes as well as short-term intention.

- `ctx_27b2e4936143566a8ca5e421`: The architecture of Caser is shown below:

- `ctx_26a6365155d601f3009c3236`: ![Illustration of the Caser Model](../img/rec-caser.svg)

- `ctx_c48fb3f822f811ccbb8750b6`: The model we will introduce, Caser :cite:`Tang.Wang.2018`, short for convolutional sequence embedding recommendation model, adopts convolutional neural networks capture the dynamic pattern influences of users' recent activities.

- `ctx_efedd61e884ed0fdc81eff25`: The main component of Caser consists of a horizontal convolutional network and a vertical convolutional network, aiming to uncover the union-level and point-level sequence patterns, respectively.

- `ctx_b400985b05d02328a55f0c52`: ```{.python .input  n=4}
class Caser(nn.Block):
    def __init__(self, num_factors, num_users, num_items, L=5, d=16,
                 d_prime=4, drop_ratio=0.05, **kwargs):
        super(Caser, self).__init__(**kwargs)
        self.P = nn.Embedding(num_users, num_factors)
        self.Q = nn.Embedding(num_items, num_factors)
        self.d_prime, self.d = d_prime, d
        # Vertical convolution layer
        self.conv_v = nn.Conv2D(d_prime, (L, 1), in_channels=1)
        # Horizontal convolution layer
        h = [i + 1 for i in range(L)]
        self.conv_h, self.max_pool = nn.Sequential(), nn.Sequential()
        for i in h:
            self.conv_h.add(nn.Conv2D(d, (i, num_factors), in_channels=1))
            self.max_pool.add(nn.MaxPool1D(L - i + 1))
        # Fully-connected layer
        self.fc1_dim_v, self.fc1_dim_h = d_prime * num_factors, d * len(h)
        self.fc = nn.Dense(in_units=d_prime * num_factors + d * L,
                           activation='relu', units=num_factors)
        self.Q_prime = nn.Embedding(num_items, num_factors * 2)
        self.b = nn.Embedding(num_items, 1)
        self.dropout = nn.Dropout(drop_ratio)

    def forward(self, user_id, seq, item_id):
        item_embs = np.expand_dims(self.Q(seq), 1)
        user_emb = self.P(user_id)
        out, out_h, out_v, out_hs = None, None, None, []
        if self.d_prime:
            out_v = self.conv_v(item_embs)
            out_v = out_v.reshape(out_v.shape[0], self.fc1_dim_v)
        if self.d:
            for conv, maxp in zip(self.conv_h, self.max_pool):
                conv_out = np.squeeze(npx.relu(conv(item_embs)), axis=3)
                t = maxp(conv_out)
                pool_out = np.squeeze(t, axis=2)
                out_hs.append(pool_out)
            out_h = np.concatenate(out_hs, axis=1)
        out = np.concatenate([out_v, out_h], axis=1)
        z = self.fc(self.dropout(out))
        x = np.concatenate([z, user_emb], axis=1)
        q_prime_i = np.squeeze(self.Q_prime(item_id))
        b = np.squeeze(self.b(item_id))
        res = (x * q_prime_i).sum(1) + b
        return res
```

- `ctx_89f8785f0d47f0a72eb28a8d`: ## Model Implementation
The following code implements the Caser model.

- `ctx_f3d1cfd65cb60c18b67864a5`: ```{.python .input  n=7}
devices = d2l.try_all_gpus()
net = Caser(10, num_users, num_items, L)
net.initialize(ctx=devices, force_reinit=True, init=mx.init.Normal(0.01))
lr, num_epochs, wd, optimizer = 0.04, 8, 1e-5, 'adam'
loss = d2l.BPRLoss()
trainer = gluon.Trainer(net.collect_params(), optimizer,
                        {"learning_rate": lr, 'wd': wd})

d2l.train_ranking(net, train_iter, test_iter, loss, trainer, test_seq_iter,
                  num_users, num_items, num_epochs, devices,
                  d2l.evaluate_ranking, candidates, eval_step=1)
```

## convolutional neural networks

- `ctx_654cb542dec605b7a07f0d38`: We exploit this versatility
throughout the following chapters,
such as when addressing
convolutional neural networks.

- `ctx_d32ca634c60e5bdb199798a6`: # Modern Convolutional Neural Networks
:label:`chap_modern_cnn`

- `ctx_d72570c9e0d6a16eed3d4320`: ```{.python .input}
%matplotlib inline
from d2l import mxnet as d2l
from mxnet import autograd, gluon, init, lr_scheduler, np, npx
from mxnet.gluon import nn
npx.set_np()

net = nn.HybridSequential()
net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'),
        nn.MaxPool2D(pool_size=2, strides=2),
        nn.Conv2D(channels=16, kernel_size=5, activation='relu'),
        nn.MaxPool2D(pool_size=2, strides=2),
        nn.Dense(120, activation='relu'),
        nn.Dense(84, activation='relu'),
        nn.Dense(10))
net.hybridize()
loss = gluon.loss.SoftmaxCrossEntropyLoss()
device = d2l.try_gpu()

batch_size = 256
train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size)

# The code is almost identical to `d2l.train_ch6` defined in the 
# lenet section of chapter convolutional neural networks
def train(net, train_iter, test_iter, num_epochs, loss, trainer, device):
    net.initialize(force_reinit=True, ctx=device, init=init.Xavier())
    animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs],
                            legend=['train loss', 'train acc', 'test acc'])
    for epoch in range(num_epochs):
        metric = d2l.Accumulator(3)  # train_loss, train_acc, num_examples
        for i, (X, y) in enumerate(train_iter):
            X, y = X.as_in_ctx(device), y.as_in_ctx(device)
            with autograd.record():
                y_hat = net(X)
                l = loss(y_hat, y)
            l.backward()
            trainer.step(X.shape[0])
            metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0])
            train_loss = metric[0] / metric[2]
            train_acc = metric[1] / metric[2]
            if (i + 1) % 50 == 0:
                animator.add(epoch + i / len(train_iter),
                             (train_loss, train_acc, None))
        test_acc = d2l.evaluate_accuracy_gpu(net, test_iter)
        animator.add(epoch + 1, (None, None, test_acc))
    print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, '
          f'test acc {test_acc:.3f}')
```

- `ctx_ae21d86ceba363f31d12fca3`: Next, :numref:`chap_cnn` and :numref:`chap_modern_cnn`,
introduce convolutional neural networks (CNNs), 
powerful tools that form the backbone 
of most modern computer vision systems.

- `ctx_7d255ebc2d354c8e85c00cb4`: # Convolutional Neural Networks
:label:`chap_cnn`

- `ctx_ffd36cb1d841c0421cbd90cc`: In short, while CNNs can efficiently process spatial information, *recurrent neural networks* (RNNs) are designed to better handle sequential information.

- `ctx_9ddb8f2418fda4eee49c9494`: This is also one of the reasons why many of the mainstays
of deep learning, such as multilayer perceptrons
:cite:`McCulloch.Pitts.1943`, convolutional neural networks
:cite:`LeCun.Bottou.Bengio.ea.1998`, long short-term memory
:cite:`Hochreiter.Schmidhuber.1997`,
and Q-Learning :cite:`Watkins.Dayan.1992`,
were essentially "rediscovered" in the past decade,
after laying comparatively dormant for considerable time.

- `ctx_cba7a66d443fedea8b0f37bf`: In deep learning,
we often use CNNs or RNNs to encode a sequence.
