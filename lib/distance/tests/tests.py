import os, sys
from array import array
try:
	from distance import cdistance
except ImportError:
	cdistance = None
from distance import _pyimports as pydistance


if sys.version_info.major < 3:
	t_unicode = unicode
	t_bytes = lambda s: s
else:
	t_unicode = lambda s: s
	t_bytes = lambda s: s.encode()

all_types = [
	("unicode", t_unicode),
	("bytes", t_bytes),
	("list", list),
	("tuple", tuple),
]


def hamming(func, t, **kwargs):

	# types; only for c
	if kwargs["lang"] == "C":
		try:
			func(1, t("foo"))
		except ValueError:
			pass
		try:
			func(t("foo"), 1)
		except ValueError:
			pass

	# empty string
	assert func(t(""), t("")) == 0
	
	# common
	assert func(t("abc"), t("abc")) == 0
	assert func(t("abc"), t("abd")) == 1
	
	# wrong length
	try:
		func(t("foo"), t("foobar"))
	except ValueError:
		pass

	try:
		func(t(""), t("foo"))
	except ValueError:
		pass
	
	# normalization
	assert func(t(""), t(""), normalized=True) == 0.0
	assert func(t("abc"), t("abc"), normalized=True) == 0.0
	assert func(t("ab"), t("ac"), normalized=True) == 0.5
	assert func(t("abc"), t("def"), normalized=True) == 1.0


def fast_comp(func, t, **kwargs):

	# types; only for c
	if kwargs["lang"] == "C":
		try:
			func(1, t("foo"))
		except ValueError:
			pass
		try:
			func(t("foo"), 1)
		except ValueError:
			pass

	# empty strings
	assert func(t(""), t("")) == 0
	assert func(t(""), t("a")) == func(t("a"), t("")) == 1

	# edit ops
	assert func(t("aa"), t("aa")) == 0
	assert func(t("ab"), t("aa")) == 1
	assert func(t("ab"), t("a")) == 1
	assert func(t("ab"), t("abc")) == 1
	
	# dist limit
	assert func(t("a"), t("bcd")) == func(t("bcd"), t("a")) == -1
	
	# transpositions
	assert func(t("abc"), t("bac"), transpositions=True) == \
		func(t("bac"), t("abc"), transpositions=True) == 1
	


def levenshtein(func, t, **kwargs):

	# types; only for c
	if kwargs["lang"] == "C":
		try:
			func(1, t("foo"))
		except ValueError:
			pass
		try:
			func(t("foo"), 1)
		except ValueError:
			pass

	# empty strings
	assert func(t(""), t("")) == 0
	assert func(t(""), t("abcd")) == func(t("abcd"), t("")) == 4
	
	# edit ops
	assert func(t("aa"), t("aa")) == 0
	assert func(t("ab"), t("aa")) == 1
	assert func(t("ab"), t("a")) == 1
	assert func(t("ab"), t("abc")) == 1
	
	# dist limit
	assert func(t("a"), t("b"), max_dist=0) == -1
	assert func(t("a"), t("b"), max_dist=1) == 1
	assert func(t("foo"), t("bar"), max_dist=-1) == 3


def nlevenshtein(func, t, **kwargs):

	# types; only for c
	if kwargs["lang"] == "C":
		try:
			func(1, t("foo"))
		except ValueError:
			pass
		try:
			func(t("foo"), 1)
		except ValueError:
			pass

	# empty strings
	assert func(t(""), t(""), 1) == func(t(""), t(""), 2) == 0.0
	assert func(t(""), t("foo"), 1) == func(t("foo"), t(""), 1) == \
		func(t(""), t("foo"), 2) == func(t("foo"), t(""), 2) == 1.0

	assert func(t("aa"), t("aa"), 1) == func(t("aa"), t("aa"), 2) == 0.0
	assert func(t("ab"), t("aa"), 1) == func(t("ab"), t("aa"), 2) == 0.5
	assert func(t("ab"), t("a"), 1) == func(t("ab"), t("a"), 2) == 0.5
	assert func(t("ab"), t("abc"), 1) == func(t("ab"), t("abc"), 2) == 0.3333333333333333

	# multiple alignments
	assert func(t("abc"), t("adb"), 1) == 0.6666666666666666
	assert func(t("abc"), t("adb"), 2) == 0.5


def lcsubstrings(func, t, **kwargs):

	# types; only for c
	if kwargs["lang"] == "C":
		try:
			func(1, t("foo"))
		except ValueError:
			pass
		try:
			func(t("foo"), 1)
		except ValueError:
			pass

	# empty strings
	try:
		assert func(t(""), t(""), False) == set()
	except TypeError:
		if t is not list: raise
	assert func(t(""), t(""), True) == (0, ())
	try:
		assert func(t(""), t("foo"), False) == func(t("foo"), t(""), False) == set()
	except TypeError:
		if t is not list: raise
	assert func(t(""), t("foo"), True) == func(t("foo"), t(""), True) == (0, ())
	
	# common
	try:
		assert func(t("abcd"), t("cdba"), False) == {t('cd')}
	except TypeError:
		if t is not list: raise
	assert func(t("abcd"), t("cdba"), True) == (2, ((2, 0),))
	
	# reverse
	try:
		assert func(t("abcdef"), t("cdba"), False) == func(t("cdba"), t("abcdef"), False)
	except TypeError:
		if t is not list: raise
	assert func(t("abcdef"), t("cdba"), True) == func(t("cdba"), t("abcdef"), True)


def itors_common(func, t, **kwargs):

	if kwargs["lang"] == "C":
		# types check; only need to do it for C impl to avoid an eventual segfaults.
		try: func(1, t("foo"))
		except ValueError: pass
	
		itor = func(t("foo"), [t("foo"), 3333])
		next(itor)
		try: next(itor)
		except ValueError: pass

	# values drop
	itor = func(t("aa"), [t("aa"), t("abcd"), t("ba")])
	assert next(itor) == (0, t("aa"))
	assert next(itor) == (1, t("ba"))


def ilevenshtein(func, t, **kwargs):
	itors_common(lambda a, b: func(a, b, max_dist=2), t, **kwargs)
	

def ifast_comp(func, t, **kwargs):
	itors_common(func, t, **kwargs)
	#transpositions
	g = func(t("abc"), [t("bac")], transpositions=False)
	assert next(g) == (2, t('bac'))
	g = func(t("abc"), [t("bac")], transpositions=True)
	assert next(g) == (1, t("bac"))
	

write = lambda s: sys.stderr.write(s + '\n')

tests = ["hamming", "fast_comp", "levenshtein", "lcsubstrings", "nlevenshtein", "ilevenshtein", "ifast_comp"]


def run_test(name):
	if cdistance:
		cfunc = getattr(cdistance, name)
		run_lang_test(name, cfunc, "C")
		write("")
	pyfunc = getattr(pydistance, name)
	run_lang_test(name, pyfunc, "py")
	if cdistance is None:
		write("skipped C tests")
	write("")


def run_lang_test(name, func, lang):
	print("%s (%s)..." % (name, lang))
	for tname, typ in all_types:
		write("type: %s" % tname)
		globals()[name](func, typ, lang=lang)

if __name__ == "__main__":
	args = sys.argv[1:]
	if not args:
		for test in tests:
			run_test(test)
		sys.exit()
	for name in args:
		if name in tests:
			run_test(name)
		else:
			write("no such test: %s" % name)
			sys.exit(1)
