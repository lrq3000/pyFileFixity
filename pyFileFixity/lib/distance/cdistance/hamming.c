#include "distance.h"

static Py_ssize_t
hamming(unicode *seq1, unicode *seq2, Py_ssize_t len)
{
	Py_ssize_t i, dist = 0;
#ifdef SEQUENCE_COMP
	int comp;
#endif
	
	for (i = 0; i < len; i++) {
#ifdef SEQUENCE_COMP
		comp = SEQUENCE_COMP(seq1, i, seq2, i);
		if (comp == -1)
			return -1;
		if (!comp)
#else
		if (seq1[i] != seq2[i])
#endif
			dist++;
	}

	return dist;
}
