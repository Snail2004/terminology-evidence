# Stage A sense casebook: test_002

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. inverse

- `sense_id`: `d2lce_98211ac6b2c27c6359ce6dae`
- Split: `test`
- Model definition: an operation, quantity, or object that reverses another; in linear algebra, especially a matrix that undoes multiplication
- Model POS: `noun`

### Primary contexts

- `ctx_b25612872c99360702920048`: * $f(\cdot)$: a function * $\log(\cdot)$: the natural logarithm (base $e$) * $\log_2(\cdot)$: logarithm with base $2$ * $\exp(\cdot)$: the exponential function * $\mathbf{1}(\cdot)$: the indicator function, evaluates to $1$ if the boolean argument is true and $0$ otherwise * $\mathbf{1}_{\mathcal{X}}(z)$: the set-membership indicator function, evaluates to $1$ if the element $z$ belongs to the set $\mathcal{X}$ and $0$ otherwise * $\mathbf{(\cdot)}^\top$: transpose of a vector or a matrix * $\mathbf{X}^{-1}$: inverse of matrix $\mathbf{X}$ * $\odot$: Hadamard (elementwise) product * $[\cdot, \cdot]$: concatenation * $\|\cdot\|_p$: $L_p$ norm * $\|\cdot\|$: $L_2$ norm * $\langle \mathbf{x}, \mathbf{y} \rangle$: dot product of vectors $\mathbf{x}$ and $\mathbf{y}$ * $\sum$: summation over a collection of elements * $\prod$: product over a collection of elements * $\stackrel{\mathrm{def}}{=}$: an equality asserted as a definition of the symbol on the left-hand side
- `ctx_f3b8e197930d717e638aae95`: We have seen above that multiplication by a matrix with linearly dependent columns cannot be undone, i.e., there is no inverse operation that can always recover the input.
- `ctx_47dd346896be4b4baac91c16`: We call such a matrix $\mathbf{A}^{-1}$ the *inverse* matrix.
- `ctx_5c43b025af57aef403bb8489`: then we can see that the inverse is
- `ctx_8cf7fef52d9596f550b824ee`: Below we implement the `offset_inverse` function that takes in anchors and offset predictions as inputs and [**applies inverse offset transformations to return the predicted bounding box coordinates**].

### Backup contexts

- `ctx_9860b0e4dbe6809813dc296b`: On the other hand, if we use a polynomial decay where the learning rate decays with the inverse square root of the number of steps, convergence gets better after only 50 steps.
- `ctx_75eb945ba12ad0637aee80b1`: This is the inverse of automatic speech recognition.
- `ctx_a3264cf3bd2a35a74a627146`: Additionally, as we saw when discussing weight decay ($L_2$ regularization) in :numref:`sec_weight_decay`, the (inverse) norm of the parameters also represents a useful measure of simplicity.

### Contrastive contexts

- `ctxx_bed233cf120704e15cfd064e`: Synthetic: In the sentence, the inverse word order sounds poetic.

### Definition evidence

- `ctx_b25612872c99360702920048`: * $f(\cdot)$: a function * $\log(\cdot)$: the natural logarithm (base $e$) * $\log_2(\cdot)$: logarithm with base $2$ * $\exp(\cdot)$: the exponential function * $\mathbf{1}(\cdot)$: the indicator function, evaluates to $1$ if the boolean argument is true and $0$ otherwise * $\mathbf{1}_{\mathcal{X}}(z)$: the set-membership indicator function, evaluates to $1$ if the element $z$ belongs to the set $\mathcal{X}$ and $0$ otherwise * $\mathbf{(\cdot)}^\top$: transpose of a vector or a matrix * $\mathbf{X}^{-1}$: inverse of matrix $\mathbf{X}$ * $\odot$: Hadamard (elementwise) product * $[\cdot, \cdot]$: concatenation * $\|\cdot\|_p$: $L_p$ norm * $\|\cdot\|$: $L_2$ norm * $\langle \mathbf{x}, \mathbf{y} \rangle$: dot product of vectors $\mathbf{x}$ and $\mathbf{y}$ * $\sum$: summation over a collection of elements * $\prod$: product over a collection of elements * $\stackrel{\mathrm{def}}{=}$: an equality asserted as a definition of the symbol on the left-hand side
- `ctx_f3b8e197930d717e638aae95`: We have seen above that multiplication by a matrix with linearly dependent columns cannot be undone, i.e., there is no inverse operation that can always recover the input.
- `ctx_47dd346896be4b4baac91c16`: We call such a matrix $\mathbf{A}^{-1}$ the *inverse* matrix.

### Part-of-speech evidence

- `ctx_47dd346896be4b4baac91c16`: We call such a matrix $\mathbf{A}^{-1}$ the *inverse* matrix.
- `ctx_5c43b025af57aef403bb8489`: then we can see that the inverse is

## 2. lanes

- `sense_id`: `d2lce_54e0621e7c3812cb511231dc`
- Split: `test`
- Model definition: Individual PCIe data channels used to connect devices and determine available bandwidth.
- Model POS: `noun`

### Primary contexts

- `ctx_416fd3e179861109b82badde`: Even PCIe lanes can be [switched](https://www.broadcom.com/products/pcie-switches-bridges/pcie-switches).
- `ctx_b9752907cbaeda87a3b404e3`: For instance AMD's Threadripper 3 has 64 PCIe 4.0 lanes, each of which is capable 16 Gbit/s data transfer in both directions.
- `ctx_b9233db2688cfcdeb5ffd609`: Processors only have a limited number of them: AMD's EPYC 3 has 128 lanes, Intel's Xeon has up to 48 lanes per chip; on desktop-grade CPUs the numbers are 20 (Ryzen 9) and 16 (Core i9) respectively.
- `ctx_2ff75bd2aba0b559e0372b89`: Since GPUs have typically 16 lanes, this limits the number of GPUs that can connect to the CPU at full bandwidth.
- `ctx_6bd7c851fbe0b08184549738`: The drives capable of handling this, referred to as NVMe (Non Volatile Memory enhanced), can use up to 4 PCIe lanes.

### Backup contexts

- `ctx_f3748c61eb87a6d37adb7d42`: Since the CPUs have too few PCIe lanes to connect to all GPUs directly (e.g., consumer-grade Intel CPUs have 24 lanes) we need a [multiplexer](https://www.broadcom.com/products/pcie-switches-bridges/pcie-switches).
- `ctx_6f956d52b9739e7911277754`: We recommend PCIe 3.0 slots with 16 lanes.
- `ctx_abcdc959b15b58506d6056ee`: It consists of multiple lanes that are directly attached to the CPU.

### Contrastive contexts

- `ctxx_6d6250704a0a3e44beb29e5c`: [Synthetic] The city added two new lanes to reduce rush-hour congestion downtown.

### Definition evidence

- `ctx_b9752907cbaeda87a3b404e3`: For instance AMD's Threadripper 3 has 64 PCIe 4.0 lanes, each of which is capable 16 Gbit/s data transfer in both directions.
- `ctx_2ff75bd2aba0b559e0372b89`: Since GPUs have typically 16 lanes, this limits the number of GPUs that can connect to the CPU at full bandwidth.
- `ctx_b9233db2688cfcdeb5ffd609`: Processors only have a limited number of them: AMD's EPYC 3 has 128 lanes, Intel's Xeon has up to 48 lanes per chip; on desktop-grade CPUs the numbers are 20 (Ryzen 9) and 16 (Core i9) respectively.

### Part-of-speech evidence

- `ctx_6f956d52b9739e7911277754`: We recommend PCIe 3.0 slots with 16 lanes.
- `ctx_b9233db2688cfcdeb5ffd609`: Processors only have a limited number of them: AMD's EPYC 3 has 128 lanes, Intel's Xeon has up to 48 lanes per chip; on desktop-grade CPUs the numbers are 20 (Ryzen 9) and 16 (Core i9) respectively.

## 3. norm

- `sense_id`: `d2lce_3e633e212e54590ca20bfc99`
- Split: `test`
- Model definition: A mathematical function that measures the size or length of a vector, matrix, or related object.
- Model POS: `noun`

### Primary contexts

- `ctx_9ffc871958a632f807c9d3f7`: ## Norms :label:`subsec_lin-algebra-norms`
- `ctx_3637a629ea39c9358f83dfd8`: ## Norms and Weight Decay
- `ctx_d8032e46013fa0aad8a8e8f9`: * $f(\cdot)$: a function * $\log(\cdot)$: the natural logarithm (base $e$) * $\log_2(\cdot)$: logarithm with base $2$ * $\exp(\cdot)$: the exponential function * $\mathbf{1}(\cdot)$: the indicator function, evaluates to $1$ if the boolean argument is true and $0$ otherwise * $\mathbf{1}_{\mathcal{X}}(z)$: the set-membership indicator function, evaluates to $1$ if the element $z$ belongs to the set $\mathcal{X}$ and $0$ otherwise * $\mathbf{(\cdot)}^\top$: transpose of a vector or a matrix * $\mathbf{X}^{-1}$: inverse of matrix $\mathbf{X}$ * $\odot$: Hadamard (elementwise) product * $[\cdot, \cdot]$: concatenation * $\|\cdot\|_p$: $L_p$ norm * $\|\cdot\|$: $L_2$ norm * $\langle \mathbf{x}, \mathbf{y} \rangle$: dot product of vectors $\mathbf{x}$ and $\mathbf{y}$ * $\sum$: summation over a collection of elements * $\prod$: product over a collection of elements * $\stackrel{\mathrm{def}}{=}$: an equality asserted as a definition of the symbol on the left-hand side
- `ctx_8668691d65db41f7ae5d3e67`: Denote by $\mathcal{B}_p[r] \stackrel{\mathrm{def}}{=} \{\mathbf{x} | \mathbf{x} \in \mathbb{R}^d \text{ and } \|\mathbf{x}\|_p \leq r\}$ the ball of radius $r$ using the $p$-norm.
- `ctx_a20bb02df73cb967f9453f6c`: By doing so we know that the gradient norm never exceeds $\theta$ and that the updated gradient is entirely aligned with the original direction of $\mathbf{g}$.

### Backup contexts

- `ctx_f8a8c5c0211fed297689abc4`: We ran a while-loop, testing on the condition its $L_1$ norm is larger than $1$, and dividing our output vector by $2$ until it satisfied the condition.

### Contrastive contexts

- `ctx_08b62bef2e6aa8d336e45cb8`: Now let us focus on the "add & norm" component in :numref:`fig_transformer`.

### Definition evidence

- `ctx_d8032e46013fa0aad8a8e8f9`: * $f(\cdot)$: a function * $\log(\cdot)$: the natural logarithm (base $e$) * $\log_2(\cdot)$: logarithm with base $2$ * $\exp(\cdot)$: the exponential function * $\mathbf{1}(\cdot)$: the indicator function, evaluates to $1$ if the boolean argument is true and $0$ otherwise * $\mathbf{1}_{\mathcal{X}}(z)$: the set-membership indicator function, evaluates to $1$ if the element $z$ belongs to the set $\mathcal{X}$ and $0$ otherwise * $\mathbf{(\cdot)}^\top$: transpose of a vector or a matrix * $\mathbf{X}^{-1}$: inverse of matrix $\mathbf{X}$ * $\odot$: Hadamard (elementwise) product * $[\cdot, \cdot]$: concatenation * $\|\cdot\|_p$: $L_p$ norm * $\|\cdot\|$: $L_2$ norm * $\langle \mathbf{x}, \mathbf{y} \rangle$: dot product of vectors $\mathbf{x}$ and $\mathbf{y}$ * $\sum$: summation over a collection of elements * $\prod$: product over a collection of elements * $\stackrel{\mathrm{def}}{=}$: an equality asserted as a definition of the symbol on the left-hand side
- `ctx_f8a8c5c0211fed297689abc4`: We ran a while-loop, testing on the condition its $L_1$ norm is larger than $1$, and dividing our output vector by $2$ until it satisfied the condition.
- `ctx_8668691d65db41f7ae5d3e67`: Denote by $\mathcal{B}_p[r] \stackrel{\mathrm{def}}{=} \{\mathbf{x} | \mathbf{x} \in \mathbb{R}^d \text{ and } \|\mathbf{x}\|_p \leq r\}$ the ball of radius $r$ using the $p$-norm.

### Part-of-speech evidence

- `ctx_d8032e46013fa0aad8a8e8f9`: * $f(\cdot)$: a function * $\log(\cdot)$: the natural logarithm (base $e$) * $\log_2(\cdot)$: logarithm with base $2$ * $\exp(\cdot)$: the exponential function * $\mathbf{1}(\cdot)$: the indicator function, evaluates to $1$ if the boolean argument is true and $0$ otherwise * $\mathbf{1}_{\mathcal{X}}(z)$: the set-membership indicator function, evaluates to $1$ if the element $z$ belongs to the set $\mathcal{X}$ and $0$ otherwise * $\mathbf{(\cdot)}^\top$: transpose of a vector or a matrix * $\mathbf{X}^{-1}$: inverse of matrix $\mathbf{X}$ * $\odot$: Hadamard (elementwise) product * $[\cdot, \cdot]$: concatenation * $\|\cdot\|_p$: $L_p$ norm * $\|\cdot\|$: $L_2$ norm * $\langle \mathbf{x}, \mathbf{y} \rangle$: dot product of vectors $\mathbf{x}$ and $\mathbf{y}$ * $\sum$: summation over a collection of elements * $\prod$: product over a collection of elements * $\stackrel{\mathrm{def}}{=}$: an equality asserted as a definition of the symbol on the left-hand side
- `ctx_9ffc871958a632f807c9d3f7`: ## Norms :label:`subsec_lin-algebra-norms`

## 4. padding tokens

- `sense_id`: `d2lce_b967af36e17c22a478eaed6d`
- Split: `test`
- Model definition: special tokens added to sequences to make them a common length, usually ignored by masking, attention, or loss computation.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_be96ec1f7ec2e0237f326eab`: Recall :numref:`sec_machine_translation` that the special padding tokens are appended to the end of sequences so sequences of varying lengths can be efficiently loaded in minibatches of the same shape.
- `ctx_05cde72313ed2987ab19ac0d`: The state of the decoder is initialized with (i) the encoder final-layer hidden states at all the time steps (as keys and values of the attention); (ii) the encoder all-layer hidden state at the final time step (to initialize the hidden state of the decoder); and (iii) the encoder valid length (to exclude the padding tokens in attention pooling).
- `ctx_12f79eaad5bc278a9b83706f`: For example, if the valid length of two sequences excluding padding tokens are one and two, respectively, the remaining entries after the first one and the first two entries are cleared to zeros.
- `ctx_451ef79974ff5019b4225f46`: Once the valid length is given, the mask corresponding to any padding token will be cleared to zero.
- `ctx_92a3a25f66c701ea53cc38e8`: In the end, the loss for all the tokens will be multipled by the mask to filter out irrelevant predictions of padding tokens in the loss.

### Backup contexts

- `ctx_b9a74a0f4d6af5455b521e4e`: However, prediction of padding tokens should be excluded from loss calculations.
- `ctx_d8aa0be85777a629e809fc47`: Besides, we also record the length of each text sequence excluding the padding tokens.
- `ctx_a2d3def650d89773da69782d`: ![Comparing CNN (padding tokens are omitted), RNN, and self-attention architectures.](../img/cnn-rnn-self-attention.svg) :label:`fig_cnn-rnn-self-attention`

### Contrastive contexts

- `ctxx_42a6357f3553d007faf93757`: Synthetic boundary probe: "padding tokens" is quoted here only as a document label, not as an occurrence of the reviewed D2L sense.

### Definition evidence

- `ctx_be96ec1f7ec2e0237f326eab`: Recall :numref:`sec_machine_translation` that the special padding tokens are appended to the end of sequences so sequences of varying lengths can be efficiently loaded in minibatches of the same shape.
- `ctx_05cde72313ed2987ab19ac0d`: The state of the decoder is initialized with (i) the encoder final-layer hidden states at all the time steps (as keys and values of the attention); (ii) the encoder all-layer hidden state at the final time step (to initialize the hidden state of the decoder); and (iii) the encoder valid length (to exclude the padding tokens in attention pooling).
- `ctx_92a3a25f66c701ea53cc38e8`: In the end, the loss for all the tokens will be multipled by the mask to filter out irrelevant predictions of padding tokens in the loss.

### Part-of-speech evidence

- `ctx_be96ec1f7ec2e0237f326eab`: Recall :numref:`sec_machine_translation` that the special padding tokens are appended to the end of sequences so sequences of varying lengths can be efficiently loaded in minibatches of the same shape.
- `ctx_b9a74a0f4d6af5455b521e4e`: However, prediction of padding tokens should be excluded from loss calculations.
- `ctx_451ef79974ff5019b4225f46`: Once the valid length is given, the mask corresponding to any padding token will be cleared to zero.

## 5. PCIe

- `sense_id`: `d2lce_35df896f9860f8aac814ce37`
- Split: `test`
- Model definition: the PCI Express hardware interconnect standard used to connect components such as GPUs and storage to a computer system
- Model POS: `proper_noun`

### Primary contexts

- `ctx_bc0b95f28a464a117086fd7d`: * A high speed expansion bus (PCIe) to connect the system to one or more GPUs.
- `ctx_eb05e20b7827c8e88746abb2`: As :numref:`fig_mobo-symbol` indicates, most components (network, GPU, and storage) are connected to the CPU across the PCIe bus.
- `ctx_1d8dbe9ec3f0a06ece3a6924`: If you mount multiple GPUs, be sure to carefully read the motherboard description to ensure that 16x bandwidth is still available when multiple GPUs are used at the same time and that you are getting PCIe 3.0 as opposed to PCIe 2.0 for the additional slots.
- `ctx_7ae3e3659cd76b766f2747b3`: For instance AMD's Threadripper 3 has 64 PCIe 4.0 lanes, each of which is capable 16 Gbit/s data transfer in both directions.
- `ctx_62bef5528a5385c4c8a8ab6a`: * Lastly, the massive increase in bandwidth has forced computer designers to attach SSDs directly to the PCIe bus.

### Backup contexts

- `ctx_67e4805a6cc4da88af5a0fa4`: The drives capable of handling this, referred to as NVMe (Non Volatile Memory enhanced), can use up to 4 PCIe lanes.
- `ctx_e7143839c5cd7a24ea737b53`: * Durable storage, such as a magnetic hard disk drive, a solid state drive, in many cases connected using the PCIe bus.
- `ctx_678990229efc17731a44c47b`: This amounts to up to 8GB/s on PCIe 4.0.

### Contrastive contexts

- `ctxx_4f964651e54483165da09758`: Synthetic: PCIe was printed on the slide as an example acronym, without referring to the hardware interconnect standard.

### Definition evidence

- `ctx_bc0b95f28a464a117086fd7d`: * A high speed expansion bus (PCIe) to connect the system to one or more GPUs.
- `ctx_eb05e20b7827c8e88746abb2`: As :numref:`fig_mobo-symbol` indicates, most components (network, GPU, and storage) are connected to the CPU across the PCIe bus.
- `ctx_67e4805a6cc4da88af5a0fa4`: The drives capable of handling this, referred to as NVMe (Non Volatile Memory enhanced), can use up to 4 PCIe lanes.

### Part-of-speech evidence

- `ctx_bc0b95f28a464a117086fd7d`: * A high speed expansion bus (PCIe) to connect the system to one or more GPUs.
- `ctx_7ae3e3659cd76b766f2747b3`: For instance AMD's Threadripper 3 has 64 PCIe 4.0 lanes, each of which is capable 16 Gbit/s data transfer in both directions.

## 6. population

- `sense_id`: `d2lce_b0fd0234a2a3049734e8011c`
- Split: `test`
- Model definition: the entire set of individuals, items, or data points from which samples or training data are drawn
- Model POS: `noun`

### Primary contexts

- `ctx_1db659b4a818a285e5f8298b`: The sample is drawn from a *population*, denotes the total set of similar individuals, items, or events of our experiment interests.
- `ctx_b2d863a949f46400d0a77de1`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.
- `ctx_af2c71ffd6f18dbe3bbd7f68`: Given the world population of humans the probability is virtually 0.
- `ctx_004cf67c0773c334bdf33ee0`: To recapitulate more formally, our goal is to discover patterns that capture regularities in the underlying population from which our training set was drawn.
- `ctx_106d744b93d4b2d0472f0c4f`: The *empirical risk* is an average loss over the training data to approximate the *risk*, which is the expectation of the loss over the entire population of data drawn from their true distribution $p(\mathbf{x},y)$:

### Backup contexts

- `ctx_3e80e5eac46165ae80b271a0`: Imagine, for example, if we try to train a face recognition system by training it exclusively on university students and then want to deploy it as a tool for monitoring geriatrics in a nursing home population.
- `ctx_6df8135b377047f7113ec544`: Assume that the population is quite healthy, e.g., $P(H=1) = 0.0015$.

### Contrastive contexts

- `ctxx_30dcd83ef77f45fbc9c6ba87`: Synthetic: In the sampler, population means the list of candidate indices rather than the full statistical population under study.

### Definition evidence

- `ctx_1db659b4a818a285e5f8298b`: The sample is drawn from a *population*, denotes the total set of similar individuals, items, or events of our experiment interests.
- `ctx_b2d863a949f46400d0a77de1`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.
- `ctx_004cf67c0773c334bdf33ee0`: To recapitulate more formally, our goal is to discover patterns that capture regularities in the underlying population from which our training set was drawn.

### Part-of-speech evidence

- `ctx_1db659b4a818a285e5f8298b`: The sample is drawn from a *population*, denotes the total set of similar individuals, items, or events of our experiment interests.
- `ctx_b2d863a949f46400d0a77de1`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.

## 7. risk

- `sense_id`: `d2lce_c9e2beab505998c5b3b560b5`
- Split: `test`
- Model definition: possible harm, error, or expected loss associated with an uncertain outcome or model performance
- Model POS: `noun`

- Source package gap (not reviewable): `definition: ctx_157199781ed5147360a98494`

### Primary contexts

- `ctx_a548badbf36a46c4f9452839`: For example, if we were training a model to predict the risk that a loan defaults, we might associate each applicant with a vector whose components correspond to their income, length of employment, number of previous defaults, and other factors.
- `ctx_7cbe29eaa7c1116fd7a5e733`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.
- `ctx_09d73755e2ce9336c387813d`: Thus, we need to compute the expected risk that we incur as the loss function, i.e., we need to multiply the probability of the outcome with the benefit (or harm) associated with it.
- `ctx_2c2639ba429795d2935fc5d5`: When we train high-capacity models we run the risk of overfitting.
- `ctx_a99932a01269042b25d04a4b`: The second one has a much larger degree of fluctuation, and thus represents a much larger risk.

### Backup contexts

- `ctx_f4a2c74c968df044ff098382`: In sensitive applications of machine learning, like predictive policing, resume screening, and risk models used for lending, we must be especially alert to the consequences of garbage data.
- `ctx_2fc169f6489bcc78299b417f`: In other words, the effect of the uncertain risk outweighs the benefit by far.
- `ctx_399193474e26307c198edb25`: We risk losing information in the cropped out portions.

### Contrastive contexts

- `ctxx_97deae5f12df8dd84a8318fa`: Synthetic: In finance, the risk of default was estimated before approving the loan.

### Definition evidence

- `ctx_7cbe29eaa7c1116fd7a5e733`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.
- `ctx_09d73755e2ce9336c387813d`: Thus, we need to compute the expected risk that we incur as the loss function, i.e., we need to multiply the probability of the outcome with the benefit (or harm) associated with it.

### Part-of-speech evidence

- `ctx_399193474e26307c198edb25`: We risk losing information in the cropped out portions.
- `ctx_2c2639ba429795d2935fc5d5`: When we train high-capacity models we run the risk of overfitting.
- `ctx_7cbe29eaa7c1116fd7a5e733`: As described in :numref:`subsec_empirical-risk-and-risk`, the empirical risk is an average loss on the training dataset while the risk is the expected loss on the entire population of data.

## 8. RNN encoder-decoder

- `sense_id`: `d2lce_43488a3e1f15598ac9b1b6bc`
- Split: `test`
- Model definition: An RNN-based sequence-to-sequence model composed of an encoder and a decoder.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_b827a98a327b101be2d2365a`: Now we can [**create and train an RNN encoder-decoder model**] for sequence to sequence learning on the machine translation dataset.
- `ctx_349b7a6daf79dfdfbe18c705`: ![Layers in an RNN encoder-decoder model.](../img/seq2seq-details.svg) :label:`fig_seq2seq_details`
- `ctx_730d49c45382c426ab34a6d9`: When describing Bahdanau attention for the RNN encoder-decoder below, we will follow the same notation in :numref:`sec_seq2seq`.
- `ctx_048676a8e033f03b9ca75239`: To summarize, the layers in the above RNN encoder-decoder model are illustrated in :numref:`fig_seq2seq_details`.
- `ctx_0858d2ceaa592e5540d8e056`: Slightly different from the vanilla RNN encoder-decoder architecture in :numref:`fig_seq2seq_details`, the same architecture with Bahdanau attention is depicted in :numref:`fig_s2s_attention_details`.

### Backup contexts

- `ctx_6c8b329324bfcbe371ac4b63`: In the end, we use the trained RNN encoder-decoder to [**translate a few English sentences into French**] and compute the BLEU of the results.
- `ctx_1ce3513d343c75746b293253`: ![Layers in an RNN encoder-decoder model with Bahdanau attention.](../img/seq2seq-attention-details.svg) :label:`fig_s2s_attention_details`
- `ctx_747765494dea2a90d593a3e5`: ![Predicting the output sequence token by token using an RNN encoder-decoder.](../img/seq2seq-predict.svg) :label:`fig_seq2seq_predict`

### Contrastive contexts

- `ctxx_944c2526011bbb07ca24e8c2`: Synthetic: The encoder-decoder for JPEG compression is not an RNN encoder-decoder.

### Definition evidence

- `ctx_048676a8e033f03b9ca75239`: To summarize, the layers in the above RNN encoder-decoder model are illustrated in :numref:`fig_seq2seq_details`.
- `ctx_b827a98a327b101be2d2365a`: Now we can [**create and train an RNN encoder-decoder model**] for sequence to sequence learning on the machine translation dataset.
- `ctx_0858d2ceaa592e5540d8e056`: Slightly different from the vanilla RNN encoder-decoder architecture in :numref:`fig_seq2seq_details`, the same architecture with Bahdanau attention is depicted in :numref:`fig_s2s_attention_details`.

### Part-of-speech evidence

- `ctx_048676a8e033f03b9ca75239`: To summarize, the layers in the above RNN encoder-decoder model are illustrated in :numref:`fig_seq2seq_details`.
- `ctx_b827a98a327b101be2d2365a`: Now we can [**create and train an RNN encoder-decoder model**] for sequence to sequence learning on the machine translation dataset.

## 9. semantic segmentation

- `sense_id`: `d2lce_2e41378b04489016bfe5707a`
- Split: `test`
- Model definition: the computer vision task of assigning semantic class labels to image regions or pixels
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c82ca11246013bc71c70683e`: This section will discuss the problem of *semantic segmentation*, which focuses on how to divide an image into regions belonging to different semantic classes.
- `ctx_f544543d23373dd72d348b73`: Compared with in object detection, the pixel-level borders labeled in semantic segmentation are obviously more fine-grained.
- `ctx_172790809649156a7e055295`: CNN-based architectures are now ubiquitous in the field of computer vision, and have become so dominant that hardly anyone today would develop a commercial application or enter a competition related to image recognition, object detection, or semantic segmentation, without building off of this approach.
- `ctx_37f65cfdd3725f0a5fd41ed1`: # Semantic Segmentation and the Dataset :label:`sec_semantic_segmentation`
- `ctx_881a115cc0a3059593925a60`: Next, we will show how to use *fully convolutional networks* for semantic segmentation of images.

### Backup contexts

- `ctx_9cde2630c518ac4fbc4f9a3d`: Since deep neural networks can effectively represent images in multiple levels, such layerwise representations have been successfully used in various computer vision tasks such as *object detection*, *semantic segmentation*, and *style transfer*.
- `ctx_a8b86db91ddc0d9b0d2daffc`: Different from object detection, semantic segmentation recognizes and understands what are in images in pixel level: its labeling and prediction of semantic regions are in pixel level.
- `ctx_c6574094eae517b78bf15473`: :numref:`fig_segmentation` shows the labels of the dog, cat, and background of the image in semantic segmentation.

### Contrastive contexts

- `ctxx_cc7978a4612a2c6dc79d01d2`: Synthetic: Semantic segmentation labels every pixel, whereas object detection only draws boxes around objects.

### Definition evidence

- `ctx_a8b86db91ddc0d9b0d2daffc`: Different from object detection, semantic segmentation recognizes and understands what are in images in pixel level: its labeling and prediction of semantic regions are in pixel level.
- `ctx_c82ca11246013bc71c70683e`: This section will discuss the problem of *semantic segmentation*, which focuses on how to divide an image into regions belonging to different semantic classes.
- `ctx_f544543d23373dd72d348b73`: Compared with in object detection, the pixel-level borders labeled in semantic segmentation are obviously more fine-grained.

### Part-of-speech evidence

- `ctx_37f65cfdd3725f0a5fd41ed1`: # Semantic Segmentation and the Dataset :label:`sec_semantic_segmentation`
- `ctx_881a115cc0a3059593925a60`: Next, we will show how to use *fully convolutional networks* for semantic segmentation of images.
- `ctx_c82ca11246013bc71c70683e`: This section will discuss the problem of *semantic segmentation*, which focuses on how to divide an image into regions belonging to different semantic classes.

## 10. SSDs

- `sense_id`: `d2lce_355f5686f2178281893eb6cb`
- Split: `test`
- Model definition: solid state drives; persistent storage devices based on flash memory
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_571553d886295f4729859f52`: Solid state drives (SSDs) use flash memory to store information persistently.
- `ctx_f9902516e49104afd3afe24a`: Modern SSDs can operate at 100,000 to 500,000 IOPs, i.e., up to 3 orders of magnitude faster than HDDs.
- `ctx_3f1cc59dfa423c8dcd335761`: * SSDs store information in blocks (256 KB or larger).
- `ctx_705c90ebb1cd32c03359a437`: * The memory cells in SSDs wear out relatively quickly (often already after a few thousand writes).
- `ctx_aeabd68e0656c4863b7b2e43`: Indeed, they come with the following caveats, due to the way SSDs are designed.

### Backup contexts

- `ctx_bfd113ac65a2d763da1c337d`: Nonetheless, writes can be much slower, in particular for QLC (quad level cell) SSDs.
- `ctx_cd56410dc228003d2dde79bc`: * Lastly, the massive increase in bandwidth has forced computer designers to attach SSDs directly to the PCIe bus.
- `ctx_f6224c38623494a8a418203b`: That said, it is not recommended to use SSDs for swapping files or for large aggregations of log-files.

### Contrastive contexts

- `ctxx_e83cbf8b4ab05bffd72e091c`: Synthetic: In a different document, SSDs could name a software subsystem, not storage drives.

### Definition evidence

- `ctx_571553d886295f4729859f52`: Solid state drives (SSDs) use flash memory to store information persistently.

### Part-of-speech evidence

- `ctx_571553d886295f4729859f52`: Solid state drives (SSDs) use flash memory to store information persistently.
- `ctx_f9902516e49104afd3afe24a`: Modern SSDs can operate at 100,000 to 500,000 IOPs, i.e., up to 3 orders of magnitude faster than HDDs.
