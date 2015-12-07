#ifndef DISTANCE_H
#define DISTANCE_H

#include "Python.h"
#include "utarray.h"

// Debugging. This kills the interpreter if an assertion fails.

#ifdef DISTANCE_DEBUG
	#undef NDEBUG
	#include <assert.h>
#endif

// Compatibility Python 2 && 3

#if PY_MAJOR_VERSION < 3
	#define PyBytes_Check        PyString_Check
	#define PyBytes_AS_STRING    PyString_AS_STRING
	#define PyBytes_GET_SIZE     PyString_GET_SIZE
	#define PyUnicode_GET_LENGTH PyUnicode_GET_SIZE
#endif

// Aliases for each sequence type

typedef Py_UNICODE unicode;

typedef char byte;

typedef PyObject array;

typedef union {
	unicode *u;
	byte    *b;
	array   *a;
} sequence;


// Used in distance.c and some other files

#define SWAP(type, a, b)								\
do {															\
	type a##_tmp = a;										\
	a = b;													\
	b = a##_tmp;											\
} while (0)


// Used in lcsubstrings.c and distance.c for dynamic array

struct pair_t {
	Py_ssize_t i;
	Py_ssize_t j;
};

UT_icd pair_icd = {sizeof(struct pair_t), NULL, NULL, NULL};

#endif
