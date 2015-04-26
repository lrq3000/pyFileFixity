#include "distance.h"


static short
fastcomp(unicode *seq1, unicode *seq2, Py_ssize_t len1, Py_ssize_t len2, int transpositions)
{
	char *models[3];
	short m, cnt, res = 3;
	Py_ssize_t i, j, c, ldiff;
#ifdef SEQUENCE_COMP
	int comp;
#endif
	
	if (len1 < len2) {
		SWAP(unicode *,  seq1, seq2);
		SWAP(Py_ssize_t, len1, len2);
	}
	
	ldiff = len1 - len2;
	switch (ldiff) {
		case 0:
			models[2] = "id";
			models[1] = "di";
			models[0] = "rr";
			m = 2;
			break;
		case 1:
			models[1] = "dr";
			models[0] = "rd";
			m = 1;
			break;
		case 2:
			models[0] = "dd";
			m = 0;
			break;
		default:
			return -1;
	}

	for (; m >= 0; m--) {
	
		i = j = c = 0;
		
		while (i < len1 && j < len2)
		{
#ifdef SEQUENCE_COMP
			comp = SEQUENCE_COMP(seq1, i, seq2, j);
			if (comp == -1)
				return -2;
			if (!comp) {
#else
			if (seq1[i] != seq2[j]) {
#endif
				c++;
				if (c > 2)
					break;
				
				/* Transpositions handling. `ldiff`, which is the absolute difference between the length
				of the sequences `seq1` and `seq2`, should not be equal to 2 because in this case only
				deletions can happen (given that the distance between the two sequences should not be
				higher than 2, this is the shortest path).
				We do a lookahead to check if a transposition is possible between the current position
				and the next one, and, if so, we systematically	choose this path over the other alternative
				edit operations. We act like so because the cost of a transposition is always the lowest
				one in such situations.
				*/
#ifdef SEQUENCE_COMP
				if (transpositions && ldiff != 2 && i < (len1 - 1) && j < (len2 - 1)) {
					comp = SEQUENCE_COMP(seq1, i + 1, seq2, j);
					if (comp == -1)
						return -2;
					else if (comp) {
						comp = SEQUENCE_COMP(seq1, i, seq2, j + 1);
						if (comp == -1)
							return -2;
						else if (comp) {
							i = i + 2;
							j = j + 2;
							continue;
						}
					}
				}
#else
				if (transpositions && ldiff != 2 && i < (len1 - 1) && j < (len2 - 1) && \
					seq1[i + 1] == seq2[j] && \
					seq1[i] == seq2[j + 1]) {
					i = i + 2;
					j = j + 2;
					continue;
				}
#endif
				if (models[m][c - 1] == 'd')
					i++;
				else if (models[m][c - 1] == 'i')
					j++;
				else {
					i++;
					j++;
				}
			}
			else {
				i++;
				j++;
			}
		}
		
		if (c > 2)
			continue;

		else if (i < len1) {
			if (c == 1)
				cnt = (models[m][1] == 'd');
			else
				cnt = (models[m][0] == 'd') + (models[m][1] == 'd');
			if (len1 - i <= cnt) {
				c = c + (len1 - i);
			}
			else
				continue;
		}
		else if (j < len2) {
			if (len2 - j <= (models[m][c] == 'i'))
				c = c + (len2 - j);
			else
				continue;
		}
		if (c < res) {
			res = c;
		}
	}

	if (res == 3)
		res = -1;
		
	return res;
}
