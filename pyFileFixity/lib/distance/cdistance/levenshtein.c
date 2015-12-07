#include "distance.h"

#define MIN3(a, b, c) ((a) < (b) ? ((a) < (c) ? (a) : (c)) : ((b) < (c) ? (b) : (c)))
#define MAX3(a, b, c) ((a) > (b) ? ((a) > (c) ? (a) : (c)) : ((b) > (c) ? (b) : (c)))

#ifndef LEVENSHTEIN_C
#define LEVENSHTEIN_C

static Py_ssize_t
minimum(const Py_ssize_t *column, Py_ssize_t len)
{
	Py_ssize_t min;

	assert(len > 0);
	min = column[--len];
	while (len-- >= 0) {
		if (column[len] < min)
			min = column[len];
	}
	
	return min;
}

#endif

static Py_ssize_t
levenshtein(unicode *seq1, unicode *seq2, Py_ssize_t len1, Py_ssize_t len2, Py_ssize_t max_dist)
{
	Py_ssize_t i, j;
	Py_ssize_t last, old;
	Py_ssize_t cost, dist = -2;
	Py_ssize_t *column;

#ifdef SEQUENCE_COMP
	int comp;
#endif
	
	if (len1 < len2) {
		SWAP(unicode *,  seq1, seq2);
		SWAP(Py_ssize_t, len1, len2);
	}
	
	if (max_dist >= 0 && (len1 - len2) > max_dist)
		return -1;
	else {
		if (len1 == 0)
			return len2;
		if (len2 == 0)
			return len1;
	}

	if ((column = (Py_ssize_t *) malloc((len2 + 1) * sizeof(Py_ssize_t))) == NULL)
		return -2;

	for (j = 1 ; j <= len2; j++)
		column[j] = j;
	
	for (i = 1 ; i <= len1; i++) {
		column[0] = i;
		for (j = 1, last = i - 1; j <= len2; j++) {
			old = column[j];
#ifdef SEQUENCE_COMP
			comp = SEQUENCE_COMP(seq1, i - 1, seq2, j - 1);
			if (comp == -1) {
				free(column);
				return -3;
			}
			cost = (!comp);
#else
			cost = (seq1[i - 1] != seq2[j - 1]);
#endif
			column[j] = MIN3(
				column[j] + 1,
				column[j - 1] + 1,
				last + cost
			);
			last = old;
		}
		if (max_dist >= 0 && minimum(column, len2 + 1) > max_dist) {
			free(column);
			return -1;
		}
	}

	dist = column[len2];
	
	free(column);
	
	if (max_dist >= 0 && dist > max_dist)
		return -1;
	return dist;
}


static double
nlevenshtein(unicode *seq1, unicode *seq2, Py_ssize_t len1, Py_ssize_t len2, short method)
{
	Py_ssize_t i, j;
	
	// distance
	Py_ssize_t ic, dc, rc;
	Py_ssize_t last, old;
	Py_ssize_t *column;
	Py_ssize_t fdist;
	
	// length
	Py_ssize_t lic, ldc, lrc;
	Py_ssize_t llast, lold;
	Py_ssize_t *length;
	Py_ssize_t flen;

#ifdef SEQUENCE_COMP
	int comp;
#endif
	
	assert(len1 >= len2);
	
	if (len1 == 0) // len2 is 0 too, so the two sequences are identical
		return 0.0;
	if (len2 == 0) // completely different
		return 1.0;
	
	if (method == 1) {
		fdist = levenshtein(seq1, seq2, len1, len2, -1);
		if (fdist < 0)  // error
			return fdist;
		return fdist / (double)len1;
	}

	if ((column = (Py_ssize_t *)malloc((len2 + 1) * sizeof(Py_ssize_t))) == NULL)
		return -1;
	if ((length = (Py_ssize_t *)malloc((len2 + 1) * sizeof(Py_ssize_t))) == NULL) {
		free(column);
		return -1;
	}

	for (j = 1 ; j <= len2; j++)
		column[j] = length[j] = j;
	
	for (i = 1 ; i <= len1; i++) {
		column[0] = length[0] = i;
		
		for (j = 1, last = llast = i - 1; j <= len2; j++) {
		
			// distance
			old = column[j];
			ic = column[j - 1] + 1;
			dc = column[j] + 1;
#ifdef SEQUENCE_COMP
			comp = SEQUENCE_COMP(seq1, i - 1, seq2, j - 1);
			if (comp == -1) {
				free(column);
				free(length);
				return -2;
			}
			rc = last + (!comp);
#else
			rc = last + (seq1[i - 1] != seq2[j - 1]);
#endif
			column[j] = MIN3(ic, dc, rc);
			last = old;
			
			// length
			lold = length[j];
			lic = (ic == column[j] ? length[j - 1] + 1 : 0);
			ldc = (dc == column[j] ? length[j] + 1 : 0);
			lrc = (rc == column[j] ? llast + 1 : 0);
			length[j] = MAX3(lic, ldc, lrc);
			llast = lold;
		}
	}

	fdist = column[len2];
	flen = length[len2];
	
	free(column);
	free(length);
	
	return fdist / (double)flen;
}
