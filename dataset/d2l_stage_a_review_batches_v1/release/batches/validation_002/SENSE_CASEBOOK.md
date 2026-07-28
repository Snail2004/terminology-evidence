# Stage A sense casebook: validation_002

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. ground truth

- `sense_id`: `d2lce_d0b3a65c5f21e6064395a475`
- Split: `validation`
- Model definition: the true observed target or correct reference value used to evaluate predictions
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_f81b65ecf8b2145ff73b3d4b`: ```{.python .input} def f(x): return 2 * d2l.sin(x) + x**0.8 y_train = f(x_train) + d2l.normal(0.0, 0.5, (n_train,)) # Training outputs x_test = d2l.arange(0, 5, 0.1) # Testing examples y_truth = f(x_test) # Ground-truth outputs for the testing examples n_test = len(x_test) # No.
- `ctx_fbe202aec2a07cda6debbc1e`: To refresh your memory: for some number of epochs, we will make a complete pass over the dataset (`train_data`), iteratively grabbing one minibatch of inputs and the corresponding ground-truth labels.
- `ctx_ae395d237a3a9a8e71e5f2ac`: Object detection algorithms usually sample a large number of regions in the input image, determine whether these regions contain objects of interest, and adjust the boundaries of the regions so as to predict the *ground-truth bounding boxes* of the objects more accurately.
- `ctx_402ad881d704f837dad6a500`: For classification, the most common objective is to minimize error rate, i.e., the fraction of examples on which our predictions disagree with the ground truth.
- `ctx_9833851b704f88b40f938e09`: With the ground truth labels `mlm_Y` of the predicted tokens `mlm_Y_hat` under masks, we can calculate the cross-entropy loss of the masked language model task in BERT pretraining.

### Backup contexts

- `ctx_5eba9c50bd8fa646fabf027e`: In deep learning, we are often trying to solve optimization problems: *maximize* the probability assigned to observed data; *minimize* the distance between predictions and the ground-truth observations.
- `ctx_7c41c1ee9c3bc8a94bf6a5b7`: We can evaluate a predicted sequence by comparing it with the label sequence (the ground-truth).
- `ctx_aa597eb85dc276f00236d01e`: The *confusion matrix*, $\mathbf{C}$, is simply a $k \times k$ matrix, where each column corresponds to the label category (ground truth) and each row corresponds to our model's predicted category.

### Contrastive contexts

- `ctxx_cf7119a0353ba2d7e3fd4d2b`: Synthetic: In filmmaking, ground truth referred to footage shot on location rather than annotated targets.

### Definition evidence

- `ctx_402ad881d704f837dad6a500`: For classification, the most common objective is to minimize error rate, i.e., the fraction of examples on which our predictions disagree with the ground truth.
- `ctx_5eba9c50bd8fa646fabf027e`: In deep learning, we are often trying to solve optimization problems: *maximize* the probability assigned to observed data; *minimize* the distance between predictions and the ground-truth observations.
- `ctx_fbe202aec2a07cda6debbc1e`: To refresh your memory: for some number of epochs, we will make a complete pass over the dataset (`train_data`), iteratively grabbing one minibatch of inputs and the corresponding ground-truth labels.
- `ctx_aa597eb85dc276f00236d01e`: The *confusion matrix*, $\mathbf{C}$, is simply a $k \times k$ matrix, where each column corresponds to the label category (ground truth) and each row corresponds to our model's predicted category.
- `ctx_7c41c1ee9c3bc8a94bf6a5b7`: We can evaluate a predicted sequence by comparing it with the label sequence (the ground-truth).
- `ctx_f81b65ecf8b2145ff73b3d4b`: ```{.python .input} def f(x): return 2 * d2l.sin(x) + x**0.8 y_train = f(x_train) + d2l.normal(0.0, 0.5, (n_train,)) # Training outputs x_test = d2l.arange(0, 5, 0.1) # Testing examples y_truth = f(x_test) # Ground-truth outputs for the testing examples n_test = len(x_test) # No.
- `ctx_ae395d237a3a9a8e71e5f2ac`: Object detection algorithms usually sample a large number of regions in the input image, determine whether these regions contain objects of interest, and adjust the boundaries of the regions so as to predict the *ground-truth bounding boxes* of the objects more accurately.
- `ctx_9833851b704f88b40f938e09`: With the ground truth labels `mlm_Y` of the predicted tokens `mlm_Y_hat` under masks, we can calculate the cross-entropy loss of the masked language model task in BERT pretraining.

### Part-of-speech evidence

- `ctx_402ad881d704f837dad6a500`: For classification, the most common objective is to minimize error rate, i.e., the fraction of examples on which our predictions disagree with the ground truth.
- `ctx_5eba9c50bd8fa646fabf027e`: In deep learning, we are often trying to solve optimization problems: *maximize* the probability assigned to observed data; *minimize* the distance between predictions and the ground-truth observations.

## 2. interaction matrix

- `sense_id`: `d2lce_c01c503b792019c6e3827ac0`
- Split: `validation`
- Model definition: A matrix whose entries represent observed user-item interactions, such as ratings, in a recommender system.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_7288cb7b7bb4df7b76d25aeb`: This dataset only records the existing ratings, so we can also call it rating matrix and we will use interaction matrix and rating matrix interchangeably in case that the values of this matrix represent exact ratings.
- `ctx_5565f012ff929a17a39b50a3`: We can construct an interaction matrix of size $n \times m$, where $n$ and $m$ are the number of users and the number of items respectively.
- `ctx_5614646f2d0d26ef6a76ee86`: Specifically, the model factorizes the user-item interaction matrix (e.g., rating matrix) into the product of two lower-rank matrices, capturing the low-rank structure of the user-item interactions.
- `ctx_b138719571716898b8d88624`: Let $\mathbf{R} \in \mathbb{R}^{m \times n}$ denote the interaction matrix with $m$ users and $n$ items, and the values of $\mathbf{R}$ represent explicit ratings.
- `ctx_8d54eee9a00c6d0088c74e34`: The first version of matrix factorization model is proposed by Simon Funk in a famous [blog post](https://sifter.org/~simon/journal/20061211.html) in which he described the idea of factorizing the interaction matrix.

### Backup contexts

- `ctx_a8d97fb4a07460b132bbdf0d`: In AutoRec, instead of explicitly embedding users/items into low-dimensional space, it uses the column/row of the interaction matrix as the input, then reconstructs the interaction matrix in the output layer.
- `ctx_04dd6ec44fd039cb21d5367d`: Clearly, the interaction matrix is extremely sparse (i.e., sparsity = 93.695%).
- `ctx_e1b68dcd92df41c824d6b973`: It uses a partially observed interaction matrix as the input, aiming to reconstruct a completed rating matrix.

### Contrastive contexts

- `ctxx_5ab100fa98fa8d89b89fa850`: Synthetic: In chemistry, an interaction matrix could summarize interactions among molecules, not user-item data.

### Definition evidence

- `ctx_5565f012ff929a17a39b50a3`: We can construct an interaction matrix of size $n \times m$, where $n$ and $m$ are the number of users and the number of items respectively.
- `ctx_7288cb7b7bb4df7b76d25aeb`: This dataset only records the existing ratings, so we can also call it rating matrix and we will use interaction matrix and rating matrix interchangeably in case that the values of this matrix represent exact ratings.
- `ctx_b138719571716898b8d88624`: Let $\mathbf{R} \in \mathbb{R}^{m \times n}$ denote the interaction matrix with $m$ users and $n$ items, and the values of $\mathbf{R}$ represent explicit ratings.
- `ctx_5614646f2d0d26ef6a76ee86`: Specifically, the model factorizes the user-item interaction matrix (e.g., rating matrix) into the product of two lower-rank matrices, capturing the low-rank structure of the user-item interactions.

### Part-of-speech evidence

- `ctx_5565f012ff929a17a39b50a3`: We can construct an interaction matrix of size $n \times m$, where $n$ and $m$ are the number of users and the number of items respectively.
- `ctx_b138719571716898b8d88624`: Let $\mathbf{R} \in \mathbb{R}^{m \times n}$ denote the interaction matrix with $m$ users and $n$ items, and the values of $\mathbf{R}$ represent explicit ratings.

## 3. linear regression

- `sense_id`: `d2lce_d8d3db5e12791f4de99286be`
- Split: `validation`
- Model definition: a regression method or model that predicts an output as a linear function of input features
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_c6fcdab6fbdb3c34121fe727`: Train a linear regression model to predict the ground-truth bounding box.
- `ctx_de10a7bd62da5f1e825f4704`: For example, Chris Bishop's excellent textbook :cite:`Bishop.2006`, teaches each topic so thoroughly that getting to the chapter on linear regression requires a non-trivial amount of work.
- `ctx_1c119086288473d0d261b1ba`: Particularly, it is a generalization of the linear regression model and the matrix factorization model.
- `ctx_4f1b397454dc88cdcdbef294`: This is just a linear regression problem where our features are given by the powers of $x$, the model's weights are given by $w_i$, and the bias is given by $w_0$ since $x^0 = 1$ for all $x$.
- `ctx_7ccf7eaa8a3ccdf7fa2896fd`: The bias error is commonly seen in a simple model (such as a linear regression model), which cannot extract high dimensional relations between the features and the outputs.

### Backup contexts

- `ctx_9f1f16a2e87c55fefeca14cc`: If you followed that much then you already understand the high-level idea behind linear regression.
- `ctx_b6400546a59e2de8affe4df3`: # Linear Regression :label:`sec_linear_regression`
- `ctx_c342d715dab448d66b1d2523`: It initializes a linear regression model and can be used to train the model with minibatch stochastic gradient descent and other algorithms introduced subsequently.

### Contrastive contexts

- `ctxx_22f3fbb4067eedef6a075290`: Synthetic: Here, linear regression means predicting with a linear function of features, not logistic regression for classification.

### Definition evidence

- `ctx_b6400546a59e2de8affe4df3`: # Linear Regression :label:`sec_linear_regression`
- `ctx_4f1b397454dc88cdcdbef294`: This is just a linear regression problem where our features are given by the powers of $x$, the model's weights are given by $w_i$, and the bias is given by $w_0$ since $x^0 = 1$ for all $x$.
- `ctx_c342d715dab448d66b1d2523`: It initializes a linear regression model and can be used to train the model with minibatch stochastic gradient descent and other algorithms introduced subsequently.

### Part-of-speech evidence

- `ctx_b6400546a59e2de8affe4df3`: # Linear Regression :label:`sec_linear_regression`
- `ctx_9f1f16a2e87c55fefeca14cc`: If you followed that much then you already understand the high-level idea behind linear regression.

## 4. matrix factorization

- `sense_id`: `d2lce_bbf89ef89c96205886255dcf`
- Split: `validation`
- Model definition: a latent-factor recommendation model that represents interactions by factorizing an interaction matrix
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_76456008737e2fa2778ac72c`: Matrix Factorization :cite:`Koren.Bell.Volinsky.2009` is a well-established algorithm in the recommender systems literature.
- `ctx_a9b72a28dee34e2910a4ca47`: In this section, we will dive into the details of the matrix factorization model and its implementation.
- `ctx_a65e2f61252cb7f76af3a6db`: The first version of matrix factorization model is proposed by Simon Funk in a famous [blog post](https://sifter.org/~simon/journal/20061211.html) in which he described the idea of factorizing the interaction matrix.
- `ctx_cfcea364b99854c40c41a050`: # Matrix Factorization
- `ctx_85322039ea0d616c001b09d4`: Latent factor models such as matrix factorization are examples of model-based CF.

### Backup contexts

- `ctx_9a721a5919d4be82909eca25`: Although the final score was the result of an ensemble solution (i.e., a combination of many algorithms), the matrix factorization algorithm played a critical role in the final blend.
- `ctx_36554f5312ed2da8c360daae`: ## The Matrix Factorization Model
- `ctx_aa3b7268d2031526ca7948bd`: This computation is important in an area called matrix factorization.

### Contrastive contexts

- `ctxx_72c3492a653c7eb9641454ed`: Synthetic: In this chapter, matrix factorization predicts user–item preferences by learning latent factors from an interaction matrix.

### Definition evidence

- `ctx_85322039ea0d616c001b09d4`: Latent factor models such as matrix factorization are examples of model-based CF.
- `ctx_76456008737e2fa2778ac72c`: Matrix Factorization :cite:`Koren.Bell.Volinsky.2009` is a well-established algorithm in the recommender systems literature.
- `ctx_a65e2f61252cb7f76af3a6db`: The first version of matrix factorization model is proposed by Simon Funk in a famous [blog post](https://sifter.org/~simon/journal/20061211.html) in which he described the idea of factorizing the interaction matrix.
- `ctx_a9b72a28dee34e2910a4ca47`: In this section, we will dive into the details of the matrix factorization model and its implementation.

### Part-of-speech evidence

- `ctx_cfcea364b99854c40c41a050`: # Matrix Factorization
- `ctx_76456008737e2fa2778ac72c`: Matrix Factorization :cite:`Koren.Bell.Volinsky.2009` is a well-established algorithm in the recommender systems literature.

## 5. observation

- `sense_id`: `d2lce_4f85955c4fd10e184dc97d32`
- Split: `validation`
- Model definition: a data point or measured/observed instance in a dataset or statistical setting
- Model POS: `noun`

### Primary contexts

- `ctx_f50d0e155359e097e4dd53f9`: In statistics, the former (predicting beyond the known observations) is called *extrapolation* whereas the latter (estimating between the existing observations) is called *interpolation*.
- `ctx_90a09c1c1d26d6c29e8dc76a`: As before, we update $\mathbf{w}$ based on the amount by which our estimate differs from the observation.
- `ctx_0a197bcf827b2c90050f9542`: Recall our observation from :numref:`sec_why-conv` of the correspondence between the cross-correlation and convolution operations.
- `ctx_3a8bc7234edcdcf52ec4704f`: Consider the somewhat contrived case where the first observation contains a checksum and the goal is to discern whether the checksum is correct at the end of the sequence.
- `ctx_3abb4265df9a90360405c9fc`: This observation, "heart attack" or "no heart attack", would be our label.

### Backup contexts

- `ctx_811d4c5e733d701bc5da5664`: First, we assume that the relationship between the independent variables $\mathbf{x}$ and the dependent variable $y$ is linear, i.e., that $y$ can be expressed as a weighted sum of the elements in $\mathbf{x}$, given some noise on the observations.
- `ctx_9ad5e74698b23886119deb3e`: To see why this is preferable consider the converse, namely that we are sampling $n$ observations from the discrete distribution *with replacement*.

### Contrastive contexts

- `ctxx_45c50c2a2b5c174155ab4c4e`: Synthetic: Her observation about the lecture was insightful.

### Definition evidence

- `ctx_3abb4265df9a90360405c9fc`: This observation, "heart attack" or "no heart attack", would be our label.
- `ctx_811d4c5e733d701bc5da5664`: First, we assume that the relationship between the independent variables $\mathbf{x}$ and the dependent variable $y$ is linear, i.e., that $y$ can be expressed as a weighted sum of the elements in $\mathbf{x}$, given some noise on the observations.
- `ctx_f50d0e155359e097e4dd53f9`: In statistics, the former (predicting beyond the known observations) is called *extrapolation* whereas the latter (estimating between the existing observations) is called *interpolation*.
- `ctx_9ad5e74698b23886119deb3e`: To see why this is preferable consider the converse, namely that we are sampling $n$ observations from the discrete distribution *with replacement*.

### Part-of-speech evidence

- `ctx_3abb4265df9a90360405c9fc`: This observation, "heart attack" or "no heart attack", would be our label.
- `ctx_811d4c5e733d701bc5da5664`: First, we assume that the relationship between the independent variables $\mathbf{x}$ and the dependent variable $y$ is linear, i.e., that $y$ can be expressed as a weighted sum of the elements in $\mathbf{x}$, given some noise on the observations.

## 6. pretrained BERT

- `sense_id`: `d2lce_e27a9787bb13f8580103adc4`
- Split: `validation`
- Model definition: A BERT model that has already been trained beforehand and is then used for encoding or fine-tuning on downstream tasks.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_74919ba83ca740fcf7b7b49e`: During supervised learning of a downstream application, parameters of the extra layers are learned from scratch while all the parameters in the pretrained BERT model are fine-tuned.
- `ctx_e2c73661a87aaf8cdb54006d`: ## Loading Pretrained BERT
- `ctx_0e2749a4df879a5753e93ab9`: * During supervised learning of a downstream application, parameters of the extra layers are learned from scratch while all the parameters in the pretrained BERT model are fine-tuned.
- `ctx_813b90db2df77652f38c4a00`: In the end, we introduce how to fine-tune a pretrained BERT model for a wide range of natural language processing applications, such as on a sequence level (single text classification and text pair classification) and a token level (text tagging and question answering).
- `ctx_f04ed703e48d432f4e1b350f`: In :numref:`chap_nlp_app`, we will fine-tune a pretrained BERT model for downstream natural language processing applications.

### Backup contexts

- `ctx_9c41d73d1f8f74867815db48`: On the other hand, the off-the-shelf pretrained BERT model may not fit for applications from specific domains like medicine.
- `ctx_e76e266186271f4f56e42317`: Similarly, `encoded_pair[:, 0, :]` is the encoded result of the entire sentence pair from the pretrained BERT.
- `ctx_c7d454145ac2ddadd1c48e11`: ![This section feeds pretrained BERT to an MLP-based architecture for natural language inference.](../img/nlp-map-nli-bert.svg) :label:`fig_nlp-map-nli-bert`

### Contrastive contexts

- `ctxx_df881922faebaacf453cbc2d`: Synthetic: A BERT model initialized randomly is not pretrained BERT.

### Definition evidence

- `ctx_813b90db2df77652f38c4a00`: In the end, we introduce how to fine-tune a pretrained BERT model for a wide range of natural language processing applications, such as on a sequence level (single text classification and text pair classification) and a token level (text tagging and question answering).
- `ctx_f04ed703e48d432f4e1b350f`: In :numref:`chap_nlp_app`, we will fine-tune a pretrained BERT model for downstream natural language processing applications.
- `ctx_74919ba83ca740fcf7b7b49e`: During supervised learning of a downstream application, parameters of the extra layers are learned from scratch while all the parameters in the pretrained BERT model are fine-tuned.

### Part-of-speech evidence

- `ctx_9c41d73d1f8f74867815db48`: On the other hand, the off-the-shelf pretrained BERT model may not fit for applications from specific domains like medicine.
- `ctx_e2c73661a87aaf8cdb54006d`: ## Loading Pretrained BERT

## 7. question answering

- `sense_id`: `d2lce_41109297e6bf8f44d9bb9178`
- Split: `validation`
- Model definition: an NLP task where a system reads text and produces answers to questions about it
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_0e18119fa086c3cb92ff4aba`: As another token-level application, *question answering* reflects capabilities of reading comprehension.
- `ctx_f478a8fd9500cc043c25cf47`: ## Question Answering
- `ctx_3d9da592d08d2b52b664985b`: On the token level, we will briefly introduce new applications such as text tagging and question answering and shed light on how BERT can represent their inputs and get transformed into output labels.
- `ctx_e5e0cc83210d92e8eeb9732e`: BERT further improved the state of the art on eleven natural language processing tasks under broad categories of (i) single text classification (e.g., sentiment analysis), (ii) text pair classification (e.g., natural language inference), (iii) question answering, (iv) text tagging (e.g., named entity recognition).
- `ctx_be8e51744f5a141736986bff`: In the end, we introduce how to fine-tune a pretrained BERT model for a wide range of natural language processing applications, such as on a sequence level (single text classification and text pair classification) and a token level (text tagging and question answering).

### Backup contexts

- `ctx_b5380097a093ff4bebcff9db`: It enjoys wide applications ranging from information retrieval to open-domain question answering.
- `ctx_c7b698a638aebbd9047e3e6d`: Leveraging different best models for different tasks at that time, adding ELMo improved the state of the art across six natural language processing tasks: sentiment analysis, natural language inference, semantic role labeling, coreference resolution, named entity recognition, and question answering.
- `ctx_fbdaf8cf3c95a1d855ee6d1f`: GPT was evaluated on twelve tasks of natural language inference, question answering, sentence similarity, and classification, and improved the state of the art in nine of them with minimal changes to the model architecture.

### Contrastive contexts

- `ctxx_0520cf62b1087d79b5de67e2`: Synthetic: In this chapter, question answering means an NLP task, not a classroom habit of students answering a teacher’s questions.

### Definition evidence

- `ctx_0e18119fa086c3cb92ff4aba`: As another token-level application, *question answering* reflects capabilities of reading comprehension.
- `ctx_e5e0cc83210d92e8eeb9732e`: BERT further improved the state of the art on eleven natural language processing tasks under broad categories of (i) single text classification (e.g., sentiment analysis), (ii) text pair classification (e.g., natural language inference), (iii) question answering, (iv) text tagging (e.g., named entity recognition).
- `ctx_b5380097a093ff4bebcff9db`: It enjoys wide applications ranging from information retrieval to open-domain question answering.

### Part-of-speech evidence

- `ctx_f478a8fd9500cc043c25cf47`: ## Question Answering
- `ctx_0e18119fa086c3cb92ff4aba`: As another token-level application, *question answering* reflects capabilities of reading comprehension.

## 8. regression

- `sense_id`: `d2lce_3b6a75bdbf023ea1f3ed2cc8`
- Split: `validation`
- Model definition: A predictive modeling task or method that estimates continuous numerical outputs from input variables.
- Model POS: `noun`

### Primary contexts

- `ctx_f1ff669290faa81e574f5c8e`: Fortunately, classic statistical learning techniques such as linear and softmax regression can be cast as *linear* neural networks.
- `ctx_07ef3e035c8693916453144f`: #### Regression
- `ctx_a4c83a54ae7da02ba9f87078`: In order to achieve this, our trader could use a regression model such as the one that we trained in :numref:`sec_linear_concise`.
- `ctx_13e112e8272712c2b81ca907`: Notably, the Nadaraya-Waston kernel regression in 1964 is a simple demonstration of machine learning with *attention mechanisms*.
- `ctx_9ee09ec62e9e9e56a663ed36`: In :numref:`chap_linear`, we introduced softmax regression (:numref:`sec_softmax`), implementing the algorithm from scratch (:numref:`sec_softmax_scratch`) and using high-level APIs (:numref:`sec_softmax_concise`), and training classifiers to recognize 10 categories of clothing from low-resolution images.

### Backup contexts

- `ctx_1422ef1a795655cc30790982`: To make such data amenable to softmax regression and MLPs, we first flattened each image from a $28\times28$ matrix into a fixed-length $784$-dimensional vector, and thereafter processed them with fully-connected layers.
- `ctx_b600daa6c4d490532e107adf`: When we worked through softmax regression, a single layer was itself the model.
- `ctx_3644f67a4a402cab9ab7890d`: For example, Chris Bishop's excellent textbook :cite:`Bishop.2006`, teaches each topic so thoroughly that getting to the chapter on linear regression requires a non-trivial amount of work.

### Contrastive contexts

- `ctxx_e5f7daaf294008c174c05e8f`: Synthetic: Here, regression means the predictive method, not just the specific fitted formula written after training.

### Definition evidence

- `ctx_07ef3e035c8693916453144f`: #### Regression
- `ctx_f1ff669290faa81e574f5c8e`: Fortunately, classic statistical learning techniques such as linear and softmax regression can be cast as *linear* neural networks.
- `ctx_a4c83a54ae7da02ba9f87078`: In order to achieve this, our trader could use a regression model such as the one that we trained in :numref:`sec_linear_concise`.
- `ctx_13e112e8272712c2b81ca907`: Notably, the Nadaraya-Waston kernel regression in 1964 is a simple demonstration of machine learning with *attention mechanisms*.

### Part-of-speech evidence

- `ctx_07ef3e035c8693916453144f`: #### Regression
- `ctx_f1ff669290faa81e574f5c8e`: Fortunately, classic statistical learning techniques such as linear and softmax regression can be cast as *linear* neural networks.

## 9. sequential partitioning

- `sense_id`: `d2lce_e8992d8478a28e673fe551dc`
- Split: `validation`
- Model definition: a way of splitting sequence data into minibatches so adjacent subsequences remain adjacent across iteration
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_f0652b693aa1982997b28188`: In addition to random sampling of the original sequence, [**we can also ensure that the subsequences from two adjacent minibatches during iteration are adjacent on the original sequence.**] This strategy preserves the order of split subsequences when iterating over minibatches, hence is called sequential partitioning.
- `ctx_588eb8c0e1f9b0a69e338bcf`: * The main choices for reading long sequences are random sampling and sequential partitioning.
- `ctx_08bfc24bcb84e8fd751de7ed`: Different sampling methods for sequential data (random sampling and sequential partitioning) will result in differences in the initialization of hidden states.
- `ctx_1a32b3cdb3a737c06828ee2f`: ### Sequential Partitioning
- `ctx_20ba0f30e6bab2976ab96ef1`: Using the same settings, let us [**print features `X` and labels `Y` for each minibatch**] of subsequences read by sequential partitioning.

### Backup contexts

- `ctx_24f466c62d7260f34d827513`: In the following, we describe how to accomplish this for both *random sampling* and *sequential partitioning* strategies.
- `ctx_7f90783f82a63497dbe94ff4`: ```{.python .input} #@tab tensorflow def seq_data_iter_sequential(corpus, batch_size, num_steps): #@save """Generate a minibatch of subsequences using sequential partitioning.""" # Start with a random offset to partition a sequence offset = random.randint(0, num_steps) num_tokens = ((len(corpus) - offset - 1) // batch_size) * batch_size Xs = d2l.tensor(corpus[offset: offset + num_tokens]) Ys = d2l.tensor(corpus[offset + 1: offset + 1 + num_tokens]) Xs = d2l.reshape(Xs, (batch_size, -1)) Ys = d2l.reshape(Ys, (batch_size, -1)) num_batches = Xs.shape[1] // num_steps for i in range(0, num_batches * num_steps, num_steps): X = Xs[:, i: i + num_steps] Y = Ys[:, i: i + num_steps] yield X, Y ```
- `ctx_e9575e9da1e8984c39373503`: ```{.python .input} #@tab mxnet, pytorch def seq_data_iter_sequential(corpus, batch_size, num_steps): #@save """Generate a minibatch of subsequences using sequential partitioning.""" # Start with a random offset to partition a sequence offset = random.randint(0, num_steps) num_tokens = ((len(corpus) - offset - 1) // batch_size) * batch_size Xs = d2l.tensor(corpus[offset: offset + num_tokens]) Ys = d2l.tensor(corpus[offset + 1: offset + 1 + num_tokens]) Xs, Ys = Xs.reshape(batch_size, -1), Ys.reshape(batch_size, -1) num_batches = Xs.shape[1] // num_steps for i in range(0, num_steps * num_batches, num_steps): X = Xs[:, i: i + num_steps] Y = Ys[:, i: i + num_steps] yield X, Y ```

### Contrastive contexts

- `ctxx_cd93a4ee5fd2b607af086446`: Synthetic: With sequential partitioning, neighboring minibatches keep neighboring subsequences from the original sequence, unlike random sampling.

### Definition evidence

- `ctx_f0652b693aa1982997b28188`: In addition to random sampling of the original sequence, [**we can also ensure that the subsequences from two adjacent minibatches during iteration are adjacent on the original sequence.**] This strategy preserves the order of split subsequences when iterating over minibatches, hence is called sequential partitioning.
- `ctx_e9575e9da1e8984c39373503`: ```{.python .input} #@tab mxnet, pytorch def seq_data_iter_sequential(corpus, batch_size, num_steps): #@save """Generate a minibatch of subsequences using sequential partitioning.""" # Start with a random offset to partition a sequence offset = random.randint(0, num_steps) num_tokens = ((len(corpus) - offset - 1) // batch_size) * batch_size Xs = d2l.tensor(corpus[offset: offset + num_tokens]) Ys = d2l.tensor(corpus[offset + 1: offset + 1 + num_tokens]) Xs, Ys = Xs.reshape(batch_size, -1), Ys.reshape(batch_size, -1) num_batches = Xs.shape[1] // num_steps for i in range(0, num_steps * num_batches, num_steps): X = Xs[:, i: i + num_steps] Y = Ys[:, i: i + num_steps] yield X, Y ```
- `ctx_588eb8c0e1f9b0a69e338bcf`: * The main choices for reading long sequences are random sampling and sequential partitioning.

### Part-of-speech evidence

- `ctx_1a32b3cdb3a737c06828ee2f`: ### Sequential Partitioning
- `ctx_f0652b693aa1982997b28188`: In addition to random sampling of the original sequence, [**we can also ensure that the subsequences from two adjacent minibatches during iteration are adjacent on the original sequence.**] This strategy preserves the order of split subsequences when iterating over minibatches, hence is called sequential partitioning.

## 10. shape

- `sense_id`: `d2lce_7d91b65d1e0031ab994be237`
- Split: `validation`
- Model definition: the dimensions or form of an object, especially the length along each axis of a tensor or array
- Model POS: `noun`

### Primary contexts

- `ctx_eaaf8f351dd451d99604be0e`: (**We can access a tensor's *shape***) (~~and the total number of elements~~) (the length along each axis) by inspecting its `shape` property.
- `ctx_f57f479949897e554691786b`: Note that the output may have a different shape from the input.
- `ctx_0f178aa4816b9e54f151c714`: To start off, we can consider an MLP with two-dimensional images $\mathbf{X}$ as inputs and their immediate hidden representations $\mathbf{H}$ similarly represented as matrices in mathematics and as two-dimensional tensors in code, where both $\mathbf{X}$ and $\mathbf{H}$ have the same shape.
- `ctx_178ff737d193d16c637c5384`: ```{.python .input} #@tab mxnet, pytorch def synthetic_data(w, b, num_examples): #@save """Generate y = Xw + b + noise.""" X = d2l.normal(0, 1, (num_examples, len(w))) y = d2l.matmul(X, w) + b y += d2l.normal(0, 0.01, y.shape) return X, d2l.reshape(y, (-1, 1)) ```
- `ctx_5a8d5f2e80e768f19b56cf52`: ```{.python .input} #@tab mxnet, pytorch def seq_data_iter_sequential(corpus, batch_size, num_steps): #@save """Generate a minibatch of subsequences using sequential partitioning.""" # Start with a random offset to partition a sequence offset = random.randint(0, num_steps) num_tokens = ((len(corpus) - offset - 1) // batch_size) * batch_size Xs = d2l.tensor(corpus[offset: offset + num_tokens]) Ys = d2l.tensor(corpus[offset + 1: offset + 1 + num_tokens]) Xs, Ys = Xs.reshape(batch_size, -1), Ys.reshape(batch_size, -1) num_batches = Xs.shape[1] // num_steps for i in range(0, num_steps * num_batches, num_steps): X = Xs[:, i: i + num_steps] Y = Ys[:, i: i + num_steps] yield X, Y ```

### Backup contexts

- `ctx_662c35c799f161b9c9cc657e`: The convolution window shape in the second layer is reduced to $5\times5$, followed by $3\times3$.
- `ctx_0485eb5efda3441a68d374c6`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_0ca0c7867a08cb23a7e74953`: While we might expect microscope images to come from standard equipment, we cannot expect images mined from the Internet to all show up with the same resolution or shape.

### Contrastive contexts

- `ctxx_f6ff268edebdf6e4c03c0f91`: [Synthetic] The shape of the tensor is (2, 3), whereas the shape of the curve is S-like.

### Definition evidence

- `ctx_eaaf8f351dd451d99604be0e`: (**We can access a tensor's *shape***) (~~and the total number of elements~~) (the length along each axis) by inspecting its `shape` property.
- `ctx_f57f479949897e554691786b`: Note that the output may have a different shape from the input.
- `ctx_0f178aa4816b9e54f151c714`: To start off, we can consider an MLP with two-dimensional images $\mathbf{X}$ as inputs and their immediate hidden representations $\mathbf{H}$ similarly represented as matrices in mathematics and as two-dimensional tensors in code, where both $\mathbf{X}$ and $\mathbf{H}$ have the same shape.

### Part-of-speech evidence

- `ctx_eaaf8f351dd451d99604be0e`: (**We can access a tensor's *shape***) (~~and the total number of elements~~) (the length along each axis) by inspecting its `shape` property.
- `ctx_0485eb5efda3441a68d374c6`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
