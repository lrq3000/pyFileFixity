Reed Solomon Encoder and Decoder written in pure Python
=======================================================

Written from scratch by Andrew Brown <brownan@gmail.com> <brownan@cs.duke.edu>
(c) 2010

I wrote this code as an exercise in implementing the Reed-Solomon error
correction algorithm. This code is published in the hopes that it will be
useful for others in learning how the algorithm works. (Nothing helps me learn
something better than a good example!)

My goal was to implement a working Reed-Solomon encoder and decoder in pure
python using no non-standard libraries. I also aimed to keep the code fairly
well commented and organized.

However, a lot of the math involved is non-trivial and I can't explain it all
in my comments. To learn more about the algorithm, see these resources:

* `<http://en.wikipedia.org/wiki/Reed–Solomon_error_correction>`_
* `<http://www.cs.duke.edu/courses/spring10/cps296.3/rs_scribe.pdf>`_
* `<http://www.cs.duke.edu/courses/spring10/cps296.3/decoding_rs_scribe.pdf>`_

The last two resources are course notes from Bruce Maggs' class, which I took
this past semester. Those notes were immensely useful and should be read by
anyone wanting to learn the algorithm.

Last two at Dr. Maggs' old site:

* `<http://www.cs.cmu.edu/afs/cs.cmu.edu/project/pscico-guyb/realworld/www/reed_solomon.ps>`_
* `<http://www.cs.cmu.edu/afs/cs.cmu.edu/project/pscico-guyb/realworld/www/rs_decode.ps>`_

Also, here's a copy of the presentation I gave to the class Spring 2010 on my
experience implementing this. The LaTeX source is in the presentation
directory.

`<http://www.cs.duke.edu/courses/spring10/cps296.3/decoding_rs.pdf>`_

The code was lately updated to support errors-and-erasures decoding (both at the same
time), and to be universal (you can supply the parameters to be compatible with almost
any other RS codec).

The codec has decent performances if you use PyPy with the fast methods (~1 MB/s),
but it would be faster if we drop the oriented-object design (implementing everything in
functions), but this would be at the expense of mathematical clarity. If you are interested,
see the reedsolo library by Tomer Filiba, which is exactly the same implementation but
without object-oriented design (about 5x speedup).

Files
-----
rs.py
    Holds the Reed-Solomon Encoder/Decoder object

polynomial.py
    Contains the Polynomial object

ff.py
    Contains the GF256int object representing an element of the GF(2^8) field

Documentation
-------------
rs.RSCoder(n, k)
     Creates a new Reed-Solomon Encoder/Decoder object configured with
     the given n and k values.
     n is the length of a codeword, must be less than 256
     k is the length of the message, must be less than n
     
     The code will have error correcting power s where 2s = n - k
     
     The typical RSCoder is RSCoder(255, 223)
 
RSCoder Objects

RSCoder.encode(message, poly=False)
    Encode a given string with reed-solomon encoding. Returns a byte
    string with the k message bytes and n-k parity bytes at the end.
    
    If a message is < k bytes long, it is assumed to be padded at the front
    with null bytes.
    
    The sequence returned is always n bytes long.
    
    If poly is not False, returns the encoded Polynomial object instead of
    the polynomial translated back to a string (useful for debugging)
    
RSCoder.decode(r, nostrip=False)
    Given a received string or byte array r, attempts to decode it. If
    it's a valid codeword, or if there are no more than (n-k)/2 errors, the
    message is returned.
    
    A message always has k bytes, if a message contained less it is left
    padded with null bytes. When decoded, these leading null bytes are
    stripped, but that can cause problems if decoding binary data. When
    nostrip is True, messages returned are always k bytes long. This is
    useful to make sure no data is lost when decoding binary data.

RSCoder.verify(code)
    Verifies the code is valid by testing that the code as a polynomial
    code divides g
    returns True/False


Besides the main RSCoder object, two other objects are used in this
implementation. Their use is not specifically tied to the coder.

polynomial.Polynomial(coefficients=(), \**sparse)
    There are three ways to initialize a Polynomial object.
    1) With a list, tuple, or other iterable, creates a polynomial using
    the items as coefficients in order of decreasing power

    2) With keyword arguments such as for example x3=5, sets the
    coefficient of x^3 to be 5

    3) With no arguments, creates an empty polynomial, equivalent to
    Polynomial((0,))

    >>> print Polynomial((5, 0, 0, 0, 0, 0))
    5x^5

    >>> print Polynomial(x32=5, x64=8)
    8x^64 + 5x^32

    >>> print Polynomial(x5=5, x9=4, x0=2) 
    4x^9 + 5x^5 + 2

Polynomial objects export the following standard functions that perform the
expected operations using polynomial arithmetic. Arithmetic of the coefficients
is determined by the type passed in, so integers or GF256int objects could be
used, the Polynomial class is agnostic to the type of the coefficients.

::

    __add__
    __divmod__
    __eq__
    __floordiv__
    __hash__
    __len__
    __mod__
    __mul__
    __ne__
    __neg__
    __sub__
    evaluate(x)
    degree()
        Returns the degree of the polynomial
    get_coefficient(degree)
        Returns the coefficient of the specified term

ff.GF256int(value)
    Instances of this object are elements of the field GF(2^8)
    Instances are integers in the range 0 to 255
    This field is defined using the irreducable polynomial
    x^8 + x^4 + x^3 + x + 1
    and using 3 as the generator for the exponent table and log table.

The GF256int class inherits from int and supports all the usual integer
operations. The following methods are overridden for arithmetic in the finite
field GF(2^8)

::

    __add__
    __div__
    __mul__
    __neg__
    __pow__
    __radd__
    __rdiv__
    __rmul__
    __rsub__
    __sub__
    inverse()
        Multiplicative inverse in GF(2^8)


Examples
--------
>>> import rs
>>> coder = rs.RSCoder(20,13)
>>> c = coder.encode("Hello, world!")
>>> print repr(c)
'Hello, world!\x8d\x13\xf4\xf9C\x10\xe5'
>>>
>>> r = "\0"*3 + c[3:]
>>> print repr(r)
'\x00\x00\x00lo, world!\x8d\x13\xf4\xf9C\x10\xe5'
>>>
>>> coder.decode(r)
'Hello, world!'

Image Encoder
~~~~~~~~~~~~~
imageencode.py is an example script that encodes codewords as rows in an image.
It requires PIL to run.

Usage: python imageencode.py [-d] <image file>

Without the -d flag, imageencode.py will encode text from standard in and
output it to the image file. With -d, imageencode.py will read in the data from
the image and output to standard out the decoded text.

An example is included: ``exampleimage.png``. Try decoding it as-is, then open
it up in an image editor and paint some vertical stripes on it. As long as no
more than 16 pixels per row are disturbed, the text will be decoded correctly.
Then draw more stripes such that more than 16 pixels per row are disturbed and
verify that the message is decoded improperly.

Notice how the parity data looks different--the last 32 pixels of each row are
colored differently. That's because this particular image contains encoded
ASCII text, which generally only has bytes from a small range (the alphabet and
printable punctuation). The parity data, however, is binary and contains bytes
from the full range 0-255. Also note that either the data area or the parity
area (or both!) can be disturbed as long as no more than 16 bytes per row are
disturbed.
