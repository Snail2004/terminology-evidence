# Stage A sense casebook

This casebook contains no Vietnamese candidates. Review the English sense
definition and part of speech from the supplied corpus evidence only.

## 1. channels

- `sense_id`: `d2lce_270e1a75bb70807d9c2dd507`
- Model definition: separate streams or dimensions of data, especially feature or color dimensions in neural networks and images
- Model POS: `noun`

### Primary contexts

- `ctx_50b02cc418dce008fb37b2ea`: Note that the dataset consists of grayscale images, whose number of channels is 1.
- `ctx_4bb23f20ff0fa67bc6c1be83`: Tensors will become more important when we start working with images,  which arrive as $n$-dimensional arrays with 3 axes corresponding to the height, width, and a *channel* axis for stacking the color channels (red, green, and blue).
- `ctx_79213e2c4e36b995f90f0b30`: A $200\times 200$ color photograph would consist of $200\times200\times3=120000$ numerical values, corresponding to the brightness of the red, green, and blue channels for each spatial location.
- `ctx_e066da075985b1450c0cd804`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels  at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_e7437fb0f0bdad9c3645e83b`: Moreover, AlexNet has ten times more convolution channels than LeNet.

### Backup contexts

- `ctx_e7ad2905fd773a830f6b4c43`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, gluon, init, lr_scheduler, np, npx from mxnet.gluon import nn npx.set_np()  net = nn.HybridSequential() net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'),         nn.MaxPool2D(pool_size=2, strides=2),         nn.Conv2D(channels=16, kernel_size=5, activation='relu'),         nn.MaxPool2D(pool_size=2, strides=2),         nn.Dense(120, activation='relu'),         nn.Dense(84, activation='relu'),         nn.Dense(10)) net.hybridize() loss = gluon.loss.SoftmaxCrossEntropyLoss() device = d2l.try_gpu()  batch_size = 256 train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size)  # The code is almost identical to `d2l.train_ch6` defined in the  # lenet section of chapter convolutional neural networks def train(net, train_iter, test_iter, num_epochs, loss, trainer, device):     net.initialize(force_reinit=True, ctx=device, init=init.Xavier())     animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs],                             legend=['train loss', 'train acc', 'test acc'])     for epoch in range(num_epochs):         metric = d2l.Accumulator(3)  # train_loss, train_acc, num_examples         for i, (X, y) in enumerate(train_iter):             X, y = X.as_in_ctx(device), y.as_in_ctx(device)             with autograd.record():                 y_hat = net(X)                 l = loss(y_hat, y)             l.backward()             trainer.step(X.shape[0])             metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0])             train_loss = metric[0] / metric[2]             train_acc = metric[1] / metric[2]             if (i + 1) % 50 == 0:                 animator.add(epoch + i / len(train_iter),                              (train_loss, train_acc, None))         test_acc = d2l.evaluate_accuracy_gpu(net, test_iter)         animator.add(epoch + 1, (None, None, test_acc))     print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, '           f'test acc {test_acc:.3f}') ```
- `ctx_93be4d86c465d785ac0a0ec1`: For now, we only need to know that since the sequence length is $n$, the numbers of input and output channels are both $d$, the computational complexity of the convolutional layer is $\mathcal{O}(knd^2)$.

### Contrastive contexts

- `ctx_0f6cacd1df0fd9a1a8c5ed8d`: CPUs have between 2 and 4 memory channels, i.e., they have between 4 0GB/s and 100 GB/s peak memory bandwidth.

## 2. Generator

- `sense_id`: `d2lce_73c8ce2915c4c64a52fab4a2`
- Model definition: the model in a GAN that produces fake data samples to resemble real data
- Model POS: `noun`

### Primary contexts

- `ctx_ce5770ebbcecab9cd14b31d1`: At their heart, GANs rely on the idea that a data generator is good if we cannot tell fake data apart from real data.
- `ctx_111ebd3664347c4b99a35b2e`: We call this the generator network.
- `ctx_2aca2894517926700f9e34d1`: This information, in turn is used to improve the generator network, and so on.
- `ctx_33e923407e067945b2c17e33`: The generator network attempts to fool the discriminator network.
- `ctx_545710fbceae0d3428fd3a00`: The discriminator is a binary classifier to distinguish if the input $x$ is real (from real data) or fake (from the generator).

### Backup contexts

- `ctx_2cc55c7c27ecd856fe623eec`: This allows us to improve the data generator until it generates something that resembles the real data.

### Contrastive contexts

- `ctx_5b966a1024783f92c10a4b61`: (index 0 is the     # excluded unknown token) in the vocabulary     sampling_weights = [counter[vocab.to_tokens(i)]**0.75                         for i in range(1, len(vocab))]     all_negatives, generator = [], RandomGenerator(sampling_weights)     for contexts in all_contexts:         negatives = []         while len(negatives) < len(contexts) * K:             neg = generator.draw()             # Noise words cannot be context words             if neg not in contexts:                 negatives.append(neg)         all_negatives.append(negatives)     return all_negatives  all_negatives = get_negatives(all_contexts, vocab, counter, 5) ```

## 3. keys

- `sense_id`: `d2lce_776fd3328d5e31aeebe484ec`
- Model definition: items in attention mechanisms that interact with queries to determine weights over values.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_3c14b0a0feee3453249740d4`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_8a0bb471a0a435399c5293f9`: ## Queries, Keys, and Values
- `ctx_a91d32742b0c4bd9260a1334`: ![Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).](../img/qkv.svg) :label:`fig_qkv`
- `ctx_cac33728aec4217e211eb0da`: In practice, attention pooling aggregates values using weighted average, where weights are computed between the given query and different keys.
- `ctx_01b68302bb447eeeccec65cb`: ```{.python .input} #@tab all attention_weights = d2l.reshape(d2l.eye(10), (1, 1, 10, 10)) show_heatmaps(attention_weights, xlabel='Keys', ylabel='Queries') ```

### Backup contexts

- `ctx_9dd2818707ebbd9b97accac9`: Its input `matrices` has the shape (number of rows for display, number of columns for display, number of queries, number of keys).

### Contrastive contexts

- `ctx_2d690f0922be1eb4be420c9d`: Since we start the merging process from a vocabulary of only single characters and special symbols, space is inserted between every pair of consecutive characters within each word (keys of the dictionary `token_freqs`).

## 4. multiple channels

- `sense_id`: `d2lce_ccf7d0a5109d86ee76a75b9c`
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
- `ctx_54f8c3cb816277ace430df97`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels  at each layer, and a careful discussion of the structure of modern architectures.

### Contrastive contexts

- `ctx_ba2a299168416499932ae161`: Typically pairs of memory modules are used to allow for multiple channels.

## 5. hypothesis

- `sense_id`: `d2lce_dbb300a90e4b0f8b815b5e12`
- Model definition: a sentence or claim paired with a premise in natural language inference, whose relation to the premise is judged
- Model POS: `noun`

### Primary contexts

- `ctx_73c90581e009fa46017ce4ac`: *Natural language inference* studies whether a *hypothesis* can be inferred from a *premise*, where both are a text sequence.
- `ctx_a40d24f872fa062513992a23`: > Hypothesis: The musicians are famous.
- `ctx_22622fdadf6bcfc02e71f0bc`: > Hypothesis: The man is sleeping.
- `ctx_368170831130d1827fe9f440`: > Hypothesis: Two women are showing affection.
- `ctx_39675d05889cacc1f1ffdf06`: * *Contradiction*: the negation of the hypothesis can be inferred from the premise.

### Backup contexts

- `ctx_48e44a2af0f53ee5fa7c2a13`: * *Entailment*: the hypothesis can be inferred from the premise.
- `ctx_5834bda7132436c8ef52cebd`: For example, the following pair will be labeled as *entailment* because "showing affection" in the hypothesis can be inferred from "hugging one another" in the premise.

### Contrastive contexts

- `ctx_d6d0b1ea059aae00cde5e9fc`: While statistics is far too large a field to do justice in a short section, we will introduce fundamental concepts that all machine learning practitioners should be aware of, in particular: evaluating and comparing estimators, conducting hypothesis tests, and constructing confidence intervals.
