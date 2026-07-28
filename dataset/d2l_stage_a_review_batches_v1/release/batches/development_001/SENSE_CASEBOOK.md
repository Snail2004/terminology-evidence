# Stage A sense casebook: development_001

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. activation function

- `sense_id`: `d2lce_e0c693366d811581abbb9e74`
- Split: `development`
- Model definition: A function applied in a neural network layer or unit to introduce nonlinear transformation of its output.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_42efd998d80ced9a64e32ec8`: In order to realize the potential of multilayer architectures, we need one more key ingredient: a nonlinear *activation function* $\sigma$ to be applied to each hidden unit following the affine transformation.
- `ctx_5f040cdbc06a01d2f5cc4d87`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_2970e39beda737feef2164c9`: This turns out to be one of the reasons that training deep learning models was quite tricky prior to the introduction of the ReLU activation function.
- `ctx_12cee07dbdee67f6be90da20`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.
- `ctx_34ee6d32a2ff535ee2d88bde`: By using $\tanh$ as the activation function and disabling bias terms, we implement additive attention in the following.

### Backup contexts

- `ctx_733d98a23bc0d5e7b59bd272`: Let the hidden layer's activation function be $\phi$.
- `ctx_6ba311f80c075eceefec2cba`: We also need to decide how to compute things efficiently, how to combine multiple layers, appropriate activation functions, and how to make reasonable design choices to yield networks that are effective in practice.
- `ctx_6882a07f8f604f30a2c75617`: Added to these obstacles, key tricks for training neural networks including parameter initialization heuristics, clever variants of stochastic gradient descent, non-squashing activation functions, and effective regularization techniques were still missing.

### Contrastive contexts

- `ctxx_22da2d4feabde1fd9e90c75b`: Synthetic: In this chapter, activation function means a mathematical mapping in a neural network, not the act of activating a software feature.

### Definition evidence

- `ctx_42efd998d80ced9a64e32ec8`: In order to realize the potential of multilayer architectures, we need one more key ingredient: a nonlinear *activation function* $\sigma$ to be applied to each hidden unit following the affine transformation.
- `ctx_5f040cdbc06a01d2f5cc4d87`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_733d98a23bc0d5e7b59bd272`: Let the hidden layer's activation function be $\phi$.
- `ctx_2970e39beda737feef2164c9`: This turns out to be one of the reasons that training deep learning models was quite tricky prior to the introduction of the ReLU activation function.

### Part-of-speech evidence

- `ctx_42efd998d80ced9a64e32ec8`: In order to realize the potential of multilayer architectures, we need one more key ingredient: a nonlinear *activation function* $\sigma$ to be applied to each hidden unit following the affine transformation.
- `ctx_5f040cdbc06a01d2f5cc4d87`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_12cee07dbdee67f6be90da20`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.

## 2. Adam

- `sense_id`: `d2lce_7ef8ed3f93210606a27312a4`
- Split: `development`
- Model definition: An adaptive gradient-based optimization algorithm used to train models.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_feb069ef1ecb8e58ef71c482`: Unlike in previous sections, [**our training functions will rely on the Adam optimizer (we will describe it in greater detail later)**].
- `ctx_5c812a90177b5b129b327432`: Indeed, anyone content with treating optimization as a black box device to minimize objective functions in a simple setting might well content oneself with the knowledge that there exists an array of incantations of such a procedure (with names such as "SGD" and "Adam").
- `ctx_3c4a7aaec02b50911df8c766`: ```{.python .input} #@save def train_seq2seq(net, data_iter, lr, num_epochs, tgt_vocab, device): """Train a model for sequence to sequence.""" net.initialize(init.Xavier(), force_reinit=True, ctx=device) trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) loss = MaskedSoftmaxCELoss() animator = d2l.Animator(xlabel='epoch', ylabel='loss', xlim=[10, num_epochs]) for epoch in range(num_epochs): timer = d2l.Timer() metric = d2l.Accumulator(2) # Sum of training loss, no.
- `ctx_4a985a7867b0862e601aa744`: This function gets all available GPUs, uses Adam as the optimization algorithm, applies image augmentation to the training dataset, and finally calls the `train_ch13` function just defined to train and evaluate the model.
- `ctx_58c0a9351bd98055ea39a9a0`: ```{.python .input} def train(net, data_iter, lr, num_epochs, device=d2l.try_gpu()): net.initialize(ctx=device, force_reinit=True) trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) animator = d2l.Animator(xlabel='epoch', ylabel='loss', xlim=[1, num_epochs]) # Sum of normalized losses, no.

### Backup contexts

- `ctx_724a58cef32d03f9a90cc4d9`: ```{.python .input} lr, num_epochs = 0.01, 5 trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) loss = gluon.loss.SoftmaxCrossEntropyLoss() d2l.train_ch13(net, train_iter, test_iter, loss, trainer, num_epochs, devices) ```
- `ctx_c4effad022bd5e216d2eaf51`: ```{.python .input} def train(net, train_iter, loss, epochs, lr): trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) for epoch in range(epochs): for X, y in train_iter: with autograd.record(): l = loss(net(X), y) l.backward() trainer.step(batch_size) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab pytorch def train(net, train_iter, loss, epochs, lr): trainer = torch.optim.Adam(net.parameters(), lr) for epoch in range(epochs): for X, y in train_iter: trainer.zero_grad() l = loss(net(X), y) l.sum().backward() trainer.step() print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab tensorflow def train(net, train_iter, loss, epochs, lr): trainer = tf.keras.optimizers.Adam() for epoch in range(epochs): for X, y in train_iter: with tf.GradientTape() as g: out = net(X) l = loss(y, out) params = net.trainable_variables grads = g.gradient(l, params) trainer.apply_gradients(zip(grads, params)) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ## Prediction Since the training loss is small, we would expect our model to work well.

### Contrastive contexts

- `ctxx_01a3b60f74c769d4a3b645f0`: Synthetic: Adam appears in the contributor list as a person's name, not as an optimizer.

### Definition evidence

- `ctx_feb069ef1ecb8e58ef71c482`: Unlike in previous sections, [**our training functions will rely on the Adam optimizer (we will describe it in greater detail later)**].
- `ctx_c4effad022bd5e216d2eaf51`: ```{.python .input} def train(net, train_iter, loss, epochs, lr): trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) for epoch in range(epochs): for X, y in train_iter: with autograd.record(): l = loss(net(X), y) l.backward() trainer.step(batch_size) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab pytorch def train(net, train_iter, loss, epochs, lr): trainer = torch.optim.Adam(net.parameters(), lr) for epoch in range(epochs): for X, y in train_iter: trainer.zero_grad() l = loss(net(X), y) l.sum().backward() trainer.step() print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab tensorflow def train(net, train_iter, loss, epochs, lr): trainer = tf.keras.optimizers.Adam() for epoch in range(epochs): for X, y in train_iter: with tf.GradientTape() as g: out = net(X) l = loss(y, out) params = net.trainable_variables grads = g.gradient(l, params) trainer.apply_gradients(zip(grads, params)) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ## Prediction Since the training loss is small, we would expect our model to work well.
- `ctx_5c812a90177b5b129b327432`: Indeed, anyone content with treating optimization as a black box device to minimize objective functions in a simple setting might well content oneself with the knowledge that there exists an array of incantations of such a procedure (with names such as "SGD" and "Adam").
- `ctx_4a985a7867b0862e601aa744`: This function gets all available GPUs, uses Adam as the optimization algorithm, applies image augmentation to the training dataset, and finally calls the `train_ch13` function just defined to train and evaluate the model.

### Part-of-speech evidence

- `ctx_feb069ef1ecb8e58ef71c482`: Unlike in previous sections, [**our training functions will rely on the Adam optimizer (we will describe it in greater detail later)**].
- `ctx_c4effad022bd5e216d2eaf51`: ```{.python .input} def train(net, train_iter, loss, epochs, lr): trainer = gluon.Trainer(net.collect_params(), 'adam', {'learning_rate': lr}) for epoch in range(epochs): for X, y in train_iter: with autograd.record(): l = loss(net(X), y) l.backward() trainer.step(batch_size) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab pytorch def train(net, train_iter, loss, epochs, lr): trainer = torch.optim.Adam(net.parameters(), lr) for epoch in range(epochs): for X, y in train_iter: trainer.zero_grad() l = loss(net(X), y) l.sum().backward() trainer.step() print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ```{.python .input} #@tab tensorflow def train(net, train_iter, loss, epochs, lr): trainer = tf.keras.optimizers.Adam() for epoch in range(epochs): for X, y in train_iter: with tf.GradientTape() as g: out = net(X) l = loss(y, out) params = net.trainable_variables grads = g.gradient(l, params) trainer.apply_gradients(zip(grads, params)) print(f'epoch {epoch + 1}, ' f'loss: {d2l.evaluate_loss(net, train_iter, loss):f}') net = get_net() train(net, train_iter, loss, 5, 0.01) ``` ## Prediction Since the training loss is small, we would expect our model to work well.

## 3. affine transformation

- `sense_id`: `d2lce_539543a2360129e2a2fa1b6d`
- Split: `development`
- Model definition: A mapping that applies a linear transformation and then adds a bias or translation.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_107aaac926dcdc82c5d33f4c`: In order to realize the potential of multilayer architectures, we need one more key ingredient: a nonlinear *activation function* $\sigma$ to be applied to each hidden unit following the affine transformation.
- `ctx_7121f7a9fa4ce1bf37a4b411`: Strictly speaking, :eqref:`eq_price-area` is an *affine transformation* of input features, which is characterized by a *linear transformation* of features via weighted sum, combined with a *translation* via the added bias.
- `ctx_0cbe39511747c15a73cb01c5`: We have described the affine transformation in :numref:`subsec_linear_model`, which is a linear transformation added by a bias.
- `ctx_a9050a3dc5a8ccd5afb793f7`: Models whose output prediction is determined by the affine transformation of input features are *linear models*, where the affine transformation is specified by the chosen weights and bias.
- `ctx_fb1febc2efebf2be14297c4f`: Although softmax is a nonlinear function, the outputs of softmax regression are still *determined* by an affine transformation of input features; thus, softmax regression is a linear model.

### Backup contexts

- `ctx_a3223aad900f9e33b14c8db7`: This model mapped our inputs directly to our outputs via a single affine transformation, followed by a softmax operation.
- `ctx_77b69954271f4ff69e4986ca`: If our labels truly were related to our input data by an affine transformation, then this approach would be sufficient.
- `ctx_8cc78c2ac5c8304bb46fbe21`: Second, for a typical MLP or CNN, as we train, the variables (e.g., affine transformation outputs in MLP) in intermediate layers may take values with widely varying magnitudes: both along the layers from the input to the output, across units in the same layer, and over time due to our updates to the model parameters.

### Contrastive contexts

- `ctxx_da7c4af0bfaae364e2438bee`: [Synthetic] Her affine transformation after the vacation made her much more patient with students.

### Definition evidence

- `ctx_7121f7a9fa4ce1bf37a4b411`: Strictly speaking, :eqref:`eq_price-area` is an *affine transformation* of input features, which is characterized by a *linear transformation* of features via weighted sum, combined with a *translation* via the added bias.
- `ctx_0cbe39511747c15a73cb01c5`: We have described the affine transformation in :numref:`subsec_linear_model`, which is a linear transformation added by a bias.

### Part-of-speech evidence

- `ctx_7121f7a9fa4ce1bf37a4b411`: Strictly speaking, :eqref:`eq_price-area` is an *affine transformation* of input features, which is characterized by a *linear transformation* of features via weighted sum, combined with a *translation* via the added bias.
- `ctx_a3223aad900f9e33b14c8db7`: This model mapped our inputs directly to our outputs via a single affine transformation, followed by a softmax operation.

## 4. Approximate Training

- `sense_id`: `d2lce_28ab2b419f6b871a62a06060`
- Split: `development`
- Model definition: training methods that reduce computation by using approximations instead of the full exact objective
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_3ac4117865b320b21d1179ce`: In order to reduce the aforementioned computational complexity, this section will introduce two approximate training methods: *negative sampling* and *hierarchical softmax*.
- `ctx_3ef031323fb6394442845745`: Due to the similarity between the skip-gram model and the continuous bag of words model, we will just take the skip-gram model as an example to describe these two approximate training methods.
- `ctx_d114388fd9000ff629d180ce`: We use negative sampling for approximate training.
- `ctx_12eba5ccda65530aa7ad9f62`: As an alternative approximate training method, *hierarchical softmax* uses the binary tree, a data structure illustrated in :numref:`fig_hi_softmax`, where each leaf node of the tree represents a word in dictionary $\mathcal{V}$.
- `ctx_255f8d1d0d00e96535232367`: Fortunately, since $L(w_o)-1$ is on the order of $\mathcal{O}(\text{log}_2|\mathcal{V}|)$ due to the binary tree structure, when the dictionary size $\mathcal{V}$ is huge, the computational cost for each training step using hierarchical softmax is significantly reduced compared with that without approximate training.

### Backup contexts

- `ctx_85acded56d4e4fc62d1ebf6b`: Now that we know the technical details of the word2vec models and approximate training methods, let us walk through their implementations.
- `ctx_edcd80c52e50572aaffd0ddf`: ![Hierarchical softmax for approximate training, where each leaf node of the tree represents a word in the dictionary.](../img/hi-softmax.svg) :label:`fig_hi_softmax`
- `ctx_23465c1f0b2d1114ed78c140`: # Approximate Training :label:`sec_approx_train`

### Contrastive contexts

- `ctxx_24e9a9c879174e4c14787b23`: [Synthetic] Approximate training cuts computation, whereas exact training evaluates the full objective each step.

### Definition evidence

- `ctx_3ac4117865b320b21d1179ce`: In order to reduce the aforementioned computational complexity, this section will introduce two approximate training methods: *negative sampling* and *hierarchical softmax*.
- `ctx_12eba5ccda65530aa7ad9f62`: As an alternative approximate training method, *hierarchical softmax* uses the binary tree, a data structure illustrated in :numref:`fig_hi_softmax`, where each leaf node of the tree represents a word in dictionary $\mathcal{V}$.
- `ctx_255f8d1d0d00e96535232367`: Fortunately, since $L(w_o)-1$ is on the order of $\mathcal{O}(\text{log}_2|\mathcal{V}|)$ due to the binary tree structure, when the dictionary size $\mathcal{V}$ is huge, the computational cost for each training step using hierarchical softmax is significantly reduced compared with that without approximate training.

### Part-of-speech evidence

- `ctx_23465c1f0b2d1114ed78c140`: # Approximate Training :label:`sec_approx_train`
- `ctx_85acded56d4e4fc62d1ebf6b`: Now that we know the technical details of the word2vec models and approximate training methods, let us walk through their implementations.

## 5. attention scoring function

- `sense_id`: `d2lce_18c3da2d5bdd6d05a83982fa`
- Split: `development`
- Model definition: a function that maps a query and key to a score used to compute attention weights.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c42a588ea67a1ab12765c55d`: Treating the exponent of the Gaussian kernel in :eqref:`eq_nadaraya-watson-gaussian` as an *attention scoring function* (or *scoring function* for short), the results of this function were essentially fed into a softmax operation.
- `ctx_8116f867673a73f0e047a71a`: where the attention weight (scalar) for the query $\mathbf{q}$ and key $\mathbf{k}_i$ is computed by the softmax operation of an attention scoring function $a$ that maps two vectors to a scalar:
- `ctx_320122f21daa284575796213`: As we can see, different choices of the attention scoring function $a$ lead to different behaviors of attention pooling.
- `ctx_aff8a66e4ec4b4cda7dbdf1b`: Denoting an attention scoring function by $a$, :numref:`fig_attention_output` illustrates how the output of attention pooling can be computed as a weighted sum of values.
- `ctx_4619262486ac659e6273c135`: Given a query $\mathbf{q} \in \mathbb{R}^q$ and a key $\mathbf{k} \in \mathbb{R}^k$, the *additive attention* scoring function

### Backup contexts

- `ctx_c47eb631641cbc20179e654c`: To ensure that the variance of the dot product still remains one regardless of vector length, the *scaled dot-product attention* scoring function
- `ctx_ceff1252a50a323ce62c83d4`: In general, when queries and keys are vectors of different lengths, we can use additive attention as the scoring function.
- `ctx_d5c7268c2ea127e80cfdfb47`: A more computationally efficient design for the scoring function can be simply dot product.

### Contrastive contexts

- `ctxx_9e8a3fd79bdc855d1a7e0d33`: Synthetic boundary probe: "attention scoring function" is quoted here only as a document label, not as an occurrence of the reviewed D2L sense.

### Definition evidence

- `ctx_c42a588ea67a1ab12765c55d`: Treating the exponent of the Gaussian kernel in :eqref:`eq_nadaraya-watson-gaussian` as an *attention scoring function* (or *scoring function* for short), the results of this function were essentially fed into a softmax operation.
- `ctx_8116f867673a73f0e047a71a`: where the attention weight (scalar) for the query $\mathbf{q}$ and key $\mathbf{k}_i$ is computed by the softmax operation of an attention scoring function $a$ that maps two vectors to a scalar:

### Part-of-speech evidence

- `ctx_c42a588ea67a1ab12765c55d`: Treating the exponent of the Gaussian kernel in :eqref:`eq_nadaraya-watson-gaussian` as an *attention scoring function* (or *scoring function* for short), the results of this function were essentially fed into a softmax operation.
- `ctx_aff8a66e4ec4b4cda7dbdf1b`: Denoting an attention scoring function by $a$, :numref:`fig_attention_output` illustrates how the output of attention pooling can be computed as a weighted sum of values.

## 6. BatchNorm

- `sense_id`: `d2lce_4abd762bcd34d370b4fe6498`
- Split: `development`
- Model definition: the layer or class name for batch normalization.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_8f8f50278fcee237079dc232`: We can now [**create a proper `BatchNorm` layer.**] Our layer will maintain proper parameters for scale `gamma` and shift `beta`, both of which will be updated in the course of training.
- `ctx_cc13b838430cc6b65f7256c9`: ```{.python .input} #@tab tensorflow class BatchNorm(tf.keras.layers.Layer): def __init__(self, **kwargs): super(BatchNorm, self).__init__(**kwargs) def build(self, input_shape): weight_shape = [input_shape[-1], ] # The scale parameter and the shift parameter (model parameters) are # initialized to 1 and 0, respectively self.gamma = self.add_weight(name='gamma', shape=weight_shape, initializer=tf.initializers.ones, trainable=True) self.beta = self.add_weight(name='beta', shape=weight_shape, initializer=tf.initializers.zeros, trainable=True) # The variables that are not model parameters are initialized to 0 self.moving_mean = self.add_weight(name='moving_mean', shape=weight_shape, initializer=tf.initializers.zeros, trainable=False) self.moving_variance = self.add_weight(name='moving_variance', shape=weight_shape, initializer=tf.initializers.ones, trainable=False) super(BatchNorm, self).build(input_shape) def assign_moving_average(self, variable, value): momentum = 0.9 delta = variable * momentum + value * (1 - momentum) return variable.assign(delta) @tf.function def call(self, inputs, training): if training: axes = list(range(len(inputs.shape) - 1)) batch_mean = tf.reduce_mean(inputs, axes, keepdims=True) batch_variance = tf.reduce_mean(tf.math.squared_difference( inputs, tf.stop_gradient(batch_mean)), axes, keepdims=True) batch_mean = tf.squeeze(batch_mean, axes) batch_variance = tf.squeeze(batch_variance, axes) mean_update = self.assign_moving_average( self.moving_mean, batch_mean) variance_update = self.assign_moving_average( self.moving_variance, batch_variance) self.add_update(mean_update) self.add_update(variance_update) mean, variance = batch_mean, batch_variance else: mean, variance = self.moving_mean, self.moving_variance output = batch_norm(inputs, moving_mean=mean, moving_var=variance, beta=self.beta, gamma=self.gamma, eps=1e-5) return output ```
- `ctx_2bba7bfd16dd89a39a9179f1`: ```{.python .input} ln = nn.LayerNorm() ln.initialize() bn = nn.BatchNorm() bn.initialize() X = d2l.tensor([[1, 2], [2, 3]]) # Compute mean and variance from `X` in the training mode with autograd.record(): print('layer norm:', ln(X), '\nbatch norm:', bn(X)) ```
- `ctx_5799f6d95cc38b1ae654394a`: ```{.python .input} class BatchNorm(nn.Block): # `num_features`: the number of outputs for a fully-connected layer # or the number of output channels for a convolutional layer.
- `ctx_a70b42d220709405815636f8`: ```{.python .input} #@tab pytorch class BatchNorm(nn.Module): # `num_features`: the number of outputs for a fully-connected layer # or the number of output channels for a convolutional layer.

### Backup contexts

- `ctx_2a4b835e03acf05a36784e49`: ```{.python .input} def down_sample_blk(num_channels): blk = nn.Sequential() for _ in range(2): blk.add(nn.Conv2D(num_channels, kernel_size=3, padding=1), nn.BatchNorm(in_channels=num_channels), nn.Activation('relu')) blk.add(nn.MaxPool2D(2)) return blk ```
- `ctx_97626c8a07aa5d9bfd5cd128`: ```{.python .input} #@save def resnet18(num_classes): """A slightly modified ResNet-18 model.""" def resnet_block(num_channels, num_residuals, first_block=False): blk = nn.Sequential() for i in range(num_residuals): if i == 0 and not first_block: blk.add(d2l.Residual( num_channels, use_1x1conv=True, strides=2)) else: blk.add(d2l.Residual(num_channels)) return blk net = nn.Sequential() # This model uses a smaller convolution kernel, stride, and padding and # removes the maximum pooling layer net.add(nn.Conv2D(64, kernel_size=3, strides=1, padding=1), nn.BatchNorm(), nn.Activation('relu')) net.add(resnet_block(64, 2, first_block=True), resnet_block(128, 2), resnet_block(256, 2), resnet_block(512, 2)) net.add(nn.GlobalAvgPool2D(), nn.Dense(num_classes)) return net ```
- `ctx_a112ae80926b023797d45e91`: ```{.python .input} class G_block(nn.Block): def __init__(self, channels, kernel_size=4, strides=2, padding=1, **kwargs): super(G_block, self).__init__(**kwargs) self.conv2d_trans = nn.Conv2DTranspose( channels, kernel_size, strides, padding, use_bias=False) self.batch_norm = nn.BatchNorm() self.activation = nn.Activation('relu') def forward(self, X): return self.activation(self.batch_norm(self.conv2d_trans(X))) ```

### Contrastive contexts

- `ctxx_e991ae3e7596cfe8d1ca56f6`: Synthetic: batch norm describes the normalization technique in general, while BatchNorm here is the specific layer/class name used in code.

### Definition evidence

- `ctx_8f8f50278fcee237079dc232`: We can now [**create a proper `BatchNorm` layer.**] Our layer will maintain proper parameters for scale `gamma` and shift `beta`, both of which will be updated in the course of training.
- `ctx_2bba7bfd16dd89a39a9179f1`: ```{.python .input} ln = nn.LayerNorm() ln.initialize() bn = nn.BatchNorm() bn.initialize() X = d2l.tensor([[1, 2], [2, 3]]) # Compute mean and variance from `X` in the training mode with autograd.record(): print('layer norm:', ln(X), '\nbatch norm:', bn(X)) ```
- `ctx_cc13b838430cc6b65f7256c9`: ```{.python .input} #@tab tensorflow class BatchNorm(tf.keras.layers.Layer): def __init__(self, **kwargs): super(BatchNorm, self).__init__(**kwargs) def build(self, input_shape): weight_shape = [input_shape[-1], ] # The scale parameter and the shift parameter (model parameters) are # initialized to 1 and 0, respectively self.gamma = self.add_weight(name='gamma', shape=weight_shape, initializer=tf.initializers.ones, trainable=True) self.beta = self.add_weight(name='beta', shape=weight_shape, initializer=tf.initializers.zeros, trainable=True) # The variables that are not model parameters are initialized to 0 self.moving_mean = self.add_weight(name='moving_mean', shape=weight_shape, initializer=tf.initializers.zeros, trainable=False) self.moving_variance = self.add_weight(name='moving_variance', shape=weight_shape, initializer=tf.initializers.ones, trainable=False) super(BatchNorm, self).build(input_shape) def assign_moving_average(self, variable, value): momentum = 0.9 delta = variable * momentum + value * (1 - momentum) return variable.assign(delta) @tf.function def call(self, inputs, training): if training: axes = list(range(len(inputs.shape) - 1)) batch_mean = tf.reduce_mean(inputs, axes, keepdims=True) batch_variance = tf.reduce_mean(tf.math.squared_difference( inputs, tf.stop_gradient(batch_mean)), axes, keepdims=True) batch_mean = tf.squeeze(batch_mean, axes) batch_variance = tf.squeeze(batch_variance, axes) mean_update = self.assign_moving_average( self.moving_mean, batch_mean) variance_update = self.assign_moving_average( self.moving_variance, batch_variance) self.add_update(mean_update) self.add_update(variance_update) mean, variance = batch_mean, batch_variance else: mean, variance = self.moving_mean, self.moving_variance output = batch_norm(inputs, moving_mean=mean, moving_var=variance, beta=self.beta, gamma=self.gamma, eps=1e-5) return output ```

### Part-of-speech evidence

- `ctx_8f8f50278fcee237079dc232`: We can now [**create a proper `BatchNorm` layer.**] Our layer will maintain proper parameters for scale `gamma` and shift `beta`, both of which will be updated in the course of training.
- `ctx_97626c8a07aa5d9bfd5cd128`: ```{.python .input} #@save def resnet18(num_classes): """A slightly modified ResNet-18 model.""" def resnet_block(num_channels, num_residuals, first_block=False): blk = nn.Sequential() for i in range(num_residuals): if i == 0 and not first_block: blk.add(d2l.Residual( num_channels, use_1x1conv=True, strides=2)) else: blk.add(d2l.Residual(num_channels)) return blk net = nn.Sequential() # This model uses a smaller convolution kernel, stride, and padding and # removes the maximum pooling layer net.add(nn.Conv2D(64, kernel_size=3, strides=1, padding=1), nn.BatchNorm(), nn.Activation('relu')) net.add(resnet_block(64, 2, first_block=True), resnet_block(128, 2), resnet_block(256, 2), resnet_block(512, 2)) net.add(nn.GlobalAvgPool2D(), nn.Dense(num_classes)) return net ```
- `ctx_a112ae80926b023797d45e91`: ```{.python .input} class G_block(nn.Block): def __init__(self, channels, kernel_size=4, strides=2, padding=1, **kwargs): super(G_block, self).__init__(**kwargs) self.conv2d_trans = nn.Conv2DTranspose( channels, kernel_size, strides, padding, use_bias=False) self.batch_norm = nn.BatchNorm() self.activation = nn.Activation('relu') def forward(self, X): return self.activation(self.batch_norm(self.conv2d_trans(X))) ```

## 7. beta

- `sense_id`: `d2lce_20a7e6887718c68fb6b88a05`
- Split: `development`
- Model definition: Greek letter used as a mathematical symbol; in batch normalization, it denotes the learnable shift parameter.
- Model POS: `symbol`

### Primary contexts

- `ctx_7f55c44f2cea0740cebddf92`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```
- `ctx_60049e1f8e96ead596f5d3a2`: Note that $\boldsymbol{\gamma}$ and $\boldsymbol{\beta}$ are parameters that need to be learned jointly with the other model parameters.
- `ctx_6c3c6612ebc8fab20277caea`: some other magic number) is an arbitrary choice, we commonly include elementwise *scale parameter* $\boldsymbol{\gamma}$ and *shift parameter* $\boldsymbol{\beta}$ that have the same shape as $\mathbf{x}$.
- `ctx_4cfe5e8d436f58421a53ed72`: $$\mathrm{BN}(\mathbf{x}) = \boldsymbol{\gamma} \odot \frac{\mathbf{x} - \hat{\boldsymbol{\mu}}_\mathcal{B}}{\hat{\boldsymbol{\sigma}}_\mathcal{B}} + \boldsymbol{\beta}.$$ :eqlabel:`eq_batchnorm`
- `ctx_878c161653cd7f18ca9484fb`: ```{.python .input} from d2l import mxnet as d2l from mxnet import autograd, np, npx, init from mxnet.gluon import nn npx.set_np() def batch_norm(X, gamma, beta, moving_mean, moving_var, eps, momentum): # Use `autograd` to determine whether the current mode is training mode or # prediction mode if not autograd.is_training(): # If it is prediction mode, directly use the mean and variance # obtained by moving average X_hat = (X - moving_mean) / np.sqrt(moving_var + eps) else: assert len(X.shape) in (2, 4) if len(X.shape) == 2: # When using a fully-connected layer, calculate the mean and # variance on the feature dimension mean = X.mean(axis=0) var = ((X - mean) ** 2).mean(axis=0) else: # When using a two-dimensional convolutional layer, calculate the # mean and variance on the channel dimension (axis=1).

### Backup contexts

- `ctx_89205c55ccfdb1cec5251eea`: Suppose that we have some fixed column vector $\boldsymbol{\beta}$, and we want to take the product function $f(\mathbf{x}) = \boldsymbol{\beta}^\top\mathbf{x}$, and understand how the dot product changes when we change $\mathbf{x}$.
- `ctx_14774fa1cfce5a1a3478275f`: $$ \boldsymbol{\beta}_i = \sum_{j=1}^{n}\frac{\exp(e_{ij})}{ \sum_{k=1}^{n} \exp(e_{ik})} \mathbf{b}_j.
- `ctx_ba0d4cc04149820abe45bc7c`: According to the mean value theorem, there exist $\alpha \in [a, x]$ and $\beta \in [x, b]$ such that

### Contrastive contexts

- `ctxx_46d8100baa5bd274aaca168a`: Synthetic: In software versioning, beta refers to a pre-release testing stage, not a mathematical parameter symbol.

### Definition evidence

- `ctx_60049e1f8e96ead596f5d3a2`: Note that $\boldsymbol{\gamma}$ and $\boldsymbol{\beta}$ are parameters that need to be learned jointly with the other model parameters.
- `ctx_6c3c6612ebc8fab20277caea`: some other magic number) is an arbitrary choice, we commonly include elementwise *scale parameter* $\boldsymbol{\gamma}$ and *shift parameter* $\boldsymbol{\beta}$ that have the same shape as $\mathbf{x}$.
- `ctx_7f55c44f2cea0740cebddf92`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```
- `ctx_4cfe5e8d436f58421a53ed72`: $$\mathrm{BN}(\mathbf{x}) = \boldsymbol{\gamma} \odot \frac{\mathbf{x} - \hat{\boldsymbol{\mu}}_\mathcal{B}}{\hat{\boldsymbol{\sigma}}_\mathcal{B}} + \boldsymbol{\beta}.$$ :eqlabel:`eq_batchnorm`

### Part-of-speech evidence

- `ctx_4cfe5e8d436f58421a53ed72`: $$\mathrm{BN}(\mathbf{x}) = \boldsymbol{\gamma} \odot \frac{\mathbf{x} - \hat{\boldsymbol{\mu}}_\mathcal{B}}{\hat{\boldsymbol{\sigma}}_\mathcal{B}} + \boldsymbol{\beta}.$$ :eqlabel:`eq_batchnorm`
- `ctx_ba0d4cc04149820abe45bc7c`: According to the mean value theorem, there exist $\alpha \in [a, x]$ and $\beta \in [x, b]$ such that
- `ctx_89205c55ccfdb1cec5251eea`: Suppose that we have some fixed column vector $\boldsymbol{\beta}$, and we want to take the product function $f(\mathbf{x}) = \boldsymbol{\beta}^\top\mathbf{x}$, and understand how the dot product changes when we change $\mathbf{x}$.

## 8. bidirectional RNN

- `sense_id`: `d2lce_80f4d6555a6ea1d2e5e881a1`
- Split: `development`
- Model definition: a recurrent neural network architecture that processes a sequence in both forward and backward directions
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_e8b4b42870033c825829a5f6`: In deep bidirectional RNNs with multiple hidden layers, such information is passed on as *input* to the next bidirectional layer.
- `ctx_97859a8cd0781c52d0d6f199`: Bidirectional RNNs were introduced by :cite:`Schuster.Paliwal.1997`.
- `ctx_f66d6f0f60f34de0d401b86a`: ![Architecture of a bidirectional RNN.](../img/birnn.svg) :label:`fig_birnn`
- `ctx_251a0545759171bb473405d4`: One of the key features of a bidirectional RNN is that information from both ends of the sequence is used to estimate the output.
- `ctx_4da4c97d28bf6a81e6e7e0fb`: As a specific example illustrated in :numref:`fig_nlp-map-sa-rnn`, we will represent each token using the pretrained GloVe model, and feed these token representations into a multilayer bidirectional RNN to obtain the text sequence representation, which will be transformed into sentiment analysis outputs :cite:`Maas.Daly.Pham.ea.2011`.

### Backup contexts

- `ctx_6ffe6a41763c493d385a9d08`: :numref:`fig_birnn` illustrates the architecture of a bidirectional RNN with a single hidden layer.
- `ctx_a262d765aa2b98acc9fb0307`: Hence, if we were to use a bidirectional RNN naively we would not get a very good accuracy: during training we have past and future data to estimate the present.
- `ctx_be13633e5269ebd62d16e8f2`: *Bidirectional RNNs* add a hidden layer that passes information in a backward direction to more flexibly process such information.

### Contrastive contexts

- `ctxx_8f427929265cd736a42fb29a`: Synthetic: A bidirectional RNN reads the sequence in both directions, unlike a unidirectional RNN.

### Definition evidence

- `ctx_be13633e5269ebd62d16e8f2`: *Bidirectional RNNs* add a hidden layer that passes information in a backward direction to more flexibly process such information.
- `ctx_251a0545759171bb473405d4`: One of the key features of a bidirectional RNN is that information from both ends of the sequence is used to estimate the output.
- `ctx_a262d765aa2b98acc9fb0307`: Hence, if we were to use a bidirectional RNN naively we would not get a very good accuracy: during training we have past and future data to estimate the present.

### Part-of-speech evidence

- `ctx_6ffe6a41763c493d385a9d08`: :numref:`fig_birnn` illustrates the architecture of a bidirectional RNN with a single hidden layer.
- `ctx_be13633e5269ebd62d16e8f2`: *Bidirectional RNNs* add a hidden layer that passes information in a backward direction to more flexibly process such information.

## 9. bit

- `sense_id`: `d2lce_53c32398310471fac3dacf35`
- Split: `development`
- Model definition: a small amount; used informally to mean slightly or somewhat.
- Model POS: `noun`

### Primary contexts

- `ctx_bc735116b032003b647bf1d5`: Determining which way to move each parameter at each step of an algorithm requires a little bit of calculus, which will be briefly introduced.
- `ctx_48fb92c20348628ff3c83349`: In this section, we will delve a bit more deeply into the details of backpropagation for sequence models and why (and how) the mathematics works.
- `ctx_30cb9519a863d7ebe60dd4e0`: To make some progress we need a bit of mathematics.
- `ctx_a08fef290a47362d440d8409`: Since the softmax and the corresponding loss are so common, it is worth understanding a bit better how it is computed.
- `ctx_296377e3411a5f06ef38c871`: Reality is a bit more complicated than the most naive interpretations of this intuition since representations are not learned independent but are rather optimized to be jointly useful.

### Backup contexts

- `ctx_5717eff884f463a81a21a526`: Within RNNs this is a bit trickier, since we first need to decide how and where to add extra nonlinearity.
- `ctx_6bf5da537a25d356b2e5e0ac`: You might think of your neural network as being a bit like the C programming language.
- `ctx_decede697ad47b1366644611`: ```{.python .input} #@tab tensorflow # tf.keras behaves a bit differently.

### Contrastive contexts

- `ctxx_500edc85fffab271e5a1c3df`: Synthetic: In information theory, a bit is a unit of information rather than just a small amount.

### Definition evidence

- `ctx_bc735116b032003b647bf1d5`: Determining which way to move each parameter at each step of an algorithm requires a little bit of calculus, which will be briefly introduced.
- `ctx_30cb9519a863d7ebe60dd4e0`: To make some progress we need a bit of mathematics.
- `ctx_48fb92c20348628ff3c83349`: In this section, we will delve a bit more deeply into the details of backpropagation for sequence models and why (and how) the mathematics works.

### Part-of-speech evidence

- `ctx_bc735116b032003b647bf1d5`: Determining which way to move each parameter at each step of an algorithm requires a little bit of calculus, which will be briefly introduced.
- `ctx_6bf5da537a25d356b2e5e0ac`: You might think of your neural network as being a bit like the C programming language.
- `ctx_5717eff884f463a81a21a526`: Within RNNs this is a bit trickier, since we first need to decide how and where to add extra nonlinearity.

## 10. broadcasting

- `sense_id`: `d2lce_499fa9391d57e930a19f1b19`
- Split: `development`
- Model definition: A tensor operation that automatically expands one or both arrays so elementwise operations can be performed despite differing shapes.
- Model POS: `noun`

### Primary contexts

- `ctx_55af151b5d571b0a523981a9`: ## Broadcasting Mechanism :label:`subsec_broadcasting`
- `ctx_84ba03c3c9e4d38df60e0aac`: Thus, broadcasting (see :numref:`subsec_broadcasting`) is applied during the summation.
- `ctx_bcf04980bdfe689c9e1c560b`: ```{.python .input} def train(lambd): w, b = init_params() net, loss = lambda X: d2l.linreg(X, w, b), d2l.squared_loss num_epochs, lr = 100, 0.003 animator = d2l.Animator(xlabel='epochs', ylabel='loss', yscale='log', xlim=[5, num_epochs], legend=['train', 'test']) for epoch in range(num_epochs): for X, y in train_iter: with autograd.record(): # The L2 norm penalty term has been added, and broadcasting # makes `l2_penalty(w)` a vector whose length is `batch_size` l = loss(net(X), y) + lambd * l2_penalty(w) l.backward() d2l.sgd([w, b], lr, batch_size) if (epoch + 1) % 5 == 0: animator.add(epoch + 1, (d2l.evaluate_loss(net, train_iter, loss), d2l.evaluate_loss(net, test_iter, loss))) print('L2 norm of w:', np.linalg.norm(w)) ```
- `ctx_84ca6088137d56c32c100be2`: Under certain conditions, even when shapes differ, we can still [**perform elementwise operations by invoking the *broadcasting mechanism*.**] This mechanism works in the following way: First, expand one or both arrays by copying elements appropriately so that after this transformation, the two tensors have the same shape.
- `ctx_326dc3e07d0b8de256dd37c6`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```

### Backup contexts

- `ctx_d3acc09e8a6080e3399bae77`: Sum them up with # broadcasting features = np.expand_dims(queries, axis=2) + np.expand_dims( keys, axis=1) features = np.tanh(features) # There is only one output of `self.w_v`, so we remove the last # one-dimensional entry from the shape.
- `ctx_6b24258694566dc3b24b4311`: where broadcasting (see :numref:`subsec_broadcasting`) is applied during the summation.
- `ctx_7b2efc8bfbd4cce59d02222e`: Note that broadcasting (see :numref:`subsec_broadcasting`) is triggered during the summation.

### Contrastive contexts

- `ctxx_f2b52228b81142cbb519a842`: [Synthetic] The broadcasting reached millions of listeners across the country that night.

### Definition evidence

- `ctx_84ca6088137d56c32c100be2`: Under certain conditions, even when shapes differ, we can still [**perform elementwise operations by invoking the *broadcasting mechanism*.**] This mechanism works in the following way: First, expand one or both arrays by copying elements appropriately so that after this transformation, the two tensors have the same shape.
- `ctx_bcf04980bdfe689c9e1c560b`: ```{.python .input} def train(lambd): w, b = init_params() net, loss = lambda X: d2l.linreg(X, w, b), d2l.squared_loss num_epochs, lr = 100, 0.003 animator = d2l.Animator(xlabel='epochs', ylabel='loss', yscale='log', xlim=[5, num_epochs], legend=['train', 'test']) for epoch in range(num_epochs): for X, y in train_iter: with autograd.record(): # The L2 norm penalty term has been added, and broadcasting # makes `l2_penalty(w)` a vector whose length is `batch_size` l = loss(net(X), y) + lambd * l2_penalty(w) l.backward() d2l.sgd([w, b], lr, batch_size) if (epoch + 1) % 5 == 0: animator.add(epoch + 1, (d2l.evaluate_loss(net, train_iter, loss), d2l.evaluate_loss(net, test_iter, loss))) print('L2 norm of w:', np.linalg.norm(w)) ```
- `ctx_326dc3e07d0b8de256dd37c6`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```

### Part-of-speech evidence

- `ctx_6b24258694566dc3b24b4311`: where broadcasting (see :numref:`subsec_broadcasting`) is applied during the summation.
- `ctx_84ca6088137d56c32c100be2`: Under certain conditions, even when shapes differ, we can still [**perform elementwise operations by invoking the *broadcasting mechanism*.**] This mechanism works in the following way: First, expand one or both arrays by copying elements appropriately so that after this transformation, the two tensors have the same shape.
