#define hamming_doc \
"hamming(seq1, seq2, normalized=False)\n\
\n\
Compute the Hamming distance between the two sequences `seq1` and `seq2`.\n\
The Hamming distance is the number of differing items in two ordered\n\
sequences of the same length. If the sequences submitted do not have the\n\
same length, an error will be raised.\n\
\n\
If `normalized` evaluates to `False`, the return value will be an integer\n\
between 0 and the length of the sequences provided, edge values included;\n\
otherwise, it will be a float between 0 and 1 included, where 0 means\n\
equal, and 1 totally different. Normalized hamming distance is computed as:\n\
\n\
    0.0                         if len(seq1) == 0\n\
    hamming_dist / len(seq1)    otherwise"


#define jaccard_doc \
"jaccard(seq1, seq2)\n\
\n\
Compute the Jaccard distance between the two sequences `seq1` and `seq2`.\n\
They should contain hashable items.\n\
\n\
The return value is a float between 0 and 1, where 0 means equal, and 1 totally different."


#define sorensen_doc \
"sorensen(seq1, seq2)\n\
\n\
Compute the Sorensen distance between the two sequences `seq1` and `seq2`.\n\
They should contain hashable items.\n\
\n\
The return value is a float between 0 and 1, where 0 means equal, and 1 totally different."


#define lcsubstrings_doc \
"lcsubstrings(seq1, seq2, positions=False)\n\
\n\
Find the longest common substring(s) in the sequences `seq1` and `seq2`.\n\
\n\
If positions evaluates to `True` only their positions will be returned,\n\
together with their length, in a tuple:\n\
\n\
    (length, [(start pos in seq1, start pos in seq2)..])\n\
\n\
Otherwise, the substrings themselves will be returned, in a set.\n\
\n\
Example:\n\
\n\
    >>> lcsubstrings(\"sedentar\", \"dentist\")\n\
    {'dent'}\n\
    >>> lcsubstrings(\"sedentar\", \"dentist\", positions=True)\n\
    (4, [(2, 0)])"


#define ilevenshtein_doc \
"ilevenshtein(seq1, seqs, max_dist=-1)\n\
\n\
Compute the Levenshtein distance between the sequence `seq1` and the series\n\
of      sequences `seqs`.\n\
\n\
    `seq1`: the reference sequence\n\
    `seqs`: a series of sequences (can be a generator)\n\
    `max_dist`: if provided and > 0, only the sequences which distance from\n\
    the reference sequence is lower or equal to this value will be returned.\n\
\n\
The return value is a series of pairs (distance, sequence).\n\
\n\
The sequence objects in `seqs` are expected to be of the same kind than\n\
the reference sequence in the C implementation; the same holds true for\n\
`ifast_comp`."


#define ifast_comp_doc \
"ifast_comp(seq1, seqs, transpositions=False)\n\
\n\
Return an iterator over all the sequences in `seqs` which distance from\n\
`seq1` is lower or equal to 2. The sequences which distance from the\n\
reference sequence is higher than that are dropped.\n\
\n\
    `seq1`: the reference sequence.\n\
    `seqs`: a series of sequences (can be a generator)\n\
    `transpositions` has the same sense than in `fast_comp`.\n\
\n\
The return value is a series of pairs (distance, sequence).\n\
\n\
You might want to call `sorted()` on the iterator to get the results in a\n\
significant order:\n\
\n\
    >>> g = ifast_comp(\"foo\", [\"fo\", \"bar\", \"foob\", \"foo\", \"foobaz\"])\n\
    >>> sorted(g)\n\
    [(0, 'foo'), (1, 'fo'), (1, 'foob')]"


#define fast_comp_doc \
"fast_comp(seq1, seq2, transpositions=False)\n\
\n\
Compute the distance between the two sequences `seq1` and `seq2` up to a\n\
maximum of 2 included, and return it. If the edit distance between the two\n\
sequences is higher than that, -1 is returned.\n\
\n\
If `transpositions` is `True`, transpositions will be taken into account for\n\
the computation of the distance. This can make a difference, e.g.:\n\
\n\
    >>> fast_comp(\"abc\", \"bac\", transpositions=False)\n\
    2\n\
    >>> fast_comp(\"abc\", \"bac\", transpositions=True)\n\
    1\n\
\n\
This is faster than `levenshtein` by an order of magnitude, but on the\n\
other hand is of limited use.\n\
\n\
The algorithm comes from `http://writingarchives.sakura.ne.jp/fastcomp`.\n\
I've added transpositions support to the original code."


#define levenshtein_doc \
"levenshtein(seq1, seq2, max_dist=-1, normalized=False)\n\
\n\
Compute the absolute Levenshtein distance between the two sequences\n\
`seq1` and `seq2`.\n\
\n\
The Levenshtein distance is the minimum number of edit operations necessary\n\
for transforming one sequence into the other. The edit operations allowed are:\n\
\n\
    * deletion:     ABC -> BC, AC, AB\n\
    * insertion:    ABC -> ABCD, EABC, AEBC..\n\
    * substitution: ABC -> ABE, ADC, FBC..\n\
\n\
The `max_dist` parameter controls at which moment we should stop computing the\n\
distance between the provided sequences. If it is a negative integer, the\n\
distance will be computed until the sequences are exhausted; otherwise, the\n\
computation will stop at the moment the calculated distance is higher than\n\
`max_dist`, and then return -1. For example:\n\
\n\
    >>> levenshtein(\"abc\", \"abcd\", max_dist=1)  # dist = 1\n\
    1\n\
    >>> levenshtein(\"abc\", \"abcde\", max_dist=1) # dist = 2\n\
    -1\n\
\n\
This can be a time saver if you're not interested in the exact distance, but\n\
only need to check if the distance between the given sequences is below a\n\
given threshold.\n\
\n\
The `normalized` parameter is here for backward compatibility; providing\n\
it will result in a call to `nlevenshtein`, which should be used directly\n\
instead. "


#define nlevenshtein_doc \
"nlevenshtein(seq1, seq2, method=1)\n\
\n\
Compute the normalized Levenshtein distance between `seq1` and `seq2`.\n\
\n\
Two normalization methods are provided. For both of them, the normalized\n\
distance will be a float between 0 and 1, where 0 means equal and 1\n\
completely different. The computation obeys the following patterns:\n\
\n\
    0.0                       if seq1 == seq2\n\
    1.0                       if len(seq1) == 0 or len(seq2) == 0\n\
    edit distance / factor    otherwise\n\
\n\
The `method` parameter specifies which normalization factor should be used.\n\
It can have the value 1 or 2, which correspond to the following:\n\
\n\
    1: the length of the shortest alignment between the sequences\n\
       (that is, the length of the longest sequence)\n\
    2: the length of the longest alignment between the sequences\n\
\n\
Which normalization factor should be chosen is a matter of taste. The first\n\
one is cheap to compute. The second one is more costly, but it accounts\n\
better than the first one for parallelisms of symbols between the sequences.\n\
    \n\
For the rationale behind the use of the second method, see:\n\
Heeringa, \"Measuring Dialect Pronunciation Differences using Levenshtein\n\
Distance\", 2004, p. 130 sq, which is available online at:\n\
http://www.let.rug.nl/~heeringa/dialectology/thesis/thesis.pdf"





#define SEQUENCE_COMPARE(s1, i1, s2, i2) \
(PyObject_RichCompareBool( \
	PySequence_Fast_GET_ITEM((s1), (i1)), \
	PySequence_Fast_GET_ITEM((s2), (i2)), \
	Py_EQ) \
)

#define unicode unicode
#define hamming uhamming
#include "hamming.c"
#undef unicode
#undef hamming

#define unicode byte
#define hamming bhamming
#include "hamming.c"
#undef unicode
#undef hamming

#define SEQUENCE_COMP SEQUENCE_COMPARE
#define unicode array
#define hamming ahamming
#include "hamming.c"
#undef unicode
#undef hamming
#undef SEQUENCE_COMP

#define unicode unicode
#define levenshtein ulevenshtein
#define nlevenshtein unlevenshtein
#include "levenshtein.c"
#undef unicode
#undef levenshtein
#undef nlevenshtein

#define unicode byte
#define levenshtein blevenshtein
#define nlevenshtein bnlevenshtein
#include "levenshtein.c"
#undef unicode
#undef levenshtein
#undef nlevenshtein

#define SEQUENCE_COMP SEQUENCE_COMPARE
#define unicode array
#define levenshtein alevenshtein
#define nlevenshtein anlevenshtein
#include "levenshtein.c"
#undef unicode
#undef levenshtein
#undef nlevenshtein
#undef SEQUENCE_COMP

#define unicode unicode
#define lcsubstrings ulcsubstrings
#include "lcsubstrings.c"
#undef unicode
#undef lcsubstrings

#define unicode byte
#define lcsubstrings blcsubstrings
#include "lcsubstrings.c"
#undef unicode
#undef lcsubstrings

#define SEQUENCE_COMP SEQUENCE_COMPARE
#define unicode array
#define lcsubstrings alcsubstrings
#include "lcsubstrings.c"
#undef unicode
#undef lcsubstrings
#undef SEQUENCE_COMP

#define unicode unicode
#define fastcomp ufastcomp
#include "fastcomp.c"
#undef unicode
#undef fastcomp

#define unicode byte
#define fastcomp bfastcomp
#include "fastcomp.c"
#undef unicode
#undef fastcomp

#define SEQUENCE_COMP SEQUENCE_COMPARE
#define unicode array
#define fastcomp afastcomp
#include "fastcomp.c"
#undef unicode
#undef fastcomp
#undef SEQUENCE_COMP
