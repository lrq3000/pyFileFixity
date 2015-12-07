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

Planned:

    * is-a
        * class/type root 
            * instances contribute to their type 
                * summary-by-type 
            

"""
import wx, sys, os, logging, imp
import wx.lib.newevent
log = logging.getLogger( __name__ )
import sys
from squaremap import squaremap
import meliaeloader

RANKS = [
    (1024*1024*1024,'%0.1fGB'),
    (1024*1024,'%0.1fMB'),
    (1024,'%0.1fKB'),
    (0,'%iB'),
]

def mb( value ):
    for (unit,format) in RANKS:
        if abs(value) >= unit * 2:
            return format%( value / float (unit or 1))
    raise ValueError( "Number where abs(x) is not >= 0?: %s"%(value,))

class MeliaeAdapter( squaremap.DefaultAdapter ):
    """Default adapter class for adapting node-trees to SquareMap API"""
    def SetPercentage( self, *args ):
        """Ignore percentage requests for now"""
    def children( self, node ):
        """Retrieve the set of nodes which are children of this node"""
        return node.get('children',[])
    def value( self, node, parent=None ):
        """Return value used to compare size of this node"""
        # this is the *weighted* size/contribution of the node 
        try:
            return node['contribution']
        except KeyError, err:
            contribution = int(node.get('totsize',0)/float( len(node.get('parents',())) or 1))
            node['contribution'] = contribution
            return contribution
    def label( self, node ):
        """Return textual description of this node"""
        result = []
        if node.get('type'):
            result.append( node['type'] )
        if node.get('name' ):
            result.append( node['name'] )
        elif node.get('value') is not None:
            result.append( unicode(node['value'])[:32])
        if 'module' in node and not node['module'] in result:
            result.append( ' in %s'%( node['module'] ))
        if node.get( 'size' ):
            result.append( '%s'%( mb( node['size'] )))
        if node.get( 'totsize' ):
            result.append( '(%s)'%( mb( node['totsize'] )))
        parent_count = len( node.get('parents',()))
        if parent_count > 1:
            result.append( '/%s refs'%( parent_count ))
        return " ".join(result)
    def overall( self, node ):
        return node.get('totsize',0)
    def empty( self, node ):
        if node.get('totsize'):
            return node['size']/float(node['totsize'])
        else:
            return 0
    def parents( self, node ):
        """Retrieve/calculate the set of parents for the given node"""
        if 'index' in node:
            index = node['index']()
            parents = list(meliaeloader.children( node, index, 'parents' ))
            return parents 
        return []
    def best_parent( self, node, tree_type=None ):
        """Choose the best parent for a given node"""
        parents = self.parents(node)
        selected_parent = None
        if node['type'] == 'type':
            module = ".".join( node['name'].split( '.' )[:-1] )
            if module:
                for mod in parents:
                    if mod['type'] == 'module' and mod['name'] == module:
                        selected_parent = mod 
        if parents and selected_parent is None:
            parents.sort( key = lambda x: self.value(node, x) )
            return parents[-1]
        return selected_parent

    color_mapping = None
    def background_color(self, node, depth):
        """Create a (unique-ish) background color for each node"""
        if self.color_mapping is None:
            self.color_mapping = {}
        if node['type'] == 'type':
            key = node['name']
        else:
            key = node['type']
        color = self.color_mapping.get(key)
        if color is None:
            depth = len(self.color_mapping)
            red = (depth * 10) % 255
            green = 200 - ((depth * 5) % 200)
            blue = (depth * 25) % 200
            self.color_mapping[key] = color = wx.Colour(red, green, blue)
        return color
    def filename( self, node ):
        if 'module' in node and not 'filename' in node:
            try:
                fp, pathname, description = imp.find_module(node['module'])
            except (ImportError), err:
                node['filename'] = None
            else:
                if fp:
                    fp.close()
                node['filename'] = pathname
        elif not 'filename' in node:
            return None 
        return node['filename']

class TestApp(wx.App):
    """Basic application for holding the viewing Frame"""
    handler = wx.PNGHandler()
    def OnInit(self):
        """Initialise the application"""
        wx.Image.AddHandler(self.handler)
        self.frame = frame = wx.Frame( None,
        )
        frame.CreateStatusBar()

        model = model = self.get_model( sys.argv[1])
        self.sq = squaremap.SquareMap( 
            frame, model=model, adapter = MeliaeAdapter(), padding=2, margin=1,
            square_style=True
        )
        squaremap.EVT_SQUARE_HIGHLIGHTED( self.sq, self.OnSquareSelected )
        frame.Show(True)
        self.SetTopWindow(frame)
        return True
    def get_model( self, path ):
        return meliaeloader.load( path )[0] # tree-only
    def OnSquareSelected( self, event ):
        text = self.sq.adapter.label( event.node )
        self.frame.SetToolTipString( text )

usage = 'meliaeloader.py somefile'

def main():
    """Mainloop for the application"""
    if not sys.argv[1:]:
        print usage
    else:
        app = TestApp(0)
        app.MainLoop()

if __name__ == "__main__":
    main()
