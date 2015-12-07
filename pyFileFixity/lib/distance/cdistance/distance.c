#include "distance.h"
#include "includes.h"


static unicode *
get_unicode(PyObject *obj, Py_ssize_t *len)
{
	unicode *u;
	
	if ((u = PyUnicode_AS_UNICODE(obj)) == NULL) {
		PyErr_Format(PyExc_RuntimeError, "failed to get unicode representation of object");
		return NULL;
	}
	*len = PyUnicode_GET_LENGTH(obj);
	
	return u;
}


static byte *
get_byte(PyObject *obj, Py_ssize_t *len)
{
	byte *b;

	b = PyBytes_AS_STRING(obj);
	*len = PyBytes_GET_SIZE(obj);
	
	return b;
}


static array *
get_array(PyObject *obj, Py_ssize_t *len)
{
	array *a;
	
	if ((a = PySequence_Fast(obj, "we got a problem")) == NULL)
		return NULL;
	*len = PySequence_Fast_GET_SIZE(a);
	
	return a;
}


static char
get_sequence(PyObject *obj, sequence *seq, Py_ssize_t *len, char type)
{
	char t = '\0';
	
	if (PyUnicode_Check(obj)) {
		t = 'u';
		if ((seq->u = get_unicode(obj, len)) == NULL)
			return '\0';
	} else if (PyBytes_Check(obj)) {
		t = 'b';
		if ((seq->b = get_byte(obj, len)) == NULL)
			return '\0';
	} else if (PySequence_Check(obj)) {
		t = 'a';
		if ((seq->a = get_array(obj, len)) == NULL)
			return '\0';
	}
	
	if (!t) {
		PyErr_SetString(PyExc_ValueError, "expected a sequence object as first argument");
		return '\0';
	}
	if (type && t != type) {
		PyErr_SetString(PyExc_ValueError, "type mismatch between the "
			"value provided as left argument and one of the elements in "
			"the right one, can't process the later");
		if (t == 'a')
			Py_DECREF(seq->a);
		return '\0';
	}
	return t;
}


static char
get_sequences(PyObject *arg1, PyObject *arg2, sequence *seq1, sequence *seq2,
              Py_ssize_t *len1, Py_ssize_t *len2)
{
	if (PyUnicode_Check(arg1) && PyUnicode_Check(arg2)) {
		
		if ((seq1->u = get_unicode(arg1, len1)) == NULL)
			return '\0';
		if ((seq2->u = get_unicode(arg2, len2)) == NULL)
			return '\0';
		return 'u';
		
	} else if (PyBytes_Check(arg1) && PyBytes_Check(arg2)) {
	
		if ((seq1->b = get_byte(arg1, len1)) == NULL)
			return '\0';
		if ((seq2->b = get_byte(arg2, len2)) == NULL)
			return '\0';
		return 'b';
		
	} else if (PySequence_Check(arg1) && PySequence_Check(arg2)) {
	
		if ((seq1->a = get_array(arg1, len1)) == NULL)
			return '\0';
		if ((seq2->a = get_array(arg2, len2)) == NULL) {
			Py_DECREF(seq1->a);				/* warning ! */
			return '\0';
		}
		return 'a';
	}
	
	PyErr_SetString(PyExc_ValueError, "expected two sequence objects");
	return '\0';
}


static PyObject *
hamming_py(PyObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *odo_normalize = NULL;
	int do_normalize = 0;
	static char *keywords[] = {"seq1", "seq2", "normalized", NULL};

	char type;
	sequence seq1, seq2;
	Py_ssize_t len1, len2;
	Py_ssize_t dist;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs,
		"OO|O:hamming", keywords, &arg1, &arg2, &odo_normalize))
		return NULL;

	if (odo_normalize && (do_normalize = PyObject_IsTrue(odo_normalize)) == -1)
		return NULL;
	
	if ((type = get_sequences(arg1, arg2, &seq1, &seq2, &len1, &len2)) == '\0')
		return NULL;
	
	if (len1 != len2) {
		PyErr_SetString(PyExc_ValueError, "expected two objects of the same length");
		if (type == 'a') {
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
		}
		return NULL;
	}
	
	switch(type) {
		case 'u':
			dist = uhamming(seq1.u, seq2.u, len1);
			break;
		case 'b':
			dist = bhamming(seq1.b, seq2.b, len1);
			break;
		default:
			dist = ahamming(seq1.a, seq2.a, len1);
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
	}
	
	if (dist == -1) // comparison failed
		return NULL;
	
	if (do_normalize) {
		if (len1 == 0)
			return Py_BuildValue("f", 0.0f);
		return Py_BuildValue("d", dist / (double)len1);
	}
	
	return Py_BuildValue("n", dist);
}


static PyObject *
lcsubstrings_py_make_set(PyObject *arg1, PyObject *arg2, UT_array *stack, Py_ssize_t mlen)
{
	PyObject *set, *ss;
	struct pair_t *pair;
	
	if ((set = PySet_New(NULL)) == NULL) {
		utarray_free(stack);
		return NULL;
	}

	for (pair = (struct pair_t*)utarray_front(stack);
		pair != NULL;
		pair = (struct pair_t*)utarray_next(stack, pair)) {
		
		ss = PySequence_GetSlice(arg2, pair->j - mlen + 1, pair->j + 1);
		if (ss == NULL)
			goto On_Error;
		if ((PySet_Add(set, ss)) == -1)
			goto On_Error;
	}

	utarray_free(stack);
	return set;
	
	On_Error:
		PySet_Clear(set);
		Py_DECREF(set);
		utarray_free(stack);
		return NULL;
}


static PyObject *
lcsubstrings_py_make_tuple(PyObject *arg1, PyObject *arg2, UT_array *stack, Py_ssize_t mlen)
{
	PyObject *tp, *stp;
	Py_ssize_t i;
	struct pair_t *pair;
	
	if ((stp = PyTuple_New(utarray_len(stack))) == NULL) {
		utarray_free(stack);
		return NULL;
	}
	for (i = 0, pair = (struct pair_t*)utarray_front(stack);
		pair != NULL;
		++i, pair = (struct pair_t*)utarray_next(stack, pair)) {
		PyTuple_SET_ITEM(stp, i, Py_BuildValue("(nn)", pair->i - mlen + 1, pair->j - mlen + 1));
	}
	if ((tp = PyTuple_New(2)) == NULL) {
		utarray_free(stack);
		Py_DECREF(stp);
		return NULL;
	}
	PyTuple_SET_ITEM(tp, 0, Py_BuildValue("n", mlen));
	PyTuple_SET_ITEM(tp, 1, stp);
	
	utarray_free(stack);
	
	return tp;
}


static PyObject *
lcsubstrings_py(PyObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *opos = NULL;
	int positions = 0;
	static char *keywords[] = {"seq1", "seq2", "positions", NULL};
	
	char type;
	sequence seq1, seq2;
	Py_ssize_t len1, len2;
	UT_array *stack;
	Py_ssize_t mlen = -1;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwargs,
		"OO|O:lcsubstrings", keywords, &arg1, &arg2, &opos))
		return NULL;
	if (opos && (positions = PyObject_IsTrue(opos)) == -1)
		return NULL;

	if ((type = get_sequences(arg1, arg2, &seq1, &seq2, &len1, &len2)) == '\0')
		return NULL;
	
	// special case
	if (type == 'a' && (!positions) && (PyList_Check(arg1) || PyList_Check(arg2))) {
		Py_DECREF(seq1.a);
		Py_DECREF(seq2.a);
		PyErr_SetString(PyExc_TypeError, "can't hash lists, pass in tuples instead");
		return NULL;
	}
	
	if (len1 < len2) {
		SWAP(PyObject *, arg1, arg2);
		SWAP(sequence,   seq1, seq2);
		SWAP(Py_ssize_t, len1, len2);
	}

	switch(type) {
		case 'u':
			stack = ulcsubstrings(seq1.u, seq2.u, len1, len2, &mlen);
			break;
		case 'b':
			stack = blcsubstrings(seq1.b, seq2.b, len1, len2, &mlen);
			break;
		default:
			stack = alcsubstrings(seq1.a, seq2.a, len1, len2, &mlen);
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
	}
	
	if (stack == NULL) {
		/* memory allocation failed */
		return PyErr_NoMemory();
	}
	
	if (positions)
		return lcsubstrings_py_make_tuple(arg1, arg2, stack, mlen);
	return lcsubstrings_py_make_set(arg1, arg2, stack, mlen);
}


static PyObject *
nlevenshtein_py(PyObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2;
	short method = 1;
	static char *keywords[] = {"seq1", "seq2", "method", NULL};

	char type;
	sequence seq1, seq2;
	Py_ssize_t len1, len2;
	double dist;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwargs,
		"OO|h:nlevenshtein", keywords, &arg1, &arg2, &method))
		return NULL;
	
	if (method != 1 && method != 2) {
		PyErr_SetString(PyExc_ValueError, "expected either 1 or 2 for `method` parameter");
		return NULL;
	}
	
	if ((type = get_sequences(arg1, arg2, &seq1, &seq2, &len1, &len2)) == '\0')
		return NULL;
	
	if (len1 < len2) {
		SWAP(sequence,   seq1, seq2);
		SWAP(Py_ssize_t, len1, len2);
	}
	
	switch(type) {
		case 'u':
			dist = unlevenshtein(seq1.u, seq2.u, len1, len2, method);
			break;
		case 'b':
			dist = bnlevenshtein(seq1.b, seq2.b, len1, len2, method);
			break;
		default:
			dist = anlevenshtein(seq1.a, seq2.a, len1, len2, method);
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
	}
	
	if (dist < 0) {
		if (dist == -1) // memory allocation failed
			return PyErr_NoMemory();
		return NULL;    // comparison failed
	}
	
	return Py_BuildValue("d", dist);	
}


static PyObject *
levenshtein_py(PyObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *onorm = NULL;
	Py_ssize_t dist = -1;
	Py_ssize_t max_dist = -1;
	int normalized = 0;
	static char *keywords[] = {"seq1", "seq2", "normalized", "max_dist", NULL};

	char type;
	sequence seq1, seq2;
	Py_ssize_t len1, len2;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwargs,
		"OO|On:levenshtein", keywords, &arg1, &arg2, &onorm, &max_dist))
		return NULL;
	if (onorm && (normalized = PyObject_IsTrue(onorm)) == -1)
		return NULL;
	
	if (normalized) {
		onorm = NULL;
		return nlevenshtein_py(self, args, onorm);
	}

	if ((type = get_sequences(arg1, arg2, &seq1, &seq2, &len1, &len2)) == '\0')
		return NULL;
	
	switch(type) {
		case 'u':
			dist = ulevenshtein(seq1.u, seq2.u, len1, len2, max_dist);
			break;
		case 'b':
			dist = blevenshtein(seq1.b, seq2.b, len1, len2, max_dist);
			break;
		default:
			dist = alevenshtein(seq1.a, seq2.a, len1, len2, max_dist);
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
	}
	
	if (dist < -1) {
		if (dist == -2)
			return PyErr_NoMemory(); // memory allocation failed
		return NULL; // comparison failed
	}
	return Py_BuildValue("n", dist);
}


static PyObject *
fastcomp_py(PyObject *self, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *otr = NULL;
	int transpositions = 0;
	static char *keywords[] = {"seq1", "seq2", "transpositions", NULL};
	
	char type;
	sequence seq1, seq2;
	Py_ssize_t len1, len2;
	short dist;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|O:fast_comp",
		keywords, &arg1, &arg2, &transpositions))
		return NULL;
	if (otr && (transpositions = PyObject_IsTrue(otr)) == -1)
		return NULL;

	if ((type = get_sequences(arg1, arg2, &seq1, &seq2, &len1, &len2)) == '\0')
		return NULL;
	
	if (len1 < len2) {
		SWAP(sequence,   seq1, seq2);
		SWAP(Py_ssize_t, len1, len2);
	}

	switch(type) {
		case 'u':
			dist = ufastcomp(seq1.u, seq2.u, len1, len2, transpositions);
			break;
		case 'b':
			dist = bfastcomp(seq1.b, seq2.b, len1, len2, transpositions);
			break;
		default:
			dist = afastcomp(seq1.a, seq2.a, len1, len2, transpositions);
			Py_DECREF(seq1.a);
			Py_DECREF(seq2.a);
	}
	
	if (dist == -2)	// comparison failed
		return NULL;
	
	return Py_BuildValue("h", dist);	
}



// Iterators (for levenshtein and fastcomp). They share the same structure.

typedef struct {
	PyObject_HEAD
	PyObject *itor;
	char seqtype;			// type of the sequence ('u', 'b', 'a')
	sequence seq1;			// the sequence itself
	Py_ssize_t len1;		// its length
	PyObject *object;		// the corresponding pyobject
	int transpos;			// only valable for fastcomp
	Py_ssize_t max_dist;	// only for levenshtein
} ItorState;


static void itor_dealloc(ItorState *state)
{
	// we got two references for tuples and lists, one for the original python object,
	// and one returned by `PySequence_fast`
	if (state->seqtype == 'a')
		Py_XDECREF(state->seq1.a);
	Py_XDECREF(state->object);
	Py_XDECREF(state->itor);
	Py_TYPE(state)->tp_free(state);
}


static PyObject *
ifastcomp_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *itor;
	int transpositions = 0;
	static char *keywords[] = {"seq1", "seqs", "transpositions", NULL};
	
	char seqtype;
	sequence seq1;
	Py_ssize_t len1;
	
	if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|O:ifast_comp",
		keywords, &arg1, &arg2, &transpositions))
		return NULL;
	if (otr && (transpositions = PyObject_IsTrue(otr)) == -1)
		return NULL;
	
	if ((seqtype = get_sequence(arg1, &seq1, &len1, '\0')) == '\0')
		return NULL;
	
	if ((itor = PyObject_GetIter(arg2)) == NULL) {
		PyErr_SetString(PyExc_ValueError, "expected an iterable as second argument");
		return NULL;
	}

	ItorState *state = (ItorState *)type->tp_alloc(type, 0);
	if (state == NULL) {
		Py_DECREF(itor);
		return NULL;
	}

	Py_INCREF(arg1);

	state->itor = itor;
	state->seqtype = seqtype;
	state->seq1 = seq1;
	state->object = arg1;
	state->len1 = len1;
	state->transpos = transpositions;
	
	return (PyObject *)state;
}


static PyObject *
ilevenshtein_new(PyTypeObject *type, PyObject *args, PyObject *kwargs)
{
	PyObject *arg1, *arg2, *itor;
	Py_ssize_t max_dist = -1;
	static char *keywords[] = {"seq1", "seqs", "max_dist", NULL};
	
	char seqtype;
	sequence seq1;
	Py_ssize_t len1;

	if (!PyArg_ParseTupleAndKeywords(args, kwargs,
		"OO|n:ilevenshtein", keywords, &arg1, &arg2, &max_dist))
		return NULL;

	if ((seqtype = get_sequence(arg1, &seq1, &len1, '\0')) == '\0')
		return NULL;
	
	if ((itor = PyObject_GetIter(arg2)) == NULL) {
		PyErr_SetString(PyExc_ValueError, "expected an iterable as second argument");
		return NULL;
	}

	ItorState *state = (ItorState *)type->tp_alloc(type, 0);
	if (state == NULL) {
		Py_DECREF(itor);
		return NULL;
	}

	Py_INCREF(arg1);

	state->itor = itor;
	state->seqtype = seqtype;
	state->seq1 = seq1;
	state->object = arg1;
	state->len1 = len1;
	state->max_dist = max_dist;
	  
	return (PyObject *)state;
}


static PyObject *
ilevenshtein_next(ItorState *state)
{
	PyObject *arg2;
	sequence seq1, seq2;
	Py_ssize_t len2;
	
	Py_ssize_t dist = -1;
	PyObject *rv;
	
	seq1 = state->seq1;

	while ((arg2 = PyIter_Next(state->itor)) != NULL) {
	
		if (get_sequence(arg2, &seq2, &len2, state->seqtype) == '\0') {
			Py_DECREF(arg2);
			return NULL;
		}
		switch(state->seqtype) {
			case 'u':
				dist = ulevenshtein(seq1.u, seq2.u, state->len1, len2, state->max_dist);
				break;
			case 'b':
				dist = blevenshtein(seq1.b, seq2.b, state->len1, len2, state->max_dist);
				break;
			default:
				dist = alevenshtein(seq1.a, seq2.a, state->len1, len2, state->max_dist);
				Py_DECREF(seq2.a);
		}
		if (dist < -1) {
			Py_DECREF(arg2);
			if (dist == -2)
				return PyErr_NoMemory(); // memory allocation failed
			return NULL; // comparison failed
		}
		if (dist != -1) {
			rv = Py_BuildValue("(nO)", dist, arg2);
			Py_DECREF(arg2);
			return rv;
		}
		Py_DECREF(arg2);
	}
	
	return NULL;
}


static PyObject *
ifastcomp_next(ItorState *state)
{
	PyObject *arg2;
	sequence seq1, seq2;
	Py_ssize_t len2;
	
	short dist = -1;
	PyObject *rv;
	
	seq1 = state->seq1;
	
	while ((arg2 = PyIter_Next(state->itor)) != NULL) {
	
		if (get_sequence(arg2, &seq2, &len2, state->seqtype) == '\0') {
			Py_DECREF(arg2);
			return NULL;
		}
		switch(state->seqtype) {
			case 'u':
				dist = ufastcomp(seq1.u, seq2.u, state->len1, len2, state->transpos);
				break;
			case 'b':
				dist = bfastcomp(seq1.b, seq2.b, state->len1, len2, state->transpos);
				break;
			default:
				dist = afastcomp(seq1.a, seq2.a, state->len1, len2, state->transpos);
				Py_DECREF(seq2.a);
		}
		if (dist == -2) {	// comparison failed
			Py_DECREF(arg2);
			return NULL;
		}
		if (dist != -1) {
			rv = Py_BuildValue("(hO)", dist, arg2);
			Py_DECREF(arg2);
			return rv;
		}
		Py_DECREF(arg2);
	}
	
	return NULL;
}


PyTypeObject IFastComp_Type = {
	PyVarObject_HEAD_INIT(&PyType_Type, 0)
	"distance.ifast_comp", /* tp_name */
	sizeof(ItorState), /* tp_basicsize */
	0, /* tp_itemsize */
	(destructor)itor_dealloc, /* tp_dealloc */
	0, /* tp_print */
	0, /* tp_getattr */
	0, /* tp_setattr */
	0, /* tp_reserved */
	0, /* tp_repr */
	0, /* tp_as_number */
	0, /* tp_as_sequence */
	0, /* tp_as_mapping */
	0, /* tp_hash */
	0, /* tp_call */
	0, /* tp_str */
	0, /* tp_getattro */
	0, /* tp_setattro */
	0, /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT, /* tp_flags */
	ifast_comp_doc, /* tp_doc */
	0, /* tp_traverse */
	0, /* tp_clear */
	0, /* tp_richcompare */
	0, /* tp_weaklistoffset */
	PyObject_SelfIter, /* tp_iter */
	(iternextfunc)ifastcomp_next, /* tp_iternext */
	0, /* tp_methods */
	0, /* tp_members */
	0, /* tp_getset */
	0, /* tp_base */
	0, /* tp_dict */
	0, /* tp_descr_get */
	0, /* tp_descr_set */
	0, /* tp_dictoffset */
	0, /* tp_init */
	PyType_GenericAlloc, /* tp_alloc */
	ifastcomp_new, /* tp_new */
};


PyTypeObject ILevenshtein_Type = {
	PyVarObject_HEAD_INIT(&PyType_Type, 0)
	"distance.ilevenshtein", /* tp_name */
	sizeof(ItorState), /* tp_basicsize */
	0, /* tp_itemsize */
	(destructor)itor_dealloc, /* tp_dealloc */
	0, /* tp_print */
	0, /* tp_getattr */
	0, /* tp_setattr */
	0, /* tp_reserved */
	0, /* tp_repr */
	0, /* tp_as_number */
	0, /* tp_as_sequence */
	0, /* tp_as_mapping */
	0, /* tp_hash */
	0, /* tp_call */
	0, /* tp_str */
	0, /* tp_getattro */
	0, /* tp_setattro */
	0, /* tp_as_buffer */
	Py_TPFLAGS_DEFAULT, /* tp_flags */
	ilevenshtein_doc, /* tp_doc */
	0, /* tp_traverse */
	0, /* tp_clear */
	0, /* tp_richcompare */
	0, /* tp_weaklistoffset */
	PyObject_SelfIter, /* tp_iter */
	(iternextfunc)ilevenshtein_next, /* tp_iternext */
	0, /* tp_methods */
	0, /* tp_members */
	0, /* tp_getset */
	0, /* tp_base */
	0, /* tp_dict */
	0, /* tp_descr_get */
	0, /* tp_descr_set */
	0, /* tp_dictoffset */
	0, /* tp_init */
	PyType_GenericAlloc, /* tp_alloc */
	ilevenshtein_new, /* tp_new */
};


static PyMethodDef CDistanceMethods[] = {
	{"hamming", (PyCFunction)hamming_py, METH_VARARGS | METH_KEYWORDS, hamming_doc},
	{"levenshtein", (PyCFunction)levenshtein_py, METH_VARARGS | METH_KEYWORDS, levenshtein_doc},
	{"nlevenshtein", (PyCFunction)nlevenshtein_py, METH_VARARGS | METH_KEYWORDS, nlevenshtein_doc},
	{"lcsubstrings", (PyCFunction)lcsubstrings_py, METH_VARARGS | METH_KEYWORDS, lcsubstrings_doc},
	{"fast_comp", (PyCFunction)fastcomp_py, METH_VARARGS | METH_KEYWORDS, fast_comp_doc},
	{NULL, NULL, 0, NULL}
};


#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef cdistancemodule = {
	PyModuleDef_HEAD_INIT, "cdistance", NULL, -1, CDistanceMethods
};
#endif

#if PY_MAJOR_VERSION >= 3
PyMODINIT_FUNC PyInit_cdistance(void)
#else
PyMODINIT_FUNC initcdistance(void)
#endif
{
	PyObject *module;

#if PY_MAJOR_VERSION >= 3
	if ((module = PyModule_Create(&cdistancemodule)) == NULL)
		return NULL;
#else
	if ((module = Py_InitModule("cdistance", CDistanceMethods)) == NULL)
		return;
#endif

	if (PyType_Ready(&IFastComp_Type) != 0 || PyType_Ready(&ILevenshtein_Type) != 0)
#if PY_MAJOR_VERSION >= 3
		return NULL;
#else
		return;
#endif
	
	Py_INCREF((PyObject *)&IFastComp_Type);
	Py_INCREF((PyObject *)&ILevenshtein_Type);
	
	PyModule_AddObject(module, "ifast_comp", (PyObject *)&IFastComp_Type);
	PyModule_AddObject(module, "ilevenshtein", (PyObject *)&ILevenshtein_Type);

#if PY_MAJOR_VERSION >= 3
	return module;
#endif
}
