# Stage A sense casebook: development_009

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. Skip-Gram Model

- `sense_id`: `d2lce_9cee0f2f668259a2568b89f4`
- Split: `development`
- Model definition: A word embedding model that predicts surrounding context words from a center word.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_408899a3fd525147fbd6f4e6`: ## The Skip-Gram Model :label:`subsec_skip-gram`
- `ctx_bfaedeed2ce02517e3497cb8`: ![The skip-gram model considers the conditional probability of generating the surrounding context words given a center word.](../img/skip-gram.svg) :label:`fig_skip_gram`
- `ctx_35d82b9dff7df8ff9a2c49cd`: The skip-gram model parameters are the center word vector and context word vector for each word in the vocabulary.
- `ctx_67062c99a9f339aaec98d9aa`: In natural language processing applications, the center word vectors of the skip-gram model are typically used as the word representations.
- `ctx_0cbd6b544c567ce5e0d6a15e`: The major difference from the skip-gram model is that the continuous bag of words model assumes that a center word is generated based on its surrounding context words in the text sequence.

### Backup contexts

- `ctx_7ab8e2d37def67d0148f52d5`: As shown in :numref:`fig_skip_gram`, given the center word "loves", the skip-gram model considers the conditional probability for generating the *context words*: "the", "man", "his", and "son", which are no more than 2 words away from the center word:
- `ctx_9afa421e80e79b49583f6bb8`: For context window size $m$, the likelihood function of the skip-gram model is the probability of generating all context words given any center word:
- `ctx_08609f360a045dec1b2c96f2`: In the skip-gram model, each word has two $d$-dimensional-vector representations for calculating conditional probabilities.

### Contrastive contexts

- `ctxx_3a64557efe58ea113612c86e`: Synthetic: In typography, a skip-gram model could be misread as a layout pattern that skips printed letter groups, not a word embedding model.

### Definition evidence

- `ctx_7ab8e2d37def67d0148f52d5`: As shown in :numref:`fig_skip_gram`, given the center word "loves", the skip-gram model considers the conditional probability for generating the *context words*: "the", "man", "his", and "son", which are no more than 2 words away from the center word:
- `ctx_bfaedeed2ce02517e3497cb8`: ![The skip-gram model considers the conditional probability of generating the surrounding context words given a center word.](../img/skip-gram.svg) :label:`fig_skip_gram`
- `ctx_9afa421e80e79b49583f6bb8`: For context window size $m$, the likelihood function of the skip-gram model is the probability of generating all context words given any center word:
- `ctx_0cbd6b544c567ce5e0d6a15e`: The major difference from the skip-gram model is that the continuous bag of words model assumes that a center word is generated based on its surrounding context words in the text sequence.

### Part-of-speech evidence

- `ctx_408899a3fd525147fbd6f4e6`: ## The Skip-Gram Model :label:`subsec_skip-gram`
- `ctx_08609f360a045dec1b2c96f2`: In the skip-gram model, each word has two $d$-dimensional-vector representations for calculating conditional probabilities.
- `ctx_35d82b9dff7df8ff9a2c49cd`: The skip-gram model parameters are the center word vector and context word vector for each word in the vocabulary.

## 2. spatial dimensions

- `sense_id`: `d2lce_5300144b7f5b4ce29dd12ec6`
- Split: `development`
- Model definition: the height-and-width axes of an input, output, or feature map in a neural network
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_951d5a5b4ee251243063d6b8`: The CNN layers we have seen so far, such as convolutional layers (:numref:`sec_conv_layer`) and pooling layers (:numref:`sec_pooling`), typically reduce (downsample) the spatial dimensions (height and width) of the input, or keep them unchanged.
- `ctx_d51d07967447de6bcbe89cba`: In semantic segmentation that classifies at pixel-level, it will be convenient if the spatial dimensions of the input and output are the same.
- `ctx_5bc9eb4631e8433a066db266`: As described in :numref:`subsec_why-conv-channels`, the convolutional layer output in :numref:`fig_correlation` is sometimes called a *feature map*, as it can be regarded as the learned representations (features) in the spatial dimensions (e.g., width and height) to the subsequent layer.
- `ctx_123d1f12ef7f7d7f33ef5e08`: To achieve this, especially after the spatial dimensions are reduced by CNN layers, we can use another type of CNN layers that can increase (upsample) the spatial dimensions of intermediate feature maps.
- `ctx_a70641e48916c52b08510cd2`: In this way, there can be a one-to-one correspondence between outputs and inputs at the same spatial dimensions (width and height) of feature maps.

### Backup contexts

- `ctx_3987a234779617d234e91796`: Since 4 anchor boxes are generated for each unit along spatial dimensions of feature maps, at all the five scales a total of $(32^2 + 16^2 + 8^2 + 4^2 + 1)\times 4 = 5444$ anchor boxes are generated for each image.
- `ctx_d32243af852da68a154db964`: In this way, each unit along the spatial dimensions of the CNN-extracted feature maps gets a new feature vector of length $c$.
- `ctx_d637282791dad50a10d04580`: * Maximum pooling, combined with a stride larger than 1 can be used to reduce the spatial dimensions (e.g., width and height).

### Contrastive contexts

- `ctxx_bf8095c454718318a7fb7990`: Synthetic: In urban planning, spatial dimensions of the park included walking distance and visual openness.

### Definition evidence

- `ctx_951d5a5b4ee251243063d6b8`: The CNN layers we have seen so far, such as convolutional layers (:numref:`sec_conv_layer`) and pooling layers (:numref:`sec_pooling`), typically reduce (downsample) the spatial dimensions (height and width) of the input, or keep them unchanged.
- `ctx_d51d07967447de6bcbe89cba`: In semantic segmentation that classifies at pixel-level, it will be convenient if the spatial dimensions of the input and output are the same.
- `ctx_5bc9eb4631e8433a066db266`: As described in :numref:`subsec_why-conv-channels`, the convolutional layer output in :numref:`fig_correlation` is sometimes called a *feature map*, as it can be regarded as the learned representations (features) in the spatial dimensions (e.g., width and height) to the subsequent layer.

### Part-of-speech evidence

- `ctx_5bc9eb4631e8433a066db266`: As described in :numref:`subsec_why-conv-channels`, the convolutional layer output in :numref:`fig_correlation` is sometimes called a *feature map*, as it can be regarded as the learned representations (features) in the spatial dimensions (e.g., width and height) to the subsequent layer.
- `ctx_951d5a5b4ee251243063d6b8`: The CNN layers we have seen so far, such as convolutional layers (:numref:`sec_conv_layer`) and pooling layers (:numref:`sec_pooling`), typically reduce (downsample) the spatial dimensions (height and width) of the input, or keep them unchanged.

## 3. SSD

- `sense_id`: `d2lce_c6d5679eb20ff0719dfc35b2`
- Split: `development`
- Model definition: abbreviation for either a solid-state drive in hardware contexts or Single Shot Multibox Detection in computer-vision contexts
- Model POS: `symbol`

### Primary contexts

- `ctx_f4c012def8b4623e96d4ac12`: Now we are ready to use such background knowledge to design an object detection model: single shot multibox detection (SSD) :cite:`Liu.Anguelov.Erhan.ea.2016`.
- `ctx_0b0937e42c26b6b23b5692f4`: Aim for 64 GB DRAM and invest into an SSD.
- `ctx_12113aa551b0b7a0b905e6bf`: ![As a multiscale object detection model, single-shot multibox detection mainly consists of a base network followed by several multiscale feature map blocks.](../img/ssd.svg) :label:`fig_ssd`
- `ctx_47a2796ead7d2454fdc45f64`: Peripherals, such as Ethernet, WiFi, Bluetooth, SSD controller, and USB, are either part of the chipset or directly attached (PCIe) to the CPU.
- `ctx_607c4610b2fb0f15081b64d0`: ```toc :maxdepth: 2 image-augmentation fine-tuning bounding-box anchor multiscale-object-detection object-detection-dataset ssd rcnn semantic-segmentation-and-dataset transposed-conv fcn neural-style kaggle-cifar10 kaggle-dog ```

### Backup contexts

- `ctx_96fce7b6560a010f307443f6`: By now SSD controllers and firmware have developed algorithms to mitigate this.
- `ctx_9d639b375fad74fc47d1c470`: (remote CPU) | 120 ns | TinyMemBench on Broadwell E5-2690v4 | | Intel Optane random read | 305 ns | UCSD Non-Volatile Systems Lab | | Send 4KB over 100 Gbps HPC fabric | 1 μs | MVAPICH2 over Intel Omni-Path | | Compress 1KB with Google Snappy | 3 μs | | | Send 4KB over 10 Gbps ethernet | 10 μs | | | Write 4KB randomly to NVMe SSD | 30 μs | DC P3608 NVMe SSD (QOS 99% is 500μs) | | Transfer 1MB to/from NVLink GPU | 30 μs | ~33GB/s on NVIDIA 40GB NVLink | | Transfer 1MB to/from PCI-E GPU | 80 μs | ~12GB/s on PCIe 3.0 x16 link | | Read 4KB randomly from NVMe SSD | 120 μs | DC P3608 NVMe SSD (QOS 99%) | | Read 1MB sequentially from NVMe SSD | 208 μs | ~4.8GB/s DC P3608 NVMe SSD | | Write 4KB randomly to SATA SSD | 500 μs | DC S3510 SATA SSD (QOS 99.9%) | | Read 4KB randomly from SATA SSD | 500 μs | DC S3510 SATA SSD (QOS 99.9%) | | Round trip within same datacenter | 500 μs | One-way ping is ~250μs | | Read 1MB sequentially from SATA SSD | 2 ms | ~550MB/s DC S3510 SATA SSD | | Read 1MB sequentially from disk | 5 ms | ~200MB/s server HDD | | Random Disk Access (seek+rotation) | 10 ms | | | Send packet CA->Netherlands->CA | 150 ms | | :label:`table_latency_numbers`
- `ctx_aa0eae6611908af9c05e40d3`: Consequently bit-wise random writes on SSD have very poor performance.

### Contrastive contexts

- `ctxx_17beba5acdb3e6a8aa8878b6`: Synthetic: In this chapter, SSD refers to Single Shot Multibox Detection, not a storage drive.

### Definition evidence

- `ctx_96fce7b6560a010f307443f6`: By now SSD controllers and firmware have developed algorithms to mitigate this.
- `ctx_0b0937e42c26b6b23b5692f4`: Aim for 64 GB DRAM and invest into an SSD.
- `ctx_f4c012def8b4623e96d4ac12`: Now we are ready to use such background knowledge to design an object detection model: single shot multibox detection (SSD) :cite:`Liu.Anguelov.Erhan.ea.2016`.
- `ctx_12113aa551b0b7a0b905e6bf`: ![As a multiscale object detection model, single-shot multibox detection mainly consists of a base network followed by several multiscale feature map blocks.](../img/ssd.svg) :label:`fig_ssd`

### Part-of-speech evidence

- `ctx_96fce7b6560a010f307443f6`: By now SSD controllers and firmware have developed algorithms to mitigate this.
- `ctx_f4c012def8b4623e96d4ac12`: Now we are ready to use such background knowledge to design an object detection model: single shot multibox detection (SSD) :cite:`Liu.Anguelov.Erhan.ea.2016`.

## 4. standardization

- `sense_id`: `d2lce_d53294d467b28b07bf000b10`
- Split: `development`
- Model definition: the operation of rescaling data so values are on a common scale, typically with zero mean and unit variance
- Model POS: `other`

### Primary contexts

- `ctx_460b67cc0b1f1dd67fa8444a`: First, we apply a heuristic, [**replacing all missing values by the corresponding feature's mean.**] Then, to put all features on a common scale, we (***standardize* the data by rescaling features to zero mean and unit variance**):
- `ctx_328006017870b26dd1187448`: Our first step when working with real data was to standardize our input features to each have a mean of zero and variance of one.
- `ctx_637765a4cacd9fb038d7eff2`: Here we # need to maintain the shape of `X`, so that the broadcasting # operation can be carried out later mean = X.mean(axis=(0, 2, 3), keepdims=True) var = ((X - mean) ** 2).mean(axis=(0, 2, 3), keepdims=True) # In training mode, the current mean and variance are used for the # standardization X_hat = (X - mean) / np.sqrt(var + eps) # Update the mean and variance using moving average moving_mean = momentum * moving_mean + (1.0 - momentum) * mean moving_var = momentum * moving_var + (1.0 - momentum) * var Y = gamma * X_hat + beta # Scale and shift return Y, moving_mean, moving_var ```
- `ctx_a167d13f629e1ae8dac46d3f`: After applying standardization, the resulting minibatch has zero mean and unit variance.
- `ctx_ed7839f97c63c1b48869a6f0`: In addition, for the three RGB (red, green, and blue) color channels we *standardize* their values channel by channel.

### Backup contexts

- `ctx_6ffc67805f59c483874ce07b`: What happens if we do not standardize the continuous numerical features like what we have done in this section?
- `ctx_3a785df09f9744986fcf3844`: Intuitively, we standardize the data for two reasons.
- `ctx_8df7153a3f4e71ce745ec7c3`: Intuitively, this standardization plays nicely with our optimizers because it puts the parameters *a priori* at a similar scale.

### Contrastive contexts

- `ctxx_7131639c7f5a388520ca7307`: Synthetic: In these contexts, standardization means rescaling numeric data, not enforcing a social or industrial standard.

### Definition evidence

- `ctx_460b67cc0b1f1dd67fa8444a`: First, we apply a heuristic, [**replacing all missing values by the corresponding feature's mean.**] Then, to put all features on a common scale, we (***standardize* the data by rescaling features to zero mean and unit variance**):
- `ctx_328006017870b26dd1187448`: Our first step when working with real data was to standardize our input features to each have a mean of zero and variance of one.
- `ctx_a167d13f629e1ae8dac46d3f`: After applying standardization, the resulting minibatch has zero mean and unit variance.

### Part-of-speech evidence

- `ctx_460b67cc0b1f1dd67fa8444a`: First, we apply a heuristic, [**replacing all missing values by the corresponding feature's mean.**] Then, to put all features on a common scale, we (***standardize* the data by rescaling features to zero mean and unit variance**):
- `ctx_3a785df09f9744986fcf3844`: Intuitively, we standardize the data for two reasons.
- `ctx_8df7153a3f4e71ce745ec7c3`: Intuitively, this standardization plays nicely with our optimizers because it puts the parameters *a priori* at a similar scale.

## 5. Statistical Bias

- `sense_id`: `d2lce_b5d6207f8142a696435e27e0`
- Split: `development`
- Model definition: The difference between the expected or average value of an estimator and the true parameter value.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_562aba8242b13a890c3a0d27`: For an estimator $\hat{\theta}_n$, the mathematical illustration of *statistical bias* can be defined as
- `ctx_83a38c0d5607709e21e74429`: ### Statistical Bias
- `ctx_ef578138a49d3927c6563ea2`: ```{.python .input} #@tab pytorch # Statistical bias def stat_bias(true_theta, est_theta): return(torch.mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(torch.mean(torch.square(data - true_theta))) ```
- `ctx_759986abc69fc46f3dc20bba`: ```{.python .input} # Statistical bias def stat_bias(true_theta, est_theta): return(np.mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(np.mean(np.square(data - true_theta))) ```
- `ctx_e165d697ee1e17ec619ac2fb`: ```{.python .input} #@tab tensorflow # Statistical bias def stat_bias(true_theta, est_theta): return(tf.reduce_mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(tf.reduce_mean(tf.square(data - true_theta))) ```

### Backup contexts

- `ctx_98e49b6d58da3c32d077b667`: In this section, we introduce three common methods to evaluate and compare estimators: the mean squared error, the standard deviation, and statistical bias.
- `ctx_daa159ed8725f271c864051c`: Since the standard deviation of an estimator has been implementing by simply calling `a.std()` for a tensor `a`, we will skip it but implement the statistical bias and the mean squared error.
- `ctx_7d0011328d40612e41406231`: * There are three most common estimators: statistical bias, standard deviation, and mean square error.

### Contrastive contexts

- `ctxx_785b930bfe321e58de2d60e0`: Synthetic: The news article discussed political bias, not statistical bias.

### Definition evidence

- `ctx_562aba8242b13a890c3a0d27`: For an estimator $\hat{\theta}_n$, the mathematical illustration of *statistical bias* can be defined as
- `ctx_759986abc69fc46f3dc20bba`: ```{.python .input} # Statistical bias def stat_bias(true_theta, est_theta): return(np.mean(est_theta) - true_theta) # Mean squared error def mse(data, true_theta): return(np.mean(np.square(data - true_theta))) ```
- `ctx_98e49b6d58da3c32d077b667`: In this section, we introduce three common methods to evaluate and compare estimators: the mean squared error, the standard deviation, and statistical bias.

### Part-of-speech evidence

- `ctx_98e49b6d58da3c32d077b667`: In this section, we introduce three common methods to evaluate and compare estimators: the mean squared error, the standard deviation, and statistical bias.
- `ctx_83a38c0d5607709e21e74429`: ### Statistical Bias

## 6. statistical power

- `sense_id`: `d2lce_2b76c0f26436945cdf880aed`
- Split: `development`
- Model definition: the probability that a statistical test detects a real effect.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_e35e3b1e2bfeb5965b0bd614`: For now, a simple rule of thumb is quite useful: a model that can readily explain arbitrary facts is what statisticians view as complex, whereas one that has only a limited expressive power but still manages to explain the data well is probably closer to the truth.

### Contrastive contexts

- `ctx_46209c337eb72da7b6db819f`: The reason for why this is possible is actually quite simple: first, power consumption tends to grow *quadratically* with clock frequency.

### Definition evidence

- `ctx_e35e3b1e2bfeb5965b0bd614`: For now, a simple rule of thumb is quite useful: a model that can readily explain arbitrary facts is what statisticians view as complex, whereas one that has only a limited expressive power but still manages to explain the data well is probably closer to the truth.

### Part-of-speech evidence

- `ctx_e35e3b1e2bfeb5965b0bd614`: For now, a simple rule of thumb is quite useful: a model that can readily explain arbitrary facts is what statisticians view as complex, whereas one that has only a limited expressive power but still manages to explain the data well is probably closer to the truth.

## 7. symbols

- `sense_id`: `d2lce_6f20c5222ebea4830603817b`
- Split: `development`
- Model definition: Written marks or token units used in notation or as basic units in text processing.
- Model POS: `noun`

### Primary contexts

- `ctx_90c426ac663609212af0b8fc`: Note that some of these symbols are placeholders, while others refer to specific objects.
- `ctx_8fbcd8bc50f3f91b245b89ba`: First, we initialize the vocabulary of symbols as all the English lowercase characters, a special end-of-word symbol `'_'`, and a special unknown symbol `'[UNK]'`.
- `ctx_742a5b289d740929a1de20f2`: For example, imagine that a slot machine system emits statistical independently symbols ${s_1, \ldots, s_k}$ with probabilities ${p_1, \ldots, p_k}$ respectively.
- `ctx_8e3bb715a8f1e73fa1eb0a44`: As a general rule of thumb, the indefinite article "a" indicates that the symbol is a placeholder and that similarly formatted symbols can denote other objects of the same type.
- `ctx_2d4f025f72fe9d0fa22226d7`: where symbols $\frac{d}{dx}$ and $D$ are *differentiation operators* that indicate operation of *differentiation*.

### Backup contexts

- `ctx_51424ecedde5d77018ac09c3`: Starting from symbols of length 1, byte pair encoding iteratively merges the most frequent pair of consecutive symbols to produce new longer symbols.
- `ctx_af8ee08c589d3eaf854b7001`: In the end, we can use such symbols as subwords to segment words.
- `ctx_bc0e8683233a7f81d8fcb9f1`: Byte pair encoding performs a statistical analysis of the training dataset to discover common symbols within a word, such as consecutive characters of arbitrary length.

### Contrastive contexts

- `ctxx_dc72eb594438e704bf2625a0`: Synthetic: The symbols in byte pair encoding differ from the stock symbols shown on the exchange screen.

### Definition evidence

- `ctx_8e3bb715a8f1e73fa1eb0a44`: As a general rule of thumb, the indefinite article "a" indicates that the symbol is a placeholder and that similarly formatted symbols can denote other objects of the same type.
- `ctx_51424ecedde5d77018ac09c3`: Starting from symbols of length 1, byte pair encoding iteratively merges the most frequent pair of consecutive symbols to produce new longer symbols.
- `ctx_8fbcd8bc50f3f91b245b89ba`: First, we initialize the vocabulary of symbols as all the English lowercase characters, a special end-of-word symbol `'_'`, and a special unknown symbol `'[UNK]'`.

### Part-of-speech evidence

- `ctx_8e3bb715a8f1e73fa1eb0a44`: As a general rule of thumb, the indefinite article "a" indicates that the symbol is a placeholder and that similarly formatted symbols can denote other objects of the same type.
- `ctx_51424ecedde5d77018ac09c3`: Starting from symbols of length 1, byte pair encoding iteratively merges the most frequent pair of consecutive symbols to produce new longer symbols.

## 8. synchronize

- `sense_id`: `d2lce_1edc567804c90f134219a8f0`
- Split: `development`
- Model definition: to make asynchronous computation wait so operations on a device or stream reach a coordinated completion point
- Model POS: `verb`

### Primary contexts

- `ctx_120834caecae7353d11a2c24`: `torch.cuda.synchronize()` waits for all kernels in all streams on a CUDA device to complete.
- `ctx_2893e1c5ddd69213232296e5`: Hint: perform a number of instructions and synchronize for an intermediate result.
- `ctx_680c9412dce02a05d32cc50f`: It is recommended to synchronize for each minibatch to keep frontend and backend approximately synchronized.
- `ctx_885cc737774521b311183188`: It takes in a `device` argument, the device for which we need to synchronize.
- `ctx_4023c93849b7225177573487`: ```{.python .input} #@tab pytorch run(x_gpu1) run(x_gpu2) # Warm-up all devices torch.cuda.synchronize(devices[0]) torch.cuda.synchronize(devices[1]) with d2l.Benchmark('GPU1 time'): run(x_gpu1) torch.cuda.synchronize(devices[0]) with d2l.Benchmark('GPU2 time'): run(x_gpu2) torch.cuda.synchronize(devices[1]) ```

### Backup contexts

- `ctx_bd29e9f4d01a7d3837c15019`: ```{.python .input} #@tab pytorch with d2l.Benchmark('GPU1 & GPU2'): run(x_gpu1) run(x_gpu2) torch.cuda.synchronize() ```
- `ctx_dc63ee4d41dfd51ccd1fb78f`: ```{.python .input} #@tab pytorch with d2l.Benchmark(): for _ in range(10): a = torch.randn(size=(1000, 1000), device=device) b = torch.mm(a, a) torch.cuda.synchronize(device) ```
- `ctx_800ddb30c90771d6eb717131`: :begin_tab:`pytorch` If we remove the `synchronize` statement between both tasks the system is free to parallelize computation on both devices automatically.

### Contrastive contexts

- `ctxx_174d66f2f62420c6e2a92dbb`: Synthetic: The dancers tried to synchronize their steps before the performance.

### Definition evidence

- `ctx_120834caecae7353d11a2c24`: `torch.cuda.synchronize()` waits for all kernels in all streams on a CUDA device to complete.
- `ctx_680c9412dce02a05d32cc50f`: It is recommended to synchronize for each minibatch to keep frontend and backend approximately synchronized.
- `ctx_2893e1c5ddd69213232296e5`: Hint: perform a number of instructions and synchronize for an intermediate result.

### Part-of-speech evidence

- `ctx_dc63ee4d41dfd51ccd1fb78f`: ```{.python .input} #@tab pytorch with d2l.Benchmark(): for _ in range(10): a = torch.randn(size=(1000, 1000), device=device) b = torch.mm(a, a) torch.cuda.synchronize(device) ```
- `ctx_680c9412dce02a05d32cc50f`: It is recommended to synchronize for each minibatch to keep frontend and backend approximately synchronized.
- `ctx_120834caecae7353d11a2c24`: `torch.cuda.synchronize()` waits for all kernels in all streams on a CUDA device to complete.

## 9. training data

- `sense_id`: `d2lce_d30763678be8999b747cf0ee`
- Split: `development`
- Model definition: The data used to fit or train a machine learning model.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_ab61947a37276da02a409618`: Given the learned linear regression model $\hat{\mathbf{w}}^\top \mathbf{x} + \hat{b}$, we can now estimate the price of a new house (not contained in the training data) given its area $x_1$ and age $x_2$.
- `ctx_e3bd3e8dcc83a702caf288d2`: Both cases raise the obvious question of how to generate training data.
- `ctx_c5e59f5a1a3a5b62dda17291`: One common failure mode occurs in datasets where some groups of people are unrepresented in the training data.
- `ctx_1ff425af2f5e658c4e18ce61`: It provides efficient transfer of training data to the system and storage of intermediate checkpoints as needed.
- `ctx_464f6dce8ce133a02dd86a13`: The phenomenon of fitting our training data more closely than we fit the underlying distribution is called *overfitting*, and the techniques used to combat overfitting are called *regularization*.

### Backup contexts

- `ctx_b035055ba332f55c6df9256e`: Suppose that we have only a finite amount of training data.
- `ctx_305668478b1cbfbf4e284ab4`: But of course, if those biases do not agree with reality, e.g., if images turned out not to be translation invariant, our models might struggle even to fit our training data.
- `ctx_5a59e7c2b380f093af715db7`: Increase the training data to include multiple books.

### Contrastive contexts

- `ctxx_94cbf1bd5b9c74a5752e92bf`: Synthetic: Here, training data means examples used to fit a model, not data for training human staff.

### Definition evidence

- `ctx_ab61947a37276da02a409618`: Given the learned linear regression model $\hat{\mathbf{w}}^\top \mathbf{x} + \hat{b}$, we can now estimate the price of a new house (not contained in the training data) given its area $x_1$ and age $x_2$.
- `ctx_464f6dce8ce133a02dd86a13`: The phenomenon of fitting our training data more closely than we fit the underlying distribution is called *overfitting*, and the techniques used to combat overfitting are called *regularization*.
- `ctx_e3bd3e8dcc83a702caf288d2`: Both cases raise the obvious question of how to generate training data.
- `ctx_b035055ba332f55c6df9256e`: Suppose that we have only a finite amount of training data.

### Part-of-speech evidence

- `ctx_c5e59f5a1a3a5b62dda17291`: One common failure mode occurs in datasets where some groups of people are unrepresented in the training data.
- `ctx_ab61947a37276da02a409618`: Given the learned linear regression model $\hat{\mathbf{w}}^\top \mathbf{x} + \hat{b}$, we can now estimate the price of a new house (not contained in the training data) given its area $x_1$ and age $x_2$.
- `ctx_1ff425af2f5e658c4e18ce61`: It provides efficient transfer of training data to the system and storage of intermediate checkpoints as needed.

## 10. transposed convolutional layer

- `sense_id`: `d2lce_b63485c15ac13f80b0d98676`
- Split: `development`
- Model definition: a neural network layer that performs transposed convolution, often used to increase the spatial size of feature maps
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_700b11b81ca2e72692a5a10b`: As in all, if we feed $\mathsf{X}$ into a convolutional layer $f$ to output $\mathsf{Y}=f(\mathsf{X})$ and create a transposed convolutional layer $g$ with the same hyperparameters as $f$ except for the number of output channels being the number of channels in $\mathsf{X}$, then $g(Y)$ will have the same shape as $\mathsf{X}$.
- `ctx_c31c40505234fb275a371e68`: Since $(320-64+16\times2+32)/32=10$ and $(480-64+16\times2+32)/32=15$, we construct a transposed convolutional layer with stride of $32$, setting the height and width of the kernel to $64$, the padding to $16$.
- `ctx_9b15a3bec2eb4c48b77389f6`: Therefore, the transposed convolutional layer can just exchange the forward propagation function and the backpropagation function of the convolutional layer: its forward propagation and backpropagation functions multiply their input vector with $\mathbf{W}^\top$ and $\mathbf{W}$, respectively.
- `ctx_d91e676cce0a871ea754a783`: The transposed convolutional layer can just exchange the forward propagation function and the backpropagation function of the convolutional layer.
- `ctx_8d6f6ef23f8bdcf7a45e53a7`: Unlike the CNNs that we encountered earlier for image classification or object detection, a fully convolutional network transforms the height and width of intermediate feature maps back to those of the input image: this is achieved by the transposed convolutional layer introduced in :numref:`sec_transposed_conv`.

### Backup contexts

- `ctx_0065bebfdcf4a9b6ce79df26`: * If we feed $\mathsf{X}$ into a convolutional layer $f$ to output $\mathsf{Y}=f(\mathsf{X})$ and create a transposed convolutional layer $g$ with the same hyperparameters as $f$ except for the number of output channels being the number of channels in $\mathsf{X}$, then $g(Y)$ will have the same shape as $\mathsf{X}$.
- `ctx_8ce15c1d9039adf76ce88c55`: ## [**Initializing Transposed Convolutional Layers**]
- `ctx_6bfa4b829229eac81f6930d5`: The hyperparameters of the convolution layer are similar to the transpose convolution layer in the generator block.

### Contrastive contexts

- `ctxx_bd3b044469ca93d412c30d46`: Synthetic: The transposed convolutional layer upsamples a feature map so its height and width move back toward the input image size.

### Definition evidence

- `ctx_700b11b81ca2e72692a5a10b`: As in all, if we feed $\mathsf{X}$ into a convolutional layer $f$ to output $\mathsf{Y}=f(\mathsf{X})$ and create a transposed convolutional layer $g$ with the same hyperparameters as $f$ except for the number of output channels being the number of channels in $\mathsf{X}$, then $g(Y)$ will have the same shape as $\mathsf{X}$.
- `ctx_9b15a3bec2eb4c48b77389f6`: Therefore, the transposed convolutional layer can just exchange the forward propagation function and the backpropagation function of the convolutional layer: its forward propagation and backpropagation functions multiply their input vector with $\mathbf{W}^\top$ and $\mathbf{W}$, respectively.
- `ctx_8d6f6ef23f8bdcf7a45e53a7`: Unlike the CNNs that we encountered earlier for image classification or object detection, a fully convolutional network transforms the height and width of intermediate feature maps back to those of the input image: this is achieved by the transposed convolutional layer introduced in :numref:`sec_transposed_conv`.
- `ctx_c31c40505234fb275a371e68`: Since $(320-64+16\times2+32)/32=10$ and $(480-64+16\times2+32)/32=15$, we construct a transposed convolutional layer with stride of $32$, setting the height and width of the kernel to $64$, the padding to $16$.

### Part-of-speech evidence

- `ctx_700b11b81ca2e72692a5a10b`: As in all, if we feed $\mathsf{X}$ into a convolutional layer $f$ to output $\mathsf{Y}=f(\mathsf{X})$ and create a transposed convolutional layer $g$ with the same hyperparameters as $f$ except for the number of output channels being the number of channels in $\mathsf{X}$, then $g(Y)$ will have the same shape as $\mathsf{X}$.
- `ctx_9b15a3bec2eb4c48b77389f6`: Therefore, the transposed convolutional layer can just exchange the forward propagation function and the backpropagation function of the convolutional layer: its forward propagation and backpropagation functions multiply their input vector with $\mathbf{W}^\top$ and $\mathbf{W}$, respectively.
