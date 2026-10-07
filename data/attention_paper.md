# 1. Introduction

Recurrent networks (including LSTMs and gated recurrent units) had been the
standard approach for sequence tasks like language modeling and translation.
Their core limitation is that they process a sequence one position at a time,
which makes it hard to parallelize computation across a sequence during
training and becomes a bigger problem as sequences get longer. Attention
mechanisms had already been layered on top of recurrent models to help relate
distant parts of a sequence, but almost always alongside recurrence rather
than replacing it. This paper introduces the Transformer, an architecture
that drops recurrence and convolution entirely and relies only on attention
to model relationships between all positions in a sequence. Because it
removes the strict step-by-step dependency of recurrent models, it trains
much faster while achieving better translation quality — reaching a new
state-of-the-art result after only about twelve hours of training on eight
GPUs.

# 2. Background

Prior work aimed at reducing sequential computation used convolutional
architectures instead of recurrence, processing all positions in parallel.
However, relating two distant positions in these convolutional models still
requires a number of operations that grows with the distance between them
(linearly or logarithmically depending on the architecture), making
long-range dependencies harder to learn. The Transformer reduces this to a
constant number of operations regardless of distance, at the cost of some
lost resolution from averaging over positions — a trade-off the authors
address with multi-head attention (covered in section 3.2). Self-attention,
where a sequence attends to its own positions to build a representation of
itself, had already proven useful in tasks like reading comprehension and
summarization. This paper claims the Transformer is the first model to rely
entirely on self-attention, without any recurrent or convolutional layers.

# 3. Model Architecture

Most competitive sequence models use an encoder-decoder structure: the
encoder turns an input sequence into a sequence of continuous
representations, and the decoder generates an output sequence one element at
a time, feeding each generated element back in to help produce the next one
(auto-regressive generation). The Transformer follows this same overall
shape, but builds both the encoder and decoder out of stacked self-attention
layers and simple feed-forward layers, rather than recurrent or convolutional
ones.

## 3.1 Encoder and Decoder Stacks

The encoder is a stack of 6 identical layers. Each layer has two parts: a
multi-head self-attention mechanism, and a simple fully-connected
feed-forward network applied independently to each position. Each of these
two parts has a residual (skip) connection around it followed by layer
normalization, and every sub-layer's output has dimension 512 to keep these
residual connections consistent.

The decoder is also a stack of 6 identical layers, but each decoder layer
adds a third sub-layer that performs multi-head attention over the encoder's
output, letting the decoder look at the full input sequence while generating
each output element. The decoder's self-attention is also modified with
masking, so that when predicting a given position, it can only use
information from earlier positions in the output — never positions that
come later, which would leak information it shouldn't have yet.

## 3.2 Attention

An attention function maps a query and a set of key-value pairs to an
output. The output is a weighted sum of the values, where each value's
weight comes from how compatible the query is with the corresponding key.

The specific attention function used here is called "Scaled Dot-Product
Attention": the queries and keys have some dimension, and the output is
computed by taking the dot product of the query with all keys, scaling by
the square root of that key dimension, applying softmax to get weights, and
using those weights to combine the values. The scaling factor matters — for
large key dimensions, unscaled dot products can grow large and push softmax
into regions with extremely small gradients, which the scaling counteracts.

Rather than performing one attention function with the full-dimensional
keys, queries, and values, the model linearly projects them into several
smaller-dimensional versions ("heads") and performs attention on each in
parallel, then concatenates and projects the results back to the original
dimension. This is Multi-Head Attention. The paper uses 8 parallel heads,
each working with a reduced dimension, so the total computational cost stays
similar to a single full-dimension attention operation while letting the
model attend to different representation subspaces at once — something a
single attention head, which averages everything together, cannot do.

The Transformer uses multi-head attention in three distinct places: (1)
encoder-decoder attention layers, where queries come from the previous
decoder layer and keys/values come from the encoder's output, letting every
decoder position attend over the entire input; (2) encoder self-attention,
where each position in the encoder can attend to every position in the
previous encoder layer; and (3) masked decoder self-attention, where each
decoder position can attend only to earlier positions (including itself),
enforced by masking out illegal connections before the softmax step.

## 3.3 Position-wise Feed-Forward Networks

In addition to attention, each encoder and decoder layer contains a
feed-forward network applied identically and separately to each position.
It consists of two linear transformations with a ReLU activation in between.
The same structure is used at every position, but the actual parameters
differ from layer to layer. Input and output dimensionality is 512, with an
inner layer dimensionality of 2048.

## 3.4 Embeddings and Softmax

Like other sequence models, learned embeddings convert input and output
tokens into 512-dimensional vectors. A learned linear transformation and
softmax convert the decoder's output into predicted next-token
probabilities. This model shares the same weight matrix between both
embedding layers and the pre-softmax linear transformation, and scales those
embedding weights by the square root of the model dimension.

## 3.5 Positional Encoding

Since the model has no recurrence or convolution, it has no inherent sense
of token order — something must be added to convey each token's position in
the sequence. The authors add "positional encodings" to the input embeddings
at the start of both the encoder and decoder stacks, using sine and cosine
functions of different frequencies, one per dimension, forming a geometric
progression of wavelengths. They chose this fixed sinusoidal scheme (over a
learned alternative, which performed nearly identically in testing) because
it may let the model generalize to sequence lengths longer than any seen
during training.

# 4. Why Self-Attention

This section compares self-attention against recurrent and convolutional
layers along three dimensions: total computational complexity per layer, how
much computation can be parallelized (measured by the minimum number of
sequential operations required), and the path length that signals must
travel between distant positions in the network — a key factor in how
easily a model can learn long-range dependencies.

A self-attention layer connects every pair of positions using a constant
number of sequential operations, while a recurrent layer requires a number
of sequential operations proportional to sequence length. Self-attention is
computationally cheaper than recurrence whenever the sequence length is
smaller than the representation dimension, which is typically true for the
sentence representations used in state-of-the-art translation systems. A
single convolutional layer, unless its kernel spans the whole sequence,
doesn't connect every pair of positions directly — doing so requires
stacking multiple convolutional layers, which increases the path length
between distant positions. As a side benefit, the authors note that
self-attention may also produce more interpretable models, since individual
attention heads appear to learn distinct roles related to a sentence's
syntactic and semantic structure.

# 5. Training

This section describes how the models were trained.

## 5.1 Training Data and Batching

The models were trained on the WMT 2014 English-German dataset (about 4.5
million sentence pairs, encoded with byte-pair encoding into a roughly
37,000-token shared vocabulary) and, separately, the much larger WMT 2014
English-French dataset (about 36 million sentences, split into a 32,000
word-piece vocabulary). Sentence pairs were batched together by approximate
length, with each training batch containing roughly 25,000 source and 25,000
target tokens.

## 5.2 Hardware and Schedule

Training ran on a single machine with 8 NVIDIA P100 GPUs. The base models
took about 0.4 seconds per training step and were trained for 100,000 steps
(about 12 hours total). The larger models took about 1.0 second per step and
were trained for 300,000 steps (about 3.5 days).

## 5.3 Optimizer

Training used the Adam optimizer with specific beta and epsilon values. The
learning rate was increased linearly for an initial warm-up period (4,000
steps), then decreased afterward proportionally to the inverse square root
of the step number.

## 5.4 Regularization

Three regularization techniques were used during training: residual
dropout, applied to each sub-layer's output before it's added back to the
sub-layer's input, as well as to the combined embeddings and positional
encodings (a dropout rate of 0.1 for the base model); and label smoothing,
which slightly hurts the model's confidence calibration (perplexity) but
improves overall accuracy and translation quality (BLEU score).

# 6. Results

## 6.1 Machine Translation

On the WMT 2014 English-to-German task, the larger Transformer model beat
the best previously reported results (including model ensembles) by more
than 2 BLEU points, setting a new state-of-the-art score, after training for
3.5 days on 8 GPUs — a fraction of the training cost of competing
architectures. Even the smaller base model outperformed all previously
published single models and ensembles at a much lower training cost. On the
English-to-French task, the larger model achieved a new best single-model
score, at under a quarter of the training cost of the previous best system.
Final translations used beam search with a fixed beam size and length
penalty, with maximum output length capped relative to input length (though
generation could stop early).

## 6.2 Model Variations

The authors tested several variations on the base model to see which
architectural choices mattered most, evaluating on the English-to-German
development set. Varying the number of attention heads (while keeping total
computation constant) showed that single-head attention performs noticeably
worse than the chosen multi-head setup, and that quality also drops if too
many heads are used. Reducing the attention key dimension also hurt
quality, suggesting that a more sophisticated compatibility function than a
simple dot product might help. As expected, larger models performed better
overall, and dropout was clearly effective at preventing overfitting.
Replacing the fixed sinusoidal positional encoding with a learned positional
embedding produced nearly identical results to the original approach.

# 7. Conclusion

The paper presents the Transformer, described as the first sequence
transduction model built entirely on attention, replacing the recurrent
layers typically used in encoder-decoder architectures with multi-headed
self-attention. On both WMT 2014 translation tasks tested, it trains
significantly faster than recurrent or convolutional alternatives while
achieving a new state of the art, with the English-to-German result beating
even previously reported ensembles. The authors express interest in
extending the approach beyond text, to other input/output modalities such as
images, audio, and video, and in exploring more efficient attention
mechanisms for very large inputs and outputs.
