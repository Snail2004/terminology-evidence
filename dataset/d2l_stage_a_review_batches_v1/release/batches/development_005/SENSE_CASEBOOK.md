# Stage A sense casebook: development_005

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. keys

- `sense_id`: `d2lce_776fd3328d5e31aeebe484ec`
- Split: `development`
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

### Definition evidence

- `ctx_3c14b0a0feee3453249740d4`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_cac33728aec4217e211eb0da`: In practice, attention pooling aggregates values using weighted average, where weights are computed between the given query and different keys.
- `ctx_9dd2818707ebbd9b97accac9`: Its input `matrices` has the shape (number of rows for display, number of columns for display, number of queries, number of keys).

### Part-of-speech evidence

- `ctx_8a0bb471a0a435399c5293f9`: ## Queries, Keys, and Values
- `ctx_3c14b0a0feee3453249740d4`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).

## 2. Label Shift

- `sense_id`: `d2lce_a5537c415bcbe54cdd82a669`
- Split: `development`
- Model definition: distribution shift where the label distribution changes, typically under the assumption that labels cause the observed features.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_fb69017e7a227340fe43b097`: Label shift is a reasonable assumption to make when we believe that $y$ causes $\mathbf{x}$.
- `ctx_ef837c5a48f145a0fcf4a0e0`: One nice thing about label shift is that if we have a reasonably good model on the source distribution, then we can get consistent estimates of these weights without ever having to deal with the ambient dimension.
- `ctx_251af3f6de41101b4a0f5e27`: ### Label Shift
- `ctx_2d01370b0dfb51002ecac107`: Label shift is the appropriate assumption here because diseases cause symptoms.
- `ctx_e46954f1823711a2d1112200`: *Label shift* describes the converse problem.

### Backup contexts

- `ctx_3eb0a985163fee2ce2dc895b`: ### Label Shift Correction
- `ctx_123ccd1b9cae341c69cfb9a3`: In some degenerate cases the label shift and covariate shift assumptions can hold simultaneously.
- `ctx_bd65044c0d3799c1e578573b`: Interestingly, in these cases, it is often advantageous to work with methods that flow from the label shift assumption.

### Contrastive contexts

- `ctxx_4a59554994576b94331e3dd9`: Synthetic: The package was rejected because of label shift on the sticker, not because of a data distribution issue.

### Definition evidence

- `ctx_fb69017e7a227340fe43b097`: Label shift is a reasonable assumption to make when we believe that $y$ causes $\mathbf{x}$.
- `ctx_2d01370b0dfb51002ecac107`: Label shift is the appropriate assumption here because diseases cause symptoms.
- `ctx_e46954f1823711a2d1112200`: *Label shift* describes the converse problem.

### Part-of-speech evidence

- `ctx_251af3f6de41101b4a0f5e27`: ### Label Shift
- `ctx_3eb0a985163fee2ce2dc895b`: ### Label Shift Correction

## 3. language model

- `sense_id`: `d2lce_a7105fea7b2b3447548b6d7a`
- Split: `development`
- Model definition: a model that estimates or predicts sequences of words or characters in text
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c20a0ec2bc47e48846e7ed5b`: The recurrent neural network language models are one example of using a discriminative network (trained to predict the next character) that once trained can act as a generative model.
- `ctx_0d6ec66184ff5ae327958de1`: Imagine that we are training a language model.
- `ctx_0d8072fac44a71369c278f26`: The character *perplexity* of a language model is defined as the inverse of the geometric mean of a set of probabilities, each probability is corresponding to a character in the word.
- `ctx_33631d6a969125ba846d82b3`: Hence, we will emphasize language models in this chapter.
- `ctx_504a913a4f4a11022e5c30ad`: Next, we discuss basic concepts of a language model and use this discussion as the inspiration for the design of RNNs.

### Backup contexts

- `ctx_79e409e6abf55603a0394035`: In practice, it is very common to use natural language processing techniques to process and analyze text (human natural language) data, such as language models in :numref:`sec_language_model` and machine translation models in :numref:`sec_machine_translation`.
- `ctx_a062cf75c1abb1a0801f30f6`: For instance, in :numref:`chap_rnn`, we have relied on RNNs to design language models to generate novella-like text.
- `ctx_aff4cfc9f37da2ffa5e529e9`: For demonstration, we implemented RNN-based language models on text data.

### Contrastive contexts

- `ctxx_84c1d4c47c3148deef80b20d`: Synthetic: In philosophy, a person's language model of the world may shape how they speak.

### Definition evidence

- `ctx_33631d6a969125ba846d82b3`: Hence, we will emphasize language models in this chapter.
- `ctx_aff4cfc9f37da2ffa5e529e9`: For demonstration, we implemented RNN-based language models on text data.
- `ctx_c20a0ec2bc47e48846e7ed5b`: The recurrent neural network language models are one example of using a discriminative network (trained to predict the next character) that once trained can act as a generative model.
- `ctx_0d8072fac44a71369c278f26`: The character *perplexity* of a language model is defined as the inverse of the geometric mean of a set of probabilities, each probability is corresponding to a character in the word.

### Part-of-speech evidence

- `ctx_33631d6a969125ba846d82b3`: Hence, we will emphasize language models in this chapter.
- `ctx_aff4cfc9f37da2ffa5e529e9`: For demonstration, we implemented RNN-based language models on text data.

## 4. latent factors

- `sense_id`: `d2lce_f7c1845f1d67dcb386e8fc22`
- Split: `development`
- Model definition: hidden learned dimensions or features used to represent users, items, or variables in a factorized model
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_d34d70bc2ec444d75355979e`: The `input_dim` is the number of items/users and the (`output_dim`) is the dimension of the latent factors ($k$).
- `ctx_f7640ef083e72312572602e6`: How does the size of latent factors influence the model performance?
- `ctx_e23c66fedee3dfe32279366e`: The user and item latent factors can be created with the `nn.Embedding`.
- `ctx_fa891237430b0fc11cd6280f`: The GMF is a generic neural network version of matrix factorization where the input is the elementwise product of user and item latent factors.
- `ctx_729f0a12fd676ffe5cb7d8a9`: where $\mathbf{w}_0 \in \mathbb{R}$ is the global bias; $\mathbf{w} \in \mathbb{R}^d$ denotes the weights of the i-th variable; $\mathbf{V} \in \mathbb{R}^{d\times k}$ represents the feature embeddings; $\mathbf{v}_i$ represents the $i^\mathrm{th}$ row of $\mathbf{V}$; $k$ is the dimensionality of latent factors; $\langle\cdot, \cdot \rangle$ is the dot product of two vectors.

### Backup contexts

- `ctx_09c1b7b99119034d4bf50391`: These latent factors might measure obvious dimensions as mentioned in those examples or are completely uninterpretable.
- `ctx_2843dc47b0a0e6aafb8597c7`: How the size of latent factors impact the model performance?
- `ctx_270d955700b7c53c38a3878e`: * Vary the size of latent factors.

### Contrastive contexts

- `ctxx_6ff4c1e031d0f55492f1ac8c`: Synthetic: Social pressure and fear were latent factors behind the decision.

### Definition evidence

- `ctx_09c1b7b99119034d4bf50391`: These latent factors might measure obvious dimensions as mentioned in those examples or are completely uninterpretable.
- `ctx_d34d70bc2ec444d75355979e`: The `input_dim` is the number of items/users and the (`output_dim`) is the dimension of the latent factors ($k$).
- `ctx_fa891237430b0fc11cd6280f`: The GMF is a generic neural network version of matrix factorization where the input is the elementwise product of user and item latent factors.
- `ctx_729f0a12fd676ffe5cb7d8a9`: where $\mathbf{w}_0 \in \mathbb{R}$ is the global bias; $\mathbf{w} \in \mathbb{R}^d$ denotes the weights of the i-th variable; $\mathbf{V} \in \mathbb{R}^{d\times k}$ represents the feature embeddings; $\mathbf{v}_i$ represents the $i^\mathrm{th}$ row of $\mathbf{V}$; $k$ is the dimensionality of latent factors; $\langle\cdot, \cdot \rangle$ is the dot product of two vectors.

### Part-of-speech evidence

- `ctx_d34d70bc2ec444d75355979e`: The `input_dim` is the number of items/users and the (`output_dim`) is the dimension of the latent factors ($k$).
- `ctx_e23c66fedee3dfe32279366e`: The user and item latent factors can be created with the `nn.Embedding`.

## 5. learning rate

- `sense_id`: `d2lce_cc4cb853eff638abcbdf7691`
- Split: `development`
- Model definition: A training hyperparameter that controls the step size of parameter updates during optimization.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_e8375363c7b7a5c455de05c5`: Now, we can [**start training AlexNet.**] Compared with LeNet in :numref:`sec_lenet`, the main change here is the use of a smaller learning rate and much slower training due to the deeper and wider network, the higher image resolution, and the more costly convolutions.
- `ctx_ac1bebe3f69e61f23a9f9382`: For instance, the optimization problem might diverge due to an overly large learning rate.
- `ctx_39e45ec1b48aa92cec021d14`: For the sake of simplicity, we ignore the bias here conv2d = nn.Conv2D(1, kernel_size=(1, 2), use_bias=False) conv2d.initialize() # The two-dimensional convolutional layer uses four-dimensional input and # output in the format of (example, channel, height, width), where the batch # size (number of examples in the batch) and the number of channels are both 1 X = X.reshape(1, 1, 6, 8) Y = Y.reshape(1, 1, 6, 7) lr = 3e-2 # Learning rate for i in range(10): with autograd.record(): Y_hat = conv2d(X) l = (Y_hat - Y) ** 2 l.backward() # Update the kernel conv2d.weight.data()[:] -= lr * conv2d.weight.grad() if (i + 1) % 2 == 0: print(f'epoch {i + 1}, loss {float(l.sum()):.3f}') ```
- `ctx_4d3789e25e89cb28e438e10a`: For example, with $\eta > 0$ as the learning rate, in one iteration we update $\mathbf{x}$ as $\mathbf{x} - \eta \mathbf{g}$.
- `ctx_510e5b25c036f0aedb8ecff2`: Overall, deep RNNs require considerable amount of work (such as learning rate and clipping) to ensure proper convergence.

### Backup contexts

- `ctx_6c4a5e45653e72a9298bb89a`: We emphasize that the values of the batch size and learning rate are manually pre-specified and not typically learned through model training.
- `ctx_7bedce5463902490acfee1a7`: On a 16-GPU server this can increase the minibatch size considerably and we may have to increase the learning rate accordingly.
- `ctx_ce7390efff0801a27a6b6619`: Fortunately, [**the training loop for MLPs is exactly the same as for softmax regression.**] Leveraging the `d2l` package again, we call the `train_ch3` function (see :numref:`sec_softmax_scratch`), setting the number of epochs to 10 and the learning rate to 0.1.

### Contrastive contexts

- `ctxx_074b644581723493cce06e22`: Synthetic: The learning rate of this student improved over the semester, which is unrelated to optimization.

### Definition evidence

- `ctx_6c4a5e45653e72a9298bb89a`: We emphasize that the values of the batch size and learning rate are manually pre-specified and not typically learned through model training.
- `ctx_39e45ec1b48aa92cec021d14`: For the sake of simplicity, we ignore the bias here conv2d = nn.Conv2D(1, kernel_size=(1, 2), use_bias=False) conv2d.initialize() # The two-dimensional convolutional layer uses four-dimensional input and # output in the format of (example, channel, height, width), where the batch # size (number of examples in the batch) and the number of channels are both 1 X = X.reshape(1, 1, 6, 8) Y = Y.reshape(1, 1, 6, 7) lr = 3e-2 # Learning rate for i in range(10): with autograd.record(): Y_hat = conv2d(X) l = (Y_hat - Y) ** 2 l.backward() # Update the kernel conv2d.weight.data()[:] -= lr * conv2d.weight.grad() if (i + 1) % 2 == 0: print(f'epoch {i + 1}, loss {float(l.sum()):.3f}') ```
- `ctx_4d3789e25e89cb28e438e10a`: For example, with $\eta > 0$ as the learning rate, in one iteration we update $\mathbf{x}$ as $\mathbf{x} - \eta \mathbf{g}$.
- `ctx_ac1bebe3f69e61f23a9f9382`: For instance, the optimization problem might diverge due to an overly large learning rate.

### Part-of-speech evidence

- `ctx_6c4a5e45653e72a9298bb89a`: We emphasize that the values of the batch size and learning rate are manually pre-specified and not typically learned through model training.
- `ctx_4d3789e25e89cb28e438e10a`: For example, with $\eta > 0$ as the learning rate, in one iteration we update $\mathbf{x}$ as $\mathbf{x} - \eta \mathbf{g}$.

## 6. likelihood

- `sense_id`: `d2lce_a1d9f9c783c09cc52dedbe55`
- Split: `development`
- Model definition: the probability or degree of chance that a data value, event, class, or sequence is observed or occurs
- Model POS: `noun`

### Primary contexts

- `ctx_d8e44ad4ce4225eacb553a6a`: Thus, we can now write out the *likelihood* of seeing a particular $y$ for a given $\mathbf{x}$ via
- `ctx_a9a2e6cdf046a082edaa6d37`: In these cases we quantify the likelihood that we see a value as a *density*.
- `ctx_2c4ae473914607dda7f7837f`: We might measure the quality of the model by computing the likelihood of the sequence.
- `ctx_6d80c41ae40afac77df593a2`: Denoting by $p$ the largest predicted likelihood, the class corresponding to this probability is the predicted class for $B$.
- `ctx_a28361adfa9c45838015504f`: ```{.python .input} #@save def predict_seq2seq(net, src_sentence, src_vocab, tgt_vocab, num_steps, device, save_attention_weights=False): """Predict for sequence to sequence.""" src_tokens = src_vocab[src_sentence.lower().split(' ')] + [ src_vocab['<eos>']] enc_valid_len = np.array([len(src_tokens)], ctx=device) src_tokens = d2l.truncate_pad(src_tokens, num_steps, src_vocab['<pad>']) # Add the batch axis enc_X = np.expand_dims(np.array(src_tokens, ctx=device), axis=0) enc_outputs = net.encoder(enc_X, enc_valid_len) dec_state = net.decoder.init_state(enc_outputs, enc_valid_len) # Add the batch axis dec_X = np.expand_dims(np.array([tgt_vocab['<bos>']], ctx=device), axis=0) output_seq, attention_weight_seq = [], [] for _ in range(num_steps): Y, dec_state = net.decoder(dec_X, dec_state) # We use the token with the highest prediction likelihood as the input # of the decoder at the next time step dec_X = Y.argmax(axis=2) pred = dec_X.squeeze(axis=0).astype('int32').item() # Save attention weights (to be covered later) if save_attention_weights: attention_weight_seq.append(net.decoder.attention_weights) # Once the end-of-sequence token is predicted, the generation of the # output sequence is complete if pred == tgt_vocab['<eos>']: break output_seq.append(pred) return ' '.join(tgt_vocab.to_tokens(output_seq)), attention_weight_seq ```

### Backup contexts

- `ctx_1dca2fe578193f22e1672147`: We could sweep the image with a Waldo detector that could assign a score to each patch, indicating the likelihood that the patch contains Waldo.
- `ctx_3ac692608d8f389e24ac043e`: An increase in income from 0 to 50 thousand likely corresponds to a bigger increase in likelihood of repayment than an increase from 1 million to 1.05 million.
- `ctx_abe99fc2cabdf28c0c793b55`: For high-dimensional problems the likelihood that at least *some* of the eigenvalues are negative is quite high.

### Contrastive contexts

- `ctxx_0d1a87a213d7b77475352984`: Synthetic: In maximum likelihood estimation, the likelihood is treated as a function of the model parameters.

### Definition evidence

- `ctx_d8e44ad4ce4225eacb553a6a`: Thus, we can now write out the *likelihood* of seeing a particular $y$ for a given $\mathbf{x}$ via
- `ctx_2c4ae473914607dda7f7837f`: We might measure the quality of the model by computing the likelihood of the sequence.
- `ctx_6d80c41ae40afac77df593a2`: Denoting by $p$ the largest predicted likelihood, the class corresponding to this probability is the predicted class for $B$.
- `ctx_a28361adfa9c45838015504f`: ```{.python .input} #@save def predict_seq2seq(net, src_sentence, src_vocab, tgt_vocab, num_steps, device, save_attention_weights=False): """Predict for sequence to sequence.""" src_tokens = src_vocab[src_sentence.lower().split(' ')] + [ src_vocab['<eos>']] enc_valid_len = np.array([len(src_tokens)], ctx=device) src_tokens = d2l.truncate_pad(src_tokens, num_steps, src_vocab['<pad>']) # Add the batch axis enc_X = np.expand_dims(np.array(src_tokens, ctx=device), axis=0) enc_outputs = net.encoder(enc_X, enc_valid_len) dec_state = net.decoder.init_state(enc_outputs, enc_valid_len) # Add the batch axis dec_X = np.expand_dims(np.array([tgt_vocab['<bos>']], ctx=device), axis=0) output_seq, attention_weight_seq = [], [] for _ in range(num_steps): Y, dec_state = net.decoder(dec_X, dec_state) # We use the token with the highest prediction likelihood as the input # of the decoder at the next time step dec_X = Y.argmax(axis=2) pred = dec_X.squeeze(axis=0).astype('int32').item() # Save attention weights (to be covered later) if save_attention_weights: attention_weight_seq.append(net.decoder.attention_weights) # Once the end-of-sequence token is predicted, the generation of the # output sequence is complete if pred == tgt_vocab['<eos>']: break output_seq.append(pred) return ' '.join(tgt_vocab.to_tokens(output_seq)), attention_weight_seq ```

### Part-of-speech evidence

- `ctx_d8e44ad4ce4225eacb553a6a`: Thus, we can now write out the *likelihood* of seeing a particular $y$ for a given $\mathbf{x}$ via
- `ctx_2c4ae473914607dda7f7837f`: We might measure the quality of the model by computing the likelihood of the sequence.

## 7. linearly independent

- `sense_id`: `d2lce_e246c0d41c7b8bc2c145f69a`
- Split: `development`
- Model definition: having no linear dependence among the vectors or columns considered
- Model POS: `adjective_phrase`

### Primary contexts

- `ctx_b614df5afd99a56025590e12`: If there is no linear dependence we say the vectors are *linearly independent*.
- `ctx_fb0bce3ae7d50e936e3d1fd2`: Finally, recall that the rank was the maximum number of linearly independent columns of your matrix.
- `ctx_12f080ce042dec5729904025`: The rank of a matrix is the size of the largest subset of its columns that are linearly independent.
- `ctx_14cc1dcbd3a77f9fc840d257`: Which of the following sets of vectors are linearly independent?
- `ctx_162d9dc7044c91d56d63078a`: In particular, the rank of a matrix $\mathbf{A}$ is the largest number of linearly independent columns amongst all subsets of columns.

### Backup contexts

- `ctx_87d3bb237e3e364754aca75a`: In the next section we will see some nice consequences of this, but for now we need only know that such a decomposition will exist as long as we can find a full collection of linearly independent eigenvectors (so that $W$ is invertible).
- `ctx_ea72ec8122738d9978381416`: and show that $\mathbf{C}$ has rank two since, for instance, the first two columns are linearly independent, however any of the four collections of three columns are dependent.
- `ctx_f07eed0f884f117c57662fd2`: If the columns of a matrix are linearly independent, no compression occurs and the operation can be undone.

### Contrastive contexts

- `ctxx_7023d62a0183cfe9af9039e4`: Synthetic: These measurements are statistically independent, but not linearly independent as vectors.

### Definition evidence

- `ctx_b614df5afd99a56025590e12`: If there is no linear dependence we say the vectors are *linearly independent*.
- `ctx_162d9dc7044c91d56d63078a`: In particular, the rank of a matrix $\mathbf{A}$ is the largest number of linearly independent columns amongst all subsets of columns.

### Part-of-speech evidence

- `ctx_b614df5afd99a56025590e12`: If there is no linear dependence we say the vectors are *linearly independent*.
- `ctx_f07eed0f884f117c57662fd2`: If the columns of a matrix are linearly independent, no compression occurs and the operation can be undone.

## 8. maximum pooling layer

- `sense_id`: `d2lce_c343a692fe9bdfdabefe7687`
- Split: `development`
- Model definition: a pooling layer that outputs the maximum value within each local window, often for downsampling
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_801d83970e9b56293ca7ce56`: One VGG block consists of a sequence of convolutional layers, followed by a maximum pooling layer for spatial downsampling.
- `ctx_ac295765755512cf5030affb`: More concretely, each downsampling block consists of two $3\times3$ convolutional layers with padding of 1 followed by a $2\times2$ maximum pooling layer with stride of 2.
- `ctx_5e90143b3f597bea613c706a`: We can demonstrate the use of padding and strides in pooling layers via the built-in two-dimensional maximum pooling layer from the deep learning framework.
- `ctx_3201c5fa0f12832e74500d2f`: That is to say, using the $2\times 2$ maximum pooling layer, we can still detect if the pattern recognized by the convolutional layer moves no more than one element in height or width.
- `ctx_690cb0198616ce9356c3d7dd`: Each NiN block is followed by a maximum pooling layer with a stride of 2 and a window shape of $3\times 3$.

### Backup contexts

- `ctx_d2068bc0172a126a547418aa`: The basic building block of classic CNNs is a sequence of the following: (i) a convolutional layer with padding to maintain the resolution, (ii) a nonlinearity such as a ReLU, (iii) a pooling layer such as a maximum pooling layer.
- `ctx_f02e4c6150e91731a4b448a8`: We can construct the input tensor `X` in :numref:`fig_pooling` to [**validate the output of the two-dimensional maximum pooling layer**].
- `ctx_14f76eec1290dbfe141ac161`: Moreover, we remove the maximum pooling layer.

### Contrastive contexts

- `ctxx_11226ba76c96a02247095670`: Synthetic: The maximum pooling layer of blankets on the bed made the room look untidy.

### Definition evidence

- `ctx_801d83970e9b56293ca7ce56`: One VGG block consists of a sequence of convolutional layers, followed by a maximum pooling layer for spatial downsampling.
- `ctx_5e90143b3f597bea613c706a`: We can demonstrate the use of padding and strides in pooling layers via the built-in two-dimensional maximum pooling layer from the deep learning framework.
- `ctx_ac295765755512cf5030affb`: More concretely, each downsampling block consists of two $3\times3$ convolutional layers with padding of 1 followed by a $2\times2$ maximum pooling layer with stride of 2.

### Part-of-speech evidence

- `ctx_801d83970e9b56293ca7ce56`: One VGG block consists of a sequence of convolutional layers, followed by a maximum pooling layer for spatial downsampling.
- `ctx_f02e4c6150e91731a4b448a8`: We can construct the input tensor `X` in :numref:`fig_pooling` to [**validate the output of the two-dimensional maximum pooling layer**].

## 9. mean squared error

- `sense_id`: `d2lce_49603071e9c21eb4bcbdf1e7`
- Split: `development`
- Model definition: The average of squared differences between predicted or estimated values and the true values, used as an error metric or loss.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_aa9bf66af57b4d0277adf479`: One way to motivate linear regression with the mean squared error loss function (or simply squared loss) is to formally assume that observations arise from noisy observations, where the noise is normally distributed as follows:
- `ctx_a3b09c164d6fc85a35c1c018`: ### Mean Squared Error
- `ctx_d54f045d576ae356763b52df`: :begin_tab:`pytorch` [**The `MSELoss` class computes the mean squared error (without the $1/2$ factor in :eqref:`eq_mse`).**] By default it returns the average loss over examples.
- `ctx_85127e11fd3023a9623643bf`: :begin_tab:`tensorflow` The `MeanSquaredError` class computes the mean squared error (without the $1/2$ factor in :eqref:`eq_mse`).
- `ctx_21ccd6b472be7b8886dfc5ba`: It follows that minimizing the mean squared error is equivalent to maximum likelihood estimation of a linear model under the assumption of additive Gaussian noise.

### Backup contexts

- `ctx_51976c239578153593bf6e10`: Then, we train the matrix factorization model by minimizing the mean squared error between predicted rating scores and real rating scores.
- `ctx_8773b84dd0e7621c8e9964bc`: In this section, we introduce three common methods to evaluate and compare estimators: the mean squared error, the standard deviation, and statistical bias.
- `ctx_f394e4eeabb8358a5b205328`: We will rely on maximum likelihood estimation, the very same concept that we encountered when providing a probabilistic justification for the mean squared error objective in linear regression (:numref:`subsec_normal_distribution_and_squared_loss`).

### Contrastive contexts

- `ctxx_ad0c031ce4d8893e1d1ad1ee`: Synthetic: In this note, mean squared error refers to prediction error, not to the mean of arbitrary squared numbers.

### Definition evidence

- `ctx_aa9bf66af57b4d0277adf479`: One way to motivate linear regression with the mean squared error loss function (or simply squared loss) is to formally assume that observations arise from noisy observations, where the noise is normally distributed as follows:
- `ctx_51976c239578153593bf6e10`: Then, we train the matrix factorization model by minimizing the mean squared error between predicted rating scores and real rating scores.
- `ctx_8773b84dd0e7621c8e9964bc`: In this section, we introduce three common methods to evaluate and compare estimators: the mean squared error, the standard deviation, and statistical bias.
- `ctx_21ccd6b472be7b8886dfc5ba`: It follows that minimizing the mean squared error is equivalent to maximum likelihood estimation of a linear model under the assumption of additive Gaussian noise.

### Part-of-speech evidence

- `ctx_a3b09c164d6fc85a35c1c018`: ### Mean Squared Error
- `ctx_d54f045d576ae356763b52df`: :begin_tab:`pytorch` [**The `MSELoss` class computes the mean squared error (without the $1/2$ factor in :eqref:`eq_mse`).**] By default it returns the average loss over examples.

## 10. minibatch

- `sense_id`: `d2lce_04b7107b328dedc7c1f9af65`
- Split: `development`
- Model definition: a small batch of training examples processed together in one step of learning or computation
- Model POS: `noun`

### Primary contexts

- `ctx_deac78418a7fa068946c9bc4`: As before, by the matrix $\mathbf{X} \in \mathbb{R}^{n \times d}$, we denote a minibatch of $n$ examples where each example has $d$ inputs (features).
- `ctx_c84f58f5911e68e47bc8ede6`: ### Minibatch Stochastic Gradient Descent
- `ctx_9d859bd559e44bb8d2a5c8c9`: One of the key challenges in designing scalable algorithms is that the workhorse of deep learning optimization, stochastic gradient descent, relies on relatively small minibatches of data to be processed.
- `ctx_0365fe98277f3f0623b7477b`: Batch normalization is applied to individual layers (optionally, to all of them) and works as follows: In each training iteration, we first normalize the inputs (of batch normalization) by subtracting their mean and dividing by their standard deviation, where both are estimated based on the statistics of the current minibatch.
- `ctx_5ab34383333d1d2b61729c04`: Now the question is how to [**read minibatches of features and labels at random.**]

### Backup contexts

- `ctx_4323c72305899d396f01af5d`: A typical mistake is as follows: computing the loss for every minibatch on the GPU and reporting it back to the user on the command line (or logging it in a NumPy `ndarray`) will trigger a global interpreter lock which stalls all GPUs.
- `ctx_07f682f0725bb71453b6f6c0`: In order to pass output from the convolutional block to the dense block, we must flatten each example in the minibatch.
- `ctx_a7783902acdf15b7a77e6d41`: For example, along the outermost axis of a tensor, we can access or enumerate minibatches of data examples, or just data examples if no minibatch exists.

### Contrastive contexts

- `ctxx_f724d6b043cdd8671450f959`: Synthetic: In printing, a minibatch means a small production run rather than a group of training examples.

### Definition evidence

- `ctx_9d859bd559e44bb8d2a5c8c9`: One of the key challenges in designing scalable algorithms is that the workhorse of deep learning optimization, stochastic gradient descent, relies on relatively small minibatches of data to be processed.
- `ctx_deac78418a7fa068946c9bc4`: As before, by the matrix $\mathbf{X} \in \mathbb{R}^{n \times d}$, we denote a minibatch of $n$ examples where each example has $d$ inputs (features).
- `ctx_5ab34383333d1d2b61729c04`: Now the question is how to [**read minibatches of features and labels at random.**]

### Part-of-speech evidence

- `ctx_c84f58f5911e68e47bc8ede6`: ### Minibatch Stochastic Gradient Descent
- `ctx_deac78418a7fa068946c9bc4`: As before, by the matrix $\mathbf{X} \in \mathbb{R}^{n \times d}$, we denote a minibatch of $n$ examples where each example has $d$ inputs (features).
