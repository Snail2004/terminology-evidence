# Stage A sense casebook: development_003

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. convolutional layer

- `sense_id`: `d2lce_d2bfc7b3a0a02ddfd71b3526`
- Split: `development`
- Model definition: a neural network layer that applies convolution filters to its input
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_5e631862394a07c36c8b145d`: Note that :eqref:`eq_conv-layer`, in a nutshell, is a *convolutional layer*.
- `ctx_63c1cf674ecc0c73541e5bad`: Compared with the bidirectional RNN model in :numref:`sec_sentiment_rnn`, besides replacing recurrent layers with convolutional layers, we also use two embedding layers: one with trainable weights and the other with fixed weights.
- `ctx_807d458f1292afa6921eb40d`: The basic block of the generator contains a transposed convolution layer followed by the batch normalization and ReLU activation.
- `ctx_122d659e4bf66f4b335db6fb`: The horizontal convolutional layer has $d$ horizontal filters $\mathbf{F}^j \in \mathbb{R}^{h \times k}, 1 \leq j \leq d, h = \{1, ..., L\}$, and the vertical convolutional layer has $d'$ vertical filters $\mathbf{G}^j \in \mathbb{R}^{ L \times 1}, 1 \leq j \leq d'$.
- `ctx_3a787d4bd1c1d0430072fda6`: Consider a convolutional layer whose kernel size is $k$.

### Backup contexts

- `ctx_bf6f31236287c027cde6c33f`: In :numref:`sec_pooling`, we explained that the pooling layer can reduce the sensitivity of a convolutional layer to the target position.
- `ctx_3a83fa91846a046a5913f179`: Fortunately, this math is strikingly similar to that required to calculate convolutional layers.
- `ctx_1c4e159780d719c00ce3022e`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.

### Contrastive contexts

- `ctxx_d055f040c0bff77d97b93e9f`: Synthetic: This convolutional layer of rock was formed over millions of years.

### Definition evidence

- `ctx_3a787d4bd1c1d0430072fda6`: Consider a convolutional layer whose kernel size is $k$.
- `ctx_122d659e4bf66f4b335db6fb`: The horizontal convolutional layer has $d$ horizontal filters $\mathbf{F}^j \in \mathbb{R}^{h \times k}, 1 \leq j \leq d, h = \{1, ..., L\}$, and the vertical convolutional layer has $d'$ vertical filters $\mathbf{G}^j \in \mathbb{R}^{ L \times 1}, 1 \leq j \leq d'$.
- `ctx_5e631862394a07c36c8b145d`: Note that :eqref:`eq_conv-layer`, in a nutshell, is a *convolutional layer*.

### Part-of-speech evidence

- `ctx_3a787d4bd1c1d0430072fda6`: Consider a convolutional layer whose kernel size is $k$.
- `ctx_5e631862394a07c36c8b145d`: Note that :eqref:`eq_conv-layer`, in a nutshell, is a *convolutional layer*.

## 2. convolutional neural networks

- `sense_id`: `d2lce_c4e87e5ee47d3e26ba618290`
- Split: `development`
- Model definition: A class of neural networks that use convolution operations, especially for processing spatial data such as images.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_ae21d86ceba363f31d12fca3`: Next, :numref:`chap_cnn` and :numref:`chap_modern_cnn`, introduce convolutional neural networks (CNNs), powerful tools that form the backbone of most modern computer vision systems.
- `ctx_7d255ebc2d354c8e85c00cb4`: # Convolutional Neural Networks :label:`chap_cnn`
- `ctx_9ddb8f2418fda4eee49c9494`: This is also one of the reasons why many of the mainstays of deep learning, such as multilayer perceptrons :cite:`McCulloch.Pitts.1943`, convolutional neural networks :cite:`LeCun.Bottou.Bengio.ea.1998`, long short-term memory :cite:`Hochreiter.Schmidhuber.1997`, and Q-Learning :cite:`Watkins.Dayan.1992`, were essentially "rediscovered" in the past decade, after laying comparatively dormant for considerable time.
- `ctx_cba7a66d443fedea8b0f37bf`: In deep learning, we often use CNNs or RNNs to encode a sequence.
- `ctx_ffd36cb1d841c0421cbd90cc`: In short, while CNNs can efficiently process spatial information, *recurrent neural networks* (RNNs) are designed to better handle sequential information.

### Backup contexts

- `ctx_654cb542dec605b7a07f0d38`: We exploit this versatility throughout the following chapters, such as when addressing convolutional neural networks.
- `ctx_d32ca634c60e5bdb199798a6`: # Modern Convolutional Neural Networks :label:`chap_modern_cnn`
- `ctx_d72570c9e0d6a16eed3d4320`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, gluon, init, lr_scheduler, np, npx from mxnet.gluon import nn npx.set_np() net = nn.HybridSequential() net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Conv2D(channels=16, kernel_size=5, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Dense(120, activation='relu'), nn.Dense(84, activation='relu'), nn.Dense(10)) net.hybridize() loss = gluon.loss.SoftmaxCrossEntropyLoss() device = d2l.try_gpu() batch_size = 256 train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size) # The code is almost identical to `d2l.train_ch6` defined in the # lenet section of chapter convolutional neural networks def train(net, train_iter, test_iter, num_epochs, loss, trainer, device): net.initialize(force_reinit=True, ctx=device, init=init.Xavier()) animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs], legend=['train loss', 'train acc', 'test acc']) for epoch in range(num_epochs): metric = d2l.Accumulator(3) # train_loss, train_acc, num_examples for i, (X, y) in enumerate(train_iter): X, y = X.as_in_ctx(device), y.as_in_ctx(device) with autograd.record(): y_hat = net(X) l = loss(y_hat, y) l.backward() trainer.step(X.shape[0]) metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0]) train_loss = metric[0] / metric[2] train_acc = metric[1] / metric[2] if (i + 1) % 50 == 0: animator.add(epoch + i / len(train_iter), (train_loss, train_acc, None)) test_acc = d2l.evaluate_accuracy_gpu(net, test_iter) animator.add(epoch + 1, (None, None, test_acc)) print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, ' f'test acc {test_acc:.3f}') ```

### Contrastive contexts

- `ctxx_00f5dd007cb768664fadf619`: Synthetic: This paper trains one convolutional neural network, while related work compares several convolutional neural networks.

### Definition evidence

- `ctx_ae21d86ceba363f31d12fca3`: Next, :numref:`chap_cnn` and :numref:`chap_modern_cnn`, introduce convolutional neural networks (CNNs), powerful tools that form the backbone of most modern computer vision systems.
- `ctx_7d255ebc2d354c8e85c00cb4`: # Convolutional Neural Networks :label:`chap_cnn`
- `ctx_ffd36cb1d841c0421cbd90cc`: In short, while CNNs can efficiently process spatial information, *recurrent neural networks* (RNNs) are designed to better handle sequential information.

### Part-of-speech evidence

- `ctx_ae21d86ceba363f31d12fca3`: Next, :numref:`chap_cnn` and :numref:`chap_modern_cnn`, introduce convolutional neural networks (CNNs), powerful tools that form the backbone of most modern computer vision systems.
- `ctx_7d255ebc2d354c8e85c00cb4`: # Convolutional Neural Networks :label:`chap_cnn`

## 3. CUDA

- `sense_id`: `d2lce_ebd36388b50538b928ebbb4a`
- Split: `development`
- Model definition: the named NVIDIA GPU computing software platform/version referenced for installing and running GPU-enabled deep learning code.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_df035bcc5db7501785c43a7e`: We now need to find out what version of CUDA you have installed.
- `ctx_f0c64b01d15f034d29c1d6ce`: Assume that you have installed CUDA 10.1, then you can install with the following command:
- `ctx_dae4dda67205c6e9b5831f82`: You can check this by running `nvcc --version` or `cat /usr/local/cuda/version.txt`.
- `ctx_d5e3c3872235604218a2a839`: Then, download the [NVIDIA driver and CUDA](https://developer.nvidia.com/cuda-downloads) and follow the prompts to set the appropriate path.
- `ctx_c8b662075f19ab652ddcc0b9`: Optionally: install CUDA or use an AMI with CUDA preinstalled.

### Backup contexts

- `ctx_88d4ac7e32b65e492b2dbc3a`: If your computer has NVIDIA graphics cards and has installed [CUDA](https://developer.nvidia.com/cuda-downloads), then you should install a GPU-enabled version.
- `ctx_6fcdbf49cf1b09495f5babfd`: ```{.python .input} #@tab pytorch with d2l.Benchmark(): for _ in range(10): a = torch.randn(size=(1000, 1000), device=device) b = torch.mm(a, a) torch.cuda.synchronize(device) ```
- `ctx_7f3025aa974fb8d15e3804a4`: The code [cuda-convnet](https://code.google.com/archive/p/cuda-convnet/) was good enough that for several years it was the industry standard and powered the first couple years of the deep learning boom.

### Contrastive contexts

- `ctxx_4dea89c90037f013e133f06d`: Synthetic: This project runs on any GPU library, so 'CUDA' here would not refer to the specific NVIDIA platform.

### Definition evidence

- `ctx_88d4ac7e32b65e492b2dbc3a`: If your computer has NVIDIA graphics cards and has installed [CUDA](https://developer.nvidia.com/cuda-downloads), then you should install a GPU-enabled version.
- `ctx_d5e3c3872235604218a2a839`: Then, download the [NVIDIA driver and CUDA](https://developer.nvidia.com/cuda-downloads) and follow the prompts to set the appropriate path.
- `ctx_df035bcc5db7501785c43a7e`: We now need to find out what version of CUDA you have installed.
- `ctx_f0c64b01d15f034d29c1d6ce`: Assume that you have installed CUDA 10.1, then you can install with the following command:

### Part-of-speech evidence

- `ctx_88d4ac7e32b65e492b2dbc3a`: If your computer has NVIDIA graphics cards and has installed [CUDA](https://developer.nvidia.com/cuda-downloads), then you should install a GPU-enabled version.
- `ctx_df035bcc5db7501785c43a7e`: We now need to find out what version of CUDA you have installed.
- `ctx_f0c64b01d15f034d29c1d6ce`: Assume that you have installed CUDA 10.1, then you can install with the following command:

## 4. custom layer

- `sense_id`: `d2lce_4d2b37402e25d2f56746ea23`
- Split: `development`
- Model definition: a user-defined neural network layer implemented to provide functionality not covered by built-in layers
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_d91ca38d8df2fb6f84356a08`: In these cases, you must build a custom layer.
- `ctx_30b81bc472e7bfa9272f2568`: # Custom Layers
- `ctx_c650fc71af7d6c2789e47035`: To start, we construct a custom layer that does not have any parameters of its own.
- `ctx_01c5f3adb58f2f2203f6a24f`: We can [**directly carry out forward propagation calculations using custom layers.**]
- `ctx_51a667c40e6f2983a4ba8c80`: This way, among other benefits, we will not need to write custom serialization routines for every custom layer.

### Backup contexts

- `ctx_5b4647a086d9552408986cb3`: We can also (**construct models using custom layers.**) Once we have that we can use it just like the built-in fully-connected layer.
- `ctx_6c7cc3e81d29fe5dcb962f5f`: In this chapter, we will peel back the curtain, digging deeper into the key components of deep learning computation, namely model construction, parameter access and initialization, designing custom layers and blocks, reading and writing models to disk, and leveraging GPUs to achieve dramatic speedups.
- `ctx_73804fdbddef8388a5550f4a`: We then integrate this functionality into a custom layer, whose code mostly addresses bookkeeping matters, such as moving data to the right device context, allocating and initializing any required variables, keeping track of moving averages (here for mean and variance), and so on.

### Contrastive contexts

- `ctxx_11de6b7878d206af216e9882`: Synthetic: The custom layer of sediment was added by the artist to the sculpture.

### Definition evidence

- `ctx_d91ca38d8df2fb6f84356a08`: In these cases, you must build a custom layer.
- `ctx_c650fc71af7d6c2789e47035`: To start, we construct a custom layer that does not have any parameters of its own.
- `ctx_5b4647a086d9552408986cb3`: We can also (**construct models using custom layers.**) Once we have that we can use it just like the built-in fully-connected layer.

### Part-of-speech evidence

- `ctx_30b81bc472e7bfa9272f2568`: # Custom Layers
- `ctx_d91ca38d8df2fb6f84356a08`: In these cases, you must build a custom layer.
- `ctx_5b4647a086d9552408986cb3`: We can also (**construct models using custom layers.**) Once we have that we can use it just like the built-in fully-connected layer.

## 5. discrete random variables

- `sense_id`: `d2lce_e1a7c8e04c91b48272b3b5ee`
- Split: `development`
- Model definition: Random variables that take values from a finite set or from countable values such as the integers.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_e7f67dd37287b32e45850474`: Precisely, on the one hand, if $(X, Y)$ is a pair of discrete random variables, then
- `ctx_dcc2558c83757b30c8a58c12`: In :numref:`sec_prob` we saw the basics of how to work with discrete random variables, which in our case refer to those random variables which take either a finite set of possible values, or the integers.
- `ctx_35cd85b391dd71dfd55cf5b7`: Continuous random variables are a significantly more subtle topic than discrete random variables.
- `ctx_631db6dfad58f0e98ac2eeaa`: Specifically, if $(X, Y)$ is a pair of discrete random variables, then
- `ctx_b4043b79b40224019aa27e38`: This has all been in terms of discrete random variables, but the case of continuous random variables is similar.

### Backup contexts

- `ctx_ddc48912aae8d4e18d86b760`: In this example, we see one of the benefits of working with the c.d.f., the ability to deal with continuous or discrete random variables in the same framework, or indeed mixtures of the two (flip a coin: if heads return the roll of a die, if tails return the distance of a dart throw from the center of a dart board).
- `ctx_f2b3de5d26527ae31c4c6363`: Everything that we have done so far assumes we are working with discrete random variables, but what if we want to work with continuous ones?
- `ctx_be8318b49ee8de45eb672658`: They have some technical difficulties that make them more challenging to work with compared to discrete random variables.

### Contrastive contexts

- `ctxx_e479e370dcd3d280d6ac3552`: Synthetic: Unlike discrete random variables, continuous random variables can take values across an interval.

### Definition evidence

- `ctx_dcc2558c83757b30c8a58c12`: In :numref:`sec_prob` we saw the basics of how to work with discrete random variables, which in our case refer to those random variables which take either a finite set of possible values, or the integers.
- `ctx_35cd85b391dd71dfd55cf5b7`: Continuous random variables are a significantly more subtle topic than discrete random variables.
- `ctx_ddc48912aae8d4e18d86b760`: In this example, we see one of the benefits of working with the c.d.f., the ability to deal with continuous or discrete random variables in the same framework, or indeed mixtures of the two (flip a coin: if heads return the roll of a die, if tails return the distance of a dart throw from the center of a dart board).

### Part-of-speech evidence

- `ctx_dcc2558c83757b30c8a58c12`: In :numref:`sec_prob` we saw the basics of how to work with discrete random variables, which in our case refer to those random variables which take either a finite set of possible values, or the integers.
- `ctx_e7f67dd37287b32e45850474`: Precisely, on the one hand, if $(X, Y)$ is a pair of discrete random variables, then

## 6. eigendecomposition

- `sense_id`: `d2lce_10d4d01fa40b67d92527e5ed`
- Split: `development`
- Model definition: a factorization of a matrix into eigenvalues and eigenvectors
- Model POS: `noun`

### Primary contexts

- `ctx_f250a8f9c758c2ea0187f79a`: This tells us that for any positive power of a matrix, the eigendecomposition is obtained by just raising the eigenvalues to the same power.
- `ctx_e5f07ff7564002cf0a876394`: # Eigendecompositions :label:`sec_eigendecompositions`
- `ctx_06aa5c9830a79f6132f4e41e`: As we saw in :numref:`sec_momentum`, it is possible to rewrite this problem in terms of its eigendecomposition $\mathbf{Q} = \mathbf{U}^\top \boldsymbol{\Lambda} \mathbf{U}$ to arrive at a much simplified problem where each coordinate can be solved individually:
- `ctx_6ff3b3d4b6e66d2fc939f8c0`: ## Operations on Eigendecompositions One nice thing about eigendecompositions :eqref:`eq_eig_decomp` is that we can write many operations we usually encounter cleanly in terms of the eigendecomposition.
- `ctx_700213fde2209115e3d7cfe0`: ```toc :maxdepth: 2 geometry-linear-algebraic-ops eigendecomposition single-variable-calculus multivariable-calculus integral-calculus random-variables maximum-likelihood distributions naive-bayes statistics information-theory ```

### Backup contexts

- `ctx_77274f381fb856ef3c8e17d8`: A key element is the development of the basics of eigen-decompositions.
- `ctx_e6c6794a381193953f6e941b`: Below, we introduce eigendecomposition and try to convey some sense of just why it is so important.
- `ctx_f11208ffa6d465fe135750ee`: We assume that the input of a function is a $k$-dimensional vector and its output is a scalar, so its Hessian matrix will have $k$ eigenvalues (refer to the [online appendix on eigendecompositions](https://d2l.ai/chapter_appendix-mathematics-for-deep-learning/eigendecomposition.html)).

### Contrastive contexts

- `ctxx_b48926bec7193caca70c4e14`: Synthetic: The sound engineer discussed the decomposition of the audio signal, not its eigendecomposition.

### Definition evidence

- `ctx_f11208ffa6d465fe135750ee`: We assume that the input of a function is a $k$-dimensional vector and its output is a scalar, so its Hessian matrix will have $k$ eigenvalues (refer to the [online appendix on eigendecompositions](https://d2l.ai/chapter_appendix-mathematics-for-deep-learning/eigendecomposition.html)).
- `ctx_06aa5c9830a79f6132f4e41e`: As we saw in :numref:`sec_momentum`, it is possible to rewrite this problem in terms of its eigendecomposition $\mathbf{Q} = \mathbf{U}^\top \boldsymbol{\Lambda} \mathbf{U}$ to arrive at a much simplified problem where each coordinate can be solved individually:
- `ctx_e6c6794a381193953f6e941b`: Below, we introduce eigendecomposition and try to convey some sense of just why it is so important.
- `ctx_f250a8f9c758c2ea0187f79a`: This tells us that for any positive power of a matrix, the eigendecomposition is obtained by just raising the eigenvalues to the same power.

### Part-of-speech evidence

- `ctx_06aa5c9830a79f6132f4e41e`: As we saw in :numref:`sec_momentum`, it is possible to rewrite this problem in terms of its eigendecomposition $\mathbf{Q} = \mathbf{U}^\top \boldsymbol{\Lambda} \mathbf{U}$ to arrive at a much simplified problem where each coordinate can be solved individually:
- `ctx_e6c6794a381193953f6e941b`: Below, we introduce eigendecomposition and try to convey some sense of just why it is so important.

## 7. Entailment

- `sense_id`: `d2lce_ca2ca961829e131bbc0fd92b`
- Split: `development`
- Model definition: the natural language inference label meaning the hypothesis follows from the premise
- Model POS: `noun`

### Primary contexts

- `ctx_c4a7169a641a791c71788313`: * *Entailment*: the hypothesis can be inferred from the premise.
- `ctx_f06f07b9418a51a6b9edecab`: The following shows that the three labels "entailment", "contradiction", and "neutral" are balanced in both the training set and the testing set.
- `ctx_0a0c93e8ea720026fc3f62e7`: ```{.python .input} class DecomposableAttention(nn.Block): def __init__(self, vocab, embed_size, num_hiddens, **kwargs): super(DecomposableAttention, self).__init__(**kwargs) self.embedding = nn.Embedding(len(vocab), embed_size) self.attend = Attend(num_hiddens) self.compare = Compare(num_hiddens) # There are 3 possible outputs: entailment, contradiction, and neutral self.aggregate = Aggregate(num_hiddens, 3) def forward(self, X): premises, hypotheses = X A = self.embedding(premises) B = self.embedding(hypotheses) beta, alpha = self.attend(A, B) V_A, V_B = self.compare(A, B, beta, alpha) Y_hat = self.aggregate(V_A, V_B) return Y_hat ```
- `ctx_207e82bfd83c7a4eca664a58`: For example, the following pair will be labeled as *entailment* because "showing affection" in the hypothesis can be inferred from "hugging one another" in the premise.
- `ctx_347324cc4f55f0de9822bf6d`: ```{.python .input} #@tab all #@save def read_snli(data_dir, is_train): """Read the SNLI dataset into premises, hypotheses, and labels.""" def extract_text(s): # Remove information that will not be used by us s = re.sub('\\(', '', s) s = re.sub('\\)', '', s) # Substitute two or more consecutive whitespace with space s = re.sub('\\s{2,}', ' ', s) return s.strip() label_set = {'entailment': 0, 'contradiction': 1, 'neutral': 2} file_name = os.path.join(data_dir, 'snli_1.0_train.txt' if is_train else 'snli_1.0_test.txt') with open(file_name, 'r') as f: rows = [row.split('\t') for row in f.readlines()[1:]] premises = [extract_text(row[1]) for row in rows if row[0] in label_set] hypotheses = [extract_text(row[2]) for row in rows if row[0] in label_set] labels = [label_set[row[0]] for row in rows if row[0] in label_set] return premises, hypotheses, labels ```

### Backup contexts

- `ctx_3e3799ff4270de82290185f5`: * In natural language inference, relationships between premises and hypotheses include entailment, contradiction, and neutral.
- `ctx_7ab76b6d9c4d288c677f1a0b`: Now let us print the first 3 pairs of premise and hypothesis, as well as their labels ("0", "1", and "2" correspond to "entailment", "contradiction", and "neutral", respectively ).
- `ctx_ebc0a0797c85b97bb1f894e1`: Natural language inference is also known as the recognizing textual entailment task.

### Contrastive contexts

- `ctxx_0db25ab29d9986cef4d46471`: Synthetic: In logic class, entailment is discussed as a formal relation, while here entailment is a dataset label between premise and hypothesis.

### Definition evidence

- `ctx_c4a7169a641a791c71788313`: * *Entailment*: the hypothesis can be inferred from the premise.
- `ctx_207e82bfd83c7a4eca664a58`: For example, the following pair will be labeled as *entailment* because "showing affection" in the hypothesis can be inferred from "hugging one another" in the premise.
- `ctx_3e3799ff4270de82290185f5`: * In natural language inference, relationships between premises and hypotheses include entailment, contradiction, and neutral.

### Part-of-speech evidence

- `ctx_c4a7169a641a791c71788313`: * *Entailment*: the hypothesis can be inferred from the premise.
- `ctx_f06f07b9418a51a6b9edecab`: The following shows that the three labels "entailment", "contradiction", and "neutral" are balanced in both the training set and the testing set.
- `ctx_3e3799ff4270de82290185f5`: * In natural language inference, relationships between premises and hypotheses include entailment, contradiction, and neutral.

## 8. forward propagation

- `sense_id`: `d2lce_fbe9efe0d390976cb31e5af7`
- Split: `development`
- Model definition: the computation that carries inputs through a model to produce outputs; in code, the corresponding forward method
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_4f8a2ab7305e5e99ddf848a4`: * Generate predictions by calling `net(X)` and calculate the loss `l` (the forward propagation).
- `ctx_18f5c52c0937b1589d8a6782`: Any subclass of it must define a forward propagation function that transforms its input into output and must store any necessary parameters.
- `ctx_d126e74d5ab3240a96363756`: We will describe deep architectures with multiple hidden layers, and discuss the bidirectional design with both forward and backward recurrent computations.
- `ctx_072a83737808daf5abee6df6`: The forward propagation function calls the `corr2d` function and adds the bias.
- `ctx_041277e59fc9e3b32469b673`: ```{.python .input} class NWKernelRegression(nn.Block): def __init__(self, **kwargs): super().__init__(**kwargs) self.w = self.params.get('w', shape=(1,)) def forward(self, queries, keys, values): # Shape of the output `queries` and `attention_weights`: # (no.

### Backup contexts

- `ctx_e3686abbec23ffeb19f2dfef`: Their idea, called *dropout*, involves injecting noise while computing each internal layer during forward propagation, and it has become a standard technique for training neural networks.

### Contrastive contexts

- `ctxx_b0f418c27ca404d28a5696bb`: Synthetic boundary probe: "forward propagation" is quoted here only as a document label, not as an occurrence of the reviewed D2L sense.

### Definition evidence

- `ctx_4f8a2ab7305e5e99ddf848a4`: * Generate predictions by calling `net(X)` and calculate the loss `l` (the forward propagation).
- `ctx_e3686abbec23ffeb19f2dfef`: Their idea, called *dropout*, involves injecting noise while computing each internal layer during forward propagation, and it has become a standard technique for training neural networks.
- `ctx_18f5c52c0937b1589d8a6782`: Any subclass of it must define a forward propagation function that transforms its input into output and must store any necessary parameters.
- `ctx_072a83737808daf5abee6df6`: The forward propagation function calls the `corr2d` function and adds the bias.
- `ctx_d126e74d5ab3240a96363756`: We will describe deep architectures with multiple hidden layers, and discuss the bidirectional design with both forward and backward recurrent computations.
- `ctx_041277e59fc9e3b32469b673`: ```{.python .input} class NWKernelRegression(nn.Block): def __init__(self, **kwargs): super().__init__(**kwargs) self.w = self.params.get('w', shape=(1,)) def forward(self, queries, keys, values): # Shape of the output `queries` and `attention_weights`: # (no.

### Part-of-speech evidence

- `ctx_4f8a2ab7305e5e99ddf848a4`: * Generate predictions by calling `net(X)` and calculate the loss `l` (the forward propagation).
- `ctx_e3686abbec23ffeb19f2dfef`: Their idea, called *dropout*, involves injecting noise while computing each internal layer during forward propagation, and it has become a standard technique for training neural networks.
- `ctx_18f5c52c0937b1589d8a6782`: Any subclass of it must define a forward propagation function that transforms its input into output and must store any necessary parameters.

## 9. frontend

- `sense_id`: `d2lce_24988c975f984ef488776c0b`
- Split: `development`
- Model definition: the user-facing part of a software framework or the language interface through which users issue operations
- Model POS: `noun`

### Primary contexts

- `ctx_a2db8ce33d67077666585b97`: :begin_tab:`mxnet` Broadly speaking, MXNet has a frontend for direct interactions with users, e.g., via Python, as well as a backend used by the system to perform the computation.
- `ctx_c97c57c246feef065fb19e6c`: As shown in :numref:`fig_frontends`, users can write PyTorch programs in various frontend languages, such as Python and C++.
- `ctx_5e61307935b8e7d87220e6f3`: :begin_tab:`pytorch` Broadly speaking, PyTorch has a frontend for direct interaction with the users, e.g., via Python, as well as a backend used by the system to perform the computation.
- `ctx_33c4a5d0c030d071cbc4dffd`: Forcing MXNet to finish all the backend computation prior to returning shows what happened previously: computation is executed by the backend while the frontend returns control to Python.
- `ctx_b19abb42c07be4849d43a0c0`: Forcing PyTorch to finish all computation prior to returning shows what happened previously: computation is being executed by the backend while the frontend returns control to Python.

### Backup contexts

- `ctx_358982713ee189170b08992f`: As shown in :numref:`fig_frontends`, users can write MXNet programs in various frontend languages, such as Python, R, Scala, and C++.
- `ctx_0dd3e0d0f7d3391d566ae6d8`: Operations issued by the frontend language are passed on to the backend for execution.
- `ctx_eda09302351a178011612455`: Regardless of the frontend programming language used, the execution of MXNet programs occurs primarily in the backend of C++ implementations.

### Contrastive contexts

- `ctxx_0d564f587c9e8db7c7f40227`: Synthetic: The frontend of the building was renovated last year.

### Definition evidence

- `ctx_a2db8ce33d67077666585b97`: :begin_tab:`mxnet` Broadly speaking, MXNet has a frontend for direct interactions with users, e.g., via Python, as well as a backend used by the system to perform the computation.
- `ctx_5e61307935b8e7d87220e6f3`: :begin_tab:`pytorch` Broadly speaking, PyTorch has a frontend for direct interaction with the users, e.g., via Python, as well as a backend used by the system to perform the computation.
- `ctx_0dd3e0d0f7d3391d566ae6d8`: Operations issued by the frontend language are passed on to the backend for execution.

### Part-of-speech evidence

- `ctx_a2db8ce33d67077666585b97`: :begin_tab:`mxnet` Broadly speaking, MXNet has a frontend for direct interactions with users, e.g., via Python, as well as a backend used by the system to perform the computation.
- `ctx_5e61307935b8e7d87220e6f3`: :begin_tab:`pytorch` Broadly speaking, PyTorch has a frontend for direct interaction with the users, e.g., via Python, as well as a backend used by the system to perform the computation.

## 10. fully-connected layers

- `sense_id`: `d2lce_98b37a7bcb47cd2ef2e5f296`
- Split: `development`
- Model definition: layers in which each output unit is connected to all input units from the previous layer
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_faa4efe019d52f783381c40a`: # From Fully-Connected Layers to Convolutions :label:`sec_why-conv`
- `ctx_28b17b3a0950632e4ac5d1f9`: Therefore, what sets attention mechanisms apart from those fully-connected layers or pooling layers is the inclusion of the volitional cues.
- `ctx_1f4f955fd892e6791b4aeef3`: These two huge fully-connected layers produce model parameters of nearly 1 GB.
- `ctx_403adb70f5312a0fa35b95be`: The easiest way to do this is to stack many fully-connected layers on top of each other.
- `ctx_58323905b57101ea133ca2d9`: The outputs of two gates are given by two fully-connected layers with a sigmoid activation function.

### Backup contexts

- `ctx_8ce751d21f2cb72d502c47b8`: Note that each of the two fully-connected layers is an instance of the `Linear` class which is itself a subclass of `Module`.
- `ctx_eafeb346f16534dd44c4414d`: ## Parameterization Cost of Fully-Connected Layers :label:`subsec_parameterization-cost-fc-layers`
- `ctx_f4fa216c07f2cf0249eb37ca`: ```{.python .input} #@tab mxnet, pytorch tau = 4 features = d2l.zeros((T - tau, tau)) for i in range(tau): features[:, i] = x[i: T - tau + i] labels = d2l.reshape(x[tau:], (-1, 1)) ``` ```{.python .input} #@tab tensorflow tau = 4 features = tf.Variable(d2l.zeros((T - tau, tau))) for i in range(tau): features[:, i].assign(x[i: T - tau + i]) labels = d2l.reshape(x[tau:], (-1, 1)) ``` ```{.python .input} #@tab all batch_size, n_train = 16, 600 # Only the first `n_train` examples are used for training train_iter = d2l.load_array((features[:n_train], labels[:n_train]), batch_size, is_train=True) ``` Here we [**keep the architecture fairly simple: just an MLP**] with two fully-connected layers, ReLU activation, and squared loss.

### Contrastive contexts

- `ctxx_e58b72f11fa52345b99c8a32`: Synthetic: Fully-connected layers connect every unit to all units in the previous layer, unlike convolutional layers with local receptive fields.

### Definition evidence

- `ctx_403adb70f5312a0fa35b95be`: The easiest way to do this is to stack many fully-connected layers on top of each other.
- `ctx_faa4efe019d52f783381c40a`: # From Fully-Connected Layers to Convolutions :label:`sec_why-conv`
- `ctx_1f4f955fd892e6791b4aeef3`: These two huge fully-connected layers produce model parameters of nearly 1 GB.

### Part-of-speech evidence

- `ctx_eafeb346f16534dd44c4414d`: ## Parameterization Cost of Fully-Connected Layers :label:`subsec_parameterization-cost-fc-layers`
- `ctx_403adb70f5312a0fa35b95be`: The easiest way to do this is to stack many fully-connected layers on top of each other.
