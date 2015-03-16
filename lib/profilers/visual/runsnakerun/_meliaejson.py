#! /usr/bin/env python
"""Horrible hack to attempt to load meliae dumps a bit faster

Makes meliae loading about 4.25x faster on python 2.6 compared to the 
json + C speedups.  This is *not* however, a full json decoder, it is 
*just* a parser for the flat records meliae produces (i.e. no recursive 
structures, no floats, just ints, strings and lists-of-ints)
"""
import re, unittest, json

whitespace = r'[ \t]'

escape = r"""(?:\\[uU][0-9a-fA-F]{4})"""
string = r"""(?:["](?P<%(key)s>([^"\\]|(\\")|%(escape)s|\\[^uU"])*?)["])"""
key = string%{'key':'key','escape':escape}
string = string%{'key':'string','escape':escape}
integer = r"""(?P<int>[+-]*\d+)"""
listcontent = r"""([+-]*\d+[,]?%(whitespace)s*?)*"""%globals()
intlist = r"""\[%(whitespace)s*(?P<list>%(listcontent)s)%(whitespace)s*\]"""%globals()

attr = r"""%(whitespace)s*%(key)s%(whitespace)s*:%(whitespace)s*(%(intlist)s|%(string)s|%(integer)s)(,)?"""%globals()

escape = re.compile( escape, re.U )
simple_escape = re.compile( r'\\([^uU])', re.U )

assert escape.match( "\u0000" )
attr = re.compile( attr )
string = re.compile( string )
integer = re.compile( integer )
intlist = re.compile( intlist )

assert string.match( '"this"' ).group('string') == "this"
assert string.match( '"this": "that"' ).group('string') == "this"
assert string.match( '"this\\u0000"' ).group('string') == "this\\u0000", string.match( '"this\\u0000"' ).group('string')

assert integer.match( '23' ).group( 'int' ) == '23'
assert intlist.match( '[1, 2,3,4]' ).group( 'list' ) == '1, 2,3,4'
assert intlist.match( '[139828625414688, 70572696, 52870672, 40989336]' ).group('list') == '139828625414688, 70572696, 52870672, 40989336'

def loads( source ):
    """Load json structure from meliae from source
    
    Supports only the required structures to support loading meliae memory dumps
    """
    source = source.strip()
    assert source.startswith( '{' )
    assert source.endswith( '}' )
    source = source[1:-1]
    result = {}
    for match in attr.finditer( source ):
        key = match.group('key')
        if match.group( 'list' ) is not None:
            value = [ 
                int(x) 
                for x in match.group( 'list' ).strip().replace(',',' ').split() 
            ]
        elif match.group( 'int' ) is not None:
            value = int( match.group( 'int' ))
        elif match.group( 'string' ) is not None:
            def deescape( match ):
                return unichr( int( match.group(0)[2:], 16 ))
            value = match.group('string').decode( 'utf-8' )
            value = escape.sub( 
                deescape,
                value,
            )
            value = simple_escape.sub(
                lambda x: x.group(1),
                value,
            )
        else:
            raise RuntimeError( "Matched something we don't know how to process:", match.groupdict() )
        result[key] = value
    return result
if __name__ == "__main__":
    import sys, pprint
    for line in open( sys.argv[1] ):
        official = json.loads( line )
