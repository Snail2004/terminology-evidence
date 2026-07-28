# Stage A sense casebook: development_004

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. Generator

- `sense_id`: `d2lce_73c8ce2915c4c64a52fab4a2`
- Split: `development`
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

- `ctx_5b966a1024783f92c10a4b61`: (index 0 is the # excluded unknown token) in the vocabulary sampling_weights = [counter[vocab.to_tokens(i)]**0.75 for i in range(1, len(vocab))] all_negatives, generator = [], RandomGenerator(sampling_weights) for contexts in all_contexts: negatives = [] while len(negatives) < len(contexts) * K: neg = generator.draw() # Noise words cannot be context words if neg not in contexts: negatives.append(neg) all_negatives.append(negatives) return all_negatives all_negatives = get_negatives(all_contexts, vocab, counter, 5) ```

### Definition evidence

- `ctx_ce5770ebbcecab9cd14b31d1`: At their heart, GANs rely on the idea that a data generator is good if we cannot tell fake data apart from real data.
- `ctx_111ebd3664347c4b99a35b2e`: We call this the generator network.
- `ctx_545710fbceae0d3428fd3a00`: The discriminator is a binary classifier to distinguish if the input $x$ is real (from real data) or fake (from the generator).

### Part-of-speech evidence

- `ctx_111ebd3664347c4b99a35b2e`: We call this the generator network.
- `ctx_33e923407e067945b2c17e33`: The generator network attempts to fool the discriminator network.

## 2. Gradient Clipping

- `sense_id`: `d2lce_8d226b48ba7ec1493faa4ec8`
- Split: `development`
- Model definition: A training technique that limits gradient size to prevent exploding gradients and improve stable convergence.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_5f804b816c9a3019d5cd256d`: ## [**Gradient Clipping**]
- `ctx_a47529e99ab8712183c51ba6`: Although we have applied implementation tricks such as gradient clipping, this issue can be alleviated further with more sophisticated designs of sequence models.
- `ctx_76aaadbd846db473944f5737`: * Gradient clipping prevents gradient explosion, but it cannot fix vanishing gradients.
- `ctx_44fd28002fe36b13e2dc8adf`: Gradient clipping provides a quick fix to the gradient exploding.
- `ctx_4464d445a080f2a1433e80df`: In particular, if you solved the exercises, you would have seen that gradient clipping is vital to ensure proper convergence.

### Backup contexts

- `ctx_e70f2e4fd3f749f374288b7a`: Besides gradient clipping, can you think of any other methods to cope with gradient explosion in recurrent neural networks?
- `ctx_68f2a29f1bb704c9ddabeaf1`: Again, we encountered them before, e.g., when dealing with gradient clipping in :numref:`sec_rnn_scratch`.
- `ctx_58e268b908c3d7ae474df7c8`: Do we still need gradient clipping?

### Contrastive contexts

- `ctxx_96e9ef1273e4b1bb986dd43e`: [Synthetic] The designer used Gradient Clipping to crop the color ramp at both ends of the poster.

### Definition evidence

- `ctx_44fd28002fe36b13e2dc8adf`: Gradient clipping provides a quick fix to the gradient exploding.
- `ctx_76aaadbd846db473944f5737`: * Gradient clipping prevents gradient explosion, but it cannot fix vanishing gradients.
- `ctx_4464d445a080f2a1433e80df`: In particular, if you solved the exercises, you would have seen that gradient clipping is vital to ensure proper convergence.

### Part-of-speech evidence

- `ctx_5f804b816c9a3019d5cd256d`: ## [**Gradient Clipping**]
- `ctx_a47529e99ab8712183c51ba6`: Although we have applied implementation tricks such as gradient clipping, this issue can be alleviated further with more sophisticated designs of sequence models.

## 3. hidden layer

- `sense_id`: `d2lce_401e038a0835f7c5733a9857`
- Split: `development`
- Model definition: an internal neural network layer between input and output layers where hidden units compute intermediate representations
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_3d2a354dd3b2ef13260bccd4`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_cc2d203b8ac0da03a68a1c0d`: However, while we might be able to get away with one hundred thousand pixels, our hidden layer of size 1000 grossly underestimates the number of hidden units that it takes to learn good representations of images, so a practical system will still require billions of parameters.
- `ctx_76cea9317d218e58cde5ce34`: Recall that we have discussed hidden layers with hidden units in :numref:`chap_perceptrons`.
- `ctx_8ed3baee31960a19edc33212`: ## Hidden Layers
- `ctx_7758e78a8a47d48b3d911192`: Consider a simple MLP with a single hidden layer of, say, $d$ dimensions in the hidden layer and a single output.

### Backup contexts

- `ctx_16722c9212846d6101148dbf`: AlexNet consists of eight layers: five convolutional layers, two fully-connected hidden layers, and one fully-connected output layer.
- `ctx_49bbc63fc9e139f356412fba`: We will describe deep architectures with multiple hidden layers, and discuss the bidirectional design with both forward and backward recurrent computations.
- `ctx_a137b3c09b9f9c51930d5371`: Equivalent to :eqref:`eq_additive-attn`, the query and the key are concatenated and fed into an MLP with a single hidden layer whose number of hidden units is $h$, a hyperparameter.

### Contrastive contexts

- `ctxx_1f75e4a4cb4f1038d9a59945`: Synthetic: The hidden layer transforms inputs into intermediate features before the output layer produces predictions.

### Definition evidence

- `ctx_3d2a354dd3b2ef13260bccd4`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).
- `ctx_cc2d203b8ac0da03a68a1c0d`: However, while we might be able to get away with one hundred thousand pixels, our hidden layer of size 1000 grossly underestimates the number of hidden units that it takes to learn good representations of images, so a practical system will still require billions of parameters.
- `ctx_76cea9317d218e58cde5ce34`: Recall that we have discussed hidden layers with hidden units in :numref:`chap_perceptrons`.
- `ctx_7758e78a8a47d48b3d911192`: Consider a simple MLP with a single hidden layer of, say, $d$ dimensions in the hidden layer and a single output.

### Part-of-speech evidence

- `ctx_8ed3baee31960a19edc33212`: ## Hidden Layers
- `ctx_3d2a354dd3b2ef13260bccd4`: The following code generates a network with one fully-connected hidden layer with 256 units and ReLU activation, followed by a fully-connected output layer with 10 units (no activation function).

## 4. hypothesis

- `sense_id`: `d2lce_dbb300a90e4b0f8b815b5e12`
- Split: `development`
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

### Definition evidence

- `ctx_73c90581e009fa46017ce4ac`: *Natural language inference* studies whether a *hypothesis* can be inferred from a *premise*, where both are a text sequence.
- `ctx_39675d05889cacc1f1ffdf06`: * *Contradiction*: the negation of the hypothesis can be inferred from the premise.
- `ctx_48e44a2af0f53ee5fa7c2a13`: * *Entailment*: the hypothesis can be inferred from the premise.

### Part-of-speech evidence

- `ctx_73c90581e009fa46017ce4ac`: *Natural language inference* studies whether a *hypothesis* can be inferred from a *premise*, where both are a text sequence.
- `ctx_368170831130d1827fe9f440`: > Hypothesis: Two women are showing affection.
- `ctx_22622fdadf6bcfc02e71f0bc`: > Hypothesis: The man is sleeping.

## 5. in place

- `sense_id`: `d2lce_2684090fd4500122fec2a334`
- Split: `development`
- Model definition: done directly on the existing object, memory, or arrangement rather than creating a separate replacement; by extension, already established or set up.
- Model POS: `adverb`

### Primary contexts

- `ctx_f813489a437efb8e7e42d969`: If we do not update in place, other references will still point to the old memory location, making it possible for parts of our code to inadvertently reference stale parameters.
- `ctx_3b646f556dedb3e0fad436ed`: Now that we have all of the parts in place, we are ready to [**implement the main training loop.**] It is crucial that you understand this code because you will see nearly identical training loops over and over again throughout your career in deep learning.
- `ctx_3d152d0258e0fc757b4f6fc6`: :begin_tab:`mxnet, pytorch` Fortunately, (**performing in-place operations**) is easy.
- `ctx_51b702393d86c10055ec9803`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import np, npx npx.set_np() def init_adadelta_states(feature_dim): s_w, s_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1) delta_w, delta_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1) return ((s_w, delta_w), (s_b, delta_b)) def adadelta(params, states, hyperparams): rho, eps = hyperparams['rho'], 1e-5 for p, (s, delta) in zip(params, states): # In-place updates via [:] s[:] = rho * s + (1 - rho) * np.square(p.grad) g = (np.sqrt(delta + eps) / np.sqrt(s + eps)) * p.grad p[:] -= g delta[:] = rho * delta + (1 - rho) * g * g ```
- `ctx_537ed43953ead18faf55b24e`: Also note that some functions are not supported in the `symbol` module (e.g., `asnumpy`) and operations in-place such as `a += b` and `a[:] = a + b` must be rewritten as `a = a + b`.

### Backup contexts

- `ctx_dd4385b29dac92b049208df2`: Typically, we will want to perform these updates *in place*.
- `ctx_25b94844ba885d1f978af59d`: In general, with activation functions in place, it is no longer possible to collapse our MLP into a linear model:
- `ctx_b28630d61d9d7f640c9a5483`: Moreover, current purchase habits are often a result of the recommendation algorithm currently in place, but learning algorithms do not always take this detail into account.

### Contrastive contexts

- `ctxx_0f47be35d8fd527a99998a48`: Synthetic: The statue remained in place during the storm.

### Definition evidence

- `ctx_dd4385b29dac92b049208df2`: Typically, we will want to perform these updates *in place*.
- `ctx_51b702393d86c10055ec9803`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import np, npx npx.set_np() def init_adadelta_states(feature_dim): s_w, s_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1) delta_w, delta_b = d2l.zeros((feature_dim, 1)), d2l.zeros(1) return ((s_w, delta_w), (s_b, delta_b)) def adadelta(params, states, hyperparams): rho, eps = hyperparams['rho'], 1e-5 for p, (s, delta) in zip(params, states): # In-place updates via [:] s[:] = rho * s + (1 - rho) * np.square(p.grad) g = (np.sqrt(delta + eps) / np.sqrt(s + eps)) * p.grad p[:] -= g delta[:] = rho * delta + (1 - rho) * g * g ```
- `ctx_f813489a437efb8e7e42d969`: If we do not update in place, other references will still point to the old memory location, making it possible for parts of our code to inadvertently reference stale parameters.
- `ctx_b28630d61d9d7f640c9a5483`: Moreover, current purchase habits are often a result of the recommendation algorithm currently in place, but learning algorithms do not always take this detail into account.

### Part-of-speech evidence

- `ctx_dd4385b29dac92b049208df2`: Typically, we will want to perform these updates *in place*.
- `ctx_3d152d0258e0fc757b4f6fc6`: :begin_tab:`mxnet, pytorch` Fortunately, (**performing in-place operations**) is easy.
- `ctx_b28630d61d9d7f640c9a5483`: Moreover, current purchase habits are often a result of the recommendation algorithm currently in place, but learning algorithms do not always take this detail into account.

## 6. Initialization

- `sense_id`: `d2lce_8373decbb6e405f0386ec8a0`
- Split: `development`
- Model definition: the act or method of setting initial values or initial state before computation or training
- Model POS: `noun`

### Primary contexts

- `ctx_bf60034bed8fac717862447e`: We will also discuss issues relating to numerical stability and parameter initialization that are key to successfully training deep networks.
- `ctx_6c651c750bd61ecf09196999`: This module provides various methods for model parameter initialization.
- `ctx_d4f8f201e33ddd0184655f6b`: # This function initializes the convolutional layer weights and performs # corresponding dimensionality elevations and reductions on the input and # output def comp_conv2d(conv2d, X): conv2d.initialize() # Here (1, 1) indicates that the batch size and the number of channels # are both 1 X = X.reshape((1, 1) + X.shape) Y = conv2d(X) # Exclude the first two dimensions that do not interest us: examples and # channels return Y.reshape(Y.shape[2:]) # Note that here 1 row or column is padded on either side, so a total of 2 # rows or columns are added conv2d = nn.Conv2D(1, kernel_size=3, padding=1) X = np.random.uniform(size=(8, 8)) comp_conv2d(conv2d, X).shape ```
- `ctx_08a00e100653d14a0ddf6485`: Good initialization of the parameters can be beneficial, too.
- `ctx_1bc308a263836f4fc041f231`: In this chapter, we will peel back the curtain, digging deeper into the key components of deep learning computation, namely model construction, parameter access and initialization, designing custom layers and blocks, reading and writing models to disk, and leveraging GPUs to achieve dramatic speedups.

### Backup contexts

- `ctx_cdcb81a3ee9a5abda1a9e0ce`: Added to these obstacles, key tricks for training neural networks including parameter initialization heuristics, clever variants of stochastic gradient descent, non-squashing activation functions, and effective regularization techniques were still missing.
- `ctx_ee12194666632f9d5902d342`: Now we will define [**the hidden state initialization function**] `init_gru_state`.
- `ctx_e826a9c4223fe2ac0df99dd6`: To define an RNN model, we first need [**an `init_rnn_state` function to return the hidden state at initialization.**] It returns a tensor filled with 0 and with a shape of (batch size, number of hidden units).

### Contrastive contexts

- `ctxx_520127f2d04dc6eac949f60b`: Synthetic: During software setup, initialization only created a default configuration file and no model parameters.

### Definition evidence

- `ctx_6c651c750bd61ecf09196999`: This module provides various methods for model parameter initialization.
- `ctx_bf60034bed8fac717862447e`: We will also discuss issues relating to numerical stability and parameter initialization that are key to successfully training deep networks.
- `ctx_1bc308a263836f4fc041f231`: In this chapter, we will peel back the curtain, digging deeper into the key components of deep learning computation, namely model construction, parameter access and initialization, designing custom layers and blocks, reading and writing models to disk, and leveraging GPUs to achieve dramatic speedups.
- `ctx_d4f8f201e33ddd0184655f6b`: # This function initializes the convolutional layer weights and performs # corresponding dimensionality elevations and reductions on the input and # output def comp_conv2d(conv2d, X): conv2d.initialize() # Here (1, 1) indicates that the batch size and the number of channels # are both 1 X = X.reshape((1, 1) + X.shape) Y = conv2d(X) # Exclude the first two dimensions that do not interest us: examples and # channels return Y.reshape(Y.shape[2:]) # Note that here 1 row or column is padded on either side, so a total of 2 # rows or columns are added conv2d = nn.Conv2D(1, kernel_size=3, padding=1) X = np.random.uniform(size=(8, 8)) comp_conv2d(conv2d, X).shape ```
- `ctx_cdcb81a3ee9a5abda1a9e0ce`: Added to these obstacles, key tricks for training neural networks including parameter initialization heuristics, clever variants of stochastic gradient descent, non-squashing activation functions, and effective regularization techniques were still missing.
- `ctx_e826a9c4223fe2ac0df99dd6`: To define an RNN model, we first need [**an `init_rnn_state` function to return the hidden state at initialization.**] It returns a tensor filled with 0 and with a shape of (batch size, number of hidden units).
- `ctx_ee12194666632f9d5902d342`: Now we will define [**the hidden state initialization function**] `init_gru_state`.
- `ctx_08a00e100653d14a0ddf6485`: Good initialization of the parameters can be beneficial, too.

### Part-of-speech evidence

- `ctx_6c651c750bd61ecf09196999`: This module provides various methods for model parameter initialization.
- `ctx_bf60034bed8fac717862447e`: We will also discuss issues relating to numerical stability and parameter initialization that are key to successfully training deep networks.
- `ctx_1bc308a263836f4fc041f231`: In this chapter, we will peel back the curtain, digging deeper into the key components of deep learning computation, namely model construction, parameter access and initialization, designing custom layers and blocks, reading and writing models to disk, and leveraging GPUs to achieve dramatic speedups.

## 7. input gate

- `sense_id`: `d2lce_c6c1c6e96c39b88a9f94e8d9`
- Split: `development`
- Model definition: the LSTM gate that controls how much new input information enters the memory cell
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_ef08148c1866b77ae7d4ed7f`: We refer to this as the *input gate*.
- `ctx_55d21390aec0ff7a7336858a`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.
- `ctx_6a19e08d950ca7bef8fb4c89`: ### Input Gate, Forget Gate, and Output Gate
- `ctx_9ee60265b7c99b18fa9a46f2`: ![Computing the input gate, the forget gate, and the output gate in an LSTM model.](../img/lstm-0.svg) :label:`lstm_0`
- `ctx_6c0d6d0d558005aaf9be6fc3`: If the forget gate is always approximately 1 and the input gate is always approximately 0, the past memory cells $\mathbf{C}_{t-1}$ will be saved over time and passed to the current time step.

### Backup contexts

- `ctx_a7c81a70b68bbf602ecfbeab`: Similarly, in LSTMs we have two dedicated gates for such purposes: the input gate $\mathbf{I}_t$ governs how much we take new data into account via $\tilde{\mathbf{C}}_t$ and the forget gate $\mathbf{F}_t$ addresses how much of the old memory cell content $\mathbf{C}_{t-1} \in \mathbb{R}^{n \times h}$ we retain.
- `ctx_b2ecc4429423fc36a19369d3`: ```{.python .input} def get_lstm_params(vocab_size, num_hiddens, device): num_inputs = num_outputs = vocab_size def normal(shape): return np.random.normal(scale=0.01, size=shape, ctx=device) def three(): return (normal((num_inputs, num_hiddens)), normal((num_hiddens, num_hiddens)), np.zeros(num_hiddens, ctx=device)) W_xi, W_hi, b_i = three() # Input gate parameters W_xf, W_hf, b_f = three() # Forget gate parameters W_xo, W_ho, b_o = three() # Output gate parameters W_xc, W_hc, b_c = three() # Candidate memory cell parameters # Output layer parameters W_hq = normal((num_hiddens, num_outputs)) b_q = np.zeros(num_outputs, ctx=device) # Attach gradients params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc, b_c, W_hq, b_q] for param in params: param.attach_grad() return params ```
- `ctx_d97ae77a3b700998ac63cadd`: ```{.python .input} #@tab pytorch def get_lstm_params(vocab_size, num_hiddens, device): num_inputs = num_outputs = vocab_size def normal(shape): return torch.randn(size=shape, device=device)*0.01 def three(): return (normal((num_inputs, num_hiddens)), normal((num_hiddens, num_hiddens)), d2l.zeros(num_hiddens, device=device)) W_xi, W_hi, b_i = three() # Input gate parameters W_xf, W_hf, b_f = three() # Forget gate parameters W_xo, W_ho, b_o = three() # Output gate parameters W_xc, W_hc, b_c = three() # Candidate memory cell parameters # Output layer parameters W_hq = normal((num_hiddens, num_outputs)) b_q = d2l.zeros(num_outputs, device=device) # Attach gradients params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc, b_c, W_hq, b_q] for param in params: param.requires_grad_(True) return params ```

### Contrastive contexts

- `ctxx_3e2772e947e6f76d5a66533c`: Synthetic: Visitors should wait at the input gate before entering the stadium.

### Definition evidence

- `ctx_ef08148c1866b77ae7d4ed7f`: We refer to this as the *input gate*.
- `ctx_55d21390aec0ff7a7336858a`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.
- `ctx_a7c81a70b68bbf602ecfbeab`: Similarly, in LSTMs we have two dedicated gates for such purposes: the input gate $\mathbf{I}_t$ governs how much we take new data into account via $\tilde{\mathbf{C}}_t$ and the forget gate $\mathbf{F}_t$ addresses how much of the old memory cell content $\mathbf{C}_{t-1} \in \mathbb{R}^{n \times h}$ we retain.
- `ctx_6c0d6d0d558005aaf9be6fc3`: If the forget gate is always approximately 1 and the input gate is always approximately 0, the past memory cells $\mathbf{C}_{t-1}$ will be saved over time and passed to the current time step.

### Part-of-speech evidence

- `ctx_ef08148c1866b77ae7d4ed7f`: We refer to this as the *input gate*.
- `ctx_6a19e08d950ca7bef8fb4c89`: ### Input Gate, Forget Gate, and Output Gate
- `ctx_55d21390aec0ff7a7336858a`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.

## 8. integration

- `sense_id`: `d2lce_9372cdb5752db6ba6fa38fbd`
- Split: `development`
- Model definition: the branch or operation of calculus concerned with accumulation, such as area under a curve
- Model POS: `noun`

### Primary contexts

- `ctx_970ad81dffba31509dfed788`: The other pillar, integration, starts out seeming a rather disjoint question, "What is the area underneath this curve?" While seemingly unrelated, integration is tightly intertwined with the differentiation via what is known as the *fundamental theorem of calculus*.
- `ctx_11630da8af693e077d8637e6`: This will be the basis for our study of integration.
- `ctx_0720de93acc3b5ddc9c08fc8`: In this way, we can develop the entire theory of integration leveraging ideas from differential calculus freely.
- `ctx_2d9c07e4c64cbce4f4a725e5`: To dive deeper into the theory of integration, let us introduce a function
- `ctx_6cb98f8df6d9db9e167c2f2f`: At the level of machine learning we discuss in this book, we will not need a deep understanding of integration.

### Backup contexts

- `ctx_1be847f50e09bfac7f900b8d`: This is a fact-of-life in the theory of integration.

### Contrastive contexts

- `ctxx_bc8b410c1463f2d7f41002e4`: The team set up continuous integration, but no one computed an integration over a curve.

### Definition evidence

- `ctx_970ad81dffba31509dfed788`: The other pillar, integration, starts out seeming a rather disjoint question, "What is the area underneath this curve?" While seemingly unrelated, integration is tightly intertwined with the differentiation via what is known as the *fundamental theorem of calculus*.
- `ctx_6cb98f8df6d9db9e167c2f2f`: At the level of machine learning we discuss in this book, we will not need a deep understanding of integration.
- `ctx_11630da8af693e077d8637e6`: This will be the basis for our study of integration.

### Part-of-speech evidence

- `ctx_970ad81dffba31509dfed788`: The other pillar, integration, starts out seeming a rather disjoint question, "What is the area underneath this curve?" While seemingly unrelated, integration is tightly intertwined with the differentiation via what is known as the *fundamental theorem of calculus*.
- `ctx_0720de93acc3b5ddc9c08fc8`: In this way, we can develop the entire theory of integration leveraging ideas from differential calculus freely.

## 9. iteration

- `sense_id`: `d2lce_c3c46748b1a49e32c07ca9d7`
- Split: `development`
- Model definition: one repeated step or cycle in an algorithm, training process, or numerical procedure
- Model POS: `noun`

### Primary contexts

- `ctx_cff5672d4e8d42484c26fd68`: Assuming that the learning rate in the Trainer instance is η, we set the learning rate of the model parameters in the member variable output to be 10η in the iteration.
- `ctx_e05b549ae3fe27be9cac0d99`: After the last epoch iteration has been completed, the training loss is still high.
- `ctx_05c2a4c1509fd139937710c2`: (**In random sampling, each example is a subsequence arbitrarily captured on the original long sequence.**) The subsequences from two adjacent random minibatches during iteration are not necessarily adjacent on the original sequence.
- `ctx_3300f63f7d694e08f6eab024`: * In any iteration of training, given a random minibatch, we split the examples in the batch into $k$ portions and distribute them evenly across the GPUs.
- `ctx_42da1c5cbf75c04eb158271d`: In each iteration, we first randomly sample a minibatch $\mathcal{B}$ consisting of a fixed number of training examples.

### Backup contexts

- `ctx_490d42eed993591209b3f212`: When the numerical solution of an optimization problem is near the local optimum, the numerical solution obtained by the final iteration may only minimize the objective function *locally*, rather than *globally*, as the gradient of the objective function's solutions approaches or becomes zero.
- `ctx_92458627d052b6a13dbc26f4`: Next, in each iteration, we will use the squared error to compare `Y` with the output of the convolutional layer.
- `ctx_ccb879141ca0cea21709bd26`: Training can take hundreds of epochs, and each iteration requires passing data through many layers of computationally-expensive linear algebra operations.

### Contrastive contexts

- `ctxx_06a7da0c75c379c01a9a2f95`: Synthetic: In literary editing, the second iteration of the poem changed its tone.

### Definition evidence

- `ctx_42da1c5cbf75c04eb158271d`: In each iteration, we first randomly sample a minibatch $\mathcal{B}$ consisting of a fixed number of training examples.
- `ctx_92458627d052b6a13dbc26f4`: Next, in each iteration, we will use the squared error to compare `Y` with the output of the convolutional layer.
- `ctx_ccb879141ca0cea21709bd26`: Training can take hundreds of epochs, and each iteration requires passing data through many layers of computationally-expensive linear algebra operations.
- `ctx_490d42eed993591209b3f212`: When the numerical solution of an optimization problem is near the local optimum, the numerical solution obtained by the final iteration may only minimize the objective function *locally*, rather than *globally*, as the gradient of the objective function's solutions approaches or becomes zero.

### Part-of-speech evidence

- `ctx_42da1c5cbf75c04eb158271d`: In each iteration, we first randomly sample a minibatch $\mathcal{B}$ consisting of a fixed number of training examples.
- `ctx_92458627d052b6a13dbc26f4`: Next, in each iteration, we will use the squared error to compare `Y` with the output of the convolutional layer.

## 10. Jupyter notebook

- `sense_id`: `d2lce_1a91fdded89249a5cd89ec14`
- Split: `development`
- Model definition: An interactive notebook environment used to write, edit, run, and inspect code and related text or documentation.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_57a080760ad64870f38e1944`: In this chapter, we will walk you through major tools for deep learning, from introducing Jupyter notebook in :numref:`sec_jupyter` to empowering you training models on Cloud such as Amazon SageMaker in :numref:`sec_sagemaker`, Amazon EC2 in :numref:`sec_aws` and Google Colab in :numref:`sec_colab`.
- `ctx_c491125cb400cc10a6b89d1f`: This section describes how to edit and run the code in the chapters of this book using Jupyter Notebooks.
- `ctx_db36af02cb86a821cf97f72d`: ```bash jupyter notebook ```
- `ctx_d28271aea73210f0b70b3d21`: Once you have completed these installation steps, we can the Jupyter notebook server by running:
- `ctx_76220c9bc5e4ee7672fc78b2`: In order to get you up and running for hands-on learning experience, we need to set you up with an environment for running Python, Jupyter notebooks, the relevant libraries, and the code needed to run the book itself.

### Backup contexts

- `ctx_4ce0dadb094ebab58d15ccc9`: * We can look up documentation for the usage of an API by calling the `dir` and `help` functions, or `?` and `??` in Jupyter notebooks.
- `ctx_d2b6cce11380684abd029f58`: In the Jupyter notebook, we can use `?` to display the document in another window.
- `ctx_80bb0597f481e29198ef67ab`: We settled on GitHub to share the source and to facilitate community contributions, Jupyter notebooks for mixing code, equations and text, Sphinx as a rendering engine to generate multiple outputs, and Discourse for the forum.

### Contrastive contexts

- `ctxx_7f072bff8c2c84e16d99964b`: Synthetic: She bought a Jupyter notebook to sketch ideas by hand during class.

### Definition evidence

- `ctx_c491125cb400cc10a6b89d1f`: This section describes how to edit and run the code in the chapters of this book using Jupyter Notebooks.
- `ctx_76220c9bc5e4ee7672fc78b2`: In order to get you up and running for hands-on learning experience, we need to set you up with an environment for running Python, Jupyter notebooks, the relevant libraries, and the code needed to run the book itself.
- `ctx_d2b6cce11380684abd029f58`: In the Jupyter notebook, we can use `?` to display the document in another window.

### Part-of-speech evidence

- `ctx_80bb0597f481e29198ef67ab`: We settled on GitHub to share the source and to facilitate community contributions, Jupyter notebooks for mixing code, equations and text, Sphinx as a rendering engine to generate multiple outputs, and Discourse for the forum.
- `ctx_57a080760ad64870f38e1944`: In this chapter, we will walk you through major tools for deep learning, from introducing Jupyter notebook in :numref:`sec_jupyter` to empowering you training models on Cloud such as Amazon SageMaker in :numref:`sec_sagemaker`, Amazon EC2 in :numref:`sec_aws` and Google Colab in :numref:`sec_colab`.
- `ctx_c491125cb400cc10a6b89d1f`: This section describes how to edit and run the code in the chapters of this book using Jupyter Notebooks.
