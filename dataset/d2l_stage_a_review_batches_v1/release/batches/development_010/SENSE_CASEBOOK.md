# Stage A sense casebook: development_010

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. two-dimensional cross-correlation operation

- `sense_id`: `d2lce_963a14fc5042969e330bb020`
- Split: `development`
- Model definition: an operation that slides a kernel over a 2D input and computes outputs from elementwise products and sums at each position
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c347d897c071e45dc443bc15`: In the two-dimensional cross-correlation operation, we begin with the convolution window positioned at the upper-left corner of the input tensor and slide it across the input tensor, both from left to right and top to bottom.
- `ctx_72a1c4b96b8dcbf9713e5a69`: We can construct the input tensor `X` and the kernel tensor `K` from :numref:`fig_correlation` to [**validate the output of the above implementation**] of the two-dimensional cross-correlation operation.
- `ctx_d5cacde964394c13f3443d68`: ![Two-dimensional cross-correlation with padding.](../img/conv-pad.svg) :label:`img_conv_pad`
- `ctx_876dc1724c5a190419098d85`: * The core computation of a two-dimensional convolutional layer is a two-dimensional cross-correlation operation.
- `ctx_31af545156a8abd1def5ed1d`: Here, the output tensor has a height of 2 and width of 2 and the four elements are derived from the two-dimensional cross-correlation operation:

### Backup contexts

- `ctx_0540231b9dc01be0b46e98a0`: :numref:`img_conv_stride` shows a two-dimensional cross-correlation operation with a stride of 3 vertically and 2 horizontally.
- `ctx_868efbddfe140e3e02c5c89d`: Note that multi-input-channel one-dimensional cross-correlations are equivalent to single-input-channel two-dimensional cross-correlations.
- `ctx_8378b0547c4e75e694d743d8`: ![Two-dimensional cross-correlation operation.

### Contrastive contexts

- `ctxx_2bc34d2f3a78b341b463ae37`: Synthetic boundary probe: "two-dimensional cross-correlation operation" is quoted here only as a document label, not as an occurrence of the reviewed D2L sense.

### Definition evidence

- `ctx_c347d897c071e45dc443bc15`: In the two-dimensional cross-correlation operation, we begin with the convolution window positioned at the upper-left corner of the input tensor and slide it across the input tensor, both from left to right and top to bottom.
- `ctx_31af545156a8abd1def5ed1d`: Here, the output tensor has a height of 2 and width of 2 and the four elements are derived from the two-dimensional cross-correlation operation:
- `ctx_876dc1724c5a190419098d85`: * The core computation of a two-dimensional convolutional layer is a two-dimensional cross-correlation operation.

### Part-of-speech evidence

- `ctx_c347d897c071e45dc443bc15`: In the two-dimensional cross-correlation operation, we begin with the convolution window positioned at the upper-left corner of the input tensor and slide it across the input tensor, both from left to right and top to bottom.
- `ctx_876dc1724c5a190419098d85`: * The core computation of a two-dimensional convolutional layer is a two-dimensional cross-correlation operation.

## 2. underflow

- `sense_id`: `d2lce_9bd5113780f8e8160a24e6ad`
- Split: `development`
- Model definition: a numerical computing condition where a value becomes too small to represent and is rounded to zero
- Model POS: `noun`

### Primary contexts

- `ctx_f6a47145f376202745ec79b1`: These might be rounded to zero due to finite precision (i.e., *underflow*), making $\hat y_j$ zero and giving us `-inf` for $\log(\hat y_j)$.
- `ctx_2667f83ba76468ba1a7c23ce`: Thus we are susceptible to the same problems of numerical underflow that often crop up when multiplying together too many probabilities.
- `ctx_eb00b5802d52495b67261199`: ```{.python .input} a = 0.1 print('underflow:', a**784) print('logarithm is normal:', 784*math.log(a)) ```
- `ctx_5d3d4728c7288bca4bf4f624`: What happens is that we experience *numerical underflow*, i.e., multiplying all the small numbers leads to something even smaller until it is rounded down to zero.
- `ctx_927dfa6b607b0cdb7925b702`: Moreover, accumulating gradients requires higher precision to avoid numerical underflow (or overflow).

### Backup contexts

- `ctx_f33974c8e2ea51a218101f34`: Note that while this looks correct mathematically, we were a bit sloppy in our implementation because we failed to take precautions against numerical overflow or underflow due to large or very small elements of the matrix.
- `ctx_9348532807a8c96895b92b49`: ```{.python .input} #@tab tensorflow a = 0.1 print('underflow:', a**784) print('logarithm is normal:', 784*tf.math.log(a).numpy()) ```
- `ctx_c429e44e5290244ff93a70cb`: ```{.python .input} #@tab pytorch a = 0.1 print('underflow:', a**784) print('logarithm is normal:', 784*math.log(a)) ```

### Contrastive contexts

- `ctxx_84628ffb91c733b908fe79fe`: Synthetic: In fluid dynamics, underflow beneath a dam changed the riverbed.

### Definition evidence

- `ctx_5d3d4728c7288bca4bf4f624`: What happens is that we experience *numerical underflow*, i.e., multiplying all the small numbers leads to something even smaller until it is rounded down to zero.
- `ctx_f6a47145f376202745ec79b1`: These might be rounded to zero due to finite precision (i.e., *underflow*), making $\hat y_j$ zero and giving us `-inf` for $\log(\hat y_j)$.
- `ctx_927dfa6b607b0cdb7925b702`: Moreover, accumulating gradients requires higher precision to avoid numerical underflow (or overflow).

### Part-of-speech evidence

- `ctx_f6a47145f376202745ec79b1`: These might be rounded to zero due to finite precision (i.e., *underflow*), making $\hat y_j$ zero and giving us `-inf` for $\log(\hat y_j)$.
- `ctx_5d3d4728c7288bca4bf4f624`: What happens is that we experience *numerical underflow*, i.e., multiplying all the small numbers leads to something even smaller until it is rounded down to zero.

## 3. unknown token

- `sense_id`: `d2lce_9e5c3dd254843c7ec95d4960`
- Split: `development`
- Model definition: a special vocabulary token used to represent unseen, removed, or excluded items
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_ea66b3ce575e4204be2d5f9e`: Any token that does not exist in the corpus or has been removed is mapped into a special unknown token “&lt;unk&gt;”.
- `ctx_c9714080bd2e308c662b5227`: To alleviate this, we can treat infrequent tokens as the same unknown token.
- `ctx_086aada07e0f520a618cc583`: ```{.python .input} #@tab all class Vocab: #@save """Vocabulary for text.""" def __init__(self, tokens=None, min_freq=0, reserved_tokens=None): if tokens is None: tokens = [] if reserved_tokens is None: reserved_tokens = [] # Sort according to frequencies counter = count_corpus(tokens) self._token_freqs = sorted(counter.items(), key=lambda x: x[1], reverse=True) # The index for the unknown token is 0 self.idx_to_token = ['<unk>'] + reserved_tokens self.token_to_idx = {token: idx for idx, token in enumerate(self.idx_to_token)} for token, freq in self._token_freqs: if freq < min_freq: break if token not in self.token_to_idx: self.idx_to_token.append(token) self.token_to_idx[token] = len(self.idx_to_token) - 1 def __len__(self): return len(self.idx_to_token) def __getitem__(self, tokens): if not isinstance(tokens, (list, tuple)): return self.token_to_idx.get(tokens, self.unk) return [self.__getitem__(token) for token in tokens] def to_tokens(self, indices): if not isinstance(indices, (list, tuple)): return self.idx_to_token[indices] return [self.idx_to_token[index] for index in indices] @property def unk(self): # Index for the unknown token return 0 @property def token_freqs(self): # Index for the unknown token return self._token_freqs def count_corpus(tokens): #@save """Count token frequencies.""" # Here `tokens` is a 1D list or 2D list if len(tokens) == 0 or isinstance(tokens[0], list): # Flatten a list of token lists into a list of tokens tokens = [token for line in tokens for token in line] return collections.Counter(tokens) ```
- `ctx_1d2e9339e55b93263b732ad7`: The vocabulary of the pretrained word vectors in `glove_6b50d` contains 400000 words and a special unknown token.
- `ctx_3866a3d1dc9bad289462f97a`: The vocabulary contains 400000 words (tokens) and a special unknown token.

### Backup contexts

- `ctx_9fad57a59804035d85ae8028`: (index 0 is the # excluded unknown token) in the vocabulary sampling_weights = [counter[vocab.to_tokens(i)]**0.75 for i in range(1, len(vocab))] all_negatives, generator = [], RandomGenerator(sampling_weights) for contexts in all_contexts: negatives = [] while len(negatives) < len(contexts) * K: neg = generator.draw() # Noise words cannot be context words if neg not in contexts: negatives.append(neg) all_negatives.append(negatives) return all_negatives all_negatives = get_negatives(all_contexts, vocab, counter, 5) ```
- `ctx_c924c2013dba4600e46dd8f8`: Excluding the input word and unknown token, among this vocabulary let us find three most semantically similar words to word "chip".

### Contrastive contexts

- `ctxx_9aab1123769ff146c3545c87`: Synthetic: A token can be any wordpiece, but the unknown token is the special placeholder for out-of-vocabulary items.

### Definition evidence

- `ctx_ea66b3ce575e4204be2d5f9e`: Any token that does not exist in the corpus or has been removed is mapped into a special unknown token “&lt;unk&gt;”.
- `ctx_c9714080bd2e308c662b5227`: To alleviate this, we can treat infrequent tokens as the same unknown token.
- `ctx_086aada07e0f520a618cc583`: ```{.python .input} #@tab all class Vocab: #@save """Vocabulary for text.""" def __init__(self, tokens=None, min_freq=0, reserved_tokens=None): if tokens is None: tokens = [] if reserved_tokens is None: reserved_tokens = [] # Sort according to frequencies counter = count_corpus(tokens) self._token_freqs = sorted(counter.items(), key=lambda x: x[1], reverse=True) # The index for the unknown token is 0 self.idx_to_token = ['<unk>'] + reserved_tokens self.token_to_idx = {token: idx for idx, token in enumerate(self.idx_to_token)} for token, freq in self._token_freqs: if freq < min_freq: break if token not in self.token_to_idx: self.idx_to_token.append(token) self.token_to_idx[token] = len(self.idx_to_token) - 1 def __len__(self): return len(self.idx_to_token) def __getitem__(self, tokens): if not isinstance(tokens, (list, tuple)): return self.token_to_idx.get(tokens, self.unk) return [self.__getitem__(token) for token in tokens] def to_tokens(self, indices): if not isinstance(indices, (list, tuple)): return self.idx_to_token[indices] return [self.idx_to_token[index] for index in indices] @property def unk(self): # Index for the unknown token return 0 @property def token_freqs(self): # Index for the unknown token return self._token_freqs def count_corpus(tokens): #@save """Count token frequencies.""" # Here `tokens` is a 1D list or 2D list if len(tokens) == 0 or isinstance(tokens[0], list): # Flatten a list of token lists into a list of tokens tokens = [token for line in tokens for token in line] return collections.Counter(tokens) ```

### Part-of-speech evidence

- `ctx_ea66b3ce575e4204be2d5f9e`: Any token that does not exist in the corpus or has been removed is mapped into a special unknown token “&lt;unk&gt;”.
- `ctx_086aada07e0f520a618cc583`: ```{.python .input} #@tab all class Vocab: #@save """Vocabulary for text.""" def __init__(self, tokens=None, min_freq=0, reserved_tokens=None): if tokens is None: tokens = [] if reserved_tokens is None: reserved_tokens = [] # Sort according to frequencies counter = count_corpus(tokens) self._token_freqs = sorted(counter.items(), key=lambda x: x[1], reverse=True) # The index for the unknown token is 0 self.idx_to_token = ['<unk>'] + reserved_tokens self.token_to_idx = {token: idx for idx, token in enumerate(self.idx_to_token)} for token, freq in self._token_freqs: if freq < min_freq: break if token not in self.token_to_idx: self.idx_to_token.append(token) self.token_to_idx[token] = len(self.idx_to_token) - 1 def __len__(self): return len(self.idx_to_token) def __getitem__(self, tokens): if not isinstance(tokens, (list, tuple)): return self.token_to_idx.get(tokens, self.unk) return [self.__getitem__(token) for token in tokens] def to_tokens(self, indices): if not isinstance(indices, (list, tuple)): return self.idx_to_token[indices] return [self.idx_to_token[index] for index in indices] @property def unk(self): # Index for the unknown token return 0 @property def token_freqs(self): # Index for the unknown token return self._token_freqs def count_corpus(tokens): #@save """Count token frequencies.""" # Here `tokens` is a 1D list or 2D list if len(tokens) == 0 or isinstance(tokens[0], list): # Flatten a list of token lists into a list of tokens tokens = [token for line in tokens for token in line] return collections.Counter(tokens) ```

## 4. Update Gate

- `sense_id`: `d2lce_a47c0fa6efae6f5b3c950575`
- Split: `development`
- Model definition: a GRU gate that controls how much of the previous hidden state is kept versus replaced by the candidate state
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_3143c3d658da09d8181b666c`: The first thing we need to introduce are the *reset gate* and the *update gate*.
- `ctx_2856d35ae63ae8dbd84d644d`: :numref:`fig_gru_1` illustrates the inputs for both the reset and update gates in a GRU, given the input of the current time step and the hidden state of the previous time step.
- `ctx_d739879531fc4668a9d14f93`: Then, the reset gate $\mathbf{R}_t \in \mathbb{R}^{n \times h}$ and update gate $\mathbf{Z}_t \in \mathbb{R}^{n \times h}$ are computed as follows:
- `ctx_2d3d087fad253f4d69369b59`: The result is a *candidate* since we still need to incorporate the action of the update gate.
- `ctx_57c90277e1fd8433f386654b`: The update gate $\mathbf{Z}_t$ can be used for this purpose, simply by taking elementwise convex combinations between both $\mathbf{H}_{t-1}$ and $\tilde{\mathbf{H}}_t$.

### Backup contexts

- `ctx_91acf4e9a95c2577a48f754e`: Likewise, an update gate would allow us to control how much of the new state is just a copy of the old state.
- `ctx_e468e6c3444203918151241e`: ![Computing the reset gate and the update gate in a GRU model.](../img/gru-1.svg) :label:`fig_gru_1`
- `ctx_0bbf3a04a91397bf545fe5dc`: ### Reset Gate and Update Gate

### Contrastive contexts

- `ctxx_d3c2318dc6ca29fa731dffbf`: Synthetic: In the castle simulation game, the update gate opens only when engineers install a new software patch.

### Definition evidence

- `ctx_91acf4e9a95c2577a48f754e`: Likewise, an update gate would allow us to control how much of the new state is just a copy of the old state.
- `ctx_d739879531fc4668a9d14f93`: Then, the reset gate $\mathbf{R}_t \in \mathbb{R}^{n \times h}$ and update gate $\mathbf{Z}_t \in \mathbb{R}^{n \times h}$ are computed as follows:
- `ctx_57c90277e1fd8433f386654b`: The update gate $\mathbf{Z}_t$ can be used for this purpose, simply by taking elementwise convex combinations between both $\mathbf{H}_{t-1}$ and $\tilde{\mathbf{H}}_t$.

### Part-of-speech evidence

- `ctx_0bbf3a04a91397bf545fe5dc`: ### Reset Gate and Update Gate
- `ctx_3143c3d658da09d8181b666c`: The first thing we need to introduce are the *reset gate* and the *update gate*.
- `ctx_d739879531fc4668a9d14f93`: Then, the reset gate $\mathbf{R}_t \in \mathbb{R}^{n \times h}$ and update gate $\mathbf{Z}_t \in \mathbb{R}^{n \times h}$ are computed as follows:

## 5. vanishing gradients

- `sense_id`: `d2lce_d7976d0b101e65c34c011871`
- Split: `development`
- Model definition: a training problem where gradients become extremely small, so parameters barely update and learning becomes difficult
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_26abf38904bfba2529b1ab9a`: We may be facing parameter updates that are either (i) excessively large, destroying our model (the *exploding gradient* problem); or (ii) excessively small (the *vanishing gradient* problem), rendering learning impossible as parameters hardly move on each update.
- `ctx_69b854938dd969b726eb92a0`: * Gradient clipping prevents gradient explosion, but it cannot fix vanishing gradients.
- `ctx_9a06089aea8285a7f38f5e36`: ### (**Vanishing Gradients**)
- `ctx_3c0646bacb04e52b12ad59ca`: One frequent culprit causing the vanishing gradient problem is the choice of the activation function $\sigma$ that is appended following each layer's linear operations.
- `ctx_ccefa9dc79f5be995f8d5599`: These designs can help us cope with the vanishing gradient problem in RNNs and better capture dependencies for sequences with large time step distances.

### Backup contexts

- `ctx_e1fa0d830f4e4018432efd83`: Poor choices here can cause us to encounter exploding or vanishing gradients while training.
- `ctx_0c2cf2fa2cea5d19f1f0a29b`: This makes optimization better behaved and it mitigated the well-documented problem of vanishing gradients that plagued previous versions of neural networks (more on this later).
- `ctx_2b3bad1bba3a00bca408c517`: Some of the most vexing ones are local minima, saddle points, and vanishing gradients.

### Contrastive contexts

- `ctxx_81f6cec0f1edf5ca60a5d1d1`: Synthetic: In the poster, the designer created vanishing gradients as a color effect from dark blue to white.

### Definition evidence

- `ctx_26abf38904bfba2529b1ab9a`: We may be facing parameter updates that are either (i) excessively large, destroying our model (the *exploding gradient* problem); or (ii) excessively small (the *vanishing gradient* problem), rendering learning impossible as parameters hardly move on each update.
- `ctx_69b854938dd969b726eb92a0`: * Gradient clipping prevents gradient explosion, but it cannot fix vanishing gradients.
- `ctx_3c0646bacb04e52b12ad59ca`: One frequent culprit causing the vanishing gradient problem is the choice of the activation function $\sigma$ that is appended following each layer's linear operations.

### Part-of-speech evidence

- `ctx_26abf38904bfba2529b1ab9a`: We may be facing parameter updates that are either (i) excessively large, destroying our model (the *exploding gradient* problem); or (ii) excessively small (the *vanishing gradient* problem), rendering learning impossible as parameters hardly move on each update.
- `ctx_9a06089aea8285a7f38f5e36`: ### (**Vanishing Gradients**)

## 6. volitional cue

- `sense_id`: `d2lce_ad03ff147d19eb2ea47d5b0e`
- Split: `development`
- Model definition: a task-dependent cue that deliberately directs attention; in attention mechanisms, it corresponds to a query.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_6733f9355787febdfa53f095`: In the context of attention mechanisms, we refer to volitional cues as *queries*.
- `ctx_31ee4f7a5863ed678a04e350`: Using the volitional cue based on variable selection criteria, this form of attention is more deliberate.
- `ctx_495329d7ea08710cf266062c`: ![Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).](../img/qkv.svg) :label:`fig_qkv`
- `ctx_61e1112cbf2424e69a7a2487`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_6e5eabbf33032ac2428b591c`: In this framework, subjects selectively direct the spotlight of attention using both the *nonvolitional cue* and *volitional cue*.

### Backup contexts

- `ctx_0018248a05d490e292afdea5`: Therefore, what sets attention mechanisms apart from those fully-connected layers or pooling layers is the inclusion of the volitional cues.
- `ctx_0196df223b107d63e312df82`: ![Using the volitional cue (want to read a book) that is task-dependent, attention is directed to the book under volitional control.](../img/eye-book.svg) :width:`400px` :label:`fig_eye-book`
- `ctx_187de8cd1e12dd890c442ade`: * Attention mechanisms are different from fully-connected layers or pooling layers due to inclusion of the volitional cues.

### Contrastive contexts

- `ctxx_9e314f27a0624fba37123793`: Synthetic: A sudden flash acts as a cue, but not a volitional cue, because it captures attention involuntarily.

### Definition evidence

- `ctx_31ee4f7a5863ed678a04e350`: Using the volitional cue based on variable selection criteria, this form of attention is more deliberate.
- `ctx_6733f9355787febdfa53f095`: In the context of attention mechanisms, we refer to volitional cues as *queries*.

### Part-of-speech evidence

- `ctx_6e5eabbf33032ac2428b591c`: In this framework, subjects selectively direct the spotlight of attention using both the *nonvolitional cue* and *volitional cue*.
- `ctx_31ee4f7a5863ed678a04e350`: Using the volitional cue based on variable selection criteria, this form of attention is more deliberate.

## 7. Warmup

- `sense_id`: `d2lce_6f3afd43e74e8d70778dc0c8`
- Split: `development`
- Model definition: an initial training phase in which the learning rate is gradually increased before following the main schedule
- Model POS: `noun`

### Primary contexts

- `ctx_df53f1201adeb15694c788d5`: A rather simple fix for this dilemma is to use a warmup period during which the learning rate *increases* to its initial maximum and to cool down the rate until the end of the optimization process.
- `ctx_a1b6c6ab71183a43fe8f7b93`: ### Warmup
- `ctx_078c04e65c06128943224c26`: In particular they find that a warmup phase limits the amount of divergence of parameters in very deep networks.
- `ctx_10409253f5d4e26f24be38e9`: It takes a few more parameters, such as warmup period, warmup mode (linear or constant), the maximum number of desired updates, etc.; Going forward we will use the built-in schedulers as appropriate and only explain their functionality here.
- `ctx_23984c926b405fd7be61d3af`: * A warmup period before optimization can prevent divergence.

### Backup contexts

- `ctx_2b99a602b964180da9cbc38c`: Warmup can be applied to any scheduler (not just cosine).
- `ctx_a512a07140b183f0582a2fa1`: This goes under the moniker of *warmup*, i.e., how rapidly we start moving towards the solution initially.

### Contrastive contexts

- `ctxx_e55058367fc052cda2365416`: Synthetic: As a warmup, compute a tiny matrix product before studying asynchronous execution.

### Definition evidence

- `ctx_a512a07140b183f0582a2fa1`: This goes under the moniker of *warmup*, i.e., how rapidly we start moving towards the solution initially.
- `ctx_df53f1201adeb15694c788d5`: A rather simple fix for this dilemma is to use a warmup period during which the learning rate *increases* to its initial maximum and to cool down the rate until the end of the optimization process.
- `ctx_23984c926b405fd7be61d3af`: * A warmup period before optimization can prevent divergence.

### Part-of-speech evidence

- `ctx_a1b6c6ab71183a43fe8f7b93`: ### Warmup
- `ctx_df53f1201adeb15694c788d5`: A rather simple fix for this dilemma is to use a warmup period during which the learning rate *increases* to its initial maximum and to cool down the rate until the end of the optimization process.
- `ctx_2b99a602b964180da9cbc38c`: Warmup can be applied to any scheduler (not just cosine).

## 8. weighted average

- `sense_id`: `d2lce_a3e7228aef125ec437a840fa`
- Split: `development`
- Model definition: An average computed by combining values with weights that determine each value's contribution.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_560fdd2106e8a9d780a76535`: The new gradient replacement no longer points into the direction of steepest descent on a particular instance any longer but rather in the direction of a weighted average of past gradients.
- `ctx_8e04ca81f5cd4758904ce28b`: If we have a discrete random variable $X$, which takes the values $x_i$ with probabilities $p_i$, then the mean is given by the weighted average: sum the values times the probability that the random variable takes on that value:
- `ctx_aba6fee7580baba0771a58d2`: Average pooling can be treated as a weighted average of inputs, where weights are uniform.
- `ctx_2b750c7f5d33f647672795c7`: Shape of `attention_weights`: # (`n_test`, `n_train`), where each row contains attention weights to be # assigned among the values (`y_train`) given each query attention_weights = npx.softmax(-(X_repeat - x_train)**2 / 2) # Each element of `y_hat` is weighted average of values, where weights are # attention weights y_hat = d2l.matmul(attention_weights, y_train) plot_kernel_reg(y_hat) ```
- `ctx_07d0a92774325109338bead5`: In practice, attention pooling aggregates values using weighted average, where weights are computed between the given query and different keys.

### Backup contexts

- `ctx_11cbd62463e49bc8907aefef`: Comparing :eqref:`eq_attn-pooling` and :eqref:`eq_avg-pooling`, the attention pooling here is a weighted average of values $y_i$.
- `ctx_19f6562b721592fe470608b6`: Note that such alignment is *soft* using weighted average, where ideally large weights are associated with the tokens to be aligned.
- `ctx_6bf957c26c6e143256cdd035`: When the weights are non-negative and sum to one (i.e., $\left(\sum_{i=1}^{d} {w_i} = 1\right)$), the dot product expresses a *weighted average*.

### Contrastive contexts

- `ctxx_f815c752c262d1e575571f1a`: Synthetic: The clerk asked for the weighted average grade, not the simple mean.

### Definition evidence

- `ctx_6bf957c26c6e143256cdd035`: When the weights are non-negative and sum to one (i.e., $\left(\sum_{i=1}^{d} {w_i} = 1\right)$), the dot product expresses a *weighted average*.
- `ctx_07d0a92774325109338bead5`: In practice, attention pooling aggregates values using weighted average, where weights are computed between the given query and different keys.
- `ctx_8e04ca81f5cd4758904ce28b`: If we have a discrete random variable $X$, which takes the values $x_i$ with probabilities $p_i$, then the mean is given by the weighted average: sum the values times the probability that the random variable takes on that value:
- `ctx_2b750c7f5d33f647672795c7`: Shape of `attention_weights`: # (`n_test`, `n_train`), where each row contains attention weights to be # assigned among the values (`y_train`) given each query attention_weights = npx.softmax(-(X_repeat - x_train)**2 / 2) # Each element of `y_hat` is weighted average of values, where weights are # attention weights y_hat = d2l.matmul(attention_weights, y_train) plot_kernel_reg(y_hat) ```

### Part-of-speech evidence

- `ctx_6bf957c26c6e143256cdd035`: When the weights are non-negative and sum to one (i.e., $\left(\sum_{i=1}^{d} {w_i} = 1\right)$), the dot product expresses a *weighted average*.
- `ctx_07d0a92774325109338bead5`: In practice, attention pooling aggregates values using weighted average, where weights are computed between the given query and different keys.

## 9. word embedding

- `sense_id`: `d2lce_ce222dd206341f61f2986f7a`
- Split: `development`
- Model definition: a technique or model family that maps words to real-valued vectors for representing them in NLP
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_a2831abdb2ca55617b3dda12`: The technique of mapping words to real vectors is called word embedding.
- `ctx_6a9b720f95aced72357fb01b`: In recent years, word embedding has gradually become the basic knowledge of natural language processing.
- `ctx_817ac1f3936900a301ec3337`: The technique of mapping words to real vectors is called *word embedding*.
- `ctx_6fa666b3c596ae376a5d62df`: # Word Embedding (word2vec) :label:`sec_word2vec`
- `ctx_108640f605901673bf814009`: In this section, we begin with the dataset for pretraining the word embedding model: the original format of the data will be transformed into minibatches that can be iterated over during training.

### Backup contexts

- `ctx_bb5ae27beb47e44884fd922c`: Let us begin by maximizing the joint probability of all such events in text sequences to train word embeddings.
- `ctx_a988c294df2c935abfa24586`: Thus, when training word embedding models, high-frequency words can be *subsampled* :cite:`Mikolov.Sutskever.Chen.ea.2013`.
- `ctx_f749ad3cd3bc4c80f1a78ce4`: # The Dataset for Pretraining Word Embeddings :label:`sec_word2vec_data`

### Contrastive contexts

- `ctxx_36cabf1c66f9b4ec24b89888`: Synthetic: In graphic design, the artist used word embedding to place text objects inside a logo shape.

### Definition evidence

- `ctx_817ac1f3936900a301ec3337`: The technique of mapping words to real vectors is called *word embedding*.
- `ctx_a2831abdb2ca55617b3dda12`: The technique of mapping words to real vectors is called word embedding.
- `ctx_108640f605901673bf814009`: In this section, we begin with the dataset for pretraining the word embedding model: the original format of the data will be transformed into minibatches that can be iterated over during training.

### Part-of-speech evidence

- `ctx_817ac1f3936900a301ec3337`: The technique of mapping words to real vectors is called *word embedding*.
- `ctx_108640f605901673bf814009`: In this section, we begin with the dataset for pretraining the word embedding model: the original format of the data will be transformed into minibatches that can be iterated over during training.

## 10. zero mean

- `sense_id`: `d2lce_eae5d94b4d2b73165c5d8795`
- Split: `development`
- Model definition: having an average value of 0 in a distribution or dataset
- Model POS: `adjective_phrase`

### Primary contexts

- `ctx_7c400e0ce4ae692c14fd57fb`: After applying standardization, the resulting minibatch has zero mean and unit variance.
- `ctx_26d890099027986105691faa`: We choose our label to be a linear function of our inputs, corrupted by Gaussian noise with zero mean and standard deviation 0.01.
- `ctx_2aa7827d7befde055f8781f4`: Typically, the Xavier initialization samples weights from a Gaussian distribution with zero mean and variance $\sigma^2 = \frac{2}{n_\mathrm{in} + n_\mathrm{out}}$.
- `ctx_61a2ce5d13e9164d72ba2a8e`: where $\epsilon$ obeys a normal distribution with zero mean and standard deviation 0.5.
- `ctx_6fbe686636eef2e18f361982`: Again, we initialize the weights at random with zero mean and standard deviation 0.01.

### Backup contexts

- `ctx_216f6113933e493b68ce8ad9`: Furthermore, let us assume that this distribution has zero mean and variance $\sigma^2$.
- `ctx_4638d23246a5ab6b7fa414b4`: For now, let us assume that the inputs to the layer $x_j$ also have zero mean and variance $\gamma^2$ and that they are independent of $w_{ij}$ and independent of each other.
- `ctx_a0f2cf276864d055204f2564`: The prior $p(\Theta)$ is a normal distribution with zero mean and variance-covariance matrix $\Sigma_\Theta$.

### Contrastive contexts

- `ctxx_43cadbfc0b9eb9648f51f1d6`: Synthetic: In this toy example, the phrase zero mean describes a distribution centered at 0, not a zero-valued sample.

### Definition evidence

- `ctx_7c400e0ce4ae692c14fd57fb`: After applying standardization, the resulting minibatch has zero mean and unit variance.
- `ctx_26d890099027986105691faa`: We choose our label to be a linear function of our inputs, corrupted by Gaussian noise with zero mean and standard deviation 0.01.
- `ctx_2aa7827d7befde055f8781f4`: Typically, the Xavier initialization samples weights from a Gaussian distribution with zero mean and variance $\sigma^2 = \frac{2}{n_\mathrm{in} + n_\mathrm{out}}$.

### Part-of-speech evidence

- `ctx_7c400e0ce4ae692c14fd57fb`: After applying standardization, the resulting minibatch has zero mean and unit variance.
- `ctx_4638d23246a5ab6b7fa414b4`: For now, let us assume that the inputs to the layer $x_j$ also have zero mean and variance $\gamma^2$ and that they are independent of $w_{ij}$ and independent of each other.
