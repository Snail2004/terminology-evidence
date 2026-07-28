# Stage A sense casebook: validation_003

This casebook contains no Vietnamese candidates. Review the English
sense definition and part of speech from supplied evidence only.

## 1. single GPU

- `sense_id`: `d2lce_e014da89e120449f8881dd5b`
- Split: `validation`
- Model definition: using only one graphics processing unit for computation or training
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_f416911a3fe34d06b66e6afd`: This allows us to process data with larger networks when compared with what a single GPU could handle.
- `ctx_0137ba0f0626d6bffd760691`: For instance, rather than computing 64 channels on a single GPU we could split up the problem across 4 GPUs, each of which generates data for 16 channels.
- `ctx_12f206d4c0b5b5d7a27319b1`: Note that in practice we *increase* the minibatch size $k$-fold when training on $k$ GPUs such that each GPU has the same amount of work to do as if we were training on a single GPU only.
- `ctx_44a715e0fcd0718a579ce239`: Let us see how well this works [**on a single GPU**].
- `ctx_bbf05b50c650923e2f670c8e`: For convenience (and conciseness of code) we compute the accuracy on a single GPU, though this is *inefficient* since the other GPUs are idle.

### Backup contexts

- `ctx_c3033b3efa90016d4c7a6711`: * In many cases, a single GPU is insufficient to process the large amounts of data available for training.
- `ctx_da18a43d55f851433ec66477`: Typically, a single operator will use all the computational resources on all CPUs or on a single GPU.
- `ctx_87e8e11751488aa4967c115a`: The same applies to a single GPU.

### Contrastive contexts

- `ctxx_c05ec3dfe7db4cfed24ec6b1`: Synthetic: The model runs on a single GPU, not across multiple GPUs.

### Definition evidence

- `ctx_f416911a3fe34d06b66e6afd`: This allows us to process data with larger networks when compared with what a single GPU could handle.
- `ctx_12f206d4c0b5b5d7a27319b1`: Note that in practice we *increase* the minibatch size $k$-fold when training on $k$ GPUs such that each GPU has the same amount of work to do as if we were training on a single GPU only.
- `ctx_44a715e0fcd0718a579ce239`: Let us see how well this works [**on a single GPU**].

### Part-of-speech evidence

- `ctx_87e8e11751488aa4967c115a`: The same applies to a single GPU.
- `ctx_44a715e0fcd0718a579ce239`: Let us see how well this works [**on a single GPU**].

## 2. statistical inference

- `sense_id`: `d2lce_1ff0c13e857af8ab6956fc96`
- Split: `validation`
- Model definition: The branch of statistics concerned with drawing conclusions about populations or processes from data.
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_2321277fc92b0af89415e01e`: More specifically, statistics can be divided to *descriptive statistics* and *statistical inference*.
- `ctx_a7b6edbe0047f5e1d803d9a2`: However, the goal of deep learning (or more broadly, statistical inference) is to reduce the generalization error.
- `ctx_5fcee3eae8b5c9088386725a`: Joe Blitzstein's [books](https://www.amazon.com/Introduction-Probability-Chapman-Statistical-Science/dp/1138369918) and [courses](https://projects.iq.harvard.edu/stat110/home) on probability and inference are pedagogical gems.

### Contrastive contexts

- `ctx_3cca6631d5799589a1c90086`: Given pretrained text representations, this chapter will explore two popular and representative downstream natural language processing tasks: sentiment analysis and natural language inference, which analyze single text and relationships of text pairs, respectively.

### Definition evidence

- `ctx_a7b6edbe0047f5e1d803d9a2`: However, the goal of deep learning (or more broadly, statistical inference) is to reduce the generalization error.
- `ctx_2321277fc92b0af89415e01e`: More specifically, statistics can be divided to *descriptive statistics* and *statistical inference*.
- `ctx_5fcee3eae8b5c9088386725a`: Joe Blitzstein's [books](https://www.amazon.com/Introduction-Probability-Chapman-Statistical-Science/dp/1138369918) and [courses](https://projects.iq.harvard.edu/stat110/home) on probability and inference are pedagogical gems.

### Part-of-speech evidence

- `ctx_a7b6edbe0047f5e1d803d9a2`: However, the goal of deep learning (or more broadly, statistical inference) is to reduce the generalization error.
- `ctx_2321277fc92b0af89415e01e`: More specifically, statistics can be divided to *descriptive statistics* and *statistical inference*.

## 3. symmetry

- `sense_id`: `d2lce_00c0e4f7d0d5537d738af8a7`
- Split: `validation`
- Model definition: A property of remaining unchanged under a transformation or exchange; in neural networks, it can refer to interchangeable parameterizations that must be broken.
- Model POS: `noun`

### Primary contexts

- `ctx_85ece440cd707c90543755ee`: Another problem in neural network design is the symmetry inherent in their parametrization.
- `ctx_2c7d7b724cf59c3bde70e182`: Note that while minibatch stochastic gradient descent would not break this symmetry, dropout regularization would!
- `ctx_3e360f75f7c8e4a72dec0489`: ### Breaking the Symmetry
- `ctx_77dc2db84932a4949515fe0d`: Such iterations would never *break the symmetry* on its own and we might never be able to realize the network's expressive power.
- `ctx_a0e3164176dc4db7e9acaf04`: In other words, we have permutation symmetry among the hidden units of each layer.

### Backup contexts

- `ctx_59c1a647fd4efce460391040`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_4dd93f52590658e6a0b3f22f`: By symmetry, this also holds for $P(A, B) = P(A \mid B) P(B)$.
- `ctx_0a972e21da1bd8980d3dde3a`: Let us go through a toy example to see the non-symmetry explicitly.

### Contrastive contexts

- `ctxx_bb8784846b3f76a165587eb0`: Synthetic: In everyday design, symmetry can mean visual balance in a logo, not mathematical or parameter-exchange invariance.

### Definition evidence

- `ctx_4dd93f52590658e6a0b3f22f`: By symmetry, this also holds for $P(A, B) = P(A \mid B) P(B)$.
- `ctx_59c1a647fd4efce460391040`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_85ece440cd707c90543755ee`: Another problem in neural network design is the symmetry inherent in their parametrization.
- `ctx_77dc2db84932a4949515fe0d`: Such iterations would never *break the symmetry* on its own and we might never be able to realize the network's expressive power.

### Part-of-speech evidence

- `ctx_59c1a647fd4efce460391040`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_85ece440cd707c90543755ee`: Another problem in neural network design is the symmetry inherent in their parametrization.

## 4. Tanh Function

- `sense_id`: `d2lce_658174b1687c73f5aa1957ab`
- Split: `validation`
- Model definition: the hyperbolic tangent function, often used to map values to the range [-1, 1]
- Model POS: `noun_phrase`

### Primary contexts

- `ctx_fd599f0c3c95a18b0f5b16da`: The `ToTensor` transformation will project the pixel value into $[0, 1]$, while our generator will use the tanh function to obtain outputs in $[-1, 1]$.
- `ctx_004316e859832b3cfcf7035e`: The derivative of tanh function is plotted below.
- `ctx_c92778674f8f7766091d01d2`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_8bd905bd87e3d1f74a1769c5`: The derivative of the tanh function is:
- `ctx_9f96534b3ab6f71f9412e1e5`: And as we saw with the sigmoid function, as the input moves away from 0 in either direction, the derivative of the tanh function approaches 0.

### Backup contexts

- `ctx_72c288a96527180e7730ec3d`: Note that as the input nears 0, the tanh function approaches a linear transformation.
- `ctx_c985b1faee54cf1ba7064dca`: ### Tanh Function
- `ctx_a57f35de660fe1e76b9815a6`: We plot the tanh function below.

### Contrastive contexts

- `ctxx_b6e39d014543fc56157b513b`: [Synthetic] The tanh function is nonlinear, unlike the identity function y = x.

### Definition evidence

- `ctx_fd599f0c3c95a18b0f5b16da`: The `ToTensor` transformation will project the pixel value into $[0, 1]$, while our generator will use the tanh function to obtain outputs in $[-1, 1]$.
- `ctx_c92778674f8f7766091d01d2`: Although the shape of the function is similar to that of the sigmoid function, the tanh function exhibits point symmetry about the origin of the coordinate system.
- `ctx_8bd905bd87e3d1f74a1769c5`: The derivative of the tanh function is:

### Part-of-speech evidence

- `ctx_c985b1faee54cf1ba7064dca`: ### Tanh Function
- `ctx_a57f35de660fe1e76b9815a6`: We plot the tanh function below.

## 5. uncertainty

- `sense_id`: `d2lce_73dbe839de3f1d00bf1226f0`
- Split: `validation`
- Model definition: lack of certainty about a value, outcome, estimate, or prediction.
- Model POS: `noun`

- Source package gap (not reviewable): `part_of_speech: ctx_a5bf53f3daed100d0d815e2a`

### Primary contexts

- `ctx_e7697bfcdc8c8d5ccbb78a65`: To reason rigorously under uncertainty we will need to invoke the language of probability.
- `ctx_dabb91193e9646a54768ead2`: However, there are some exceptions: some researchers use dropout at test time as a heuristic for estimating the *uncertainty* of neural network predictions: if the predictions agree across many different dropout masks, then we might say that the network is more confident.
- `ctx_923ebaa50c2bbcd9a6a3ab6c`: When estimating the value of a parameter $\theta$, point estimators like $\hat \theta$ are of limited utility since they contain no notion of uncertainty.
- `ctx_47b329913c771cfa32340120`: To be able to discuss uncertainty in estimated values, we must learn some statistics.
- `ctx_b7c61fc74173e5004c850c59`: The magnitude of the probability for the predicted class conveys one notion of uncertainty.

### Backup contexts

- `ctx_45b8a459ecccebb193b7d570`: It is not the only notion of uncertainty and we will discuss others in more advanced chapters.
- `ctx_d9d4e1e8372876c3a0bf9c2f`: That is, even when we arrive near the minimum, we are still subject to the uncertainty injected by the instantaneous gradient via $\eta \nabla f_i(\mathbf{x})$.
- `ctx_24231d5e4f53e2fed10ee784`: This is a process fraught with computational and statistical uncertainty.

### Contrastive contexts

- `ctxx_5780e748e8152fceb29fe2ec`: Synthetic: In everyday speech, uncertainty can mean personal hesitation rather than statistical or predictive uncertainty.

### Definition evidence

- `ctx_e7697bfcdc8c8d5ccbb78a65`: To reason rigorously under uncertainty we will need to invoke the language of probability.
- `ctx_dabb91193e9646a54768ead2`: However, there are some exceptions: some researchers use dropout at test time as a heuristic for estimating the *uncertainty* of neural network predictions: if the predictions agree across many different dropout masks, then we might say that the network is more confident.
- `ctx_47b329913c771cfa32340120`: To be able to discuss uncertainty in estimated values, we must learn some statistics.
- `ctx_923ebaa50c2bbcd9a6a3ab6c`: When estimating the value of a parameter $\theta$, point estimators like $\hat \theta$ are of limited utility since they contain no notion of uncertainty.

### Part-of-speech evidence

- `ctx_45b8a459ecccebb193b7d570`: It is not the only notion of uncertainty and we will discuss others in more advanced chapters.
- `ctx_dabb91193e9646a54768ead2`: However, there are some exceptions: some researchers use dropout at test time as a heuristic for estimating the *uncertainty* of neural network predictions: if the predictions agree across many different dropout masks, then we might say that the network is more confident.
