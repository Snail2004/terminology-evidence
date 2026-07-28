# Stage A sense casebook: development_007

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. nonvolitional cue

- `sense_id`: `d2lce_abae8f75b732ffe9c8a965c0`
- Split: `development`
- Model definition: an attention cue arising automatically from salient sensory input rather than deliberate intention
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_1078723c87f441d3c978087a`: The nonvolitional cue is based on the saliency and conspicuity of objects in the environment.
- `ctx_6f54563163ae90a7881eb6fe`: To begin with, consider the simpler case where only nonvolitional cues are available.
- `ctx_6e3c3388630aea54771ba51c`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_b24d7938abbc76287221b851`: ![Using the nonvolitional cue based on saliency (red cup, non-paper), attention is involuntarily directed to the coffee.](../img/eye-coffee.svg) :width:`400px` :label:`fig_eye-coffee`
- `ctx_d4a06af98b28daa12e898464`: In this framework, subjects selectively direct the spotlight of attention using both the *nonvolitional cue* and *volitional cue*.

### Backup contexts

- `ctx_d3cdd3abd54093da62a2cc19`: More generally, every value is paired with a *key*, which can be thought of the nonvolitional cue of that sensory input.
- `ctx_b5ad8a4aa3e90970b3a0f97a`: ![Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).](../img/qkv.svg) :label:`fig_qkv`
- `ctx_f0330e5bbe33531cd9316565`: * Attention mechanisms bias selection over values (sensory inputs) via attention pooling, which incorporates queries (volitional cues) and keys (nonvolitional cues).

### Contrastive contexts

- `ctxx_015c489f82e2cf03ab841d57`: Synthetic: In psychology, a nonvolitional cue can pull attention to a bright object even when the observer intends to look elsewhere.

### Definition evidence

- `ctx_d4a06af98b28daa12e898464`: In this framework, subjects selectively direct the spotlight of attention using both the *nonvolitional cue* and *volitional cue*.
- `ctx_1078723c87f441d3c978087a`: The nonvolitional cue is based on the saliency and conspicuity of objects in the environment.
- `ctx_6e3c3388630aea54771ba51c`: As shown in :numref:`fig_qkv`, we can design attention pooling so that the given query (volitional cue) can interact with keys (nonvolitional cues), which guides bias selection over values (sensory inputs).
- `ctx_d3cdd3abd54093da62a2cc19`: More generally, every value is paired with a *key*, which can be thought of the nonvolitional cue of that sensory input.

### Part-of-speech evidence

- `ctx_d4a06af98b28daa12e898464`: In this framework, subjects selectively direct the spotlight of attention using both the *nonvolitional cue* and *volitional cue*.
- `ctx_1078723c87f441d3c978087a`: The nonvolitional cue is based on the saliency and conspicuity of objects in the environment.

## 2. null hypothesis

- `sense_id`: `d2lce_11e1c294000ac67785408dcd`
- Split: `development`
- Model definition: the default hypothesis in significance testing that is tested for possible rejection using observed data.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_a5a1f0f18709f7fa8442aea2`: We refer the default statement as the *null hypothesis* $H_0$, which we try to reject using the observed data.
- `ctx_22557e183923aa9f4d962fb5`: The *alternative hypothesis* $H_A$ (or $H_1$) is a statement that is contrary to the null hypothesis.
- `ctx_f4392f740a7e9df79b8c5e6a`: If we can now show that the null hypothesis is very unlikely to be true, we may reject it with confidence.
- `ctx_e4f5d547b5a2e976a337fefd`: In this case, our null hypothesis will be that there is no difference between the two groups, and our alternate will be that there is.
- `ctx_3b89d2852c572ba5f6a4df35`: A null hypothesis is often stated in a declarative form which posits a relationship between variables.

### Backup contexts

- `ctx_0c97ab4184b145c22144afa1`: The significance level can be explained as the level of risk that we are willing to take, when we reject a true null hypothesis.
- `ctx_4a439805e5ee6481bd8ca2d7`: The *statistical significance* measures the probability of erroneously rejecting the null hypothesis, $H_0$, when it should not be rejected, i.e.,
- `ctx_78f8341f577bbf7e3922131c`: Following that, the modern significance testing is the intelligence heritage by Karl Pearson who invented $p$-value and Pearson's chi-squared test, William Gosset who is the father of Student's t-distribution, and Ronald Fisher who initialed the null hypothesis and the significance test.

### Contrastive contexts

- `ctxx_ee2a54b1abc918e1f611434e`: Synthetic: A scientific hypothesis can be any proposed explanation, but a null hypothesis is the specific default claim tested for rejection.

### Definition evidence

- `ctx_a5a1f0f18709f7fa8442aea2`: We refer the default statement as the *null hypothesis* $H_0$, which we try to reject using the observed data.
- `ctx_22557e183923aa9f4d962fb5`: The *alternative hypothesis* $H_A$ (or $H_1$) is a statement that is contrary to the null hypothesis.
- `ctx_f4392f740a7e9df79b8c5e6a`: If we can now show that the null hypothesis is very unlikely to be true, we may reject it with confidence.

### Part-of-speech evidence

- `ctx_22557e183923aa9f4d962fb5`: The *alternative hypothesis* $H_A$ (or $H_1$) is a statement that is contrary to the null hypothesis.
- `ctx_a5a1f0f18709f7fa8442aea2`: We refer the default statement as the *null hypothesis* $H_0$, which we try to reject using the observed data.
- `ctx_4a439805e5ee6481bd8ca2d7`: The *statistical significance* measures the probability of erroneously rejecting the null hypothesis, $H_0$, when it should not be rejected, i.e.,

## 3. object detection model

- `sense_id`: `d2lce_1cc990a2aa4f03a55ea8c851`
- Split: `development`
- Model definition: a model that detects objects in an image by predicting their classes and locations.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_75539ee50da6b74f48edbf25`: In a nutshell, via its base network and several multiscale feature map blocks, single-shot multibox detection generates a varying number of anchor boxes with different sizes, and detects varying-size objects by predicting classes and offsets of these anchor boxes (thus the bounding boxes); thus, this is a multiscale object detection model.
- `ctx_a80a0f96555a881e8a2d64e2`: Now we are ready to use such background knowledge to design an object detection model: single shot multibox detection (SSD) :cite:`Liu.Anguelov.Erhan.ea.2016`.
- `ctx_37042d54237b28f1a02cd33b`: * Single shot multibox detection is a multiscale object detection model.
- `ctx_d86d6e76e7a6fb556d8b58fe`: ![As a multiscale object detection model, single-shot multibox detection mainly consists of a base network followed by several multiscale feature map blocks.](../img/ssd.svg) :label:`fig_ssd`
- `ctx_ae46b94d1a1ad441b6292470`: In order to train an object detection model, we need *class* and *offset* labels for each anchor box, where the former is the class of the object relevant to the anchor box and the latter is the offset of the ground-truth bounding box relative to the anchor box.

### Backup contexts

- `ctx_19f05cc4fb14916ea6c8830b`: At the current scale, the object detection model needs to predict the classes and offsets of $hw$ sets of anchor boxes on the input image, where different sets have different centers.
- `ctx_a91676d4a36f289125221b76`: We will design an object detection model based on anchor boxes in :numref:`sec_ssd`.
- `ctx_8e94e3fe2eccae4e18df81ce`: For a predicted bounding box $B$, the object detection model calculates the predicted likelihood for each class.

### Contrastive contexts

- `ctxx_c825c790f8c9fea20851505b`: Synthetic: Object detection is the task, while an object detection model is the trained network that performs it.

### Definition evidence

- `ctx_ae46b94d1a1ad441b6292470`: In order to train an object detection model, we need *class* and *offset* labels for each anchor box, where the former is the class of the object relevant to the anchor box and the latter is the offset of the ground-truth bounding box relative to the anchor box.
- `ctx_75539ee50da6b74f48edbf25`: In a nutshell, via its base network and several multiscale feature map blocks, single-shot multibox detection generates a varying number of anchor boxes with different sizes, and detects varying-size objects by predicting classes and offsets of these anchor boxes (thus the bounding boxes); thus, this is a multiscale object detection model.

### Part-of-speech evidence

- `ctx_a91676d4a36f289125221b76`: We will design an object detection model based on anchor boxes in :numref:`sec_ssd`.
- `ctx_a80a0f96555a881e8a2d64e2`: Now we are ready to use such background knowledge to design an object detection model: single shot multibox detection (SSD) :cite:`Liu.Anguelov.Erhan.ea.2016`.

## 4. objective

- `sense_id`: `d2lce_cf168d11faf5e675efa7e0a3`
- Split: `development`
- Model definition: the goal being optimized in learning or optimization; often the quantity expressed by an objective function
- Model POS: `noun`

### Primary contexts

- `ctx_e8877b610c0af1e834561705`: An *algorithm* to adjust the model's parameters to optimize the objective function.
- `ctx_622b0a2786bbcaf9095a093c`: Indeed, anyone content with treating optimization as a black box device to minimize objective functions in a simple setting might well content oneself with the knowledge that there exists an array of incantations of such a procedure (with names such as "SGD" and "Adam").
- `ctx_6f97e9a634e8f6551250acc0`: Negative sampling modifies the original objective function.
- `ctx_3b91b2f9f2875a350642ef75`: Thus we replace our original objective, *minimizing the prediction loss on the training labels*, with new objective, *minimizing the sum of the prediction loss and the penalty term*.
- `ctx_71e1b52a108cecca970b6aef`: Note that a single neuron (i) takes some set of inputs; (ii) generates a corresponding scalar output; and (iii) has a set of associated parameters that can be updated to optimize some objective function of interest.

### Backup contexts

- `ctx_654d5b054d1a8a6629be86be`: While you can already get your hands dirty using only the information above, in the following we can more formally motivate the squared loss objective via assumptions about the distribution of noise.
- `ctx_254e012e0fc7f6d2b7e12488`: Through elementwise multiplications, zeros in the mask variable will filter out negative class offsets before calculating the objective function.
- `ctx_2fe7c674ada36093ebc54726`: Let us further assume that the objective function $f$ is well behaved, say, *Lipschitz continuous* with constant $L$.

### Contrastive contexts

- `ctxx_288b025e2226d308d6374f8f`: Synthetic: The training objective is to minimize prediction error plus regularization.

### Definition evidence

- `ctx_e8877b610c0af1e834561705`: An *algorithm* to adjust the model's parameters to optimize the objective function.
- `ctx_3b91b2f9f2875a350642ef75`: Thus we replace our original objective, *minimizing the prediction loss on the training labels*, with new objective, *minimizing the sum of the prediction loss and the penalty term*.
- `ctx_71e1b52a108cecca970b6aef`: Note that a single neuron (i) takes some set of inputs; (ii) generates a corresponding scalar output; and (iii) has a set of associated parameters that can be updated to optimize some objective function of interest.
- `ctx_6f97e9a634e8f6551250acc0`: Negative sampling modifies the original objective function.

### Part-of-speech evidence

- `ctx_e8877b610c0af1e834561705`: An *algorithm* to adjust the model's parameters to optimize the objective function.
- `ctx_3b91b2f9f2875a350642ef75`: Thus we replace our original objective, *minimizing the prediction loss on the training labels*, with new objective, *minimizing the sum of the prediction loss and the penalty term*.

## 5. offsets

- `sense_id`: `d2lce_e749bbd007351d6963f2bbd0`
- Split: `development`
- Model definition: values or positional shifts that indicate displacement relative to a reference, such as pixel centers, sequence positions, or box coordinates
- Model POS: `noun`

### Primary contexts

- `ctx_9af45708693a272ccbee02ce`: ```{.python .input} #@tab pytorch #@save def multibox_prior(data, sizes, ratios): """Generate anchor boxes with different shapes centered on each pixel.""" in_height, in_width = data.shape[-2:] device, num_sizes, num_ratios = data.device, len(sizes), len(ratios) boxes_per_pixel = (num_sizes + num_ratios - 1) size_tensor = d2l.tensor(sizes, device=device) ratio_tensor = d2l.tensor(ratios, device=device) # Offsets are required to move the anchor to the center of a pixel.
- `ctx_993688889952b7346efdcaf7`: During the prediction, for each image we generate multiple anchor boxes, predict classes and offsets for all the anchor boxes, adjust their positions according to the predicted offsets to obtain the predicted bounding boxes, and finally only output those predicted bounding boxes that satisfy certain criteria.
- `ctx_00060c0d518148705d609385`: ```{.python .input} #@save def multibox_prior(data, sizes, ratios): """Generate anchor boxes with different shapes centered on each pixel.""" in_height, in_width = data.shape[-2:] device, num_sizes, num_ratios = data.ctx, len(sizes), len(ratios) boxes_per_pixel = (num_sizes + num_ratios - 1) size_tensor = d2l.tensor(sizes, ctx=device) ratio_tensor = d2l.tensor(ratios, ctx=device) # Offsets are required to move the anchor to the center of a pixel.
- `ctx_11250deeba2dfb3a9290f422`: Given varying positions and sizes of different boxes in the dataset, we can apply transformations to those relative positions and sizes that may lead to more uniformly distributed offsets that are easier to fit.
- `ctx_7c03da734cfb73140f39675c`: The indices $a$ and $b$ run over both positive and negative offsets, covering the entire image.

### Backup contexts

- `ctx_fa4857a0dd6e85e72fbd8c3a`: ### Labeling Classes and Offsets
- `ctx_8b947d5e873543c5099e853b`: ![Different offsets lead to different subsequences when splitting up text.](../img/timemachine-5gram.svg) :label:`fig_timemachine_5gram`
- `ctx_f8448e2bed424bbc3037f2af`: ```{.python .input n=13} #@save class CTRDataset(gluon.data.Dataset): def __init__(self, data_path, feat_mapper=None, defaults=None, min_threshold=4, num_feat=34): self.NUM_FEATS, self.count, self.data = num_feat, 0, {} feat_cnts = defaultdict(lambda: defaultdict(int)) self.feat_mapper, self.defaults = feat_mapper, defaults self.field_dims = np.zeros(self.NUM_FEATS, dtype=np.int64) with open(data_path) as f: for line in f: instance = {} values = line.rstrip('\n').split('\t') if len(values) != self.NUM_FEATS + 1: continue label = np.float32([0, 0]) label[int(values[0])] = 1 instance['y'] = [np.float32(values[0])] for i in range(1, self.NUM_FEATS + 1): feat_cnts[i][values[i]] += 1 instance.setdefault('x', []).append(values[i]) self.data[self.count] = instance self.count = self.count + 1 if self.feat_mapper is None and self.defaults is None: feat_mapper = {i: {feat for feat, c in cnt.items() if c >= min_threshold} for i, cnt in feat_cnts.items()} self.feat_mapper = {i: {feat_v: idx for idx, feat_v in enumerate(feat_values)} for i, feat_values in feat_mapper.items()} self.defaults = {i: len(feat_values) for i, feat_values in feat_mapper.items()} for i, fm in self.feat_mapper.items(): self.field_dims[i - 1] = len(fm) + 1 self.offsets = np.array((0, *np.cumsum(self.field_dims).asnumpy() [:-1])) def __len__(self): return self.count def __getitem__(self, idx): feat = np.array([self.feat_mapper[i + 1].get(v, self.defaults[i + 1]) for i, v in enumerate(self.data[idx]['x'])]) return feat + self.offsets, self.data[idx]['y'] ```

### Contrastive contexts

- `ctxx_10cb8156b50875d285114451`: Synthetic: In accounting, offsets are balancing entries that reduce a debt rather than position shifts.

### Definition evidence

- `ctx_7c03da734cfb73140f39675c`: The indices $a$ and $b$ run over both positive and negative offsets, covering the entire image.
- `ctx_8b947d5e873543c5099e853b`: ![Different offsets lead to different subsequences when splitting up text.](../img/timemachine-5gram.svg) :label:`fig_timemachine_5gram`
- `ctx_00060c0d518148705d609385`: ```{.python .input} #@save def multibox_prior(data, sizes, ratios): """Generate anchor boxes with different shapes centered on each pixel.""" in_height, in_width = data.shape[-2:] device, num_sizes, num_ratios = data.ctx, len(sizes), len(ratios) boxes_per_pixel = (num_sizes + num_ratios - 1) size_tensor = d2l.tensor(sizes, ctx=device) ratio_tensor = d2l.tensor(ratios, ctx=device) # Offsets are required to move the anchor to the center of a pixel.
- `ctx_f8448e2bed424bbc3037f2af`: ```{.python .input n=13} #@save class CTRDataset(gluon.data.Dataset): def __init__(self, data_path, feat_mapper=None, defaults=None, min_threshold=4, num_feat=34): self.NUM_FEATS, self.count, self.data = num_feat, 0, {} feat_cnts = defaultdict(lambda: defaultdict(int)) self.feat_mapper, self.defaults = feat_mapper, defaults self.field_dims = np.zeros(self.NUM_FEATS, dtype=np.int64) with open(data_path) as f: for line in f: instance = {} values = line.rstrip('\n').split('\t') if len(values) != self.NUM_FEATS + 1: continue label = np.float32([0, 0]) label[int(values[0])] = 1 instance['y'] = [np.float32(values[0])] for i in range(1, self.NUM_FEATS + 1): feat_cnts[i][values[i]] += 1 instance.setdefault('x', []).append(values[i]) self.data[self.count] = instance self.count = self.count + 1 if self.feat_mapper is None and self.defaults is None: feat_mapper = {i: {feat for feat, c in cnt.items() if c >= min_threshold} for i, cnt in feat_cnts.items()} self.feat_mapper = {i: {feat_v: idx for idx, feat_v in enumerate(feat_values)} for i, feat_values in feat_mapper.items()} self.defaults = {i: len(feat_values) for i, feat_values in feat_mapper.items()} for i, fm in self.feat_mapper.items(): self.field_dims[i - 1] = len(fm) + 1 self.offsets = np.array((0, *np.cumsum(self.field_dims).asnumpy() [:-1])) def __len__(self): return self.count def __getitem__(self, idx): feat = np.array([self.feat_mapper[i + 1].get(v, self.defaults[i + 1]) for i, v in enumerate(self.data[idx]['x'])]) return feat + self.offsets, self.data[idx]['y'] ```
- `ctx_9af45708693a272ccbee02ce`: ```{.python .input} #@tab pytorch #@save def multibox_prior(data, sizes, ratios): """Generate anchor boxes with different shapes centered on each pixel.""" in_height, in_width = data.shape[-2:] device, num_sizes, num_ratios = data.device, len(sizes), len(ratios) boxes_per_pixel = (num_sizes + num_ratios - 1) size_tensor = d2l.tensor(sizes, device=device) ratio_tensor = d2l.tensor(ratios, device=device) # Offsets are required to move the anchor to the center of a pixel.
- `ctx_993688889952b7346efdcaf7`: During the prediction, for each image we generate multiple anchor boxes, predict classes and offsets for all the anchor boxes, adjust their positions according to the predicted offsets to obtain the predicted bounding boxes, and finally only output those predicted bounding boxes that satisfy certain criteria.
- `ctx_fa4857a0dd6e85e72fbd8c3a`: ### Labeling Classes and Offsets
- `ctx_11250deeba2dfb3a9290f422`: Given varying positions and sizes of different boxes in the dataset, we can apply transformations to those relative positions and sizes that may lead to more uniformly distributed offsets that are easier to fit.

### Part-of-speech evidence

- `ctx_7c03da734cfb73140f39675c`: The indices $a$ and $b$ run over both positive and negative offsets, covering the entire image.
- `ctx_00060c0d518148705d609385`: ```{.python .input} #@save def multibox_prior(data, sizes, ratios): """Generate anchor boxes with different shapes centered on each pixel.""" in_height, in_width = data.shape[-2:] device, num_sizes, num_ratios = data.ctx, len(sizes), len(ratios) boxes_per_pixel = (num_sizes + num_ratios - 1) size_tensor = d2l.tensor(sizes, ctx=device) ratio_tensor = d2l.tensor(ratios, ctx=device) # Offsets are required to move the anchor to the center of a pixel.
- `ctx_993688889952b7346efdcaf7`: During the prediction, for each image we generate multiple anchor boxes, predict classes and offsets for all the anchor boxes, adjust their positions according to the predicted offsets to obtain the predicted bounding boxes, and finally only output those predicted bounding boxes that satisfy certain criteria.

## 6. output gate

- `sense_id`: `d2lce_c6b4477a845e2e0e0e02f088`
- Split: `development`
- Model definition: the LSTM gate that controls how much memory information is exposed to the output at a time step.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_df998c3c68076fd4dfeea859`: Whenever the output gate approximates 1 we effectively pass all memory information through to the predictor, whereas for the output gate close to 0 we retain all the information only within the memory cell and perform no further processing.
- `ctx_ce0994b03956d4032b57ec95`: ```{.python .input} def get_lstm_params(vocab_size, num_hiddens, device): num_inputs = num_outputs = vocab_size def normal(shape): return np.random.normal(scale=0.01, size=shape, ctx=device) def three(): return (normal((num_inputs, num_hiddens)), normal((num_hiddens, num_hiddens)), np.zeros(num_hiddens, ctx=device)) W_xi, W_hi, b_i = three() # Input gate parameters W_xf, W_hf, b_f = three() # Forget gate parameters W_xo, W_ho, b_o = three() # Output gate parameters W_xc, W_hc, b_c = three() # Candidate memory cell parameters # Output layer parameters W_hq = normal((num_hiddens, num_outputs)) b_q = np.zeros(num_outputs, ctx=device) # Attach gradients params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc, b_c, W_hq, b_q] for param in params: param.attach_grad() return params ```
- `ctx_1236c8eedefbed662cef9104`: ### Input Gate, Forget Gate, and Output Gate
- `ctx_4a8ce9c7f087c3d08d32ccad`: ![Computing the input gate, the forget gate, and the output gate in an LSTM model.](../img/lstm-0.svg) :label:`lstm_0`
- `ctx_044bf29b52339083b6accce1`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.

### Backup contexts

- `ctx_83304deb770138c0273a3f19`: ```{.python .input} #@tab pytorch def get_lstm_params(vocab_size, num_hiddens, device): num_inputs = num_outputs = vocab_size def normal(shape): return torch.randn(size=shape, device=device)*0.01 def three(): return (normal((num_inputs, num_hiddens)), normal((num_hiddens, num_hiddens)), d2l.zeros(num_hiddens, device=device)) W_xi, W_hi, b_i = three() # Input gate parameters W_xf, W_hf, b_f = three() # Forget gate parameters W_xo, W_ho, b_o = three() # Output gate parameters W_xc, W_hc, b_c = three() # Candidate memory cell parameters # Output layer parameters W_hq = normal((num_hiddens, num_outputs)) b_q = d2l.zeros(num_outputs, device=device) # Attach gradients params = [W_xi, W_hi, b_i, W_xf, W_hf, b_f, W_xo, W_ho, b_o, W_xc, W_hc, b_c, W_hq, b_q] for param in params: param.requires_grad_(True) return params ```
- `ctx_ba0d3fd808401fd086323e3f`: This is where the output gate comes into play.
- `ctx_6143b29417b0fe55f7875c10`: We will refer to this as the *output gate*.

### Contrastive contexts

- `ctxx_821e879eea68458c73930916`: Synthetic: In digital electronics, an output gate may refer to a circuit output stage, not an LSTM component.

### Definition evidence

- `ctx_044bf29b52339083b6accce1`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.
- `ctx_df998c3c68076fd4dfeea859`: Whenever the output gate approximates 1 we effectively pass all memory information through to the predictor, whereas for the output gate close to 0 we retain all the information only within the memory cell and perform no further processing.

### Part-of-speech evidence

- `ctx_6143b29417b0fe55f7875c10`: We will refer to this as the *output gate*.
- `ctx_044bf29b52339083b6accce1`: Correspondingly, the gates at time step $t$ are defined as follows: the input gate is $\mathbf{I}_t \in \mathbb{R}^{n \times h}$, the forget gate is $\mathbf{F}_t \in \mathbb{R}^{n \times h}$, and the output gate is $\mathbf{O}_t \in \mathbb{R}^{n \times h}$.

## 7. pooling layer

- `sense_id`: `d2lce_2b9f63478b6ef59511a4f930`
- Split: `development`
- Model definition: a neural network layer that aggregates nearby values, typically reducing spatial sensitivity and downsampling without learnable kernel parameters
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_e3ef71ac342723539664fb0b`: ```{.python .input} class TextCNN(nn.Block): def __init__(self, vocab_size, embed_size, kernel_sizes, num_channels, **kwargs): super(TextCNN, self).__init__(**kwargs) self.embedding = nn.Embedding(vocab_size, embed_size) # The embedding layer not to be trained self.constant_embedding = nn.Embedding(vocab_size, embed_size) self.dropout = nn.Dropout(0.5) self.decoder = nn.Dense(2) # The max-over-time pooling layer has no parameters, so this instance # can be shared self.pool = nn.GlobalMaxPool1D() # Create multiple one-dimensional convolutional layers self.convs = nn.Sequential() for c, k in zip(num_channels, kernel_sizes): self.convs.add(nn.Conv1D(c, k, activation='relu')) def forward(self, inputs): # Concatenate two embedding layer outputs with shape (batch size, no.
- `ctx_fc7040b8bb11e8f5908a5b2e`: In :numref:`sec_pooling`, we explained that the pooling layer can reduce the sensitivity of a convolutional layer to the target position.
- `ctx_5b2b6c454358b72cbc4ddf00`: This section introduces *pooling layers*, which serve the dual purposes of mitigating the sensitivity of convolutional layers to location and of spatially downsampling representations.
- `ctx_f99c821572f5bad6256c826c`: However, unlike the cross-correlation computation of the inputs and kernels in the convolutional layer, the pooling layer contains no parameters (there is no *kernel*).
- `ctx_5e4de4eeef8a8e535e757172`: In addition, after the first, second, and fifth convolutional layers, the network adds maximum pooling layers with a window shape of $3\times3$ and a stride of 2.

### Backup contexts

- `ctx_d73510d8bcc8b4db2d674358`: Moreover, we remove the maximum pooling layer.
- `ctx_2caa9497e1430c49c9c6179e`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_8e23dd2d6763c4ee696bb066`: Therefore, what sets attention mechanisms apart from those fully-connected layers or pooling layers is the inclusion of the volitional cues.

### Contrastive contexts

- `ctxx_72700cb3a60e1d3db06d223e`: Synthetic: The resort's pooling layer is the final tile coating applied inside the swimming pool.

### Definition evidence

- `ctx_fc7040b8bb11e8f5908a5b2e`: In :numref:`sec_pooling`, we explained that the pooling layer can reduce the sensitivity of a convolutional layer to the target position.
- `ctx_5b2b6c454358b72cbc4ddf00`: This section introduces *pooling layers*, which serve the dual purposes of mitigating the sensitivity of convolutional layers to location and of spatially downsampling representations.
- `ctx_f99c821572f5bad6256c826c`: However, unlike the cross-correlation computation of the inputs and kernels in the convolutional layer, the pooling layer contains no parameters (there is no *kernel*).

### Part-of-speech evidence

- `ctx_2caa9497e1430c49c9c6179e`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_d73510d8bcc8b4db2d674358`: Moreover, we remove the maximum pooling layer.
- `ctx_f99c821572f5bad6256c826c`: However, unlike the cross-correlation computation of the inputs and kernels in the convolutional layer, the pooling layer contains no parameters (there is no *kernel*).

## 8. positional embeddings

- `sense_id`: `d2lce_d96258f97579b9b414c21815`
- Split: `development`
- Model definition: vector representations that encode token positions in a sequence and are added to other input embeddings
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_b36e02e023df099b64aa3633`: Common in the transformer encoder, positional embeddings are added at every position of the BERT input sequence.
- `ctx_de666609a3f80804219b8277`: However, different from the original transformer encoder, BERT uses *learnable* positional embeddings.
- `ctx_b86239fbecdd4400667164fa`: ```{.python .input} #@tab pytorch #@save class BERTEncoder(nn.Module): """BERT encoder.""" def __init__(self, vocab_size, num_hiddens, norm_shape, ffn_num_input, ffn_num_hiddens, num_heads, num_layers, dropout, max_len=1000, key_size=768, query_size=768, value_size=768, **kwargs): super(BERTEncoder, self).__init__(**kwargs) self.token_embedding = nn.Embedding(vocab_size, num_hiddens) self.segment_embedding = nn.Embedding(2, num_hiddens) self.blks = nn.Sequential() for i in range(num_layers): self.blks.add_module(f"{i}", d2l.EncoderBlock( key_size, query_size, value_size, num_hiddens, norm_shape, ffn_num_input, ffn_num_hiddens, num_heads, dropout, True)) # In BERT, positional embeddings are learnable, thus we create a # parameter of positional embeddings that are long enough self.pos_embedding = nn.Parameter(torch.randn(1, max_len, num_hiddens)) def forward(self, tokens, segments, valid_lens): # Shape of `X` remains unchanged in the following code snippet: # (batch size, max sequence length, `num_hiddens`) X = self.token_embedding(tokens) + self.segment_embedding(segments) X = X + self.pos_embedding.data[:, :X.shape[1], :] for blk in self.blks: X = blk(X, valid_lens) return X ```
- `ctx_bb968ec70a7eddfb7572bf84`: To sum up, :numref:`fig_bert-input` shows that the embeddings of the BERT input sequence are the sum of the token embeddings, segment embeddings, and positional embeddings.
- `ctx_2e2c010ed9f3e5f77a7ac3a1`: ```{.python .input} #@save class BERTEncoder(nn.Block): """BERT encoder.""" def __init__(self, vocab_size, num_hiddens, ffn_num_hiddens, num_heads, num_layers, dropout, max_len=1000, **kwargs): super(BERTEncoder, self).__init__(**kwargs) self.token_embedding = nn.Embedding(vocab_size, num_hiddens) self.segment_embedding = nn.Embedding(2, num_hiddens) self.blks = nn.Sequential() for _ in range(num_layers): self.blks.add(d2l.EncoderBlock( num_hiddens, ffn_num_hiddens, num_heads, dropout, True)) # In BERT, positional embeddings are learnable, thus we create a # parameter of positional embeddings that are long enough self.pos_embedding = self.params.get('pos_embedding', shape=(1, max_len, num_hiddens)) def forward(self, tokens, segments, valid_lens): # Shape of `X` remains unchanged in the following code snippet: # (batch size, max sequence length, `num_hiddens`) X = self.token_embedding(tokens) + self.segment_embedding(segments) X = X + self.pos_embedding.data(ctx=X.ctx)[:, :X.shape[1], :] for blk in self.blks: X = blk(X, valid_lens) return X ```

### Backup contexts

- `ctx_c9b63496779ed532f23eb959`: * The embeddings of the BERT input sequence are the sum of the token embeddings, segment embeddings, and positional embeddings.
- `ctx_f22071ca36597da8b867623d`: ![The embeddings of the BERT input sequence are the sum of the token embeddings, segment embeddings, and positional embeddings.](../img/bert-input.svg) :label:`fig_bert-input`
- `ctx_1caf4d22bfae71a85895f2f0`: Different from `TransformerEncoder`, `BERTEncoder` uses segment embeddings and learnable positional embeddings.

### Contrastive contexts

- `ctxx_7135e843d205a1df7aacad41`: Synthetic: In image editing, “positional embeddings” could be misused to mean coordinates pasted into metadata, not neural sequence representations.

### Definition evidence

- `ctx_b36e02e023df099b64aa3633`: Common in the transformer encoder, positional embeddings are added at every position of the BERT input sequence.
- `ctx_bb968ec70a7eddfb7572bf84`: To sum up, :numref:`fig_bert-input` shows that the embeddings of the BERT input sequence are the sum of the token embeddings, segment embeddings, and positional embeddings.
- `ctx_de666609a3f80804219b8277`: However, different from the original transformer encoder, BERT uses *learnable* positional embeddings.

### Part-of-speech evidence

- `ctx_b36e02e023df099b64aa3633`: Common in the transformer encoder, positional embeddings are added at every position of the BERT input sequence.
- `ctx_de666609a3f80804219b8277`: However, different from the original transformer encoder, BERT uses *learnable* positional embeddings.

## 9. positions

- `sense_id`: `d2lce_06b54fbb7406aced0daac405`
- Split: `development`
- Model definition: places or ordered locations of items, especially within a sequence or an image
- Model POS: `noun`

### Primary contexts

- `ctx_a72845dbe0a8b9e092650e9b`: In forward inference, it takes two inputs: the encoded result of `BERTEncoder` and the token positions for prediction.
- `ctx_5fe3b944f1a60bfc3b477089`: For example, we can crop an image in different ways to make the object of interest appear in different positions, thereby reducing the dependence of a model on the position of the object.
- `ctx_1cf2f1e5cdb9e7af829c8002`: Note that sequential operations prevent parallel computation, while a shorter path between any combination of sequence positions makes it easier to learn long-range dependencies within the sequence :cite:`Hochreiter.Bengio.Frasconi.ea.2001`.
- `ctx_2cd6faabab946087d3c1fb1c`: For question answering, the supervised learning's training objective is as straightforward as maximizing the log-likelihoods of the ground-truth start and end positions.
- `ctx_5238e6e3413873833910fa5d`: ```{.python .input} # Plus one to include the end-of-sequence token d2l.show_heatmaps( attention_weights[:, :, :, :len(engs[-1].split()) + 1], xlabel='Key positions', ylabel='Query positions') ```

### Backup contexts

- `ctx_9576eca6d7858c451dd930bc`: ```{.python .input} #@tab pytorch # Plus one to include the end-of-sequence token d2l.show_heatmaps( attention_weights[:, :, :, :len(engs[-1].split()) + 1].cpu(), xlabel='Key positions', ylabel='Query positions') ```
- `ctx_f297f857fe5597d369537a7a`: Here we use the $\text{prod}$ operator to multiply its arguments after the necessary operations, such as transposition and swapping input positions, have been carried out.

### Contrastive contexts

- `ctxx_e72f538b020e89cac916d4f3`: Synthetic: The bounding box positions are given as four coordinates.

### Definition evidence

- `ctx_f297f857fe5597d369537a7a`: Here we use the $\text{prod}$ operator to multiply its arguments after the necessary operations, such as transposition and swapping input positions, have been carried out.
- `ctx_5238e6e3413873833910fa5d`: ```{.python .input} # Plus one to include the end-of-sequence token d2l.show_heatmaps( attention_weights[:, :, :, :len(engs[-1].split()) + 1], xlabel='Key positions', ylabel='Query positions') ```
- `ctx_5fe3b944f1a60bfc3b477089`: For example, we can crop an image in different ways to make the object of interest appear in different positions, thereby reducing the dependence of a model on the position of the object.
- `ctx_a72845dbe0a8b9e092650e9b`: In forward inference, it takes two inputs: the encoded result of `BERTEncoder` and the token positions for prediction.
- `ctx_2cd6faabab946087d3c1fb1c`: For question answering, the supervised learning's training objective is as straightforward as maximizing the log-likelihoods of the ground-truth start and end positions.
- `ctx_9576eca6d7858c451dd930bc`: ```{.python .input} #@tab pytorch # Plus one to include the end-of-sequence token d2l.show_heatmaps( attention_weights[:, :, :, :len(engs[-1].split()) + 1].cpu(), xlabel='Key positions', ylabel='Query positions') ```
- `ctx_1cf2f1e5cdb9e7af829c8002`: Note that sequential operations prevent parallel computation, while a shorter path between any combination of sequence positions makes it easier to learn long-range dependencies within the sequence :cite:`Hochreiter.Bengio.Frasconi.ea.2001`.

### Part-of-speech evidence

- `ctx_f297f857fe5597d369537a7a`: Here we use the $\text{prod}$ operator to multiply its arguments after the necessary operations, such as transposition and swapping input positions, have been carried out.
- `ctx_5238e6e3413873833910fa5d`: ```{.python .input} # Plus one to include the end-of-sequence token d2l.show_heatmaps( attention_weights[:, :, :, :len(engs[-1].split()) + 1], xlabel='Key positions', ylabel='Query positions') ```
- `ctx_5fe3b944f1a60bfc3b477089`: For example, we can crop an image in different ways to make the object of interest appear in different positions, thereby reducing the dependence of a model on the position of the object.
- `ctx_a72845dbe0a8b9e092650e9b`: In forward inference, it takes two inputs: the encoded result of `BERTEncoder` and the token positions for prediction.

## 10. R-CNN

- `sense_id`: `d2lce_ad0d7cbd5f90ad33075e89aa`
- Split: `development`
- Model definition: a region-based convolutional neural network method for object detection.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_82a716f88498c45284012fbc`: The *R-CNN* first extracts many (e.g., 2000) *region proposals* from the input image (e.g., anchor boxes can also be considered as region proposals), labeling their classes and bounding boxes (e.g., offsets).
- `ctx_04626b072f9bfbcc966fac5c`: Besides single shot multibox detection described in :numref:`sec_ssd`, region-based CNNs or regions with CNN features (R-CNNs) are also among many pioneering approaches of applying deep learning to object detection :cite:`Girshick.Donahue.Darrell.ea.2014`.
- `ctx_42a91e8bb6e0449e3926152e`: ## R-CNNs
- `ctx_7b2934db82a8f5e942551192`: In this section, we will introduce the R-CNN and its series of improvements: the fast R-CNN :cite:`Girshick.2015`, the faster R-CNN :cite:`Ren.He.Girshick.ea.2015`, and the mask R-CNN :cite:`He.Gkioxari.Dollar.ea.2017`.
- `ctx_b71e137a4385ced462547be2`: # Region-based CNNs (R-CNNs) :label:`sec_rcnn`

### Backup contexts

- `ctx_824f6a3ffdf2593aacbb41d4`: :numref:`fig_r-cnn` shows the R-CNN model.
- `ctx_c3e2e6f9a837a104a2ffaacc`: ![The R-CNN model.](../img/r-cnn.svg) :label:`fig_r-cnn`
- `ctx_281feac9e302997ea88b1aea`: More concretely, the R-CNN consists of the following four steps:

### Contrastive contexts

- `ctxx_1f21c52c8120c8f15dfa2c07`: Synthetic: Unlike SSD, the R-CNN first generates region proposals before classification.

### Definition evidence

- `ctx_04626b072f9bfbcc966fac5c`: Besides single shot multibox detection described in :numref:`sec_ssd`, region-based CNNs or regions with CNN features (R-CNNs) are also among many pioneering approaches of applying deep learning to object detection :cite:`Girshick.Donahue.Darrell.ea.2014`.
- `ctx_82a716f88498c45284012fbc`: The *R-CNN* first extracts many (e.g., 2000) *region proposals* from the input image (e.g., anchor boxes can also be considered as region proposals), labeling their classes and bounding boxes (e.g., offsets).

### Part-of-speech evidence

- `ctx_b71e137a4385ced462547be2`: # Region-based CNNs (R-CNNs) :label:`sec_rcnn`
- `ctx_42a91e8bb6e0449e3926152e`: ## R-CNNs
