# Stage A sense casebook: development_008

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. Reduction

- `sense_id`: `d2lce_fa115d4c3a8140d91339df15`
- Split: `development`
- Model definition: an operation that combines values across one or more dimensions into fewer values, such as summing or averaging
- Model POS: `noun`

### Primary contexts

- `ctx_815a4c1f8b1f4b5fb069b1d7`: Design a layer that takes an input and computes a tensor reduction, i.e., it returns $y_k = \sum_{i, j} W_{ijk} x_i x_j$.
- `ctx_1181d8a3e218811366f7b56e`: ```{.python .input} #@tab pytorch #@save class MaskedSoftmaxCELoss(nn.CrossEntropyLoss): """The softmax cross-entropy loss with masks.""" # `pred` shape: (`batch_size`, `num_steps`, `vocab_size`) # `label` shape: (`batch_size`, `num_steps`) # `valid_len` shape: (`batch_size`,) def forward(self, pred, label, valid_len): weights = torch.ones_like(label) weights = sequence_mask(weights, valid_len) self.reduction='none' unweighted_loss = super(MaskedSoftmaxCELoss, self).forward( pred.permute(0, 2, 1), label) weighted_loss = (unweighted_loss * weights).mean(dim=1) return weighted_loss ```
- `ctx_d1f9348ef19cdcd8ff5ac0de`: According to our discussions of parameterization cost of fully-connected layers in :numref:`subsec_parameterization-cost-fc-layers`, even an aggressive reduction to one thousand hidden dimensions would require a fully-connected layer characterized by $10^6 \times 10^3 = 10^9$ parameters.
- `ctx_401ea4ab60773305df974141`: ## Reduction :label:`subseq_lin-alg-reduction`
- `ctx_7666d9241aa1a4a1804291fb`: If we replace `nn.MSELoss(reduction='sum')` with `nn.MSELoss()`, how can we change the learning rate for the code to behave identically.

### Backup contexts

- `ctx_df2876c9d5c03af64137057f`: ```{.python .input} #@tab pytorch net = NWKernelRegression() loss = nn.MSELoss(reduction='none') trainer = torch.optim.SGD(net.parameters(), lr=0.5) animator = d2l.Animator(xlabel='epoch', ylabel='loss', xlim=[1, 5]) for epoch in range(5): trainer.zero_grad() l = loss(net(x_train, keys, values), y_train) l.sum().backward() trainer.step() print(f'epoch {epoch + 1}, loss {float(l.sum()):.6f}') animator.add(epoch + 1, float(l.sum())) ```
- `ctx_0a74b6b6fec3cd733bef82fc`: ```{.python .input} # A simple MLP def get_net(): net = nn.Sequential() net.add(nn.Dense(10, activation='relu'), nn.Dense(1)) net.initialize(init.Xavier()) return net # Square loss loss = gluon.loss.L2Loss() ``` ```{.python .input} #@tab pytorch # Function for initializing the weights of the network def init_weights(m): if type(m) == nn.Linear: nn.init.xavier_uniform_(m.weight) # A simple MLP def get_net(): net = nn.Sequential(nn.Linear(4, 10), nn.ReLU(), nn.Linear(10, 1)) net.apply(init_weights) return net # Note: `MSELoss` computes squared error without the 1/2 factor loss = nn.MSELoss(reduction='none') ``` ```{.python .input} #@tab tensorflow # Vanilla MLP architecture def get_net(): net = tf.keras.Sequential([tf.keras.layers.Dense(10, activation='relu'), tf.keras.layers.Dense(1)]) return net # Note: `MeanSquaredError` computes squared error without the 1/2 factor loss = tf.keras.losses.MeanSquaredError() ``` Now we are ready to [**train the model**].
- `ctx_7d313060719ea864c98aabb1`: ```{.python .input} #@tab pytorch batch_size, lr, num_epochs = 256, 0.1, 10 loss = nn.CrossEntropyLoss(reduction='none') trainer = torch.optim.SGD(net.parameters(), lr=lr) ```

### Contrastive contexts

- `ctxx_7bf4f962ca5e36499fdcecbb`: Synthetic: The chemistry lab discussed reduction, meaning gain of electrons, which is unrelated to tensor reduction here.

### Definition evidence

- `ctx_401ea4ab60773305df974141`: ## Reduction :label:`subseq_lin-alg-reduction`
- `ctx_815a4c1f8b1f4b5fb069b1d7`: Design a layer that takes an input and computes a tensor reduction, i.e., it returns $y_k = \sum_{i, j} W_{ijk} x_i x_j$.
- `ctx_7666d9241aa1a4a1804291fb`: If we replace `nn.MSELoss(reduction='sum')` with `nn.MSELoss()`, how can we change the learning rate for the code to behave identically.

### Part-of-speech evidence

- `ctx_401ea4ab60773305df974141`: ## Reduction :label:`subseq_lin-alg-reduction`
- `ctx_815a4c1f8b1f4b5fb069b1d7`: Design a layer that takes an input and computes a tensor reduction, i.e., it returns $y_k = \sum_{i, j} W_{ijk} x_i x_j$.

## 2. region of interest pooling layer

- `sense_id`: `d2lce_88251c1ff8b5d3756955ca7b`
- Split: `development`
- Model definition: a neural network layer that pools features from each region of interest into a fixed output shape
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_788954d63cedc392831d5044`: The region of interest pooling layer proposed in the fast R-CNN is different from the pooling layer introduced in :numref:`sec_pooling`.
- `ctx_808752f6de5f09f78b2ac2c6`: In contrast, we can directly specify the output shape in the region of interest pooling layer.
- `ctx_06e708938888799ff3a5dffa`: Specifically, the mask R-CNN replaces the region of interest pooling layer with the *region of interest (RoI) alignment* layer.
- `ctx_18b4f72effde16746e8f5bd5`: Therefore, the region of interest pooling layer can extract features of the same shape even when regions of interest have different shapes.
- `ctx_1ad01f8bfdd4e76617b7a827`: ![A $2\times 2$ region of interest pooling layer.](../img/roi.svg) :label:`fig_roi`

### Backup contexts

- `ctx_23e5008854737fe4bc296b60`: For this region of interest, we use a $2\times 2$ region of interest pooling layer to obtain a $2\times 2$ output.
- `ctx_5091b8db5e4618b9d88151b8`: Below we demonstrate the computation of the region of interest pooling layer.
- `ctx_6e7571c8f722862870d999c0`: The remaining predicted bounding boxes for objects are the region proposals required by the region of interest pooling layer.

### Contrastive contexts

- `ctxx_b7279a50f25ae4d072e83b57`: Synthetic: The region of interest pooling layer pools each proposed box, whereas ordinary pooling layers pool over a regular feature map neighborhood.

### Definition evidence

- `ctx_788954d63cedc392831d5044`: The region of interest pooling layer proposed in the fast R-CNN is different from the pooling layer introduced in :numref:`sec_pooling`.
- `ctx_18b4f72effde16746e8f5bd5`: Therefore, the region of interest pooling layer can extract features of the same shape even when regions of interest have different shapes.
- `ctx_808752f6de5f09f78b2ac2c6`: In contrast, we can directly specify the output shape in the region of interest pooling layer.

### Part-of-speech evidence

- `ctx_788954d63cedc392831d5044`: The region of interest pooling layer proposed in the fast R-CNN is different from the pooling layer introduced in :numref:`sec_pooling`.
- `ctx_06e708938888799ff3a5dffa`: Specifically, the mask R-CNN replaces the region of interest pooling layer with the *region of interest (RoI) alignment* layer.

## 3. ReLU activation

- `sense_id`: `d2lce_42900db05a19228ce33eafe0`
- Split: `development`
- Model definition: the use of the ReLU function as the activation applied in a neural network layer
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_f9d71dcb8bd80dd6e5eeb4f5`: The basic block of the generator contains a transposed convolution layer followed by the batch normalization and ReLU activation.
- `ctx_1c92074d454d9307635f4319`: The first is [**our hidden layer**], which (**contains 256 hidden units and applies the ReLU activation function**).
- `ctx_42d57a5ddede95c06600e690`: On the other hand, the ReLU activation function makes model training easier when using different parameter initialization methods.
- `ctx_7c7d5d50af4eb953a4e181ba`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_bd4860d3d44e08593cf1c9fd`: To make sure we know how everything works, we will [**implement the ReLU activation**] ourselves using the maximum function rather than invoking the built-in `relu` function directly.

### Backup contexts

- `ctx_6d18c54fb03ed4d0a466cdac`: This turns out to be one of the reasons that training deep learning models was quite tricky prior to the introduction of the ReLU activation function.
- `ctx_8c4194ab74302b6b3fccfd63`: * ReLU activation functions mitigate the vanishing gradient problem.
- `ctx_9fd1fe552d657e4fbfcf9abd`: ```{.python .input} #@tab mxnet, pytorch tau = 4 features = d2l.zeros((T - tau, tau)) for i in range(tau): features[:, i] = x[i: T - tau + i] labels = d2l.reshape(x[tau:], (-1, 1)) ``` ```{.python .input} #@tab tensorflow tau = 4 features = tf.Variable(d2l.zeros((T - tau, tau))) for i in range(tau): features[:, i].assign(x[i: T - tau + i]) labels = d2l.reshape(x[tau:], (-1, 1)) ``` ```{.python .input} #@tab all batch_size, n_train = 16, 600 # Only the first `n_train` examples are used for training train_iter = d2l.load_array((features[:n_train], labels[:n_train]), batch_size, is_train=True) ``` Here we [**keep the architecture fairly simple: just an MLP**] with two fully-connected layers, ReLU activation, and squared loss.

### Contrastive contexts

- `ctxx_20879e21980bfe53804ca4b9`: Synthetic: ReLU activation names the layer’s nonlinearity, not the weight initialization scheme.

### Definition evidence

- `ctx_7c7d5d50af4eb953a4e181ba`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_42d57a5ddede95c06600e690`: On the other hand, the ReLU activation function makes model training easier when using different parameter initialization methods.
- `ctx_1c92074d454d9307635f4319`: The first is [**our hidden layer**], which (**contains 256 hidden units and applies the ReLU activation function**).

### Part-of-speech evidence

- `ctx_bd4860d3d44e08593cf1c9fd`: To make sure we know how everything works, we will [**implement the ReLU activation**] ourselves using the maximum function rather than invoking the built-in `relu` function directly.
- `ctx_f9d71dcb8bd80dd6e5eeb4f5`: The basic block of the generator contains a transposed convolution layer followed by the batch normalization and ReLU activation.

## 4. representation

- `sense_id`: `d2lce_f33d434f8362f23d43285427`
- Split: `development`
- Model definition: A way of encoding or expressing data, labels, or internal features so they can be used by a model.
- Model POS: `noun`

### Primary contexts

- `ctx_d01d38e638f7b5b3665a55bd`: Note that it takes `X` as the input, calculates the hidden representation with the activation function applied, and outputs its logits.
- `ctx_0f6b002a2460b36bc8bbacd6`: The easiest representation is called *one-hot encoding*, which is introduced in :numref:`subsec_classification-problem`.
- `ctx_5f24690542e3c0e46ba4cc69`: With deep neural networks, we used observational data to jointly learn both a representation via hidden layers and a linear predictor that acts upon that representation.
- `ctx_12689008f7e03f4832cb6a99`: Let $[\mathbf{X}]_{i, j}$ and $[\mathbf{H}]_{i, j}$ denote the pixel at location ($i$, $j$) in the input image and hidden representation, respectively.
- `ctx_252c35105ca972372bb2c810`: In :numref:`chap_nlp_pretrain` and :numref:`chap_nlp_app`, we show how to pretrain language representation models and apply them to natural language processing tasks.

### Backup contexts

- `ctx_d36c794f5cb48c84cfeb1ae0`: We can use the same representation as before for the label $\mathbf{y}$.
- `ctx_b91f8656a74c323310072798`: And up until 2012 the representation was calculated mechanically.
- `ctx_cb76cb4b95e46eb37730ea64`: In order to work with data usefully, we typically need to come up with a suitable numerical representation.

### Contrastive contexts

- `ctxx_30b779e89788fa1c53d8f922`: Synthetic: The representation from the hidden layer improved classification, but the elected representation changed after the vote.

### Definition evidence

- `ctx_5f24690542e3c0e46ba4cc69`: With deep neural networks, we used observational data to jointly learn both a representation via hidden layers and a linear predictor that acts upon that representation.
- `ctx_d01d38e638f7b5b3665a55bd`: Note that it takes `X` as the input, calculates the hidden representation with the activation function applied, and outputs its logits.
- `ctx_cb76cb4b95e46eb37730ea64`: In order to work with data usefully, we typically need to come up with a suitable numerical representation.

### Part-of-speech evidence

- `ctx_cb76cb4b95e46eb37730ea64`: In order to work with data usefully, we typically need to come up with a suitable numerical representation.
- `ctx_5f24690542e3c0e46ba4cc69`: With deep neural networks, we used observational data to jointly learn both a representation via hidden layers and a linear predictor that acts upon that representation.

## 5. second derivative

- `sense_id`: `d2lce_bee01b92f7b0b02cc1d77bd7`
- Split: `development`
- Model definition: the derivative obtained by differentiating a function twice
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_8a430806097a3e11f597ee65`: Formally, a twice-differentiable one-dimensional function $f: \mathbb{R} \rightarrow \mathbb{R}$ is convex if and only if its second derivative $f'' \geq 0$.
- `ctx_c63be52377fb45f394c67865`: Compute the second derivative of the cross-entropy loss $l(\mathbf{y},\hat{\mathbf{y}})$ for the softmax.
- `ctx_4a0757f79d783bf9dfd3591b`: We will call this the second derivative of $f$.
- `ctx_48009dd3fb027cf7c0d50839`: Whenever the second derivative of a function $f: \mathbb{R}^n \rightarrow \mathbb{R}$ exists it is very easy to check whether $f$ is convex.
- `ctx_1f8898813854f010ead57a18`: Why is the second derivative much more expensive to compute than the first derivative?

### Backup contexts

- `ctx_5b8b82c37cbbe2526e94e29e`: Compute the variance of the distribution given by $\mathrm{softmax}(\mathbf{o})$ and show that it matches the second derivative computed above.
- `ctx_20c88126cf28f7c6338fd7ce`: Its first and second derivative vanish for $x=0$.
- `ctx_7882197b45dfa30a41481b4e`: What is the form of a kernel for the second derivative?

### Contrastive contexts

- `ctxx_4f681a1f06ff96894ab423a7`: Synthetic: The second derivative in a pricing spreadsheet was left blank because no calculus was being applied.

### Definition evidence

- `ctx_4a0757f79d783bf9dfd3591b`: We will call this the second derivative of $f$.
- `ctx_8a430806097a3e11f597ee65`: Formally, a twice-differentiable one-dimensional function $f: \mathbb{R} \rightarrow \mathbb{R}$ is convex if and only if its second derivative $f'' \geq 0$.
- `ctx_48009dd3fb027cf7c0d50839`: Whenever the second derivative of a function $f: \mathbb{R}^n \rightarrow \mathbb{R}$ exists it is very easy to check whether $f$ is convex.

### Part-of-speech evidence

- `ctx_4a0757f79d783bf9dfd3591b`: We will call this the second derivative of $f$.
- `ctx_c63be52377fb45f394c67865`: Compute the second derivative of the cross-entropy loss $l(\mathbf{y},\hat{\mathbf{y}})$ for the softmax.

## 6. sensory input

- `sense_id`: `d2lce_bc240ce7b3e0abeb18f82a6b`
- Split: `development`
- Model definition: incoming sensory information considered as items to be selected or weighted by attention
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_718ca2aa7353cfe6ec7be41e`: The optic nerve of a primate's visual system receives massive sensory input, far exceeding what the brain can fully process.
- `ctx_cc74ec1d4759c01b8c2aeb02`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_f2f9bdd4c1c0ac5391f9f713`: These sensory inputs are called *values* in the context of attention mechanisms.
- `ctx_5116b5fdf318003ffedaf8df`: Given any query, attention mechanisms bias selection over sensory inputs (e.g., intermediate feature representations) via *attention pooling*.
- `ctx_94ce02b7241c9ce39ca2bbb4`: ![Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).](../img/qkv.svg) :label:`fig_qkv`

### Backup contexts

- `ctx_a3dea1caaff77f50a3d722b3`: Fortunately, our ancestors had learned from experience (also known as data) that *not all sensory inputs are created equal*.
- `ctx_84826f7dac9a86c191985d21`: To bias selection over sensory inputs, we can simply use a parameterized fully-connected layer or even non-parameterized max or average pooling.
- `ctx_c118b6fc83c7f0f86f025bbe`: More generally, every value is paired with a *key*, which can be thought of the nonvolitional cue of that sensory input.

### Contrastive contexts

- `ctxx_62a44bacfcfd9838900887b9`: Synthetic: The robot lost sensory input from its temperature sensor after the cable broke.

### Definition evidence

- `ctx_718ca2aa7353cfe6ec7be41e`: The optic nerve of a primate's visual system receives massive sensory input, far exceeding what the brain can fully process.
- `ctx_a3dea1caaff77f50a3d722b3`: Fortunately, our ancestors had learned from experience (also known as data) that *not all sensory inputs are created equal*.
- `ctx_84826f7dac9a86c191985d21`: To bias selection over sensory inputs, we can simply use a parameterized fully-connected layer or even non-parameterized max or average pooling.
- `ctx_5116b5fdf318003ffedaf8df`: Given any query, attention mechanisms bias selection over sensory inputs (e.g., intermediate feature representations) via *attention pooling*.
- `ctx_c118b6fc83c7f0f86f025bbe`: More generally, every value is paired with a *key*, which can be thought of the nonvolitional cue of that sensory input.
- `ctx_cc74ec1d4759c01b8c2aeb02`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_f2f9bdd4c1c0ac5391f9f713`: These sensory inputs are called *values* in the context of attention mechanisms.
- `ctx_94ce02b7241c9ce39ca2bbb4`: ![Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).](../img/qkv.svg) :label:`fig_qkv`

### Part-of-speech evidence

- `ctx_718ca2aa7353cfe6ec7be41e`: The optic nerve of a primate's visual system receives massive sensory input, far exceeding what the brain can fully process.
- `ctx_a3dea1caaff77f50a3d722b3`: Fortunately, our ancestors had learned from experience (also known as data) that *not all sensory inputs are created equal*.

## 7. sequence data

- `sense_id`: `d2lce_b85d9a7a642afee03175796f`
- Split: `development`
- Model definition: data whose observations are arranged in an ordered sequence, often across positions or time steps.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_48778feb4f6b4e043ea02087`: We need statistical tools and new deep neural network architectures to deal with sequence data.
- `ctx_57e94c23a338288414c30cf1`: To keep things simple we (**generate our sequence data by using a sine function with some additive noise for time steps $1, 2, \ldots, 1000$.**) ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, np, npx, gluon, init from mxnet.gluon import nn npx.set_np() ``` ```{.python .input} #@tab pytorch %matplotlib inline from d2l import torch as d2l import torch from torch import nn ``` ```{.python .input} #@tab tensorflow %matplotlib inline from d2l import tensorflow as d2l import tensorflow as tf ``` ```{.python .input} #@tab mxnet, pytorch T = 1000 # Generate a total of 1000 points time = d2l.arange(1, T + 1, dtype=d2l.float32) x = d2l.sin(0.01 * time) + d2l.normal(0, 0.2, (T,)) d2l.plot(time, [x], 'time', 'x', xlim=[1, 1000], figsize=(6, 3)) ``` ```{.python .input} #@tab tensorflow T = 1000 # Generate a total of 1000 points time = d2l.arange(1, T + 1, dtype=d2l.float32) x = d2l.sin(0.01 * time) + d2l.normal([T], 0, 0.2) d2l.plot(time, [x], 'time', 'x', xlim=[1, 1000], figsize=(6, 3)) ``` Next, we need to turn such a sequence into features and labels that our model can train on.
- `ctx_283a25d9322a8783b9c51766`: However, there is just one little problem to this: if we observe sequence data only until time step 604, we cannot hope to receive the inputs for all the future one-step-ahead predictions.
- `ctx_b6036c566fcf4ded24d31bee`: Of course, sequence data are not just about movie ratings.
- `ctx_49c9f549ad2f64ca91888fd2`: To facilitate our future experiments with sequence data, we will dedicate this section to explain common preprocessing steps for text.

### Backup contexts

- `ctx_12a769b04e422d6f6739fc5c`: We have reviewed and evaluated statistical tools and prediction challenges for sequence data.
- `ctx_8710926068d0f1fb4746e134`: After a more formal review of sequence data we introduce practical techniques for preprocessing text data.
- `ctx_23bae34b7c7a3e597d0cac0d`: We have introduced the basics of RNNs, which can better handle sequence data.

### Contrastive contexts

- `ctxx_e699d91caaa3cd6d980d9221`: Synthetic: Although stored in a table, these customer records are not sequence data because the row order carries no meaning.

### Definition evidence

- `ctx_48778feb4f6b4e043ea02087`: We need statistical tools and new deep neural network architectures to deal with sequence data.
- `ctx_283a25d9322a8783b9c51766`: However, there is just one little problem to this: if we observe sequence data only until time step 604, we cannot hope to receive the inputs for all the future one-step-ahead predictions.
- `ctx_57e94c23a338288414c30cf1`: To keep things simple we (**generate our sequence data by using a sine function with some additive noise for time steps $1, 2, \ldots, 1000$.**) ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, np, npx, gluon, init from mxnet.gluon import nn npx.set_np() ``` ```{.python .input} #@tab pytorch %matplotlib inline from d2l import torch as d2l import torch from torch import nn ``` ```{.python .input} #@tab tensorflow %matplotlib inline from d2l import tensorflow as d2l import tensorflow as tf ``` ```{.python .input} #@tab mxnet, pytorch T = 1000 # Generate a total of 1000 points time = d2l.arange(1, T + 1, dtype=d2l.float32) x = d2l.sin(0.01 * time) + d2l.normal(0, 0.2, (T,)) d2l.plot(time, [x], 'time', 'x', xlim=[1, 1000], figsize=(6, 3)) ``` ```{.python .input} #@tab tensorflow T = 1000 # Generate a total of 1000 points time = d2l.arange(1, T + 1, dtype=d2l.float32) x = d2l.sin(0.01 * time) + d2l.normal([T], 0, 0.2) d2l.plot(time, [x], 'time', 'x', xlim=[1, 1000], figsize=(6, 3)) ``` Next, we need to turn such a sequence into features and labels that our model can train on.

### Part-of-speech evidence

- `ctx_8710926068d0f1fb4746e134`: After a more formal review of sequence data we introduce practical techniques for preprocessing text data.
- `ctx_48778feb4f6b4e043ea02087`: We need statistical tools and new deep neural network architectures to deal with sequence data.
- `ctx_49c9f549ad2f64ca91888fd2`: To facilitate our future experiments with sequence data, we will dedicate this section to explain common preprocessing steps for text.

## 8. Sequential

- `sense_id`: `d2lce_40a50503f2fdc79aa0a549fc`
- Split: `development`
- Model definition: A neural network container class that stacks layers in order, passing outputs from one layer to the next.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_4a91c71a44a35cb9a603e221`: We need only to instantiate a `Sequential` block and chain together the appropriate layers.
- `ctx_de121275094e0872769613f6`: ```{.python .input} from mxnet import np, npx from mxnet.gluon import nn npx.set_np() net = nn.Sequential() net.add(nn.Dense(256, activation='relu')) net.add(nn.Dense(10)) net.initialize() X = np.random.uniform(size=(2, 20)) net(X) ```
- `ctx_1c286a6e0465f52ed228797c`: ```{.python .input} from d2l import mxnet as d2l from mxnet import np, npx from mxnet.gluon import nn npx.set_np() net = nn.Sequential() # Here, we use a larger 11 x 11 window to capture objects.
- `ctx_3e14117a045ebf17876f5d0d`: ```{.python .input} net = nn.Sequential() net.add(nn.Dense(256, activation='relu'), nn.Dense(10)) net.initialize(init.Normal(sigma=0.01)) ```
- `ctx_4948ac0797bf6c281ee7ac67`: We will first define a model variable `net`, which will refer to an instance of the `Sequential` class.

### Contrastive contexts

- `ctxx_db6036616175f01970672c09`: Synthetic: The frames are sequential, but the model is not built with Sequential.

### Definition evidence

- `ctx_4948ac0797bf6c281ee7ac67`: We will first define a model variable `net`, which will refer to an instance of the `Sequential` class.
- `ctx_3e14117a045ebf17876f5d0d`: ```{.python .input} net = nn.Sequential() net.add(nn.Dense(256, activation='relu'), nn.Dense(10)) net.initialize(init.Normal(sigma=0.01)) ```
- `ctx_de121275094e0872769613f6`: ```{.python .input} from mxnet import np, npx from mxnet.gluon import nn npx.set_np() net = nn.Sequential() net.add(nn.Dense(256, activation='relu')) net.add(nn.Dense(10)) net.initialize() X = np.random.uniform(size=(2, 20)) net(X) ```
- `ctx_4a91c71a44a35cb9a603e221`: We need only to instantiate a `Sequential` block and chain together the appropriate layers.

### Part-of-speech evidence

- `ctx_4948ac0797bf6c281ee7ac67`: We will first define a model variable `net`, which will refer to an instance of the `Sequential` class.
- `ctx_4a91c71a44a35cb9a603e221`: We need only to instantiate a `Sequential` block and chain together the appropriate layers.

## 9. sigmoid activation function

- `sense_id`: `d2lce_2485cc2d1b2606bcc62d63c1`
- Split: `development`
- Model definition: An activation function that applies the sigmoid mapping, producing outputs between 0 and 1.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_81a329be9d149269cbb9e238`: where $\sigma$ uses the definition of the sigmoid activation function:
- `ctx_7440cb039806378db99b4cf3`: This is because, when the output of the sigmoid activation function is very close to 0 or 1, the gradient of these regions is almost 0, so that backpropagation cannot continue to update some of the model parameters.
- `ctx_4049427e7cba44c6a4d86b2f`: Besides, AlexNet changed the sigmoid activation function to a simpler ReLU activation function.
- `ctx_2e8cc79d478165e2fadbde2b`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.
- `ctx_85f3e69f989b8ba0e6c34543`: For example, it does not have the exponentiation operation found in the sigmoid activation function.

### Backup contexts

- `ctx_a57ada1779c485390423ba15`: Each convolutional layer uses a $5\times 5$ kernel and a sigmoid activation function.
- `ctx_fb27ea5cc8cb345d667494e6`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.
- `ctx_b4869503275a2fafa7ed121c`: Afterwards, the ouputs are projected with matrix $\mathbf{h}$ and a sigmoid activation function.

### Contrastive contexts

- `ctxx_d35dce40a2fd3dd8c0d8f5c4`: Synthetic: The sigmoid activation function should not be confused with a hard threshold step function.

### Definition evidence

- `ctx_81a329be9d149269cbb9e238`: where $\sigma$ uses the definition of the sigmoid activation function:
- `ctx_7440cb039806378db99b4cf3`: This is because, when the output of the sigmoid activation function is very close to 0 or 1, the gradient of these regions is almost 0, so that backpropagation cannot continue to update some of the model parameters.
- `ctx_2e8cc79d478165e2fadbde2b`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.

### Part-of-speech evidence

- `ctx_2e8cc79d478165e2fadbde2b`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.
- `ctx_4049427e7cba44c6a4d86b2f`: Besides, AlexNet changed the sigmoid activation function to a simpler ReLU activation function.

## 10. sigmoid function

- `sense_id`: `d2lce_00f50f89defd8652bb8c429e`
- Split: `development`
- Model definition: an S-shaped activation function that maps a real-valued input to a value between 0 and 1
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_b1671787eb98927f1ad13a78`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.
- `ctx_0c2556749af5509e2a8a0d38`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.
- `ctx_677a8cad69668bf7ea4b032d`: ### Sigmoid Function
- `ctx_6fba33e1194891da74822687`: Typically, the discriminator outputs a scalar prediction $o\in\mathbb R$ for input $\mathbf x$, such as using a dense layer with hidden size 1, and then applies sigmoid function to obtain the predicted probability $D(\mathbf x) = 1/(1+e^{-o})$.
- `ctx_5998384435b11da31468fd92`: where $\sigma$ uses the definition of the sigmoid activation function:

### Backup contexts

- `ctx_83aa1ec70a5aa698b67dadb3`: Second, AlexNet used the ReLU instead of the sigmoid as its activation function.
- `ctx_26b5e8bf7b8da7042c80bc48`: For that we pick a slightly modernized version of LeNet (`relu` instead of `sigmoid` activation, MaxPooling rather than AveragePooling), as applied to Fashion-MNIST.
- `ctx_cf0365ae6ea1bcdfd1296ed3`: The activation of encoder is set to `sigmoid` by default and no activation is applied for decoder.

### Contrastive contexts

- `ctxx_6e2436fba822b8df6af232ec`: Synthetic: In medicine, a sigmoid function could be discussed as an S-shaped dose-response curve rather than specifically as a neural-network activation.

### Definition evidence

- `ctx_0c2556749af5509e2a8a0d38`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.
- `ctx_b1671787eb98927f1ad13a78`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.
- `ctx_6fba33e1194891da74822687`: Typically, the discriminator outputs a scalar prediction $o\in\mathbb R$ for input $\mathbf x$, such as using a dense layer with hidden size 1, and then applies sigmoid function to obtain the predicted probability $D(\mathbf x) = 1/(1+e^{-o})$.

### Part-of-speech evidence

- `ctx_677a8cad69668bf7ea4b032d`: ### Sigmoid Function
- `ctx_0c2556749af5509e2a8a0d38`: The basic units in each convolutional block are a convolutional layer, a sigmoid activation function, and a subsequent average pooling operation.
- `ctx_6fba33e1194891da74822687`: Typically, the discriminator outputs a scalar prediction $o\in\mathbb R$ for input $\mathbf x$, such as using a dense layer with hidden size 1, and then applies sigmoid function to obtain the predicted probability $D(\mathbf x) = 1/(1+e^{-o})$.
