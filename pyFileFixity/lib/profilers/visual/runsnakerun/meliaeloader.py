#! /usr/bin/env python
"""Module to load meliae memory-profile dumps

Trees:

    * has-a
        * module root 
        * each held reference contributes a weighted cost to the parent 
        * hierarchy of held objects, so globals, classes, functions, and their children
        * held modules do not contribute to cost
        
        * module 
            * instance-tree
"""
import logging, sys, weakref
log = logging.getLogger( __name__ )
from gettext import gettext as _
try:
    from _meliaejson import loads as json_loads
except ImportError, err:
    try:
        from json import loads as json_loads
    except ImportError, err:
        from simplejson import loads as json_loads
import sys

LOOP_TYPE = _('<loop>')
MANY_TYPE = _('<many>')
NON_MODULE_REFS = _('<non-module-references>')

STOP_TYPES = set(['module'])

def recurse( record, index, stop_types=STOP_TYPES,already_seen=None, type_group=False ):
    """Depth first traversal of a tree, all children are yielded before parent
    
    record -- dictionary record to be recursed upon 
    index -- mapping 'address' ids to dictionary records 
    stop_types -- types which will *not* recurse 
    already_seen -- set storing already-visited nodes 
    
    yields the traversed nodes
    """
    if already_seen is None:
        already_seen = set()
    if record['address'] not in already_seen:
        already_seen.add(record['address'])
        if 'refs' in record:
            for child in children( record, index, stop_types=stop_types ):
                if child['address'] not in already_seen:
                    for descendant in recurse( 
                        child, index, stop_types, 
                        already_seen=already_seen, type_group=type_group,
                    ):
                        yield descendant
        yield record 

def find_loops( record, index, stop_types = STOP_TYPES, open=None, seen = None ):
    """Find all loops within the index and replace with loop records"""
    if open is None:
        open = []
    if seen is None:
        seen = set()
    for child in children( record, index, stop_types = stop_types ):
        if child['type'] in stop_types or child['type'] == LOOP_TYPE:
            continue
        if child['address'] in open:
            # loop has been found 
            start = open.index( child['address'] )
            new = frozenset( open[start:] )
            if new not in seen:
                seen.add(new)
                yield new
        elif child['address'] in seen:
            continue 
        else:
            seen.add( child['address'])
            open.append( child['address'] )
            for loop in find_loops( child, index, stop_types=stop_types, open=open, seen=seen ):
                yield loop 
            open.pop( -1 )

def promote_loops( loops, index, shared ):
    """Turn loops into "objects" that can be processed normally"""
    for loop in loops:
        loop = list(loop)
        members = [index[addr] for addr in loop]
        external_parents = list(set([
            addr for addr in sum([shared.get(addr,[]) for addr in loop],[])
            if addr not in loop 
        ]))
        if external_parents:
            if len(external_parents) == 1:
                # potentially a loop that's been looped...
                parent = index.get( external_parents[0] )
                if parent['type'] == LOOP_TYPE:
                    continue 
            # we haven't already been looped...
            loop_addr = new_address( index )
            shared[loop_addr] = external_parents
            loop_record = index[loop_addr] = {
                'address': loop_addr,
                'refs': loop,
                'parents': external_parents,
                'type': LOOP_TYPE,
                'size': 0,
            }
            for member in members:
                # member's references must *not* point to loop...
                member['refs'] = [
                    ref for ref in member['refs']
                    if ref not in loop 
                ]
                # member's parents are *just* the loop
                member['parents'][:] = [loop_addr]
            # each referent to loop holds a single reference to the loop rather than many to children
            for parent in external_parents:
                parent = index[parent]
                for member in members:
                    rewrite_references( parent['refs'], member['address'], None )
                parent['refs'].append( loop_addr )

def children( record, index, key='refs', stop_types=STOP_TYPES ):
    """Retrieve children records for given record"""
    result = []
    for ref in record.get( key,[]):
        try:
            record = index[ref]
        except KeyError, err:
            #print 'No record for %s address %s in %s'%(key, ref, record['address'] )
            pass # happens when an unreachable references a reachable that has been compressed out...
        else:
            if record['type'] not in stop_types:
                result.append(  record  )
    return result

def children_types( record, index, key='refs', stop_types=STOP_TYPES ):
    """Produce dictionary mapping type-key to instances for all children"""
    types = {}
    for child in children( record, index, key, stop_types=stop_types ):
        types.setdefault(child['type'],[]).append( child )
    return types
        

def recurse_module( overall_record, index, shared, stop_types=STOP_TYPES, already_seen=None, min_size=0 ):
    """Creates a has-a recursive-cost hierarchy
    
    Mutates objects in-place to produce a hierarchy of memory usage based on 
    reference-holding cost assignment
    """
    for record in recurse( 
        overall_record, index, 
        stop_types=stop_types, 
        already_seen=already_seen, 
        type_group=True,
    ):
        # anything with a totsize we've already processed...
        if record.get('totsize') is not None:
            continue 
        rinfo = record 
        rinfo['module'] = overall_record.get('name',NON_MODULE_REFS )
        if not record['refs']:
            rinfo['rsize'] = 0
            rinfo['children'] = []
        else:
            # TODO: provide a flag to coalesce based on e.g. type at each level or throughout...
            rinfo['children'] = rinfo_children = list ( children( record, index, stop_types=stop_types ) )
            rinfo['rsize'] = sum([
                (
                    child.get('totsize',0.0)/float(len(shared.get( child['address'], [])) or 1)
                )
                for child in rinfo_children
            ], 0.0 )
        rinfo['totsize'] = record['size'] + rinfo['rsize']
    
    return None
    
def as_id( x ):
    if isinstance( x, dict ):
        return x['address']
    else:
        return x

def rewrite_refs( targets, old,new, index, key='refs', single_ref=False ):
    """Rewrite key in all targets (from index if necessary) to replace old with new"""
    for parent in targets:
        if not isinstance( parent, dict ):
            try:
                parent = index[parent]
            except KeyError, err:
                continue 
        rewrite_references( parent[key], old, new, single_ref=single_ref )

def rewrite_references( sequence, old, new, single_ref=False ):
    """Rewrite parents to point to new in old
    
    sequence -- sequence of id references 
    old -- old id 
    new -- new id
    
    returns rewritten sequence
    """
    old,new = as_id(old),as_id(new)
    to_delete = []
    for i,n in enumerate(sequence):
        if n == old:
            if new is None:
                to_delete.append( i )
            else:
                sequence[i] = new 
                if single_ref:
                    new = None
        elif n == new and single_ref:
            new = None
    if to_delete:
        to_delete.reverse()
        for i in to_delete:
            del sequence[i]
    return sequence

def simple( child, shared, parent ):
    """Return sub-set of children who are "simple" in the sense of group_children"""
    return (
        not child.get('refs',())
        and (
            not shared.get(child['address'])
        or 
            shared.get(child['address']) == [parent['address']]
        )
    )

def group_children( index, shared, min_kids=10, stop_types=STOP_TYPES, delete_children=True ):
    """Collect like-type children into sub-groups of objects for objects with long children-lists
    
    Only group if:
    
        * there are more than X children of type Y
        * children are "simple"
            * individual children have no children themselves
            * individual children have no other parents...
    """
    to_compress = []
    
    for to_simplify in list(iterindex( index )):
        if not isinstance( to_simplify, dict ):
            continue
        for typ,kids in children_types( to_simplify, index, stop_types=stop_types ).items():
            kids = [k for k in kids if k and simple(k,shared, to_simplify)]
            if len(kids) >= min_kids:
                # we can group and compress out...
                to_compress.append( (to_simplify,typ,kids))
    
    for to_simplify,typ,kids in to_compress:
        typ_address = new_address(index)
        kid_addresses = [k['address'] for k in kids]
        index[typ_address] = {
            'address': typ_address,
            'type': MANY_TYPE,
            'name': typ,
            'size': sum( [k.get('size',0) for k in kids], 0),
            'parents': [to_simplify['address']],
        }
        
        shared[typ_address] = index[typ_address]['parents']
        to_simplify['refs'][:] = [typ_address]
        
        if delete_children:
            for address in kid_addresses:
                try:
                    del index[address]
                except KeyError, err: 
                    pass # already compressed out
                try:
                    del shared[address]
                except KeyError, err:
                    pass # already compressed out
            index[typ_address]['refs'] = []
        else:
            index[typ_address]['refs'] = kid_addresses

# Types which *can* have their dictionaries compressed out
SIMPLIFY_DICTS = set( ['module','type','classobj'])
# Types which will *always* have their dictionaries compressed out,
# even if there are multiple references to the dictionary, these values 
# should *only* ever be part of STOP_TYPES, as their size contributions 
# will be lost (STOP_TYPES make no contribution)
ALWAYS_COMPRESS_DICTS = set( ['module'] )


def simplify_dicts( index, shared, simplify_dicts=SIMPLIFY_DICTS, always_compress=ALWAYS_COMPRESS_DICTS ):
    """Eliminate "noise" dictionary records from the index 
    
    index -- overall index of objects (including metadata such as type records)
    shared -- parent-count mapping for records in index
    
    module/type/class dictionaries
    """
    
    # things which will have their dictionaries compressed out
    
    to_delete = set()
    
    for to_simplify in iterindex(index):
        if to_simplify['address'] in to_delete:
            continue 
        if to_simplify['type'] in simplify_dicts and not 'compressed' in to_simplify:
            refs = to_simplify['refs']
            for ref in refs:
                child = index.get( ref )
                if child is not None and child['type'] == 'dict':
                    child_referrers = child['parents'][:]
                    if len(child_referrers) == 1 or to_simplify['type'] in always_compress:
                        
                        to_simplify['compressed'] = True
                        to_simplify['refs'] = child['refs']
                        to_simplify['size'] += child['size']
                        
                        # rewrite anything *else* that was pointing to child to point to us...
                        while to_simplify['address'] in child_referrers:
                            child_referrers.remove( to_simplify['address'] )
                        if child_referrers:
                            rewrite_refs( 
                                child_referrers, 
                                child['address'],
                                to_simplify['address'], 
                                index, single_ref=True
                            )
                        
                        # now rewrite grandchildren to point to root obj instead of dict
                        for grandchild in child['refs']:
                            grandchild = index[grandchild]
                            parent_set = grandchild['parents']
                            if parent_set:
                                rewrite_references( 
                                    parent_set, 
                                    child,
                                    to_simplify,
                                    single_ref = True,
                                )
                            assert parent_set
                        to_delete.add( child['address'] )
    for item in to_delete:
        del index[item]
        del shared[item]
    
    return index

def find_reachable( modules, index, shared, stop_types=STOP_TYPES ):
    """Find the set of all reachable objects from given root nodes (modules)"""
    reachable = set()
    already_seen = set()
    for module in modules:
        for child in recurse( module, index, stop_types=stop_types, already_seen=already_seen):
            reachable.add( child['address'] )
    return reachable

def deparent_unreachable( reachable, shared ):
    """Eliminate all parent-links from unreachable objects from reachable objects
    """
    for id,shares in shared.iteritems():
        if id in reachable: # child is reachable
            filtered = [
                x 
                for x in shares 
                if x in reachable # only those parents which are reachable
            ]
            if len(filtered) != len(shares):
                shares[:] = filtered

class _syntheticaddress( object ):
    current = -1
    def __call__( self, target ):
        while self.current in target:
            self.current -= 1
        target[self.current] = True
        return self.current 
new_address = _syntheticaddress()

def index_size( index ):
    return sum([
        v.get('size',0)
        for v in iterindex( index )
    ],0)

def iterindex( index ):
    for (k,v) in index.iteritems():
        if (
            isinstance(v,dict) and 
            isinstance(k,(int,long))
        ):
            yield v

def bind_parents( index, shared ):
    """Set parents on all items in index"""
    for v in iterindex( index ):
        v['parents'] = shared.get( v['address'], [] )


def check_parents( index, reachable ):
    for item in iterindex( index ):
        if item['type'] == '<many>':
            print 'parents', item['parents']

def load( filename, include_interpreter=False ):
    index = {
    } # address: structure
    shared = dict() # address: [parent addresses,...]
    modules = set()
    
    root_address = new_address( index )
    root = {
        'type':'dump',
        'name': filename,
        'children': [],
        'totsize': 0,
        'rsize': 0,
        'size': 0,
        'address': root_address,
    }
    index[root_address] = root
    index_ref = Ref( index )
    root_ref = Ref( root )
    
    root['root'] = root_ref 
    root['index'] = index_ref
    
    raw_total = 0
    
    for line in open( filename ):
        struct = json_loads( line.strip())
        index[struct['address']] = struct 
        
        struct['root'] = root_ref
        struct['index'] = index_ref

        refs = struct['refs']
        for ref in refs:
            parents = shared.get( ref )
            if parents is None:
                shared[ref] = []
            shared[ref].append( struct['address'])
        raw_total += struct['size']
        if struct['type'] == 'module':
            modules.add( struct['address'] )
    
    modules = [index[addr] for addr in modules]
    
    reachable = find_reachable( modules, index, shared )
    deparent_unreachable( reachable, shared )
    
    bind_parents( index, shared )
    
#    unreachable = sum([
#        v.get( 'size' )
#        for v in iterindex( index )
#        if v['address'] not in reachable
#    ], 0 )
#    print '%s bytes are unreachable from modules'%( unreachable )

    simplify_dicts( index,shared )

    group_children( index, shared, min_kids=10 )

    records = []
    for m in modules:
        loops = list( find_loops( m, index ) )
        promote_loops( loops, index, shared )
        recurse_module(
            m, index, shared
        )
        
    modules.sort( key = lambda m: m.get('totsize',0))
    for module in modules:
        module['parents'].append( root_address )


    if include_interpreter:
        # Meliae produces quite a few of these un-referenced records, they aren't normally useful AFAICS
        # reachable from any module, but are present in the dump...
        disconnected = [
            x for x in iterindex( index )
            if x.get('totsize') is None 
        ]
        for pseudo_module in find_roots( disconnected, index, shared ):
            pseudo_module['root'] = root_ref
            pseudo_module['index'] = index_ref 
            pseudo_module.setdefault('parents',[]).append( root_address )
            modules.append( pseudo_module )
    else:
        to_delete = []
        for v in iterindex(index):
            if v.get('totsize') is None:
                to_delete.append( v['address'] )
        for k in to_delete:
            del index[k]

    all_modules = sum([x.get('totsize',0) for x in modules],0)
 
    root['totsize'] = all_modules
    root['rsize'] = all_modules
    root['size'] = 0
    root['children'] = modules

    for item in iterindex( index ):
        item['root'] = root_ref
        item['index'] = index_ref
    
    return root, index

def find_roots( disconnected, index, shared ):
    """Find appropriate "root" objects from which to recurse the hierarchies
    
    Will generate a synthetic root for anything which doesn't have any parents...
    """
    log.warn( '%s disconnected objects in %s total objects', len(disconnected), len(index))
    natural_roots = [x for x in disconnected if x.get('refs') and not x.get('parents')]
    log.warn( '%s objects with no parents at all' ,len(natural_roots))
    for natural_root in natural_roots:
        recurse_module(
            natural_root, index, shared
        )
        yield natural_root
    rest = [x for x in disconnected if x.get( 'totsize' ) is None]
    un_found = {
        'type': 'module',
        'name': '<disconnected objects>',
        'children': rest,
        'parents': [ ],
        'size': 0,
        'totsize': sum([x['size'] for x in rest],0),
        'address': new_address( index ),
    }
    index[un_found['address']] = un_found
    yield un_found

class Ref(object):
    def __init__( self, target ):
        self.target = target
    def __call__( self ):
        return self.target

class Loader( object ):
    """A data-set loader for pulling root and rows from a meliae dump"""
    def __init__( self, filename, include_interpreter=False ):
        self.filename = filename 
        self.include_interpreter = include_interpreter
        self.roots = {}
    ROOTS = ['memory']
    
    def get_root( self, key ):
        """Retrieve the given root by type-key"""
        if key not in self.roots:
            root,self.rows = load( self.filename, include_interpreter = self.include_interpreter )
            self.roots[key] = root
        return self.roots[key]
    def get_rows( self, key ):
        """Get the set of rows for the type-key"""
        if key not in self.roots:
            self.get_root( key )
        return self.rows
    def get_adapter( self, key ):
        import meliaeadapter
        return meliaeadapter.MeliaeAdapter()

if __name__ == "__main__":
    import logging
    logging.basicConfig( level=logging.DEBUG )
    import sys
    load( sys.argv[1] )
#    import cProfile, sys
#    cProfile.runctx( "load(sys.argv[1])", globals(),locals(),'melialoader.profile' )
    
