# D2L Targeted Repair Casebook - 5 senses

Tat ca context duoi day la block that tu source snapshot D2L da khoa hash.
Khong co context synthetic trong tap evidence duong.

## fully-connected layers - NO_SPLIT

- Output sense: `d2lce_98b37a7bcb47cd2ef2e5f296`
- Parent sense: `d2lce_98b37a7bcb47cd2ef2e5f296`
- Definition de xuat: Layers in which each output unit is connected to all input units from the previous layer.
- POS de xuat: `noun_phrase`
- Scope de xuat: `NEURAL_NETWORK_LAYER_CONNECTIVITY`
- Repair: `ADD_DIRECT_SAME_SENSE_DEFINITION_EVIDENCE`
- Candidates:
  - CANDIDATE_1: các lớp kết nối đầy đủ
  - CANDIDATE_2: các lớp liên kết đầy đủ
  - CANDIDATE_3: các tầng kết nối đầy đủ

### Contexts

#### 1. `d2l_linear_networks_linear_regression_b091`

Since for linear regression, every input is connected
to every output (in this case there is only one output),
we can regard this transformation (the output layer in :numref:`fig_single_neuron`)
as a *fully-connected layer* or *dense layer*.
We will talk a lot more about networks composed of such layers
in the next chapter.

#### 2. `d2l_linear_networks_linear_regression_concise_b021`

Recall the architecture of a single-layer network as shown in :numref:`fig_single_neuron`.
The layer is said to be *fully-connected*
because each of its inputs is connected to each of its outputs
by means of a matrix-vector multiplication.

#### 3. `d2l_linear_networks_softmax_regression_b015`

We can depict this calculation with the neural network diagram shown in :numref:`fig_softmaxreg`.
Just as in linear regression, softmax regression is also a single-layer neural network.
And since the calculation of each output, $o_1, o_2$, and $o_3$,
depends on all inputs, $x_1$, $x_2$, $x_3$, and $x_4$,
the output layer of softmax regression can also be described as fully-connected layer.

#### 4. `d2l_multilayer_perceptrons_index_b002`

In this chapter, we will introduce your first truly *deep* network.
The simplest deep networks are called multilayer perceptrons,
and they consist of multiple layers of neurons
each fully connected to those in the layer below
(from which they receive input)
and those above (which they, in turn, influence).
When we train high-capacity models we run the risk of overfitting.
Thus, we will need to provide your first rigorous introduction
to the notions of overfitting, underfitting, and model selection.
To help you combat these problems,
we will introduce regularization techniques such as weight decay and dropout.
We will also discuss issues relating to numerical stability and parameter initialization
that are key to successfully training deep networks.
Throughout, we aim to give you a firm grasp not just of the concepts
but also of the practice of using deep networks.
At the end of this chapter,
we apply what we have introduced so far to a real case: house price prediction.
We punt matters relating to the computational performance,
scalability, and efficiency of our models to subsequent chapters.

#### 5. `d2l_multilayer_perceptrons_mlp_b013`

This MLP has 4 inputs, 3 outputs,
and its hidden layer contains 5 hidden units.
Since the input layer does not involve any calculations,
producing outputs with this network
requires implementing the computations
for both the hidden and output layers;
thus, the number of layers in this MLP is 2.
Note that these layers are both fully connected.
Every input influences every neuron in the hidden layer,
and each of these in turn influences
every neuron in the output layer.
However, as suggested by :numref:`subsec_parameterization-cost-fc-layers`,
the parameterization cost of MLPs
with fully-connected layers
can be prohibitively high,
which may motivate
tradeoff between parameter saving and model effectiveness even without changing the input or output size :cite:`Zhang.Tay.Zhang.ea.2021`.

## statistical power - NO_SPLIT

- Output sense: `d2lce_2b76c0f26436945cdf880aed`
- Parent sense: `d2lce_2b76c0f26436945cdf880aed`
- Definition de xuat: The probability that a statistical test rejects the null hypothesis when the null hypothesis is false.
- POS de xuat: `noun_phrase`
- Scope de xuat: `STATISTICAL_HYPOTHESIS_TESTING`
- Repair: `REPLACE_WRONG_SENSE_CONTEXT_WITH_PRIMARY_EVIDENCE`
- Candidates:
  - CANDIDATE_1: lực kiểm định
  - CANDIDATE_2: mạnh
  - CANDIDATE_3: độ mạnh thống kê

### Contexts

#### 1. `d2l_appendix_mathematics_for_deep_learning_statistics_b064`

The *statistical power* (or *sensitivity*) measures the probability of reject the null hypothesis, $H_0$, when it should be rejected, i.e.,

#### 2. `d2l_appendix_mathematics_for_deep_learning_statistics_b065`

$$ \text{statistical power }= 1 - \beta = 1 - P(\text{ fail to reject } H_0  \mid H_0 \text{ is false} ).$$

#### 3. `d2l_appendix_mathematics_for_deep_learning_statistics_b066`

Recall that a *type I error* is error caused by rejecting the null hypothesis when it is true, whereas a *type II error* is resulted from failing to reject the null hypothesis when it is false. A type II error is usually denoted as $\beta$, and hence the corresponding statistical power is $1-\beta$.

#### 4. `d2l_appendix_mathematics_for_deep_learning_statistics_b067`

Intuitively, statistical power can be interpreted as how likely our test will detect a real discrepancy of some minimum magnitude at a desired statistical significance level. $80\%$ is a commonly used statistical power threshold. The higher the statistical power, the more likely we are to detect true differences.

#### 5. `d2l_appendix_mathematics_for_deep_learning_statistics_b068`

One of the most common uses of statistical power is in determining the number of samples needed.  The probability you reject the null hypothesis when it is false depends on the degree to which it is false (known as the *effect size*) and the number of samples you have.  As you might expect, small effect sizes will require a very large number of samples to be detectable with high probability.  While beyond the scope of this brief appendix to derive in detail, as an example, want to be able to reject a null hypothesis that our sample came from a mean zero variance one Gaussian, and we believe that our sample's mean is actually close to one, we can do so with acceptable error rates with a sample size of only $8$.  However, if we think our sample population true mean is close to $0.01$, then we'd need a sample size of nearly $80000$ to detect the difference.

## in place - IN_PLACE_MUTATION

- Output sense: `d2lce_97f1f447efe7908ef1e8daf4`
- Parent sense: `d2lce_2684090fd4500122fec2a334`
- Definition de xuat: Performed directly on an existing object or memory location rather than by creating a separate replacement.
- POS de xuat: `adverb`
- Scope de xuat: `ARRAY_OR_PARAMETER_UPDATE_ON_EXISTING_STORAGE`
- Repair: `SPLIT_PARENT_AND_REVIEW_MUTATION_SENSE`
- Candidates:
  - CANDIDATE_1: tại chỗ
  - CANDIDATE_2: cập nhật tại chỗ
  - CANDIDATE_3: trực tiếp trên đối tượng hiện có

### Contexts

#### 1. `d2l_preliminaries_ndarray_b091`

This might be undesirable for two reasons.
First, we do not want to run around
allocating memory unnecessarily all the time.
In machine learning, we might have
hundreds of megabytes of parameters
and update all of them multiple times per second.
Typically, we will want to perform these updates *in place*.
Second, we might point at the same parameters from multiple variables.
If we do not update in place, other references will still point to
the old memory location, making it possible for parts of our code
to inadvertently reference stale parameters.

#### 2. `d2l_preliminaries_ndarray_b092`

:begin_tab:`mxnet, pytorch`
Fortunately, (**performing in-place operations**) is easy.
We can assign the result of an operation
to a previously allocated array with slice notation,
e.g., `Y[:] = <expression>`.
To illustrate this concept, we first create a new matrix `Z`
with the same shape as another `Y`,
using `zeros_like` to allocate a block of $0$ entries.
:end_tab:

#### 3. `d2l_preliminaries_ndarray_b099`

Because TensorFlow `Tensors` are immutable and gradients do not flow through
`Variable` assignments, TensorFlow does not provide an explicit way to run
an individual operation in-place.

#### 4. `d2l_preliminaries_ndarray_b104`

:begin_tab:`pytorch`
[**Converting to a NumPy tensor (`ndarray`)**], or vice versa, is easy.
The torch Tensor and numpy array will share their underlying memory
locations, and changing one through an in-place operation will also
change the other.
:end_tab:

#### 5. `d2l_computational_performance_hybridize_b064`

:begin_tab:`mxnet`
This is quite different from what we saw previously. All print statements, as defined in `hybrid_forward`, are omitted. Indeed, after hybridization the execution of `net(x)` does not involve the Python interpreter any longer. This means that any spurious Python code is omitted (such as print statements) in favor of a much more streamlined execution and better performance. Instead, MXNet directly calls the C++ backend. Also note that some functions are not supported in the `symbol` module (e.g.,  `asnumpy`) and operations in-place such as `a += b` and `a[:] = a + b` must be rewritten as `a = a + b`. Nonetheless, compilation of models is worth the effort whenever speed matters. The benefit can range from small percentage points to more than twice the speed, depending on the complexity of the model, the speed of the CPU, and the speed and number of GPUs.
:end_tab:

## Adam - NO_SPLIT

- Output sense: `d2lce_7ef8ed3f93210606a27312a4`
- Parent sense: `d2lce_7ef8ed3f93210606a27312a4`
- Definition de xuat: An optimization algorithm used to train models.
- POS de xuat: `proper_noun`
- Scope de xuat: `DEEP_LEARNING_OPTIMIZATION_ALGORITHM`
- Repair: `REVIEW_TRIMMED_DEFINITION_WITH_NEW_PRIMARY_EVIDENCE`
- Candidates:
  - CANDIDATE_1: Adam
  - CANDIDATE_2: thuật toán tối ưu Adam
  - CANDIDATE_3: bộ tối ưu Adam

### Contexts

#### 1. `d2l_multilayer_perceptrons_kaggle_house_price_b053`

Unlike in previous sections, [**our training functions
will rely on the Adam optimizer
(we will describe it in greater detail later)**].
The main appeal of this optimizer is that,
despite doing no better (and sometimes worse)
given unlimited resources for hyperparameter optimization,
people tend to find that it is significantly less sensitive
to the initial learning rate.

#### 2. `d2l_optimization_index_b002`

If you read the book in sequence up to this point you already used a number of optimization algorithms to train deep learning models.
They were the tools that allowed us to continue updating model parameters and to minimize the value of the loss function, as evaluated on the training set. Indeed, anyone content with treating optimization as a black box device to minimize objective functions in a simple setting might well content oneself with the knowledge that there exists an array of incantations of such a procedure (with names such as "SGD" and "Adam").

#### 3. `d2l_optimization_adam_b004`

Adam :cite:`Kingma.Ba.2014` combines all these techniques into one efficient learning algorithm. As expected, this is an algorithm that has become rather popular as one of the more robust and effective optimization algorithms to use in deep learning. It is not without issues, though. In particular, :cite:`Reddi.Kale.Kumar.2019` show that there are situations where Adam can diverge due to poor variance control. In a follow-up work :cite:`Zaheer.Reddi.Sachan.ea.2018` proposed a hotfix to Adam, called Yogi which addresses these issues. More on this later. For now let us review the Adam algorithm.

#### 4. `d2l_optimization_adam_b006`

One of the key components of Adam is that it uses exponential weighted moving averages (also known as leaky averaging) to obtain an estimate of both the momentum and also the second moment of the gradient. That is, it uses the state variables

#### 5. `d2l_computer_vision_image_augmentation_b055`

Now we can [**define the `train_with_data_aug` function to train the model with image augmentation**].
This function gets all available GPUs,
uses Adam as the optimization algorithm,
applies image augmentation to the training dataset,
and finally calls the `train_ch13` function just defined to train and evaluate the model.

## in place - ESTABLISHED_CONFIGURATION

- Output sense: `d2lce_51ce8cc13680668af18c9d10`
- Parent sense: `d2lce_2684090fd4500122fec2a334`
- Definition de xuat: Present, established, or arranged so that the relevant system, component, or process is ready or operating.
- POS de xuat: `adverb`
- Scope de xuat: `SYSTEM_COMPONENT_OR_PROCESS_READINESS`
- Repair: `SPLIT_PARENT_AND_REVIEW_ESTABLISHED_SENSE`
- Candidates:
  - CANDIDATE_1: đã được thiết lập
  - CANDIDATE_2: đã sẵn sàng
  - CANDIDATE_3: đang được áp dụng

### Contexts

#### 1. `d2l_introduction_index_b079`

Despite their tremendous economic value,
recommendation systems
naively built on top of predictive models
suffer some serious conceptual flaws.
To start, we only observe *censored feedback*:
users preferentially rate movies that they feel strongly about.
For example,
on a five-point scale,
you might notice that items receive many five and one star ratings
but that there are conspicuously few three-star ratings.
Moreover, current purchase habits are often a result
of the recommendation algorithm currently in place,
but learning algorithms do not always take this detail into account.
Thus it is possible for feedback loops to form
where a recommender system preferentially pushes an item
that is then taken to be better (due to greater purchases)
and in turn is recommended even more frequently.
Many of these problems about how to deal with censoring,
incentives, and feedback loops, are important open research questions.

#### 2. `d2l_linear_networks_linear_regression_scratch_b047`

Now that we have all of the parts in place,
we are ready to [**implement the main training loop.**]
It is crucial that you understand this code
because you will see nearly identical training loops
over and over again throughout your career in deep learning.

#### 3. `d2l_linear_networks_linear_regression_concise_b057`

You might have noticed that expressing our model through
high-level APIs of a deep learning framework
requires comparatively few lines of code.
We did not have to individually allocate parameters,
define our loss function, or implement minibatch stochastic gradient descent.
Once we start working with much more complex models,
advantages of high-level APIs will grow considerably.
However, once we have all the basic pieces in place,
[**the training loop itself is strikingly similar
to what we did when implementing everything from scratch.**]

#### 4. `d2l_multilayer_perceptrons_mlp_b020`

In order to realize the potential of multilayer architectures,
we need one more key ingredient: a
nonlinear *activation function* $\sigma$
to be applied to each hidden unit
following the affine transformation.
The outputs of activation functions
(e.g., $\sigma(\cdot)$)
are called *activations*.
In general, with activation functions in place,
it is no longer possible to collapse our MLP into a linear model:

#### 5. `d2l_optimization_adam_b013`

Now we have all the pieces in place to compute updates. This is slightly anticlimactic and we have a simple update of the form
