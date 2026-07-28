# Stage A sense casebook: test_001

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. aspect ratio

- `sense_id`: `d2lce_ddf8557de1cd5ff23b86e10e`
- Split: `test`
- Model definition: The ratio of width to height of an image, crop, or bounding box shape.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_edee5fe2e1661000bfa4fb46`: To generate multiple anchor boxes with different shapes, let us set a series of scales $s_1,\ldots, s_n$ and a series of aspect ratios $r_1,\ldots, r_m$.
- `ctx_ec292af69704274aef814a00`: Let the *scale* be $s\in (0, 1]$ and the *aspect ratio* (ratio of width to height) is $r > 0$.
- `ctx_1771d4213211e7f2f5001fa2`: We specify the input image, a list of scales, and a list of aspect ratios, then this function will return all the anchor boxes.
- `ctx_49d0624ce664cb21c21aefb1`: Here we introduce one of such methods: it generates multiple bounding boxes with varying scales and aspect ratios centered on each pixel.
- `ctx_88bff3b8804e23bebb2d55a1`: During training, we first crop a random area of random size and random aspect ratio from the image, and then scale this area to a $224 \times 224$ input image.

### Backup contexts

- `ctx_c073292947644f0178d4e119`: When using all the combinations of these scales and aspect ratios with each pixel as the center, the input image will have a total of $whnm$ anchor boxes.
- `ctx_2ef83967671b4c94ed02f565`: As you can see, [**the images vary in size and aspect ratio**].
- `ctx_b48760685d8ba1fd7b94cf59`: As you can see, the blue anchor box with a scale of 0.75 and an aspect ratio of 1 well surrounds the dog in the image.

### Contrastive contexts

- `ctxx_21b8f88447b5c0d4d9adc8b7`: Synthetic: In these examples, aspect ratio means the numeric width-to-height ratio, not a named media format category.

### Definition evidence

- `ctx_ec292af69704274aef814a00`: Let the *scale* be $s\in (0, 1]$ and the *aspect ratio* (ratio of width to height) is $r > 0$.
- `ctx_2ef83967671b4c94ed02f565`: As you can see, [**the images vary in size and aspect ratio**].
- `ctx_49d0624ce664cb21c21aefb1`: Here we introduce one of such methods: it generates multiple bounding boxes with varying scales and aspect ratios centered on each pixel.

### Part-of-speech evidence

- `ctx_ec292af69704274aef814a00`: Let the *scale* be $s\in (0, 1]$ and the *aspect ratio* (ratio of width to height) is $r > 0$.
- `ctx_1771d4213211e7f2f5001fa2`: We specify the input image, a list of scales, and a list of aspect ratios, then this function will return all the anchor boxes.

## 2. biases

- `sense_id`: `d2lce_ad13d119a140210b487eeb9c`
- Split: `test`
- Model definition: additive parameter terms in a model or layer, separate from weights
- Model POS: `noun`

### Primary contexts

- `ctx_f39416c0356d035abdc7883d`: where $\mathbf{W}_{xr}, \mathbf{W}_{xz} \in \mathbb{R}^{d \times h}$ and $\mathbf{W}_{hr}, \mathbf{W}_{hz} \in \mathbb{R}^{h \times h}$ are weight parameters and $\mathbf{b}_r, \mathbf{b}_z \in \mathbb{R}^{1 \times h}$ are biases.
- `ctx_8220d3cebdb8d8496afc7dec`: First, this fully-connected layer contains two parameters, corresponding to that layer's weights and biases, respectively.
- `ctx_e3bf9e80bcc3730f9ba86f3f`: Since the hidden and output layers are both fully connected, we have hidden-layer weights $\mathbf{W}^{(1)} \in \mathbb{R}^{d \times h}$ and biases $\mathbf{b}^{(1)} \in \mathbb{R}^{1 \times h}$ and output-layer weights $\mathbf{W}^{(2)} \in \mathbb{R}^{h \times q}$ and biases $\mathbf{b}^{(2)} \in \mathbb{R}^{1 \times q}$.
- `ctx_c0e733027b5b88c5c367bd09`: Suppose that $\mathbf{U}$ contains biases, we could formally express the fully-connected layer as
- `ctx_226004d4a6485dcdc36de876`: That is, for all $f \in \mathcal{F}$ there exists some set of parameters (e.g., weights and biases) that can be obtained through training on a suitable dataset.

### Backup contexts

- `ctx_cc6c6f7b38edd14783c3c98a`: Note that these diagrams highlight the connectivity pattern such as how each input is connected to the output, but not the values taken by the weights or biases.

### Contrastive contexts

- `ctx_099f24b82e0d670010409a81`: Different from the case in :numref:`fig_eye-coffee` where the coffee biases you towards selecting based on saliency, in this task-dependent case you select the book under cognitive and volitional control.

### Definition evidence

- `ctx_e3bf9e80bcc3730f9ba86f3f`: Since the hidden and output layers are both fully connected, we have hidden-layer weights $\mathbf{W}^{(1)} \in \mathbb{R}^{d \times h}$ and biases $\mathbf{b}^{(1)} \in \mathbb{R}^{1 \times h}$ and output-layer weights $\mathbf{W}^{(2)} \in \mathbb{R}^{h \times q}$ and biases $\mathbf{b}^{(2)} \in \mathbb{R}^{1 \times q}$.
- `ctx_f39416c0356d035abdc7883d`: where $\mathbf{W}_{xr}, \mathbf{W}_{xz} \in \mathbb{R}^{d \times h}$ and $\mathbf{W}_{hr}, \mathbf{W}_{hz} \in \mathbb{R}^{h \times h}$ are weight parameters and $\mathbf{b}_r, \mathbf{b}_z \in \mathbb{R}^{1 \times h}$ are biases.
- `ctx_8220d3cebdb8d8496afc7dec`: First, this fully-connected layer contains two parameters, corresponding to that layer's weights and biases, respectively.

### Part-of-speech evidence

- `ctx_e3bf9e80bcc3730f9ba86f3f`: Since the hidden and output layers are both fully connected, we have hidden-layer weights $\mathbf{W}^{(1)} \in \mathbb{R}^{d \times h}$ and biases $\mathbf{b}^{(1)} \in \mathbb{R}^{1 \times h}$ and output-layer weights $\mathbf{W}^{(2)} \in \mathbb{R}^{h \times q}$ and biases $\mathbf{b}^{(2)} \in \mathbb{R}^{1 \times q}$.
- `ctx_f39416c0356d035abdc7883d`: where $\mathbf{W}_{xr}, \mathbf{W}_{xz} \in \mathbb{R}^{d \times h}$ and $\mathbf{W}_{hr}, \mathbf{W}_{hz} \in \mathbb{R}^{h \times h}$ are weight parameters and $\mathbf{b}_r, \mathbf{b}_z \in \mathbb{R}^{1 \times h}$ are biases.

## 3. blocks

- `sense_id`: `d2lce_20c658fd4e221ee551790ec2`
- Split: `test`
- Model definition: modular units or chunks treated as grouped components in a model, program, or computation
- Model POS: `noun`

### Primary contexts

- `ctx_20b4a3b3e9da0f80ed6d5279`: The base model ($\text{BERT}_{\text{BASE}}$) uses 12 layers (transformer encoder blocks) with 768 hidden units (hidden size) and 12 self-attention heads.
- `ctx_b9ce0a059491eaaa6fbf542f`: However, option 4 offers a practically useful alternative: we can move blocks of the matrix into cache and multiply them locally.
- `ctx_46d4831aad13e3c413d4aaef`: The generator consists of four basic blocks that increase input's both width and height from 1 to 32.
- `ctx_8e452eff442f6f0cb419316b`: * In traditional CNNs, the representations encoded by the convolutional blocks are processed by one or more fully-connected layers prior to emitting output.
- `ctx_f7e9706f82de50c8f6380d6c`: Just as semiconductor designers went from specifying transistors to logical circuits to writing code, neural networks researchers have moved from thinking about the behavior of individual artificial neurons to conceiving of networks in terms of whole layers, and now often design architectures with far coarser *blocks* in mind.

### Backup contexts

- `ctx_6481a5fd90279243349a9cd9`: This model mainly consists of a base network followed by several multiscale feature map blocks.
- `ctx_26916f0b3985aa996c0cee2c`: These models include AlexNet, the first large-scale network deployed to beat conventional computer vision methods on a large-scale vision challenge; the VGG network, which makes use of a number of repeating blocks of elements; the network in network (NiN) which convolves whole neural networks patch-wise over inputs; GoogLeNet, which uses networks with parallel concatenations; residual networks (ResNet), which remain the most popular off-the-shelf architecture in computer vision; and densely connected networks (DenseNet), which are expensive to compute but have set some recent benchmarks.
- `ctx_0c72a2d7feb8a2a7f2b17bfd`: We will illustrate the benefits below, focusing on sequential models and blocks.

### Contrastive contexts

- `ctxx_09ae76f62d4c4c6032674315`: Synthetic: The city planner divided the street into blocks for navigation.

### Definition evidence

- `ctx_f7e9706f82de50c8f6380d6c`: Just as semiconductor designers went from specifying transistors to logical circuits to writing code, neural networks researchers have moved from thinking about the behavior of individual artificial neurons to conceiving of networks in terms of whole layers, and now often design architectures with far coarser *blocks* in mind.
- `ctx_8e452eff442f6f0cb419316b`: * In traditional CNNs, the representations encoded by the convolutional blocks are processed by one or more fully-connected layers prior to emitting output.
- `ctx_b9ce0a059491eaaa6fbf542f`: However, option 4 offers a practically useful alternative: we can move blocks of the matrix into cache and multiply them locally.

### Part-of-speech evidence

- `ctx_f7e9706f82de50c8f6380d6c`: Just as semiconductor designers went from specifying transistors to logical circuits to writing code, neural networks researchers have moved from thinking about the behavior of individual artificial neurons to conceiving of networks in terms of whole layers, and now often design architectures with far coarser *blocks* in mind.
- `ctx_8e452eff442f6f0cb419316b`: * In traditional CNNs, the representations encoded by the convolutional blocks are processed by one or more fully-connected layers prior to emitting output.
- `ctx_b9ce0a059491eaaa6fbf542f`: However, option 4 offers a practically useful alternative: we can move blocks of the matrix into cache and multiply them locally.

## 4. bus

- `sense_id`: `d2lce_0e100796a86968fbdb5730e8`
- Split: `test`
- Model definition: a hardware communication channel that connects computer components and carries data between them
- Model POS: `noun`

### Primary contexts

- `ctx_e8008e6c726f8c456dd13670`: * A high speed expansion bus (PCIe) to connect the system to one or more GPUs.
- `ctx_9c7cb530892c541864a886a0`: Again, GPUs shine here with buses that are at least 10 times as wide as many CPUs.
- `ctx_31d9d345d8772a7d7d3b2609`: As :numref:`fig_mobo-symbol` indicates, most components (network, GPU, and storage) are connected to the CPU across the PCIe bus.
- `ctx_78a920407a1e59b211a91a2e`: Note that this task is different from parallel computation as it uses a different resource: the bus between the CPU and GPUs.
- `ctx_b44942e2470ad6fe760cd183`: * Durable storage, such as a magnetic hard disk drive, a solid state drive, in many cases connected using the PCIe bus.

### Backup contexts

- `ctx_7349ee9d9b4a8278ad2c5a30`: Hence it works to our advantage to start using PCI-Express bus bandwidth while the GPU is still running.
- `ctx_e19d49bc2dd4e4708089da67`: Look for wide memory buses if using GDDR6.

### Contrastive contexts

- `ctxx_136190004cd2926397f62441`: The bus stopped in front of the station.

### Definition evidence

- `ctx_7349ee9d9b4a8278ad2c5a30`: Hence it works to our advantage to start using PCI-Express bus bandwidth while the GPU is still running.
- `ctx_e8008e6c726f8c456dd13670`: * A high speed expansion bus (PCIe) to connect the system to one or more GPUs.
- `ctx_31d9d345d8772a7d7d3b2609`: As :numref:`fig_mobo-symbol` indicates, most components (network, GPU, and storage) are connected to the CPU across the PCIe bus.

### Part-of-speech evidence

- `ctx_7349ee9d9b4a8278ad2c5a30`: Hence it works to our advantage to start using PCI-Express bus bandwidth while the GPU is still running.
- `ctx_31d9d345d8772a7d7d3b2609`: As :numref:`fig_mobo-symbol` indicates, most components (network, GPU, and storage) are connected to the CPU across the PCIe bus.

## 5. CNN

- `sense_id`: `d2lce_eba859df6c63311dce4a5eb7`
- Split: `test`
- Model definition: a convolutional neural network; a neural network architecture based on convolutional layers
- Model POS: `noun`

### Primary contexts

- `ctx_d958615e5797dcf7dbebc74d`: We now have all the ingredients required to assemble a fully-functional CNN.
- `ctx_d3ee9a0901707fef51f604cc`: In the following we introduce a CNN-based multiscale object detection method that we will implement in :numref:`sec_ssd`.
- `ctx_061ed2ce35d54d5df8e71544`: CNN-based architectures are now ubiquitous in the field of computer vision, and have become so dominant that hardly anyone today would develop a commercial application or enter a competition related to image recognition, object detection, or semantic segmentation, without building off of this approach.
- `ctx_167b091ef55430ca8f9a74c1`: Now that we understand the basics of wiring together CNNs, we will take you through a tour of modern CNN architectures.
- `ctx_623445579aad7a2214e0e1e3`: Now let us denote the $2 \times 2$ output as $\mathbf{Y}$ and consider a deeper CNN with an additional $2 \times 2$ convolutional layer that takes $\mathbf{Y}$ as its input, outputting a single element $z$.

### Backup contexts

- `ctx_8b3dbbc201dd9f141734c7f2`: ```toc :maxdepth: 2 sentiment-analysis-and-dataset sentiment-analysis-rnn sentiment-analysis-cnn natural-language-inference-and-dataset natural-language-inference-attention finetuning-bert natural-language-inference-bert ```
- `ctx_a111db6cfdc3af70e259eae0`: In the next chapter, we will dive into full implementations of some popular and comparatively recent CNN architectures whose designs represent most of the techniques commonly used by modern practitioners.
- `ctx_b623c596d3c134838c86f0ba`: ![Comparing CNN (padding tokens are omitted), RNN, and self-attention architectures.](../img/cnn-rnn-self-attention.svg) :label:`fig_cnn-rnn-self-attention`

### Contrastive contexts

- `ctxx_0395788ecac190f90a2c3609`: Synthetic: The CNN uses convolutional layers, unlike an RNN that processes sequences recurrently.

### Definition evidence

- `ctx_167b091ef55430ca8f9a74c1`: Now that we understand the basics of wiring together CNNs, we will take you through a tour of modern CNN architectures.
- `ctx_623445579aad7a2214e0e1e3`: Now let us denote the $2 \times 2$ output as $\mathbf{Y}$ and consider a deeper CNN with an additional $2 \times 2$ convolutional layer that takes $\mathbf{Y}$ as its input, outputting a single element $z$.
- `ctx_d958615e5797dcf7dbebc74d`: We now have all the ingredients required to assemble a fully-functional CNN.

### Part-of-speech evidence

- `ctx_167b091ef55430ca8f9a74c1`: Now that we understand the basics of wiring together CNNs, we will take you through a tour of modern CNN architectures.
- `ctx_b623c596d3c134838c86f0ba`: ![Comparing CNN (padding tokens are omitted), RNN, and self-attention architectures.](../img/cnn-rnn-self-attention.svg) :label:`fig_cnn-rnn-self-attention`
- `ctx_d958615e5797dcf7dbebc74d`: We now have all the ingredients required to assemble a fully-functional CNN.

## 6. constant

- `sense_id`: `d2lce_46e81052dcb25b16e429062a`
- Split: `test`
- Model definition: a fixed value or quantity that does not change within the given setting or calculation
- Model POS: `noun`

### Primary contexts

- `ctx_ea695244ac38f31f89ef729b`: Now the *input* for step 2 is perturbed by $\epsilon_1$, hence we suffer some error in the order of $\epsilon_2 = \bar\epsilon + c \epsilon_1$ for some constant $c$, and so on.
- `ctx_1f1572c94613de76cd12614d`: Typically, we will want our matrices initialized either with zeros, ones, some other constants, or numbers randomly sampled from a specific distribution.
- `ctx_426bd774623f1d7d45637e8c`: Note that we add a small constant $\epsilon > 0$ to the variance estimate to ensure that we never attempt division by zero, even in cases where the empirical variance estimate might vanish.
- `ctx_6680b855ff6f781511dd10c7`: The constant $\frac{1}{2}$ makes no real difference but will prove notationally convenient, canceling out when we take the derivative of the loss.
- `ctx_a81307e03098966ed96b74bf`: This is only possible if $\mathsf{V}$ and $\mathbf{U}$ do not actually depend on $(i, j)$, i.e., we have $[\mathsf{V}]_{i, j, a, b} = [\mathbf{V}]_{a, b}$ and $\mathbf{U}$ is a constant, say $u$.

### Backup contexts

- `ctx_3596d41647ddaacf0aed8755`: We call these *constant parameters*.
- `ctx_e3a4772ecd482355d1d71feb`: When every example is characterized by the same number of numerical values, we say that the data consist of fixed-length vectors and we describe the constant length of the vectors as the *dimensionality* of the data.
- `ctx_1468868079bb9b62650af1ce`: Determine the best value of this hyperparameter, keeping all others constant.

### Contrastive contexts

- `ctxx_4b9123a043f392cf6798ebdd`: Synthetic: She remained constant in her support throughout the project.

### Definition evidence

- `ctx_6680b855ff6f781511dd10c7`: The constant $\frac{1}{2}$ makes no real difference but will prove notationally convenient, canceling out when we take the derivative of the loss.
- `ctx_a81307e03098966ed96b74bf`: This is only possible if $\mathsf{V}$ and $\mathbf{U}$ do not actually depend on $(i, j)$, i.e., we have $[\mathsf{V}]_{i, j, a, b} = [\mathbf{V}]_{a, b}$ and $\mathbf{U}$ is a constant, say $u$.
- `ctx_426bd774623f1d7d45637e8c`: Note that we add a small constant $\epsilon > 0$ to the variance estimate to ensure that we never attempt division by zero, even in cases where the empirical variance estimate might vanish.

### Part-of-speech evidence

- `ctx_6680b855ff6f781511dd10c7`: The constant $\frac{1}{2}$ makes no real difference but will prove notationally convenient, canceling out when we take the derivative of the loss.
- `ctx_a81307e03098966ed96b74bf`: This is only possible if $\mathsf{V}$ and $\mathbf{U}$ do not actually depend on $(i, j)$, i.e., we have $[\mathsf{V}]_{i, j, a, b} = [\mathbf{V}]_{a, b}$ and $\mathbf{U}$ is a constant, say $u$.
- `ctx_ea695244ac38f31f89ef729b`: Now the *input* for step 2 is perturbed by $\epsilon_1$, hence we suffer some error in the order of $\epsilon_2 = \bar\epsilon + c \epsilon_1$ for some constant $c$, and so on.

## 7. DenseNet

- `sense_id`: `d2lce_20dc13bc32661f00e7c68b89`
- Split: `test`
- Model definition: A densely connected convolutional neural network architecture with cross-layer concatenation.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_e9402aa6f9b633df0ecf9fc4`: These models include AlexNet, the first large-scale network deployed to beat conventional computer vision methods on a large-scale vision challenge; the VGG network, which makes use of a number of repeating blocks of elements; the network in network (NiN) which convolves whole neural networks patch-wise over inputs; GoogLeNet, which uses networks with parallel concatenations; residual networks (ResNet), which remain the most popular off-the-shelf architecture in computer vision; and densely connected networks (DenseNet), which are expensive to compute but have set some recent benchmarks.
- `ctx_981520000f6c76ee266ec54f`: *DenseNet* (dense convolutional network) is to some extent the logical extension of this :cite:`Huang.Liu.Van-Der-Maaten.ea.2017`.
- `ctx_f9057a408bf3295c1dcc296d`: ## From ResNet to DenseNet
- `ctx_19e916efd49f7b3c9be7b919`: ](../img/densenet-block.svg) :label:`fig_densenet_block`
- `ctx_a3cd664e61e3be597eb099e5`: ![The main difference between ResNet (left) and DenseNet (right) in cross-layer connections: use of addition and use of concatenation.

### Backup contexts

- `ctx_b8d101968126191ff892ca33`: # Densely Connected Networks (DenseNet)
- `ctx_e103354145e998be1861c7f8`: ```toc :maxdepth: 2 alexnet vgg nin googlenet batch-norm resnet densenet ```
- `ctx_e31d70fd51aadff019c9601e`: One solution was DenseNet :cite:`Huang.Liu.Van-Der-Maaten.ea.2017`.

### Contrastive contexts

- `ctxx_9773fd20dd889464110d4597`: Synthetic: The lab used a dense net to catch fish, which is unrelated to DenseNet.

### Definition evidence

- `ctx_e9402aa6f9b633df0ecf9fc4`: These models include AlexNet, the first large-scale network deployed to beat conventional computer vision methods on a large-scale vision challenge; the VGG network, which makes use of a number of repeating blocks of elements; the network in network (NiN) which convolves whole neural networks patch-wise over inputs; GoogLeNet, which uses networks with parallel concatenations; residual networks (ResNet), which remain the most popular off-the-shelf architecture in computer vision; and densely connected networks (DenseNet), which are expensive to compute but have set some recent benchmarks.
- `ctx_b8d101968126191ff892ca33`: # Densely Connected Networks (DenseNet)
- `ctx_981520000f6c76ee266ec54f`: *DenseNet* (dense convolutional network) is to some extent the logical extension of this :cite:`Huang.Liu.Van-Der-Maaten.ea.2017`.
- `ctx_a3cd664e61e3be597eb099e5`: ![The main difference between ResNet (left) and DenseNet (right) in cross-layer connections: use of addition and use of concatenation.

### Part-of-speech evidence

- `ctx_e9402aa6f9b633df0ecf9fc4`: These models include AlexNet, the first large-scale network deployed to beat conventional computer vision methods on a large-scale vision challenge; the VGG network, which makes use of a number of repeating blocks of elements; the network in network (NiN) which convolves whole neural networks patch-wise over inputs; GoogLeNet, which uses networks with parallel concatenations; residual networks (ResNet), which remain the most popular off-the-shelf architecture in computer vision; and densely connected networks (DenseNet), which are expensive to compute but have set some recent benchmarks.
- `ctx_b8d101968126191ff892ca33`: # Densely Connected Networks (DenseNet)

## 8. dimensionality

- `sense_id`: `d2lce_f3dedf5fcd54a46940474022`
- Split: `test`
- Model definition: The number of components, features, or axes used to represent data or an internal representation.
- Model POS: `noun`

### Primary contexts

- `ctx_cf2fee46db0f41e6ec64a579`: To make the effects of overfitting pronounced, we can increase the dimensionality of our problem to $d = 200$ and work with a small training set containing only 20 examples.
- `ctx_9a25a4253bc511ca8268d02a`: ### Length, Dimensionality, and Shape
- `ctx_305c430849e3734c0aa7afaf`: When every example is characterized by the same number of numerical values, we say that the data consist of fixed-length vectors and we describe the constant length of the vectors as the *dimensionality* of the data.
- `ctx_4d511a9e270716621c12b480`: * We defined the network architectures without specifying the input dimensionality.
- `ctx_571461d7592e0eb07fae9808`: For the neural network shown in :numref:`fig_single_neuron`, the inputs are $x_1, \ldots, x_d$, so the *number of inputs* (or *feature dimensionality*) in the input layer is $d$.

### Backup contexts

- `ctx_3923942a6da07182f6169b13`: While previously, we might have required billions of parameters to represent just a single layer in an image-processing network, we now typically need just a few hundred, without altering the dimensionality of either the inputs or the hidden representations.
- `ctx_e9947a95d89c9d79c07f1e69`: Let us [**check whether the outputs have the correct shapes**], e.g., to ensure that the dimensionality of the hidden state remains unchanged.
- `ctx_bc1664e975977f0d9d0df8c9`: Maximum pooling between inception blocks reduces the dimensionality.

### Contrastive contexts

- `ctxx_a3ccd49d589dc3af43f18b02`: Synthetic: Here, dimensionality means how many features or axes represent the data, not the physical length of an object.

### Definition evidence

- `ctx_305c430849e3734c0aa7afaf`: When every example is characterized by the same number of numerical values, we say that the data consist of fixed-length vectors and we describe the constant length of the vectors as the *dimensionality* of the data.
- `ctx_571461d7592e0eb07fae9808`: For the neural network shown in :numref:`fig_single_neuron`, the inputs are $x_1, \ldots, x_d$, so the *number of inputs* (or *feature dimensionality*) in the input layer is $d$.
- `ctx_e9947a95d89c9d79c07f1e69`: Let us [**check whether the outputs have the correct shapes**], e.g., to ensure that the dimensionality of the hidden state remains unchanged.

### Part-of-speech evidence

- `ctx_305c430849e3734c0aa7afaf`: When every example is characterized by the same number of numerical values, we say that the data consist of fixed-length vectors and we describe the constant length of the vectors as the *dimensionality* of the data.
- `ctx_9a25a4253bc511ca8268d02a`: ### Length, Dimensionality, and Shape

## 9. distribution

- `sense_id`: `d2lce_c47822c187c02e12aa499ec6`
- Split: `test`
- Model definition: the way probability mass, density, values, or data characteristics are spread over possible outcomes or examples
- Model POS: `noun`

### Primary contexts

- `ctx_2606fc94edd8ad29a05c47bb`: * $X$: a random variable * $P$: a probability distribution * $X \sim P$: the random variable $X$ has distribution $P$ * $P(X=x)$: the probability assigned to the event where random variable $X$ takes value $x$ * $P(X \mid Y)$: the conditional probability distribution of $X$ given $Y$ * $p(\cdot)$: a probability density function (PDF) associated with distribution P * ${E}[X]$: expectation of a random variable $X$ * $X \perp Y$: random variables $X$ and $Y$ are independent * $X \perp Y \mid Z$: random variables $X$ and $Y$ are conditionally independent given $Z$ * $\sigma_X$: standard deviation of random variable $X$ * $\mathrm{Var}(X)$: variance of random variable $X$, equal to $\sigma^2_X$ * $\mathrm{Cov}(X, Y)$: covariance of random variables $X$ and $Y$ * $\rho(X, Y)$: the Pearson correlation coefficient between $X$ and $Y$, equals $\frac{\mathrm{Cov}(X, Y)}{\sigma_X \sigma_Y}$ * $H(X)$: entropy of random variable $X$ * $D_{\mathrm{KL}}(P\|Q)$: the KL-divergence (or relative entropy) from distribution $Q$ to distribution $P$
- `ctx_d9e926841554c7c006b73e6d`: The inventors of batch normalization postulated informally that this drift in the distribution of such variables could hamper the convergence of the network.
- `ctx_1641e82199eae62cda1187c0`: Second, we assume that any noise is well-behaved (following a Gaussian distribution).
- `ctx_fee67727bfbe4157c5c6994e`: :begin_tab:`mxnet` By default, MXNet initializes weight parameters by randomly drawing from a uniform distribution $U(-0.07, 0.07)$, clearing bias parameters to zero.
- `ctx_22ee6c085ab714120f38865d`: Typically, we will want our matrices initialized either with zeros, ones, some other constants, or numbers randomly sampled from a specific distribution.

### Backup contexts

- `ctx_adfc32dfad2c16e59d906c41`: Along the way, we learned how to wrangle data, coerce our outputs into a valid probability distribution, apply an appropriate loss function, and minimize it with respect to our model's parameters.
- `ctx_4110fd6b0cfb72d128594a20`: This last question raises the problem of *distribution shift*, when training and test data are different.

### Contrastive contexts

- `ctxx_85285f0d027767b78f70c1d2`: Synthetic: The company changed the distribution of books across its retail stores last month.

### Definition evidence

- `ctx_2606fc94edd8ad29a05c47bb`: * $X$: a random variable * $P$: a probability distribution * $X \sim P$: the random variable $X$ has distribution $P$ * $P(X=x)$: the probability assigned to the event where random variable $X$ takes value $x$ * $P(X \mid Y)$: the conditional probability distribution of $X$ given $Y$ * $p(\cdot)$: a probability density function (PDF) associated with distribution P * ${E}[X]$: expectation of a random variable $X$ * $X \perp Y$: random variables $X$ and $Y$ are independent * $X \perp Y \mid Z$: random variables $X$ and $Y$ are conditionally independent given $Z$ * $\sigma_X$: standard deviation of random variable $X$ * $\mathrm{Var}(X)$: variance of random variable $X$, equal to $\sigma^2_X$ * $\mathrm{Cov}(X, Y)$: covariance of random variables $X$ and $Y$ * $\rho(X, Y)$: the Pearson correlation coefficient between $X$ and $Y$, equals $\frac{\mathrm{Cov}(X, Y)}{\sigma_X \sigma_Y}$ * $H(X)$: entropy of random variable $X$ * $D_{\mathrm{KL}}(P\|Q)$: the KL-divergence (or relative entropy) from distribution $Q$ to distribution $P$
- `ctx_22ee6c085ab714120f38865d`: Typically, we will want our matrices initialized either with zeros, ones, some other constants, or numbers randomly sampled from a specific distribution.
- `ctx_4110fd6b0cfb72d128594a20`: This last question raises the problem of *distribution shift*, when training and test data are different.

### Part-of-speech evidence

- `ctx_2606fc94edd8ad29a05c47bb`: * $X$: a random variable * $P$: a probability distribution * $X \sim P$: the random variable $X$ has distribution $P$ * $P(X=x)$: the probability assigned to the event where random variable $X$ takes value $x$ * $P(X \mid Y)$: the conditional probability distribution of $X$ given $Y$ * $p(\cdot)$: a probability density function (PDF) associated with distribution P * ${E}[X]$: expectation of a random variable $X$ * $X \perp Y$: random variables $X$ and $Y$ are independent * $X \perp Y \mid Z$: random variables $X$ and $Y$ are conditionally independent given $Z$ * $\sigma_X$: standard deviation of random variable $X$ * $\mathrm{Var}(X)$: variance of random variable $X$, equal to $\sigma^2_X$ * $\mathrm{Cov}(X, Y)$: covariance of random variables $X$ and $Y$ * $\rho(X, Y)$: the Pearson correlation coefficient between $X$ and $Y$, equals $\frac{\mathrm{Cov}(X, Y)}{\sigma_X \sigma_Y}$ * $H(X)$: entropy of random variable $X$ * $D_{\mathrm{KL}}(P\|Q)$: the KL-divergence (or relative entropy) from distribution $Q$ to distribution $P$
- `ctx_22ee6c085ab714120f38865d`: Typically, we will want our matrices initialized either with zeros, ones, some other constants, or numbers randomly sampled from a specific distribution.
- `ctx_d9e926841554c7c006b73e6d`: The inventors of batch normalization postulated informally that this drift in the distribution of such variables could hamper the convergence of the network.

## 10. feature interactions

- `sense_id`: `d2lce_8de4d36bcb2f1ad2291dd52e`
- Split: `test`
- Model definition: relationships or combined effects between multiple features that a model tries to capture
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_28fec5561cc94064400b1c46`: Factorization machines model feature interactions in a linear paradigm (e.g., bilinear interactions).
- `ctx_733d5a1b31d277da5bd2d2ec`: So modeling feature interactions automatically can greatly reduce the efforts in feature engineering.
- `ctx_2aa16b95d94946e5cd854397`: Some feature interactions can be easily understood so they can be designed by experts.
- `ctx_9238bc67b0ba4c1dae5edfe0`: However, most other feature interactions are hidden in data and difficult to identify.
- `ctx_a472d799fb6e0d324456f48d`: The FM component is the same as the 2-way factorization machines which is used to model the low-order feature interactions.

### Backup contexts

- `ctx_aae65f26294db8e10b63b72f`: Deep neural networks are powerful in feature representation learning and have the potential to learn sophisticated feature interactions.
- `ctx_e7740f3e3eacd0600fc7f1e8`: The deep component is an MLP that is used to capture high-order feature interactions and nonlinearities.
- `ctx_8f299ed874eca81dd1cb992d`: What's worse, second-order feature interactions are generally used in factorization machines in practice.

### Contrastive contexts

- `ctxx_441a920e9299feaf54a20bf2`: Synthetic: The museum exhibit focused on feature interactions between carved surfaces and light, not data fields.

### Definition evidence

- `ctx_2aa16b95d94946e5cd854397`: Some feature interactions can be easily understood so they can be designed by experts.
- `ctx_28fec5561cc94064400b1c46`: Factorization machines model feature interactions in a linear paradigm (e.g., bilinear interactions).
- `ctx_e7740f3e3eacd0600fc7f1e8`: The deep component is an MLP that is used to capture high-order feature interactions and nonlinearities.

### Part-of-speech evidence

- `ctx_733d5a1b31d277da5bd2d2ec`: So modeling feature interactions automatically can greatly reduce the efforts in feature engineering.
- `ctx_28fec5561cc94064400b1c46`: Factorization machines model feature interactions in a linear paradigm (e.g., bilinear interactions).
