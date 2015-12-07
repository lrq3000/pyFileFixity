#include "distance.h"


static UT_array *
lcsubstrings(unicode *seq1, unicode *seq2,
             Py_ssize_t len1, Py_ssize_t len2, Py_ssize_t *max_len)
{
	Py_ssize_t i, j, mlen = -1;
	Py_ssize_t old, last, *column;
	UT_array *stack = NULL;
	struct pair_t pos;
#ifdef SEQUENCE_COMP
	int comp;
#endif
	
	assert(len1 >= len2);
	
	utarray_new(stack, &pair_icd);
	
	if (len2 == 0) {
		*max_len = 0;
		return stack;
	}
	
	if ((column = (Py_ssize_t *)malloc((len2 + 1) * sizeof(Py_ssize_t))) == NULL)
		goto On_Error;
	
	last = 0;
	for (j = 0; j < len2; j++)
		column[j] = j;
	
	for (i = 0; i < len1; i++) {
		for (j = 0; j < len2; j++) {
			old = column[j];
#ifdef SEQUENCE_COMP
			comp = SEQUENCE_COMP(seq1, i, seq2, j);
			if (comp == -1)
				goto On_Error;
			if (comp) {
#else
			if (seq1[i] == seq2[j]) {
#endif
				column[j] = ((i == 0 || j == 0) ? 1 : (last + 1));
				if (column[j] > mlen) {
					mlen = column[j];
					pos.i = i;
					pos.j = j;
					utarray_clear(stack);
					utarray_push_back(stack, &pos);
				}
				else if (column[j] == mlen) {
					pos.i = i;
					pos.j = j;
					utarray_push_back(stack, &pos);
				}
			}
			else
				column[j] = 0;
			last = old;
		}
	}
	
	free(column);

	*max_len = mlen;
	return stack;
	
	On_Error:
		free(column);
		utarray_free(stack);
		return NULL;
}
