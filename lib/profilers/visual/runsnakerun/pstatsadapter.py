import wx, sys, os, logging
log = logging.getLogger( __name__ )
from squaremap import squaremap
import pstatsloader

class PStatsAdapter(squaremap.DefaultAdapter):

    percentageView = False
    total = 0
    
    TREE = pstatsloader.TREE_CALLS

    def value(self, node, parent=None):
        if isinstance(parent, pstatsloader.PStatGroup):
            if parent.cumulative:
                return node.cumulative / parent.cumulative
            else:
                return 0
        elif parent is None:
            return node.cumulative
        return parent.child_cumulative_time(node)

    def label(self, node):
        if isinstance(node, pstatsloader.PStatGroup):
            return '%s / %s' % (node.filename, node.directory)
        if self.percentageView and self.total:
            time = '%0.2f%%' % round(node.cumulative * 100.0 / self.total, 2)
        else:
            time = '%0.3fs' % round(node.cumulative, 3)
        return '%s@%s:%s [%s]' % (node.name, node.filename, node.lineno, time)

    def empty(self, node):
        if node.cumulative:
            return node.local / float(node.cumulative)
        return 0.0

    def parents(self, node):
        """Determine all parents of node in our tree"""
        return [
            parent for parent in
            getattr( node, 'parents', [] )
            if getattr(parent, 'tree', self.TREE) == self.TREE
        ]

    color_mapping = None

    def background_color(self, node, depth):
        """Create a (unique-ish) background color for each node"""
        if self.color_mapping is None:
            self.color_mapping = {}
        color = self.color_mapping.get(node.key)
        if color is None:
            depth = len(self.color_mapping)
            red = (depth * 10) % 255
            green = 200 - ((depth * 5) % 200)
            blue = (depth * 25) % 200
            self.color_mapping[node.key] = color = wx.Colour(red, green, blue)
        return color

    def SetPercentage(self, percent, total):
        """Set whether to display percentage values (and total for doing so)"""
        self.percentageView = percent
        self.total = total

    def filename( self, node ):
        """Extension to squaremap api to provide "what file is this" information"""
        if not node.directory:
            # TODO: any cases other than built-ins?
            return None
        if node.filename == '~':
            # TODO: look up C/Cython/whatever source???
            return None
        return os.path.join(node.directory, node.filename)
        

class DirectoryViewAdapter(PStatsAdapter):
    """Provides a directory-view-only adapter for PStats objects"""
    TREE = pstatsloader.TREE_FILES
    def children(self, node):
        if isinstance(node, pstatsloader.PStatGroup):
            return node.children
        return []
