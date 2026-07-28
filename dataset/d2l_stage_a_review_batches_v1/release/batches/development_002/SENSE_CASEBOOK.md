# Stage A sense casebook: development_002

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. Caser

- `sense_id`: `d2lce_52085fef12f840d2350b2049`
- Split: `development`
- Model definition: A convolution-based sequential recommendation model that captures recent activity patterns and user preferences.
- Model POS: `proper_noun`

### Primary contexts

- `ctx_89f8785f0d47f0a72eb28a8d`: ## Model Implementation The following code implements the Caser model.
- `ctx_b400985b05d02328a55f0c52`: ```{.python .input n=4} class Caser(nn.Block): def __init__(self, num_factors, num_users, num_items, L=5, d=16, d_prime=4, drop_ratio=0.05, **kwargs): super(Caser, self).__init__(**kwargs) self.P = nn.Embedding(num_users, num_factors) self.Q = nn.Embedding(num_items, num_factors) self.d_prime, self.d = d_prime, d # Vertical convolution layer self.conv_v = nn.Conv2D(d_prime, (L, 1), in_channels=1) # Horizontal convolution layer h = [i + 1 for i in range(L)] self.conv_h, self.max_pool = nn.Sequential(), nn.Sequential() for i in h: self.conv_h.add(nn.Conv2D(d, (i, num_factors), in_channels=1)) self.max_pool.add(nn.MaxPool1D(L - i + 1)) # Fully-connected layer self.fc1_dim_v, self.fc1_dim_h = d_prime * num_factors, d * len(h) self.fc = nn.Dense(in_units=d_prime * num_factors + d * L, activation='relu', units=num_factors) self.Q_prime = nn.Embedding(num_items, num_factors * 2) self.b = nn.Embedding(num_items, 1) self.dropout = nn.Dropout(drop_ratio) def forward(self, user_id, seq, item_id): item_embs = np.expand_dims(self.Q(seq), 1) user_emb = self.P(user_id) out, out_h, out_v, out_hs = None, None, None, [] if self.d_prime: out_v = self.conv_v(item_embs) out_v = out_v.reshape(out_v.shape[0], self.fc1_dim_v) if self.d: for conv, maxp in zip(self.conv_h, self.max_pool): conv_out = np.squeeze(npx.relu(conv(item_embs)), axis=3) t = maxp(conv_out) pool_out = np.squeeze(t, axis=2) out_hs.append(pool_out) out_h = np.concatenate(out_hs, axis=1) out = np.concatenate([out_v, out_h], axis=1) z = self.fc(self.dropout(out)) x = np.concatenate([z, user_emb], axis=1) q_prime_i = np.squeeze(self.Q_prime(item_id)) b = np.squeeze(self.b(item_id)) res = (x * q_prime_i).sum(1) + b return res ```
- `ctx_c48fb3f822f811ccbb8750b6`: The model we will introduce, Caser :cite:`Tang.Wang.2018`, short for convolutional sequence embedding recommendation model, adopts convolutional neural networks capture the dynamic pattern influences of users' recent activities.
- `ctx_efedd61e884ed0fdc81eff25`: The main component of Caser consists of a horizontal convolutional network and a vertical convolutional network, aiming to uncover the union-level and point-level sequence patterns, respectively.
- `ctx_f3d1cfd65cb60c18b67864a5`: ```{.python .input n=7} devices = d2l.try_all_gpus() net = Caser(10, num_users, num_items, L) net.initialize(ctx=devices, force_reinit=True, init=mx.init.Normal(0.01)) lr, num_epochs, wd, optimizer = 0.04, 8, 1e-5, 'adam' loss = d2l.BPRLoss() trainer = gluon.Trainer(net.collect_params(), optimizer, {"learning_rate": lr, 'wd': wd}) d2l.train_ranking(net, train_iter, test_iter, loss, trainer, test_seq_iter, num_users, num_items, num_epochs, devices, d2l.evaluate_ranking, candidates, eval_step=1) ```

### Backup contexts

- `ctx_a07c31185d557a9cba947172`: The goal of Caser is to recommend item by considering user general tastes as well as short-term intention.
- `ctx_27b2e4936143566a8ca5e421`: The architecture of Caser is shown below:
- `ctx_26a6365155d601f3009c3236`: ![Illustration of the Caser Model](../img/rec-caser.svg)

### Contrastive contexts

- `ctxx_bf63c5eaf66d6b7ef991742c`: [Synthetic] Everyone in the lab called him Caser because he always carried old cassette cases.

### Definition evidence

- `ctx_c48fb3f822f811ccbb8750b6`: The model we will introduce, Caser :cite:`Tang.Wang.2018`, short for convolutional sequence embedding recommendation model, adopts convolutional neural networks capture the dynamic pattern influences of users' recent activities.
- `ctx_efedd61e884ed0fdc81eff25`: The main component of Caser consists of a horizontal convolutional network and a vertical convolutional network, aiming to uncover the union-level and point-level sequence patterns, respectively.
- `ctx_a07c31185d557a9cba947172`: The goal of Caser is to recommend item by considering user general tastes as well as short-term intention.

### Part-of-speech evidence

- `ctx_c48fb3f822f811ccbb8750b6`: The model we will introduce, Caser :cite:`Tang.Wang.2018`, short for convolutional sequence embedding recommendation model, adopts convolutional neural networks capture the dynamic pattern influences of users' recent activities.
- `ctx_b400985b05d02328a55f0c52`: ```{.python .input n=4} class Caser(nn.Block): def __init__(self, num_factors, num_users, num_items, L=5, d=16, d_prime=4, drop_ratio=0.05, **kwargs): super(Caser, self).__init__(**kwargs) self.P = nn.Embedding(num_users, num_factors) self.Q = nn.Embedding(num_items, num_factors) self.d_prime, self.d = d_prime, d # Vertical convolution layer self.conv_v = nn.Conv2D(d_prime, (L, 1), in_channels=1) # Horizontal convolution layer h = [i + 1 for i in range(L)] self.conv_h, self.max_pool = nn.Sequential(), nn.Sequential() for i in h: self.conv_h.add(nn.Conv2D(d, (i, num_factors), in_channels=1)) self.max_pool.add(nn.MaxPool1D(L - i + 1)) # Fully-connected layer self.fc1_dim_v, self.fc1_dim_h = d_prime * num_factors, d * len(h) self.fc = nn.Dense(in_units=d_prime * num_factors + d * L, activation='relu', units=num_factors) self.Q_prime = nn.Embedding(num_items, num_factors * 2) self.b = nn.Embedding(num_items, 1) self.dropout = nn.Dropout(drop_ratio) def forward(self, user_id, seq, item_id): item_embs = np.expand_dims(self.Q(seq), 1) user_emb = self.P(user_id) out, out_h, out_v, out_hs = None, None, None, [] if self.d_prime: out_v = self.conv_v(item_embs) out_v = out_v.reshape(out_v.shape[0], self.fc1_dim_v) if self.d: for conv, maxp in zip(self.conv_h, self.max_pool): conv_out = np.squeeze(npx.relu(conv(item_embs)), axis=3) t = maxp(conv_out) pool_out = np.squeeze(t, axis=2) out_hs.append(pool_out) out_h = np.concatenate(out_hs, axis=1) out = np.concatenate([out_v, out_h], axis=1) z = self.fc(self.dropout(out)) x = np.concatenate([z, user_emb], axis=1) q_prime_i = np.squeeze(self.Q_prime(item_id)) b = np.squeeze(self.b(item_id)) res = (x * q_prime_i).sum(1) + b return res ```

## 2. channels

- `sense_id`: `d2lce_270e1a75bb70807d9c2dd507`
- Split: `development`
- Model definition: separate streams or dimensions of data, especially feature or color dimensions in neural networks and images
- Model POS: `noun`

### Primary contexts

- `ctx_50b02cc418dce008fb37b2ea`: Note that the dataset consists of grayscale images, whose number of channels is 1.
- `ctx_4bb23f20ff0fa67bc6c1be83`: Tensors will become more important when we start working with images, which arrive as $n$-dimensional arrays with 3 axes corresponding to the height, width, and a *channel* axis for stacking the color channels (red, green, and blue).
- `ctx_79213e2c4e36b995f90f0b30`: A $200\times 200$ color photograph would consist of $200\times200\times3=120000$ numerical values, corresponding to the brightness of the red, green, and blue channels for each spatial location.
- `ctx_e066da075985b1450c0cd804`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_e7437fb0f0bdad9c3645e83b`: Moreover, AlexNet has ten times more convolution channels than LeNet.

### Backup contexts

- `ctx_e7ad2905fd773a830f6b4c43`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, gluon, init, lr_scheduler, np, npx from mxnet.gluon import nn npx.set_np() net = nn.HybridSequential() net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Conv2D(channels=16, kernel_size=5, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Dense(120, activation='relu'), nn.Dense(84, activation='relu'), nn.Dense(10)) net.hybridize() loss = gluon.loss.SoftmaxCrossEntropyLoss() device = d2l.try_gpu() batch_size = 256 train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size) # The code is almost identical to `d2l.train_ch6` defined in the # lenet section of chapter convolutional neural networks def train(net, train_iter, test_iter, num_epochs, loss, trainer, device): net.initialize(force_reinit=True, ctx=device, init=init.Xavier()) animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs], legend=['train loss', 'train acc', 'test acc']) for epoch in range(num_epochs): metric = d2l.Accumulator(3) # train_loss, train_acc, num_examples for i, (X, y) in enumerate(train_iter): X, y = X.as_in_ctx(device), y.as_in_ctx(device) with autograd.record(): y_hat = net(X) l = loss(y_hat, y) l.backward() trainer.step(X.shape[0]) metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0]) train_loss = metric[0] / metric[2] train_acc = metric[1] / metric[2] if (i + 1) % 50 == 0: animator.add(epoch + i / len(train_iter), (train_loss, train_acc, None)) test_acc = d2l.evaluate_accuracy_gpu(net, test_iter) animator.add(epoch + 1, (None, None, test_acc)) print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, ' f'test acc {test_acc:.3f}') ```
- `ctx_93be4d86c465d785ac0a0ec1`: For now, we only need to know that since the sequence length is $n$, the numbers of input and output channels are both $d$, the computational complexity of the convolutional layer is $\mathcal{O}(knd^2)$.

### Contrastive contexts

- `ctx_0f6cacd1df0fd9a1a8c5ed8d`: CPUs have between 2 and 4 memory channels, i.e., they have between 4 0GB/s and 100 GB/s peak memory bandwidth.

### Definition evidence

- `ctx_79213e2c4e36b995f90f0b30`: A $200\times 200$ color photograph would consist of $200\times200\times3=120000$ numerical values, corresponding to the brightness of the red, green, and blue channels for each spatial location.
- `ctx_4bb23f20ff0fa67bc6c1be83`: Tensors will become more important when we start working with images, which arrive as $n$-dimensional arrays with 3 axes corresponding to the height, width, and a *channel* axis for stacking the color channels (red, green, and blue).
- `ctx_50b02cc418dce008fb37b2ea`: Note that the dataset consists of grayscale images, whose number of channels is 1.
- `ctx_e066da075985b1450c0cd804`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.
- `ctx_e7437fb0f0bdad9c3645e83b`: Moreover, AlexNet has ten times more convolution channels than LeNet.
- `ctx_93be4d86c465d785ac0a0ec1`: For now, we only need to know that since the sequence length is $n$, the numbers of input and output channels are both $d$, the computational complexity of the convolutional layer is $\mathcal{O}(knd^2)$.
- `ctx_e7ad2905fd773a830f6b4c43`: ```{.python .input} %matplotlib inline from d2l import mxnet as d2l from mxnet import autograd, gluon, init, lr_scheduler, np, npx from mxnet.gluon import nn npx.set_np() net = nn.HybridSequential() net.add(nn.Conv2D(channels=6, kernel_size=5, padding=2, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Conv2D(channels=16, kernel_size=5, activation='relu'), nn.MaxPool2D(pool_size=2, strides=2), nn.Dense(120, activation='relu'), nn.Dense(84, activation='relu'), nn.Dense(10)) net.hybridize() loss = gluon.loss.SoftmaxCrossEntropyLoss() device = d2l.try_gpu() batch_size = 256 train_iter, test_iter = d2l.load_data_fashion_mnist(batch_size=batch_size) # The code is almost identical to `d2l.train_ch6` defined in the # lenet section of chapter convolutional neural networks def train(net, train_iter, test_iter, num_epochs, loss, trainer, device): net.initialize(force_reinit=True, ctx=device, init=init.Xavier()) animator = d2l.Animator(xlabel='epoch', xlim=[0, num_epochs], legend=['train loss', 'train acc', 'test acc']) for epoch in range(num_epochs): metric = d2l.Accumulator(3) # train_loss, train_acc, num_examples for i, (X, y) in enumerate(train_iter): X, y = X.as_in_ctx(device), y.as_in_ctx(device) with autograd.record(): y_hat = net(X) l = loss(y_hat, y) l.backward() trainer.step(X.shape[0]) metric.add(l.sum(), d2l.accuracy(y_hat, y), X.shape[0]) train_loss = metric[0] / metric[2] train_acc = metric[1] / metric[2] if (i + 1) % 50 == 0: animator.add(epoch + i / len(train_iter), (train_loss, train_acc, None)) test_acc = d2l.evaluate_accuracy_gpu(net, test_iter) animator.add(epoch + 1, (None, None, test_acc)) print(f'train loss {train_loss:.3f}, train acc {train_acc:.3f}, ' f'test acc {test_acc:.3f}') ```

### Part-of-speech evidence

- `ctx_79213e2c4e36b995f90f0b30`: A $200\times 200$ color photograph would consist of $200\times200\times3=120000$ numerical values, corresponding to the brightness of the red, green, and blue channels for each spatial location.
- `ctx_4bb23f20ff0fa67bc6c1be83`: Tensors will become more important when we start working with images, which arrive as $n$-dimensional arrays with 3 axes corresponding to the height, width, and a *channel* axis for stacking the color channels (red, green, and blue).
- `ctx_50b02cc418dce008fb37b2ea`: Note that the dataset consists of grayscale images, whose number of channels is 1.
- `ctx_e066da075985b1450c0cd804`: These include the convolutional layers themselves, nitty-gritty details including padding and stride, the pooling layers used to aggregate information across adjacent spatial regions, the use of multiple channels at each layer, and a careful discussion of the structure of modern architectures.

## 3. Collaborative Filtering

- `sense_id`: `d2lce_fb9ad6a6ac7e4ba9167913e1`
- Split: `development`
- Model definition: a recommendation approach that filters or predicts preferences using patterns derived from multiple users’ interactions or feedback.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_bb4169d27d43ea9f72386558`: We start the journey with the important concept in recommender systems---collaborative filtering (CF), which was first coined by the Tapestry system :cite:`Goldberg.Nichols.Oki.ea.1992`, referring to "people collaborate to help one another perform the filtering process in order to handle the large amounts of email and messages posted to newsgroups".
- `ctx_8f9b78e1ec3bfbc4e8e8f524`: In this section, we introduce a nonlinear neural network collaborative filtering model, AutoRec :cite:`Sedhain.Menon.Sanner.ea.2015`.
- `ctx_75434b30d17229e486daa408`: ## Collaborative Filtering
- `ctx_6c1b00ba70e27b85908261c3`: # Neural Collaborative Filtering for Personalized Ranking
- `ctx_f875ab990af98aaf8fbc46b2`: Collaborative filtering is a key concept in recommendation.

### Backup contexts

- `ctx_6f061caa3cf5adf9643ce3cf`: Matrix factorization is a class of collaborative filtering models.
- `ctx_3ef068df4dff9397568c05a1`: It identifies collaborative filtering (CF) with an autoencoder architecture and aims to integrate nonlinear transformations into CF on the basis of explicit feedback.
- `ctx_b163c5e1230dbed8d61eda33`: However, it is also common in other areas such as computational advertising and personalized collaborative filtering.

### Contrastive contexts

- `ctxx_6e73fc3ec644b4b97b928c84`: Synthetic: The moderators used collaborative filtering to jointly sort spam emails by hand.

### Definition evidence

- `ctx_bb4169d27d43ea9f72386558`: We start the journey with the important concept in recommender systems---collaborative filtering (CF), which was first coined by the Tapestry system :cite:`Goldberg.Nichols.Oki.ea.1992`, referring to "people collaborate to help one another perform the filtering process in order to handle the large amounts of email and messages posted to newsgroups".
- `ctx_f875ab990af98aaf8fbc46b2`: Collaborative filtering is a key concept in recommendation.
- `ctx_6f061caa3cf5adf9643ce3cf`: Matrix factorization is a class of collaborative filtering models.

### Part-of-speech evidence

- `ctx_75434b30d17229e486daa408`: ## Collaborative Filtering
- `ctx_bb4169d27d43ea9f72386558`: We start the journey with the important concept in recommender systems---collaborative filtering (CF), which was first coined by the Tapestry system :cite:`Goldberg.Nichols.Oki.ea.1992`, referring to "people collaborate to help one another perform the filtering process in order to handle the large amounts of email and messages posted to newsgroups".
- `ctx_6f061caa3cf5adf9643ce3cf`: Matrix factorization is a class of collaborative filtering models.

## 4. Concept Shift

- `sense_id`: `d2lce_6239b2ef1cec1800e3d6f13f`
- Split: `development`
- Model definition: a change in what labels or categories mean, so the definition of the prediction target shifts
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_877769c7d10adbd8a43011a6`: We may also encounter the related problem of *concept shift*, which arises when the very definitions of labels can change.
- `ctx_30ad642fb487987fba85babd`: ### Concept Shift
- `ctx_a37d035d836b9e4a6c867c99`: Diagnostic criteria for mental illness, what passes for fashionable, and job titles, are all subject to considerable amounts of concept shift.
- `ctx_4422b292ae2706ac3853e015`: Before delving into formalism and algorithms, we can discuss some concrete situations where covariate or concept shift might not be obvious.
- `ctx_a28b330881ada6423af8128e`: It turns out that if we navigate around the United States, shifting the source of our data by geography, we will find considerable concept shift regarding the distribution of names for *soft drinks* as shown in :numref:`fig_popvssoda`.

### Backup contexts

- `ctx_65ee0c7626e807bcbfcdf1cf`: In some cases, we get lucky and the models work despite covariate, label, or concept shift.
- `ctx_661ce5b03c03edebdfde8f55`: ### Concept Shift Correction
- `ctx_dcc02d9a71dc0b1466d0d8f2`: ![Concept shift on soft drink names in the United States.](../img/popvssoda.png) :width:`400px` :label:`fig_popvssoda`

### Contrastive contexts

- `ctxx_f0910b6ff0468e52839a49e3`: Synthetic: A concept shift happens when the meaning of the target label changes, not merely when input features become more common or rare.

### Definition evidence

- `ctx_877769c7d10adbd8a43011a6`: We may also encounter the related problem of *concept shift*, which arises when the very definitions of labels can change.
- `ctx_a37d035d836b9e4a6c867c99`: Diagnostic criteria for mental illness, what passes for fashionable, and job titles, are all subject to considerable amounts of concept shift.
- `ctx_4422b292ae2706ac3853e015`: Before delving into formalism and algorithms, we can discuss some concrete situations where covariate or concept shift might not be obvious.

### Part-of-speech evidence

- `ctx_30ad642fb487987fba85babd`: ### Concept Shift
- `ctx_661ce5b03c03edebdfde8f55`: ### Concept Shift Correction

## 5. constructor

- `sense_id`: `d2lce_7d7b617aacd41c76538d06af`
- Split: `development`
- Model definition: the class method or function that initializes an object when it is created
- Model POS: `noun`

### Primary contexts

- `ctx_7fa9447905f17f25b43e1bbf`: We will heavily rely on the parent class's functions, supplying only our own constructor (the `__init__` function in Python) and the forward propagation function.
- `ctx_8b948684ac54a83a4d0f3076`: We [**instantiate the MLP's layers**] in the constructor (**and subsequently invoke these layers**) on each call to the forward propagation function.
- `ctx_27c8a3f3418b0aec81720a7a`: Here, we declare two fully # connected layers def __init__(self): # Call the constructor of the `MLP` parent class `Module` to perform # the necessary initialization.
- `ctx_45e7aa8bb2892e1512df16ec`: Here, we declare two fully # connected layers def __init__(self): # Call the constructor of the `MLP` parent class `Model` to perform # the necessary initialization.
- `ctx_54000812f62f7bf37881febb`: Here, we declare two # fully-connected layers def __init__(self, **kwargs): # Call the constructor of the `MLP` parent class `Block` to perform # the necessary initialization.

### Backup contexts

- `ctx_7a88eb1b4219d42a945874f2`: In the `__init__` constructor function, we declare `weight` and `bias` as the two model parameters.
- `ctx_cdfc7e2c9d284b99240ac4e4`: With high-level APIs, all we need to do is add a `Dropout` layer after each fully-connected layer, passing in the dropout probability as the only argument to its constructor.
- `ctx_e484e6d55d0193ab9cfe2285`: The argument `num_steps` in the class constructor specifies the length of a text sequence so that each minibatch of sequences will have the same shape.

### Contrastive contexts

- `ctxx_c47b6ca799a008173ab48724`: Synthetic: The bridge constructor finished the project ahead of schedule.

### Definition evidence

- `ctx_7fa9447905f17f25b43e1bbf`: We will heavily rely on the parent class's functions, supplying only our own constructor (the `__init__` function in Python) and the forward propagation function.
- `ctx_54000812f62f7bf37881febb`: Here, we declare two # fully-connected layers def __init__(self, **kwargs): # Call the constructor of the `MLP` parent class `Block` to perform # the necessary initialization.
- `ctx_8b948684ac54a83a4d0f3076`: We [**instantiate the MLP's layers**] in the constructor (**and subsequently invoke these layers**) on each call to the forward propagation function.

### Part-of-speech evidence

- `ctx_7fa9447905f17f25b43e1bbf`: We will heavily rely on the parent class's functions, supplying only our own constructor (the `__init__` function in Python) and the forward propagation function.
- `ctx_7a88eb1b4219d42a945874f2`: In the `__init__` constructor function, we declare `weight` and `bias` as the two model parameters.

## 6. contexts

- `sense_id`: `d2lce_382e4bbab285d56a08249753`
- Split: `development`
- Model definition: surrounding linguistic or situational settings in which something appears or is used
- Model POS: `noun`

### Primary contexts

- `ctx_8d01d5c8ba8b22afa8297f86`: For example, the word "bank" has different meanings in contexts “i went to the bank to deposit cash” and “i went to the bank to sit down”.
- `ctx_a1d30a054504f29bcb20b25b`: ### Cosine Similarity In ML contexts where the angle is employed to measure the closeness of two vectors, practitioners adopt the term *cosine similarity* to refer to the portion $$ \cos(\theta) = \frac{\mathbf{v}\cdot\mathbf{w}}{\|\mathbf{v}\|\|\mathbf{w}\|}.
- `ctx_85c155993547287904ebb77e`: For text, we can train models to "fill in the blanks" by predicting randomly masked words using their surrounding words (contexts) in big corpora without any labeling effort :cite:`Devlin.Chang.Lee.ea.2018`!
- `ctx_a703c64944c46d8745b2290e`: Thus, many more recent pretraining models adapt representation of the same token to different contexts.
- `ctx_938a7ef4c625c0fdaa81a1ed`: It is quite difficult to adjust such models to additional contexts, whereas, deep learning based language models are well suited to take this into account.

### Backup contexts

- `ctx_ad827e72cc1bfa17dfbdadef`: Note that the word "dimension" tends to get overloaded in these contexts and this tends to confuse people.
- `ctx_c40b35f077d50245b79ff9f6`: Dot products are useful in a wide range of contexts.
- `ctx_d84189ac843db03cf9cfdc82`: * Once defined, custom layers can be invoked in arbitrary contexts and architectures.

### Contrastive contexts

- `ctxx_94774b666e3a5ea9bb5cba01`: Synthetic boundary probe: "contexts" is quoted here only as a document label, not as an occurrence of the reviewed D2L sense.

### Definition evidence

- `ctx_85c155993547287904ebb77e`: For text, we can train models to "fill in the blanks" by predicting randomly masked words using their surrounding words (contexts) in big corpora without any labeling effort :cite:`Devlin.Chang.Lee.ea.2018`!
- `ctx_ad827e72cc1bfa17dfbdadef`: Note that the word "dimension" tends to get overloaded in these contexts and this tends to confuse people.
- `ctx_938a7ef4c625c0fdaa81a1ed`: It is quite difficult to adjust such models to additional contexts, whereas, deep learning based language models are well suited to take this into account.
- `ctx_8d01d5c8ba8b22afa8297f86`: For example, the word "bank" has different meanings in contexts “i went to the bank to deposit cash” and “i went to the bank to sit down”.
- `ctx_a703c64944c46d8745b2290e`: Thus, many more recent pretraining models adapt representation of the same token to different contexts.
- `ctx_a1d30a054504f29bcb20b25b`: ### Cosine Similarity In ML contexts where the angle is employed to measure the closeness of two vectors, practitioners adopt the term *cosine similarity* to refer to the portion $$ \cos(\theta) = \frac{\mathbf{v}\cdot\mathbf{w}}{\|\mathbf{v}\|\|\mathbf{w}\|}.
- `ctx_c40b35f077d50245b79ff9f6`: Dot products are useful in a wide range of contexts.

### Part-of-speech evidence

- `ctx_85c155993547287904ebb77e`: For text, we can train models to "fill in the blanks" by predicting randomly masked words using their surrounding words (contexts) in big corpora without any labeling effort :cite:`Devlin.Chang.Lee.ea.2018`!
- `ctx_ad827e72cc1bfa17dfbdadef`: Note that the word "dimension" tends to get overloaded in these contexts and this tends to confuse people.
- `ctx_d84189ac843db03cf9cfdc82`: * Once defined, custom layers can be invoked in arbitrary contexts and architectures.
- `ctx_8d01d5c8ba8b22afa8297f86`: For example, the word "bank" has different meanings in contexts “i went to the bank to deposit cash” and “i went to the bank to sit down”.

## 7. continuous bag of words

- `sense_id`: `d2lce_dc193feb1eeef3a1349d9b74`
- Split: `development`
- Model definition: a word2vec model that predicts a center word from its surrounding context words
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c5722940f2ea3be48a188764`: ## The Continuous Bag of Words (CBOW) Model
- `ctx_500e392a6212984ed97679b6`: Since there are multiple context words in the continuous bag of words model, these context word vectors are averaged in the calculation of the conditional probability.
- `ctx_ba4bc22bf919f20441dc05b2`: ![The continuous bag of words model considers the conditional probability of generating the center word given its surrounding context words.](../img/cbow.svg) :eqlabel:`fig_cbow`
- `ctx_3e4d253c9ff11b6a3080d990`: For example, in the same text sequence "the", "man", "loves", "his", and "son", with "loves" as the center word and the context window size being 2, the continuous bag of words model considers the conditional probability of generating the center word "loves" based on the context words "the", "man", "his" and "son" (as shown in :numref:`fig_cbow`), which is
- `ctx_7592d6eb1986a0c2bd965c36`: The major difference from the skip-gram model is that the continuous bag of words model assumes that a center word is generated based on its surrounding context words in the text sequence.

### Backup contexts

- `ctx_9539bbe8c2ac486d267b808a`: The *continuous bag of words* (CBOW) model is similar to the skip-gram model.
- `ctx_27620623f1cb8074d3971cbc`: The word2vec tool contains two models, namely *skip-gram* :cite:`Mikolov.Sutskever.Chen.ea.2013` and *continuous bag of words* (CBOW) :cite:`Mikolov.Chen.Corrado.ea.2013`.
- `ctx_8ae5ddde35de799cd4b51696`: Since supervision comes from the data without labels, both skip-gram and continuous bag of words are self-supervised models.

### Contrastive contexts

- `ctxx_48fcd5c971dd15c9961d3824`: Synthetic: The phrase continuous bag of words here refers to a named prediction model, not just any continuously updated bag of vocabulary items.

### Definition evidence

- `ctx_3e4d253c9ff11b6a3080d990`: For example, in the same text sequence "the", "man", "loves", "his", and "son", with "loves" as the center word and the context window size being 2, the continuous bag of words model considers the conditional probability of generating the center word "loves" based on the context words "the", "man", "his" and "son" (as shown in :numref:`fig_cbow`), which is
- `ctx_7592d6eb1986a0c2bd965c36`: The major difference from the skip-gram model is that the continuous bag of words model assumes that a center word is generated based on its surrounding context words in the text sequence.
- `ctx_ba4bc22bf919f20441dc05b2`: ![The continuous bag of words model considers the conditional probability of generating the center word given its surrounding context words.](../img/cbow.svg) :eqlabel:`fig_cbow`

### Part-of-speech evidence

- `ctx_27620623f1cb8074d3971cbc`: The word2vec tool contains two models, namely *skip-gram* :cite:`Mikolov.Sutskever.Chen.ea.2013` and *continuous bag of words* (CBOW) :cite:`Mikolov.Chen.Corrado.ea.2013`.
- `ctx_c5722940f2ea3be48a188764`: ## The Continuous Bag of Words (CBOW) Model

## 8. Control Flow

- `sense_id`: `d2lce_6c7e95cd232fb7fcca6b3bdc`
- Split: `development`
- Model definition: The branching and looping behavior in a program that determines the order of execution, such as conditionals and loops.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_eaf1420ee977982e7eb8baf6`: ## Computing the Gradient of Python Control Flow
- `ctx_57d8f326884934a0af1fb2b4`: Note, though that hybridization can affect model flexibility, in particular in terms of control flow.
- `ctx_0da3afb393686e85b578238a`: One benefit of using automatic differentiation is that [**even if**] building the computational graph of (**a function required passing through a maze of Python control flow**) (e.g., conditionals, loops, and arbitrary function calls), (**we can still calculate the gradient of the resulting variable.**) In the following snippet, note that the number of iterations of the `while` loop and the evaluation of the `if` statement both depend on the value of the input `a`.
- `ctx_cb1896b0540e303727e896ea`: In the control flow example where we calculate the derivative of `d` with respect to `a`, what would happen if we changed the variable `a` to a random vector or matrix.
- `ctx_bc0786f0d324cf5127b590f1`: This is equivalent to sharing # parameters with two fully-connected layers X = self.dense(X) # Control flow while np.abs(X).sum() > 1: X /= 2 return X.sum() ```

### Backup contexts

- `ctx_e859a0568c857a572640c892`: This is equivalent to sharing # parameters with two fully-connected layers X = self.linear(X) # Control flow while X.abs().sum() > 1: X /= 2 return X.sum() ```
- `ctx_404061e58e2c4cb0d3631319`: For example, we might want to execute Python's control flow within the forward propagation function.
- `ctx_2ba928581bca7998708eb201`: Redesign an example of finding the gradient of the control flow.

### Contrastive contexts

- `ctxx_fd6c9fc1a240e723c479db5f`: Synthetic: Police improved control flow at the intersection during rush hour.

### Definition evidence

- `ctx_0da3afb393686e85b578238a`: One benefit of using automatic differentiation is that [**even if**] building the computational graph of (**a function required passing through a maze of Python control flow**) (e.g., conditionals, loops, and arbitrary function calls), (**we can still calculate the gradient of the resulting variable.**) In the following snippet, note that the number of iterations of the `while` loop and the evaluation of the `if` statement both depend on the value of the input `a`.
- `ctx_404061e58e2c4cb0d3631319`: For example, we might want to execute Python's control flow within the forward propagation function.
- `ctx_bc0786f0d324cf5127b590f1`: This is equivalent to sharing # parameters with two fully-connected layers X = self.dense(X) # Control flow while np.abs(X).sum() > 1: X /= 2 return X.sum() ```

### Part-of-speech evidence

- `ctx_eaf1420ee977982e7eb8baf6`: ## Computing the Gradient of Python Control Flow
- `ctx_404061e58e2c4cb0d3631319`: For example, we might want to execute Python's control flow within the forward propagation function.
- `ctx_57d8f326884934a0af1fb2b4`: Note, though that hybridization can affect model flexibility, in particular in terms of control flow.

## 9. convex function

- `sense_id`: `d2lce_0a19e86b29b5e64f79a45ddc`
- Split: `development`
- Model definition: a function whose graph lies below every line segment connecting two points on it
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_7bee0abcb221cab547cc2608`: ### Convex Functions
- `ctx_8e344cf296b5641fb066c073`: Before convex analysis, we need to define *convex sets* and *convex functions*.
- `ctx_901801bd834259cc113d20db`: Now that we have convex sets we can introduce *convex functions* $f$.
- `ctx_79f335a2e1adffa9d03d4429`: In other words, the expectation of a convex function is no less than the convex function of an expectation, where the latter is usually a simpler expression.
- `ctx_b12e31c5344ac1b417f474e4`: In short, convex functions are those where the eigenvalues of the Hessian are never negative.

### Backup contexts

- `ctx_bacc572c06a4d91414ef51a6`: Given a convex function $f$, one of the most useful mathematical tools is *Jensen's inequality*.
- `ctx_31af6599f592fa61978eda00`: Hint: use Jensen's inequality, i.e., use the fact that $-\log x$ is a convex function.
- `ctx_69f7abf7e90b1e8df21abc19`: Convex functions have many useful properties.

### Contrastive contexts

- `ctxx_8d0da7248b4a456b1d43166f`: Synthetic: The mirror had a convex function in the decorative engraving, but no mathematical meaning was intended.

### Definition evidence

- `ctx_8e344cf296b5641fb066c073`: Before convex analysis, we need to define *convex sets* and *convex functions*.
- `ctx_901801bd834259cc113d20db`: Now that we have convex sets we can introduce *convex functions* $f$.
- `ctx_bacc572c06a4d91414ef51a6`: Given a convex function $f$, one of the most useful mathematical tools is *Jensen's inequality*.

### Part-of-speech evidence

- `ctx_b12e31c5344ac1b417f474e4`: In short, convex functions are those where the eigenvalues of the Hessian are never negative.
- `ctx_31af6599f592fa61978eda00`: Hint: use Jensen's inequality, i.e., use the fact that $-\log x$ is a convex function.
- `ctx_901801bd834259cc113d20db`: Now that we have convex sets we can introduce *convex functions* $f$.

## 10. convex sets

- `sense_id`: `d2lce_9c874642b8c028465cfbb71e`
- Split: `development`
- Model definition: collections of points with the property that the line segment between any two points in the collection also lies in the collection
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_d78c176acb32ac55bfa5fc4f`: ### Convex Sets
- `ctx_0786467f80f822e79b33c1be`: We can strengthen this result with little effort: given convex sets $\mathcal{X}_i$, their intersection $\cap_{i} \mathcal{X}_i$ is convex.
- `ctx_019e9ed567f578c8342df0cc`: Typically the problems in deep learning are defined on convex sets.
- `ctx_ab1437837560228b5ab996d0`: Before convex analysis, we need to define *convex sets* and *convex functions*.
- `ctx_3cd1f9f092ed97036b277ed1`: ![The intersection between two convex sets is convex.](../img/convex-intersect.svg) :label:`fig_convex_intersect`

### Backup contexts

- `ctx_b8a70afb7e97de94755c1439`: Hence the line segment is not in $\mathcal{X} \cup \mathcal{Y}$ either, thus proving that in general unions of convex sets need not be convex.
- `ctx_d406fccab1c59c92aff48880`: Assume that $\mathcal{X}$ and $\mathcal{Y}$ are convex sets.
- `ctx_ca7dbc7a8024211ac2e41dad`: ![The union of two convex sets need not be convex.](../img/nonconvex.svg) :label:`fig_nonconvex`

### Contrastive contexts

- `ctxx_0ae256b503125d8a9be1e7d5`: Synthetic: In a graphics editor, “convex sets” might be mentioned informally for shapes, not as the formal optimization concept defined here.

### Definition evidence

- `ctx_ab1437837560228b5ab996d0`: Before convex analysis, we need to define *convex sets* and *convex functions*.
- `ctx_0786467f80f822e79b33c1be`: We can strengthen this result with little effort: given convex sets $\mathcal{X}_i$, their intersection $\cap_{i} \mathcal{X}_i$ is convex.
- `ctx_b8a70afb7e97de94755c1439`: Hence the line segment is not in $\mathcal{X} \cup \mathcal{Y}$ either, thus proving that in general unions of convex sets need not be convex.

### Part-of-speech evidence

- `ctx_ab1437837560228b5ab996d0`: Before convex analysis, we need to define *convex sets* and *convex functions*.
- `ctx_d78c176acb32ac55bfa5fc4f`: ### Convex Sets
